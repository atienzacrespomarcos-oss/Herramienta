"""Proyecto abierto: punto de entrada de la interfaz, los scripts y (en su día) la IA."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from traza.app.ordenes import (
    Orden,
    OrdenRechazada,
    RegistrarDocumento,
    ahora,
    nuevo_id,
)
from traza.core.estados import Estado
from traza.io.pdf import contar_paginas
from traza.persistence import carpeta as fs
from traza.persistence.filas import Delta, a_json, aplicar, leer

AUTORES = ("usuario", "motor", "ia", "importacion")


class ElementoBloqueado(OrdenRechazada):
    """Se intentó modificar un elemento aprobado sin reabrirlo."""


@dataclass(frozen=True)
class _Paso:
    orden_id: str
    nombre: str
    deltas: tuple[Delta, ...]


class Proyecto:
    def __init__(self, c: fs.Carpeta, con: sqlite3.Connection) -> None:
        self.carpeta = c
        self._con = con
        self._deshacer: list[_Paso] = []
        self._rehacer: list[_Paso] = []

    # --- Ciclo de vida -----------------------------------------------------------------

    @classmethod
    def crear(cls, destino: Path, nombre: str) -> Proyecto:
        if not nombre.strip():
            raise OrdenRechazada("El proyecto necesita un nombre.")
        c = fs.crear(destino)
        _, con = fs.abrir(c.raiz)
        con.execute("BEGIN IMMEDIATE")
        con.execute("INSERT INTO meta VALUES ('nombre', ?)", (nombre.strip(),))
        con.execute("INSERT INTO meta VALUES ('creado', ?)", (ahora(),))
        con.execute("COMMIT")
        return cls(c, con)

    @classmethod
    def abrir(cls, raiz: Path) -> Proyecto:
        c, con = fs.abrir(raiz)
        # Copia al abrir: si algo sale mal durante la sesión, el estado de partida existe.
        fs.copia_de_seguridad(c, con, etiqueta="apertura")
        return cls(c, con)

    def cerrar(self) -> None:
        self._con.close()

    @property
    def nombre(self) -> str:
        return self._con.execute("SELECT valor FROM meta WHERE clave='nombre'").fetchone()[0]

    def copia_de_seguridad(self) -> Path:
        return fs.copia_de_seguridad(self.carpeta, self._con, etiqueta="manual")

    # --- Órdenes -----------------------------------------------------------------------

    def ejecutar(self, orden: Orden, autor: str = "usuario") -> str:
        """Aplica una orden entera o nada. Devuelve el id de la orden."""
        if autor not in AUTORES:
            raise ValueError(f"Autor no válido: {autor}")
        paso = self._transaccion(orden.nombre, autor, lambda: self._planificar(orden))
        self._deshacer.append(paso)
        self._rehacer.clear()
        return paso.orden_id

    def deshacer(self) -> str | None:
        if not self._deshacer:
            return None
        paso = self._deshacer[-1]
        inverso = tuple(d.invertido() for d in reversed(paso.deltas))
        self._transaccion(paso.nombre, "deshacer", lambda: inverso, orden_id=paso.orden_id)
        self._rehacer.append(self._deshacer.pop())
        return paso.nombre

    def rehacer(self) -> str | None:
        if not self._rehacer:
            return None
        paso = self._rehacer[-1]
        self._transaccion(paso.nombre, "rehacer", lambda: paso.deltas, orden_id=paso.orden_id)
        self._deshacer.append(self._rehacer.pop())
        return paso.nombre

    @property
    def puede_deshacer(self) -> bool:
        return bool(self._deshacer)

    @property
    def puede_rehacer(self) -> bool:
        return bool(self._rehacer)

    def _planificar(self, orden: Orden) -> tuple[Delta, ...]:
        deltas = tuple(orden.planificar(self._con))
        if not deltas:
            raise OrdenRechazada("La orden no cambia nada.")
        if not orden.puede_tocar_aprobado:
            for d in deltas:
                self._comprobar_bloqueo(d)
        return deltas

    def _comprobar_bloqueo(self, d: Delta) -> None:
        """Línea roja 5: lo aprobado no se toca sin reabrirlo con una decisión escrita."""
        if d.tabla == "elemento":
            el = d.antes
        elif d.tabla in ("propiedad", "decision"):
            fila = d.antes or d.despues
            assert fila is not None
            el = leer(self._con, "elemento", {"id": fila["elemento_id"]})
        else:
            return
        if el is not None and el["estado"] == Estado.APROBADO:
            raise ElementoBloqueado(
                f"«{el['codigo']}» está aprobado. Para cambiarlo hay que reabrirlo indicando "
                "el motivo."
            )

    def _transaccion(self, nombre, autor, obtener_deltas, orden_id: str | None = None) -> _Paso:
        orden_id = orden_id or nuevo_id()
        con = self._con
        con.execute("BEGIN IMMEDIATE")
        try:
            deltas = tuple(obtener_deltas())
            fecha = ahora()
            for d in deltas:
                aplicar(con, d)
                con.execute(
                    "INSERT INTO cambio (orden_id, orden, autor, fecha, entidad, entidad_id,"
                    " campo, antes, despues) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        orden_id,
                        nombre,
                        autor,
                        fecha,
                        d.tabla,
                        d.id_legible,
                        ",".join(d.campos_cambiados()) or None,
                        a_json(d.antes),
                        a_json(d.despues),
                    ),
                )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        return _Paso(orden_id, nombre, deltas)

    # --- Documentos --------------------------------------------------------------------

    def incorporar_documento(self, origen: Path, clasificacion: str | None = None) -> str:
        """Copia el original al almacén (sin modificarlo) y lo registra. Devuelve su id.

        La copia física no se deshace: el almacén es de solo-añadir y un fichero sin
        registro no aparece en ningún sitio. Deshacer quita el registro.
        """
        origen = Path(origen)
        if not origen.is_file():
            raise OrdenRechazada(f"No se encuentra el fichero «{origen}».")
        extension = origen.suffix.lower()
        paginas = None
        if extension == ".pdf":
            try:
                paginas = contar_paginas(origen)
            except Exception as exc:
                raise OrdenRechazada(f"«{origen.name}» no se puede leer como PDF: {exc}") from exc
        sha, _ = fs.guardar_documento(self.carpeta, origen)
        orden = RegistrarDocumento(
            sha256=sha,
            nombre_original=origen.name,
            extension=extension,
            tamano=origen.stat().st_size,
            paginas=paginas,
            clasificacion=clasificacion,
        )
        self.ejecutar(orden)
        return orden.id

    def ruta_documento(self, documento_id: str) -> Path:
        doc = leer(self._con, "documento", {"id": documento_id})
        if doc is None:
            raise OrdenRechazada("Documento no incorporado.")
        return fs.ruta_documento(self.carpeta, doc["sha256"], doc["extension"])

    # --- Consultas (solo lectura) ------------------------------------------------------

    def _filas(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [dict(r) for r in self._con.execute(sql, params)]

    def elementos(self) -> list[dict[str, Any]]:
        return self._filas("SELECT * FROM elemento ORDER BY codigo")

    def elemento(self, elemento_id: str) -> dict[str, Any] | None:
        return leer(self._con, "elemento", {"id": elemento_id})

    def propiedades(self, elemento_id: str) -> list[dict[str, Any]]:
        filas = self._filas(
            "SELECT p.*, d.nombre_original AS documento_nombre FROM propiedad p"
            " LEFT JOIN documento d ON d.id = p.documento_id"
            " WHERE p.elemento_id = ? ORDER BY p.clave",
            (elemento_id,),
        )
        for f in filas:
            f["valor"] = json.loads(f["valor"])
        return filas

    def documentos(self) -> list[dict[str, Any]]:
        return self._filas("SELECT * FROM documento ORDER BY incorporado, nombre_original")

    def decisiones(self, elemento_id: str | None = None) -> list[dict[str, Any]]:
        if elemento_id is None:
            return self._filas("SELECT * FROM decision ORDER BY fecha")
        return self._filas(
            "SELECT * FROM decision WHERE elemento_id = ? ORDER BY fecha", (elemento_id,)
        )

    def pendientes(self, solo_abiertos: bool = True) -> list[dict[str, Any]]:
        sql = "SELECT * FROM pendiente"
        if solo_abiertos:
            sql += " WHERE estado = 'abierto'"
        return self._filas(sql + " ORDER BY creado")

    def cambios(self, limite: int = 500) -> list[dict[str, Any]]:
        return self._filas("SELECT * FROM cambio ORDER BY n DESC LIMIT ?", (limite,))

    def usos_de_documento(self, documento_id: str) -> list[dict[str, Any]]:
        """Qué valores del modelo citan este documento (trazabilidad inversa)."""
        return self._filas(
            "SELECT e.codigo, p.clave, p.localizador FROM propiedad p"
            " JOIN elemento e ON e.id = p.elemento_id WHERE p.documento_id = ?"
            " ORDER BY e.codigo, p.clave",
            (documento_id,),
        )
