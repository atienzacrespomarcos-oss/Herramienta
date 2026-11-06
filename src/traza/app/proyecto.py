"""Proyecto abierto: punto de entrada de la interfaz, los scripts y (en su día) la IA."""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from traza.ai import claude_code
from traza.app import lectura_ia
from traza.app import modificados as calculo_mod
from traza.app.ordenes import (
    ENCARGOS,
    CambiarEstado,
    CrearPendiente,
    FijarPropiedad,
    ImportarMedicion,
    Orden,
    OrdenRechazada,
    PartidaNueva,
    RegistrarDocumento,
    ahora,
    nuevo_id,
)
from traza.core.estados import Estado
from traza.core.procedencia import Origen
from traza.io import bc3, bc3_modificar
from traza.io.bc3_escritura import Bc3EscrituraError, CapituloBc3, PartidaBc3
from traza.io.bc3_escritura import escribir as escribir_bc3
from traza.io.excel import exportar_modificado, exportar_partidas
from traza.io.pdf import contar_paginas, renderizar_pagina
from traza.persistence import carpeta as fs
from traza.persistence.filas import Conflicto, Delta, a_json, aplicar, leer

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
        #: Quién lee PDF y Excel. Por defecto Claude Code (ADR-0013); las pruebas lo sustituyen.
        self.extractor_ia = claude_code.extraer
        self._rehacer: list[_Paso] = []

    # --- Ciclo de vida -----------------------------------------------------------------

    @classmethod
    def crear(cls, destino: Path, nombre: str, encargo: str = "diseno") -> Proyecto:
        if not nombre.strip():
            raise OrdenRechazada("El proyecto necesita un nombre.")
        if set('<>:"/\\|?*') & set(nombre) or ".." in nombre:
            # Con «/» o «..» el proyecto acabaría fuera de la carpeta elegida.
            raise OrdenRechazada('El nombre no puede contener < > : " / \\ | ? * ni «..».')
        c = fs.crear(destino)
        con = None
        try:
            _, con = fs.abrir(c.raiz)
            con.execute("BEGIN IMMEDIATE")
            con.execute("INSERT INTO meta VALUES ('nombre', ?)", (nombre.strip(),))
            con.execute("INSERT INTO meta VALUES ('creado', ?)", (ahora(),))
            if encargo not in ENCARGOS:
                raise OrdenRechazada(f"Tipo de encargo desconocido: «{encargo}».")
            con.execute("INSERT INTO meta VALUES ('encargo', ?)", (encargo,))
            con.execute("COMMIT")
        except BaseException:
            # Un proyecto a medio crear dejaría ocupado el nombre («ya existe») sin servir
            # para nada. La carpeta la acabamos de crear nosotros: se puede retirar.
            if con is not None:
                con.close()
            shutil.rmtree(c.raiz, ignore_errors=True)
            raise
        return cls(c, con)

    @classmethod
    def abrir(cls, raiz: Path) -> Proyecto:
        # La copia «antes de migrar», si hace falta, la hace fs.abrir antes de tocar nada.
        c, con = fs.abrir(raiz)
        try:
            # Copia al abrir: si algo sale mal durante la sesión, el estado de partida existe.
            fs.copia_de_seguridad(c, con, etiqueta=fs.ETIQUETA_APERTURA)
        except BaseException:
            con.close()
            raise
        return cls(c, con)

    def cerrar(self) -> None:
        self._con.close()

    @property
    def nombre(self) -> str:
        return self._con.execute("SELECT valor FROM meta WHERE clave='nombre'").fetchone()[0]

    @property
    def encargo(self) -> str:
        fila = self._con.execute("SELECT valor FROM meta WHERE clave='encargo'").fetchone()
        # Proyectos creados antes de existir el tipo de encargo: se tratan como diseño
        # completo, que es el que muestra todos los pasos (no oculta nada).
        return fila[0] if fila else "diseno"

    def copia_de_seguridad(self) -> Path:
        return fs.copia_de_seguridad(self.carpeta, self._con, etiqueta="manual")

    def copias(self) -> list[Path]:
        return fs.copias(self.carpeta)

    @staticmethod
    def restaurar_copia(raiz: Path, copia: Path) -> None:
        """Restaura una copia. El proyecto debe estar cerrado (lo exige la interfaz)."""
        fs.restaurar(fs.Carpeta(raiz), copia)

    # --- Órdenes -----------------------------------------------------------------------

    def ejecutar(self, orden: Orden, autor: str = "usuario") -> str:
        """Aplica una orden entera o nada. Devuelve el id de la orden."""
        if autor not in AUTORES:
            raise ValueError(f"Autor no válido: {autor}")
        self._comprobar_autor(orden, autor)
        try:
            paso = self._transaccion(orden.nombre, autor, lambda: self._planificar(orden))
        except (sqlite3.IntegrityError, Conflicto) as exc:
            # Segunda barrera (CHECK, claves únicas, estado inesperado): la orden no entra y
            # la transacción ya se ha deshecho entera.
            raise OrdenRechazada(f"No se aplica el cambio: {exc}") from exc
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

    @staticmethod
    def _comprobar_autor(orden: Orden, autor: str) -> None:
        """Quién puede hacer qué.

        - La IA solo propone (línea roja 7): valores con origen «ia_propuesta» y avisos de
          información pendiente. No confirma, no aprueba, no reabre.
        - «Calculado» y «comprobado» solo los fija un motor: marcarlos a mano sería mostrar
          un indicador de cumplimiento sin haber ejecutado la comprobación.
        """
        if autor == "ia":
            propone = (
                isinstance(orden, FijarPropiedad)
                and orden.procedencia.origen is Origen.IA_PROPUESTA
            )
            if not (propone or isinstance(orden, CrearPendiente)):
                raise OrdenRechazada(
                    "La IA solo puede proponer valores (origen «propuesta de IA») o señalar "
                    "información pendiente; lo demás lo decide el usuario."
                )
        elif isinstance(orden, FijarPropiedad) and orden.procedencia.origen is Origen.IA_PROPUESTA:
            raise OrdenRechazada("Solo la IA genera propuestas de IA.")
        if (
            isinstance(orden, CambiarEstado)
            and orden.estado in (Estado.CALCULADO, Estado.COMPROBADO)
            and autor != "motor"
        ):
            raise OrdenRechazada(
                f"El estado «{orden.estado}» lo fija un motor de cálculo al ejecutarse, no a mano."
            )

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
            if el is None and d.despues is not None and d.despues["padre_id"]:
                # Añadir un componente a un conjunto aprobado también lo modifica.
                el = leer(self._con, "elemento", {"id": d.despues["padre_id"]})
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
        except BaseException:
            # BaseException: también una interrupción (Ctrl+C) deshace la transacción.
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
        sha, almacenado = fs.guardar_documento(self.carpeta, origen)
        # Páginas y tamaño se leen de la copia verificada, no del original: si el original
        # cambiara entre medias, el registro describiría otro fichero.
        paginas = None
        if extension == ".pdf":
            try:
                paginas = contar_paginas(almacenado)
            except Exception as exc:
                raise OrdenRechazada(f"«{origen.name}» no se puede leer como PDF: {exc}") from exc
        orden = RegistrarDocumento(
            sha256=sha,
            nombre_original=origen.name,
            extension=extension,
            tamano=almacenado.stat().st_size,
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
            return self._filas("SELECT * FROM decision ORDER BY fecha, rowid")
        # rowid desempata decisiones del mismo segundo (aprobar y reabrir seguidos).
        return self._filas(
            "SELECT * FROM decision WHERE elemento_id = ? ORDER BY fecha, rowid", (elemento_id,)
        )

    def pendientes(self, solo_abiertos: bool = True) -> list[dict[str, Any]]:
        sql = "SELECT * FROM pendiente"
        if solo_abiertos:
            sql += " WHERE estado = 'abierto'"
        return self._filas(sql + " ORDER BY creado")

    def cambios(self, limite: int | None = None) -> list[dict[str, Any]]:
        """Registro de cambios, el más reciente primero. Sin límite: se muestra entero."""
        if limite is None:
            return self._filas("SELECT * FROM cambio ORDER BY n DESC")
        return self._filas("SELECT * FROM cambio ORDER BY n DESC LIMIT ?", (limite,))

    def usos_de_documento(self, documento_id: str) -> list[dict[str, Any]]:
        """Qué valores del modelo citan este documento (trazabilidad inversa)."""
        return self._filas(
            "SELECT e.codigo, p.clave, p.localizador FROM propiedad p"
            " JOIN elemento e ON e.id = p.elemento_id WHERE p.documento_id = ?"
            " ORDER BY e.codigo, p.clave",
            (documento_id,),
        )

    # --- Mediciones, ofertas y presupuestos ---------------------------------------------

    #: Formatos que se pueden leer como medición. Se amplía con cada lector (Excel, PDF).
    #: BC3 se lee sin IA (exacto). PDF y Excel se leen con IA + comprobaciones (ADR-0013).
    FORMATOS_MEDICION = (".bc3", ".pdf", ".xlsx", ".xlsm")
    FORMATOS_CON_IA = (".pdf", ".xlsx", ".xlsm")

    def leer_medicion(
        self,
        documento_id: str,
        clase: str,
        proveedor: str | None = None,
        esperar: Callable[[Callable[[], Any]], Any] | None = None,
    ) -> tuple[str, list[str]]:
        """Lee un documento incorporado como medición/oferta/presupuesto y guarda sus partidas.

        Se lee la copia del almacén (la verificada por su huella), no el original.
        Devuelve (id de la medición, avisos del lector).

        `esperar` ejecuta la parte lenta (la llamada a la IA, que no toca la base de datos)
        mientras la interfaz sigue respondiendo; por defecto se ejecuta sin más.
        """
        doc = leer(self._con, "documento", {"id": documento_id})
        if doc is None:
            raise OrdenRechazada("Documento no incorporado.")
        if doc["extension"] not in self.FORMATOS_MEDICION:
            raise OrdenRechazada(
                f"Todavía no se pueden leer mediciones en formato «{doc['extension']}». "
                f"Formatos disponibles: {', '.join(self.FORMATOS_MEDICION)}."
            )
        previa = self._con.execute(
            "SELECT nombre FROM medicion WHERE documento_id = ?", (documento_id,)
        ).fetchone()
        if previa:
            # Antes de leer: así no se envía a la IA (ni se gasta suscripción) en balde.
            raise OrdenRechazada(
                f"«{previa['nombre']}» ya está leído. Quita esa medición si quieres volver a "
                "leerlo."
            )
        ruta = self.ruta_documento(documento_id)
        if doc["extension"] in self.FORMATOS_CON_IA:
            return self._leer_con_ia(doc, ruta, clase, proveedor, esperar or (lambda f: f()))
        try:
            leido = bc3.leer_bc3(ruta)
        except bc3.Bc3Error as exc:
            raise OrdenRechazada(f"«{doc['nombre_original']}»: {exc}") from exc
        resultado = bc3.leer_partidas(leido)
        ps = resultado.partidas
        avisos = leido.avisos + resultado.avisos
        orden = ImportarMedicion(
            documento_id=documento_id,
            titulo=doc["nombre_original"],
            clase=clase,
            proveedor=proveedor,
            lector=bc3.LECTOR,
            version_lector=bc3.VERSION_LECTOR,
            partidas=[
                PartidaNueva(
                    capitulo=[list(c) for c in p.capitulos],
                    codigo=p.codigo,
                    etiqueta=p.etiqueta,
                    unidad=p.unidad,
                    resumen=p.resumen,
                    texto=p.texto,
                    cantidad=p.cantidad,
                    precio=p.precio,
                    localizador=p.localizador,
                )
                for p in ps
            ],
            avisos=avisos,
            omitidas=resultado.omitidas,
        )
        self.ejecutar(orden)
        return orden.id, avisos

    def _leer_con_ia(
        self,
        doc: dict[str, Any],
        ruta: Path,
        clase: str,
        proveedor: str | None,
        esperar: Callable[[Callable[[], Any]], Any],
    ) -> tuple[str, list[str]]:
        avisos: list[str] = []
        imagenes: dict[int, Path] = {}
        temporal: Path | None = None
        if doc["extension"] == ".pdf":
            fuente: lectura_ia.Fuente = lectura_ia.FuentePdf(ruta)
            sin_texto = fuente.paginas_sin_texto
            if sin_texto:
                # Páginas escaneadas (todas o algunas): la IA las lee como imagen, pero no hay
                # texto con que comprobarlas: sus líneas quedan «a revisar».
                avisos.append(
                    f"Páginas sin texto (escaneadas): {', '.join(map(str, sin_texto))}. La IA "
                    "las lee como imagen; sus líneas no se pueden comprobar y quedan «a revisar»."
                )
                temporal = Path(tempfile.mkdtemp(prefix="traza-pdf-"))
                imagenes = {
                    n: renderizar_pagina(ruta, n, temporal / f"pagina_{n:03d}.png")
                    for n in sin_texto
                }
        else:
            fuente = lectura_ia.FuenteExcel(ruta)
            avisos += fuente.avisos
        texto = fuente.texto_para_ia()
        try:
            extraido = esperar(lambda: self.extractor_ia(texto, imagenes or None))
        except (claude_code.IaNoDisponible, claude_code.IaError) as exc:
            raise OrdenRechazada(f"«{doc['nombre_original']}»: {exc}") from exc
        finally:
            if temporal is not None:
                shutil.rmtree(temporal, ignore_errors=True)
        r = lectura_ia.comprobar(extraido, fuente)
        if r.proveedor and not proveedor:
            # Leído por la IA y no comprobado: se dice, no se guarda como dato.
            avisos.append(f"La IA identifica el proveedor como «{r.proveedor}» (sin comprobar).")
        avisos += r.avisos
        orden = ImportarMedicion(
            documento_id=doc["id"],
            titulo=doc["nombre_original"],
            clase=clase,
            proveedor=proveedor,
            lector=claude_code.PROVEEDOR,
            version_lector=claude_code.VERSION,
            partidas=r.partidas,
            avisos=avisos,
            total_documento=r.total_documento,
        )
        self.ejecutar(orden, autor="importacion")
        return orden.id, avisos

    def mediciones(self) -> list[dict[str, Any]]:
        filas = self._filas(
            "SELECT m.*, d.nombre_original AS documento_nombre,"
            " (SELECT count(*) FROM partida p WHERE p.medicion_id = m.id) AS n_partidas"
            " FROM medicion m JOIN documento d ON d.id = m.documento_id ORDER BY m.leido"
        )
        for f in filas:
            f["avisos"] = json.loads(f["avisos"])
        return filas

    def partidas(self, medicion_id: str) -> list[dict[str, Any]]:
        filas = self._filas(
            "SELECT * FROM partida WHERE medicion_id = ? ORDER BY orden", (medicion_id,)
        )
        for f in filas:
            f["capitulo"] = json.loads(f["capitulo"])
            f["motivos"] = json.loads(f["motivos"])
            f["importe"] = (
                f["cantidad"] * f["precio"]
                if f["cantidad"] is not None and f["precio"] is not None
                else None
            )
        return filas

    def exportar_excel(self, destino: Path, medicion_ids: list[str] | None = None) -> Path:
        """El «Excel con todo» para hacer los pedidos en el ERP del usuario."""
        meds = [m for m in self.mediciones() if medicion_ids is None or m["id"] in medicion_ids]
        if not meds:
            raise OrdenRechazada("No hay mediciones leídas que exportar.")
        bloques = [(m, self.partidas(m["id"])) for m in meds]
        return exportar_partidas(Path(destino), self.nombre, bloques)

    # --- Ampliaciones y modificaciones ---------------------------------------------------

    def modificados(self, medicion_id: str | None = None) -> list[dict[str, Any]]:
        sql = (
            "SELECT o.*, d.nombre_original AS base_nombre,"
            " (SELECT count(*) FROM cambio_modificado c WHERE c.modificado_id = o.id)"
            " AS n_cambios"
            " FROM modificado o JOIN medicion m ON m.id = o.medicion_id"
            " JOIN documento d ON d.id = m.documento_id"
        )
        if medicion_id is None:
            return self._filas(sql + " ORDER BY o.creado, o.numero")
        return self._filas(sql + " WHERE o.medicion_id = ? ORDER BY o.numero", (medicion_id,))

    def modificado(self, modificado_id: str) -> dict[str, Any] | None:
        return next((m for m in self.modificados() if m["id"] == modificado_id), None)

    def ofertas_utilizables(self) -> list[dict[str, Any]]:
        """Líneas de ofertas leídas que pueden ser partida nueva: fiables y con precio."""
        filas = self._filas(
            "SELECT p.*, d.nombre_original AS documento_nombre, m.proveedor"
            " FROM partida p JOIN medicion m ON m.id = p.medicion_id"
            " JOIN documento d ON d.id = m.documento_id"
            " WHERE m.clase = 'oferta' AND p.precio IS NOT NULL"
            " AND p.estado IN ('exacta','comprobada','confirmada')"
            " ORDER BY d.nombre_original, p.orden"
        )
        for f in filas:
            f["capitulo"] = json.loads(f["capitulo"])
        return filas

    def resumen_modificado(self, modificado_id: str) -> calculo_mod.Resumen:
        mod = leer(self._con, "modificado", {"id": modificado_id})
        if mod is None:
            raise OrdenRechazada("Ese modificado no existe.")
        cambios = self._filas(
            "SELECT * FROM cambio_modificado WHERE modificado_id = ? ORDER BY orden",
            (modificado_id,),
        )
        nuevas = {}
        for c in cambios:
            if c["tipo"] == "nueva":
                p = leer(self._con, "partida", {"id": c["partida_id"]})
                nuevas[c["partida_id"]] = p
        nombres = {m["id"]: m["documento_nombre"] for m in self.mediciones()}
        return calculo_mod.calcular(self.partidas(mod["medicion_id"]), cambios, nuevas, nombres)

    def exportar_modificado_excel(self, modificado_id: str, destino: Path) -> Path:
        mod = self.modificado(modificado_id)
        if mod is None:
            raise OrdenRechazada("Ese modificado no existe.")
        r = self.resumen_modificado(modificado_id)
        if not r.cambios:
            raise OrdenRechazada("El modificado no tiene cambios que exportar.")
        return exportar_modificado(Path(destino), self.nombre, mod, r)

    def exportar_modificado_bc3(self, modificado_id: str, destino: Path) -> tuple[Path, list[str]]:
        """BC3 del presupuesto completo actualizado (decisión del usuario, 06-11-2026).

        Base leída de un BC3: se parte del fichero original (conserva descompuestos, textos y
        todo lo que TRAZA no interpreta). Base leída de PDF o Excel: se genera con lo leído.
        En ambos casos el fichero se relee y se compara antes de guardarlo.
        """
        mod = self.modificado(modificado_id)
        if mod is None:
            raise OrdenRechazada("Ese modificado no existe.")
        r = self.resumen_modificado(modificado_id)
        if not r.cambios:
            raise OrdenRechazada("El modificado no tiene cambios que exportar.")
        base = next(m for m in self.mediciones() if m["id"] == mod["medicion_id"])
        destino = Path(destino)
        if destino.suffix.lower() != ".bc3":
            destino = destino.with_name(destino.name + ".bc3")
        nuevas = [
            PartidaBc3(x.codigo or "", x.unidad, x.resumen, None, x.cantidad_modificada, x.precio)
            for x in r.cambios
            if x.tipo == "nueva"
        ]
        try:
            if base["lector"] == bc3.LECTOR:
                partidas = {p["id"]: p for p in self.partidas(base["id"])}
                variaciones = [
                    bc3_modificar.Variacion(
                        localizador=partidas[x.partida_id]["localizador"],
                        codigo=x.codigo or "",
                        cantidad_contrato=x.cantidad_contrato,
                        cantidad_nueva=x.cantidad_modificada,
                        precio=x.precio,
                        capitulos=[c[0] for c in x.capitulo],
                        comentario=f"{x.motivo}. {x.justificacion}",
                    )
                    for x in r.cambios
                    if x.tipo != "nueva"
                ]
                return bc3_modificar.actualizar(
                    self.ruta_documento(base["documento_id"]),
                    destino,
                    mod["numero"],
                    variaciones,
                    nuevas,
                )
            return self._bc3_generado(mod, r, destino, nuevas)
        except (bc3_modificar.Bc3ModificarError, Bc3EscrituraError) as exc:
            raise OrdenRechazada(str(exc)) from exc

    def _bc3_generado(self, mod, r, destino: Path, nuevas) -> tuple[Path, list[str]]:
        """Base que no es BC3 (leída de PDF o Excel): presupuesto generado con lo leído."""
        raiz = CapituloBc3("OBRA", f"{self.nombre} - modificado nº {mod['numero']}")
        capitulos: dict[str, CapituloBc3] = {}
        usados: set[str] = set()
        for n, x in enumerate((x for x in r.lineas if x.tipo != "nueva"), start=1):
            nombre = " / ".join(c[0] for c in x.capitulo) or "Sin capítulo"
            if nombre not in capitulos:
                capitulos[nombre] = CapituloBc3(f"C{len(capitulos) + 1:02d}", nombre)
                raiz.capitulos.append(capitulos[nombre])
            codigo = (
                x.codigo
                if x.codigo and x.codigo not in usados and len(x.codigo) <= 20
                else f"P{n:04d}"
            )
            usados.add(codigo)
            capitulos[nombre].partidas.append(
                PartidaBc3(codigo, x.unidad, x.resumen, None, x.cantidad_modificada, x.precio)
            )
        if nuevas:
            cap = CapituloBc3(
                f"MOD{mod['numero']}", f"Modificado nº {mod['numero']} - partidas nuevas"
            )
            for k, p in enumerate(nuevas, start=1):
                if not p.codigo or p.codigo in usados or len(p.codigo) > 20:
                    p.codigo = f"MOD{mod['numero']}.{k}"
                usados.add(p.codigo)
                cap.partidas.append(p)
            raiz.capitulos.append(cap)
        ruta, avisos = escribir_bc3(
            destino, raiz, propiedad=self.nombre, comentario=f"Modificado nº {mod['numero']}"
        )
        avisos.insert(
            0,
            "La base se leyó de PDF o Excel: el BC3 se ha generado con lo leído (capítulos con "
            "códigos C01, C02…; sin descompuestos ni textos originales).",
        )
        return ruta, avisos
