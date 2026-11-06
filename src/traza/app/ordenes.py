"""Órdenes: la ÚNICA vía para modificar el modelo (ADR-0010, línea roja 8).

Una orden no escribe: lee el estado y devuelve los `Delta` que quiere aplicar.
`Proyecto.ejecutar` los aplica en una transacción, comprueba el bloqueo de lo aprobado,
los anota en el registro de cambios y los apila para deshacer. Por eso ninguna orden
puede saltarse ni el registro ni el bloqueo.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from traza.core.estados import Estado, transicion_permitida
from traza.core.procedencia import Origen, Procedencia
from traza.core.tipos import Clase, tipo, validar_valor
from traza.io.pdf import pagina_citada
from traza.persistence.filas import Delta, Fila, leer


class OrdenRechazada(ValueError):
    """La orden no se puede ejecutar; el mensaje explica por qué en términos de proyecto."""


def ahora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def nuevo_id() -> str:
    return str(uuid.uuid4())


class Orden(ABC):
    #: Solo las órdenes que dejan una decisión escrita (reabrir) pueden tocar lo aprobado.
    puede_tocar_aprobado: bool = False

    @property
    def nombre(self) -> str:
        return type(self).__name__

    @abstractmethod
    def planificar(self, con: sqlite3.Connection) -> list[Delta]: ...


def _elemento(con: sqlite3.Connection, elemento_id: str) -> Fila:
    fila = leer(con, "elemento", {"id": elemento_id})
    if fila is None:
        raise OrdenRechazada(f"No existe el elemento {elemento_id}.")
    return fila


# --- Elementos -----------------------------------------------------------------------


@dataclass
class CrearElemento(Orden):
    tipo: str
    codigo: str
    padre_id: str | None = None
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        try:
            t = tipo(self.tipo)
        except KeyError as exc:
            raise OrdenRechazada(str(exc)) from None
        codigo = self.codigo.strip()
        if not codigo:
            raise OrdenRechazada("El elemento necesita un código (p. ej. UTA-01).")
        if con.execute("SELECT 1 FROM elemento WHERE codigo = ?", (codigo,)).fetchone():
            raise OrdenRechazada(f"Ya existe un elemento con el código «{codigo}».")
        if self.padre_id is not None:
            _elemento(con, self.padre_id)
        t_ahora = ahora()
        return [
            Delta(
                "elemento",
                None,
                {
                    "id": self.id,
                    "codigo": codigo,
                    "tipo": t.nombre,
                    "tipo_version": t.version,
                    "disciplina": str(t.disciplina),
                    "estado": str(Estado.BORRADOR),
                    "padre_id": self.padre_id,
                    "creado": t_ahora,
                    "modificado": t_ahora,
                },
            )
        ]


@dataclass
class CambiarEstado(Orden):
    elemento_id: str
    estado: Estado

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        el = _elemento(con, self.elemento_id)
        desde = Estado(el["estado"])
        if self.estado is Estado.APROBADO:
            raise OrdenRechazada("Para aprobar se usa la orden Aprobar (deja decisión escrita).")
        if not transicion_permitida(desde, self.estado):
            raise OrdenRechazada(f"No se pasa de «{desde}» a «{self.estado}».")
        return [Delta("elemento", el, {**el, "estado": str(self.estado), "modificado": ahora()})]


@dataclass
class Aprobar(Orden):
    elemento_id: str
    motivo: str
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        el = _elemento(con, self.elemento_id)
        if el["estado"] == Estado.APROBADO:
            raise OrdenRechazada(f"«{el['codigo']}» ya está aprobado.")
        if not self.motivo.strip():
            raise OrdenRechazada("Aprobar exige escribir el motivo.")
        t = tipo(el["tipo"])
        props = {
            r["clave"]: r
            for r in con.execute(
                "SELECT clave, origen, confirmado FROM propiedad WHERE elemento_id = ?",
                (self.elemento_id,),
            )
        }
        faltan = [
            p.etiqueta for p in t.propiedades if p.obligatoria_para_aprobar and p.clave not in props
        ]
        if faltan:
            raise OrdenRechazada(
                f"No se puede aprobar «{el['codigo']}»: faltan {', '.join(faltan)}."
            )
        sin_confirmar = [k for k, r in props.items() if not r["confirmado"]]
        if sin_confirmar:
            raise OrdenRechazada(
                f"No se puede aprobar «{el['codigo']}»: hay propuestas sin confirmar "
                f"({', '.join(sorted(sin_confirmar))})."
            )
        t_ahora = ahora()
        return [
            Delta("elemento", el, {**el, "estado": str(Estado.APROBADO), "modificado": t_ahora}),
            Delta(
                "decision",
                None,
                {
                    "id": self.id,
                    "elemento_id": self.elemento_id,
                    "tipo": "aprobar",
                    "motivo": self.motivo.strip(),
                    "fecha": t_ahora,
                },
            ),
        ]


@dataclass
class Reabrir(Orden):
    elemento_id: str
    motivo: str
    id: str = field(default_factory=nuevo_id)
    puede_tocar_aprobado = True

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        el = _elemento(con, self.elemento_id)
        if el["estado"] != Estado.APROBADO:
            raise OrdenRechazada(f"«{el['codigo']}» no está aprobado; no hay nada que reabrir.")
        if not self.motivo.strip():
            raise OrdenRechazada("Reabrir un elemento aprobado exige escribir el motivo.")
        t_ahora = ahora()
        return [
            Delta("elemento", el, {**el, "estado": str(Estado.BORRADOR), "modificado": t_ahora}),
            Delta(
                "decision",
                None,
                {
                    "id": self.id,
                    "elemento_id": self.elemento_id,
                    "tipo": "reabrir",
                    "motivo": self.motivo.strip(),
                    "fecha": t_ahora,
                },
            ),
        ]


# --- Propiedades ---------------------------------------------------------------------


def _comprobar_cita(con: sqlite3.Connection, p: Procedencia) -> None:
    if p.documento_id is None:
        return
    doc = leer(con, "documento", {"id": p.documento_id})
    if doc is None:
        raise OrdenRechazada("El documento citado no está incorporado al proyecto.")
    if doc["paginas"] is not None:
        assert p.localizador is not None
        pagina = pagina_citada(p.localizador)
        if pagina is None:
            raise OrdenRechazada(
                f"«{doc['nombre_original']}» es un PDF: la cita debe empezar por la página "
                "(p. ej. «p. 14» o «p. 14, tabla 3»)."
            )
        if not 1 <= pagina <= doc["paginas"]:
            raise OrdenRechazada(
                f"«{doc['nombre_original']}» tiene {doc['paginas']} páginas; "
                f"no existe la página {pagina}."
            )


@dataclass
class FijarPropiedad(Orden):
    elemento_id: str
    clave: str
    valor: str | int | float
    unidad: str | None
    procedencia: Procedencia

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        el = _elemento(con, self.elemento_id)
        t = tipo(el["tipo"])
        try:
            defn = t.propiedad(self.clave)
        except KeyError as exc:
            raise OrdenRechazada(str(exc)) from None
        try:
            validar_valor(defn, self.valor, self.unidad)
        except ValueError as exc:
            raise OrdenRechazada(str(exc)) from None
        if self.procedencia.origen is Origen.CALCULO:
            raise OrdenRechazada("Los resultados de cálculo los escribe el motor, no a mano.")
        _comprobar_cita(con, self.procedencia)
        valor = self.valor.strip() if defn.clase is Clase.TEXTO else self.valor
        antes = leer(con, "propiedad", {"elemento_id": self.elemento_id, "clave": self.clave})
        p = self.procedencia
        despues = {
            "elemento_id": self.elemento_id,
            "clave": self.clave,
            "valor": json.dumps(valor, ensure_ascii=False),
            "unidad": self.unidad.strip() if self.unidad else None,
            "origen": str(p.origen),
            "documento_id": p.documento_id,
            "localizador": p.localizador.strip() if p.localizador else None,
            "registro_calculo_id": None,
            "nota": p.nota.strip() if p.nota else None,
            "confirmado": 0 if p.requiere_confirmacion else 1,
            "modificado": ahora(),
        }
        return [Delta("propiedad", antes, despues)]


@dataclass
class ConfirmarPropuesta(Orden):
    """El usuario hace suya una propuesta de la IA. Si citaba documento, pasa a «documento»."""

    elemento_id: str
    clave: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        antes = leer(con, "propiedad", {"elemento_id": self.elemento_id, "clave": self.clave})
        if antes is None or antes["origen"] != Origen.IA_PROPUESTA:
            raise OrdenRechazada("No hay ninguna propuesta pendiente de confirmar en ese campo.")
        origen = Origen.DOCUMENTO if antes["documento_id"] else Origen.USUARIO
        nota = "Confirmado por el usuario a partir de una propuesta de la IA."
        return [
            Delta(
                "propiedad",
                antes,
                {
                    **antes,
                    "origen": str(origen),
                    "confirmado": 1,
                    "nota": nota,
                    "modificado": ahora(),
                },
            )
        ]


@dataclass
class BorrarPropiedad(Orden):
    elemento_id: str
    clave: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        antes = leer(con, "propiedad", {"elemento_id": self.elemento_id, "clave": self.clave})
        if antes is None:
            raise OrdenRechazada("Esa propiedad no tiene valor.")
        return [Delta("propiedad", antes, None)]


# --- Documentos y pendientes ---------------------------------------------------------


@dataclass
class RegistrarDocumento(Orden):
    """Da de alta en el proyecto un documento YA copiado al almacén (ver Proyecto)."""

    sha256: str
    nombre_original: str
    extension: str
    tamano: int
    paginas: int | None
    clasificacion: str | None = None
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        previo = con.execute(
            "SELECT nombre_original FROM documento WHERE sha256 = ?", (self.sha256,)
        ).fetchone()
        if previo:
            raise OrdenRechazada(
                f"Ese documento ya está incorporado como «{previo['nombre_original']}»."
            )
        return [
            Delta(
                "documento",
                None,
                {
                    "id": self.id,
                    "sha256": self.sha256,
                    "nombre_original": Path(self.nombre_original).name,
                    "extension": self.extension,
                    "tamano": self.tamano,
                    "paginas": self.paginas,
                    "clasificacion": self.clasificacion,
                    "incorporado": ahora(),
                },
            )
        ]


@dataclass
class CrearPendiente(Orden):
    descripcion: str
    elemento_id: str | None = None
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        if not self.descripcion.strip():
            raise OrdenRechazada("Describe qué información falta.")
        if self.elemento_id is not None:
            _elemento(con, self.elemento_id)
        return [
            Delta(
                "pendiente",
                None,
                {
                    "id": self.id,
                    "elemento_id": self.elemento_id,
                    "descripcion": self.descripcion.strip(),
                    "estado": "abierto",
                    "resolucion": None,
                    "creado": ahora(),
                },
            )
        ]


@dataclass
class ResolverPendiente(Orden):
    pendiente_id: str
    resolucion: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        antes = leer(con, "pendiente", {"id": self.pendiente_id})
        if antes is None:
            raise OrdenRechazada("No existe ese pendiente.")
        if antes["estado"] == "resuelto":
            raise OrdenRechazada("Ese pendiente ya está resuelto.")
        if not self.resolucion.strip():
            raise OrdenRechazada("Indica cómo se ha resuelto.")
        return [
            Delta(
                "pendiente",
                antes,
                {**antes, "estado": "resuelto", "resolucion": self.resolucion.strip()},
            )
        ]


# --- Tipo de encargo ----------------------------------------------------------------

#: Tipos de encargo del usuario (06-11-2026). Deciden qué pasos del proyecto se muestran.
ENCARGOS = {
    "diseno": "Diseño + presupuesto + instalación",
    "presupuesto": "Presupuesto + instalación",
    "instalacion": "Solo instalación",
}


@dataclass
class CambiarEncargo(Orden):
    encargo: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        if self.encargo not in ENCARGOS:
            raise OrdenRechazada(f"Tipo de encargo desconocido: «{self.encargo}».")
        antes = leer(con, "meta", {"clave": "encargo"})
        despues = {"clave": "encargo", "valor": self.encargo}
        if antes == despues:
            raise OrdenRechazada("El proyecto ya tiene ese tipo de encargo.")
        return [Delta("meta", antes, despues)]


# --- Mediciones, ofertas y presupuestos ----------------------------------------------

CLASES_MEDICION = {"medicion": "Medición", "oferta": "Oferta", "presupuesto": "Presupuesto"}


@dataclass
class PartidaNueva:
    capitulo: list[list[str]]
    codigo: str | None
    etiqueta: str | None
    unidad: str | None
    resumen: str | None
    texto: str | None
    cantidad: float | None
    precio: float | None
    localizador: str
    #: «exacta» (BC3, sin interpretar), «comprobada» (IA + comprobaciones superadas) o
    #: «a_revisar» (IA + alguna comprobación no superada; ver motivos).
    estado: str = "exacta"
    motivos: list[str] = field(default_factory=list)


ESTADOS_PARTIDA = ("exacta", "comprobada", "a_revisar", "confirmada")


@dataclass
class ImportarMedicion(Orden):
    """Da de alta lo leído de un documento: una medición/oferta/presupuesto y sus partidas.

    Todo entra en una sola orden: o se importa entero o no se importa, y se deshace de una vez.
    """

    documento_id: str
    # No se llama «nombre»: Orden ya tiene una propiedad con ese nombre y dataclass la
    # tomaría como valor por defecto del campo.
    titulo: str
    clase: str
    proveedor: str | None
    lector: str
    version_lector: str
    partidas: list[PartidaNueva]
    avisos: list[str]
    omitidas: int = 0
    total_documento: float | None = None
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        if leer(con, "documento", {"id": self.documento_id}) is None:
            raise OrdenRechazada("El documento no está incorporado al proyecto.")
        if self.clase not in CLASES_MEDICION:
            raise OrdenRechazada(f"Clase desconocida: «{self.clase}».")
        previa = con.execute(
            "SELECT nombre FROM medicion WHERE documento_id = ?", (self.documento_id,)
        ).fetchone()
        if previa:
            # Leerlo dos veces duplicaría todas las partidas en totales y en el Excel.
            raise OrdenRechazada(
                f"«{previa['nombre']}» ya está leído. Quita esa medición si quieres volver a "
                "leerlo."
            )
        if not self.partidas:
            motivo = "; ".join(self.avisos[:5]) if self.avisos else "sin más detalle"
            raise OrdenRechazada(f"El documento no contiene partidas que importar ({motivo}).")
        deltas = [
            Delta(
                "medicion",
                None,
                {
                    "id": self.id,
                    "documento_id": self.documento_id,
                    "nombre": self.titulo.strip() or "(sin nombre)",
                    "clase": self.clase,
                    "proveedor": (self.proveedor or "").strip() or None,
                    "lector": self.lector,
                    "version_lector": self.version_lector,
                    "leido": ahora(),
                    "avisos": json.dumps(self.avisos, ensure_ascii=False),
                    "omitidas": self.omitidas,
                    "total_documento": self.total_documento,
                },
            )
        ]
        for n, p in enumerate(self.partidas, start=1):
            deltas.append(
                Delta(
                    "partida",
                    None,
                    {
                        "id": nuevo_id(),
                        "medicion_id": self.id,
                        "orden": n,
                        "capitulo": json.dumps(p.capitulo, ensure_ascii=False),
                        "codigo": p.codigo,
                        "etiqueta": p.etiqueta,
                        "unidad": p.unidad,
                        "resumen": p.resumen,
                        "texto": p.texto,
                        "cantidad": p.cantidad,
                        "precio": p.precio,
                        "localizador": p.localizador,
                        "estado": p.estado,
                        "motivos": json.dumps(p.motivos, ensure_ascii=False),
                    },
                )
            )
        return deltas


@dataclass
class QuitarMedicion(Orden):
    medicion_id: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        med = leer(con, "medicion", {"id": self.medicion_id})
        if med is None:
            raise OrdenRechazada("Esa medición no existe.")
        filas = [
            dict(r)
            for r in con.execute(
                "SELECT * FROM partida WHERE medicion_id = ? ORDER BY orden", (self.medicion_id,)
            )
        ]
        usada = con.execute(
            "SELECT m.titulo FROM modificado m WHERE m.medicion_id = ?"
            " UNION SELECT m.titulo FROM cambio_modificado c"
            " JOIN modificado m ON m.id = c.modificado_id"
            " JOIN partida p ON p.id = c.partida_id WHERE p.medicion_id = ?",
            (self.medicion_id, self.medicion_id),
        ).fetchone()
        if usada:
            # Quitarla dejaría un modificado sin base o sin el precio de sus partidas nuevas.
            raise OrdenRechazada(
                f"No se puede quitar: la usa el modificado «{usada['titulo']}». Quita antes "
                "ese modificado o sus cambios."
            )
        # Partidas primero y la cabecera después: al deshacer, el orden se invierte solo.
        return [Delta("partida", f, None) for f in filas] + [Delta("medicion", med, None)]


@dataclass
class ConfirmarPartida(Orden):
    """El usuario ha revisado contra el documento una partida «a revisar» y la da por buena."""

    partida_id: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        antes = leer(con, "partida", {"id": self.partida_id})
        if antes is None:
            raise OrdenRechazada("Esa partida no existe.")
        if antes["estado"] != "a_revisar":
            raise OrdenRechazada("Solo se confirman partidas marcadas «a revisar».")
        return [Delta("partida", antes, {**antes, "estado": "confirmada"})]


# --- Ampliaciones y modificaciones --------------------------------------------------------

#: Motivos de un cambio (decisión del usuario, 06-11-2026): siempre con justificación escrita.
MOTIVOS = {
    "medicion": "Error de medición",
    "diseno": "Fallo de diseño",
    "economica": "Mejora económica",
    "otro": "Otro",
}
#: Una partida leída solo puede alimentar un modificado si su lectura es fiable.
ESTADOS_FIABLES = ("exacta", "comprobada", "confirmada")


def _modificado(con: sqlite3.Connection, modificado_id: str) -> Fila:
    m = leer(con, "modificado", {"id": modificado_id})
    if m is None:
        raise OrdenRechazada("Ese modificado no existe.")
    return m


def _motivo(motivo: str, justificacion: str) -> str:
    if motivo not in MOTIVOS:
        raise OrdenRechazada(f"Motivo desconocido: «{motivo}».")
    if not justificacion.strip():
        raise OrdenRechazada("Cada cambio necesita su justificación escrita.")
    return justificacion.strip()


def _cantidad(cantidad: float) -> float:
    if isinstance(cantidad, bool) or not isinstance(cantidad, int | float):
        raise OrdenRechazada("La cantidad tiene que ser un número.")
    if cantidad != cantidad or cantidad in (float("inf"), float("-inf")) or cantidad < 0:
        raise OrdenRechazada("La cantidad tiene que ser un número finito y no negativo.")
    return float(cantidad)


def _siguiente_orden(con: sqlite3.Connection, modificado_id: str) -> int:
    fila = con.execute(
        "SELECT coalesce(max(orden), 0) + 1 FROM cambio_modificado WHERE modificado_id = ?",
        (modificado_id,),
    ).fetchone()
    return int(fila[0])


@dataclass
class CrearModificado(Orden):
    medicion_id: str
    titulo: str
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        if leer(con, "medicion", {"id": self.medicion_id}) is None:
            raise OrdenRechazada("La medición de base no existe.")
        if not self.titulo.strip():
            raise OrdenRechazada("El modificado necesita un título.")
        numero = con.execute(
            "SELECT coalesce(max(numero), 0) + 1 FROM modificado WHERE medicion_id = ?",
            (self.medicion_id,),
        ).fetchone()[0]
        return [
            Delta(
                "modificado",
                None,
                {
                    "id": self.id,
                    "medicion_id": self.medicion_id,
                    "numero": int(numero),
                    "titulo": self.titulo.strip(),
                    "creado": ahora(),
                },
            )
        ]


@dataclass
class VariarPartida(Orden):
    """Nueva cantidad (aumento, disminución o anulación con 0) de una partida de la base."""

    modificado_id: str
    partida_id: str
    cantidad: float
    motivo: str
    justificacion: str
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        mod = _modificado(con, self.modificado_id)
        justificacion = _motivo(self.motivo, self.justificacion)
        cantidad = _cantidad(self.cantidad)
        p = leer(con, "partida", {"id": self.partida_id})
        if p is None or p["medicion_id"] != mod["medicion_id"]:
            raise OrdenRechazada("Solo se pueden variar partidas de la medición de base.")
        if p["estado"] not in ESTADOS_FIABLES:
            raise OrdenRechazada(
                "Esa partida está «a revisar»: compruébala y confírmala antes de modificarla."
            )
        if p["cantidad"] is None:
            raise OrdenRechazada(
                "La cantidad de contrato de esa partida no consta: no se puede calcular la "
                "variación."
            )
        if abs(cantidad - p["cantidad"]) < 1e-9:
            raise OrdenRechazada("La cantidad nueva es igual a la de contrato: no hay cambio.")
        if con.execute(
            "SELECT 1 FROM cambio_modificado WHERE modificado_id = ? AND tipo = 'variacion'"
            " AND partida_id = ?",
            (self.modificado_id, self.partida_id),
        ).fetchone():
            raise OrdenRechazada("Esa partida ya tiene una variación en este modificado.")
        return [_fila_cambio(self, "variacion", cantidad, justificacion, con)]


@dataclass
class AnadirPartidaNueva(Orden):
    """Partida nueva tomada de una oferta leída: código, unidad, descripción y precio de la
    oferta (enlazados a su origen); la cantidad la pone el usuario."""

    modificado_id: str
    partida_id: str  # partida de una OFERTA leída
    cantidad: float
    motivo: str
    justificacion: str
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        _modificado(con, self.modificado_id)
        justificacion = _motivo(self.motivo, self.justificacion)
        cantidad = _cantidad(self.cantidad)
        if cantidad == 0:
            raise OrdenRechazada("Una partida nueva necesita una cantidad mayor que cero.")
        p = con.execute(
            "SELECT p.*, m.clase FROM partida p JOIN medicion m ON m.id = p.medicion_id"
            " WHERE p.id = ?",
            (self.partida_id,),
        ).fetchone()
        if p is None or p["clase"] != "oferta":
            raise OrdenRechazada("Las partidas nuevas se toman de una oferta leída.")
        if p["estado"] not in ESTADOS_FIABLES:
            raise OrdenRechazada(
                "Esa línea de la oferta está «a revisar»: compruébala y confírmala antes de "
                "usar su precio."
            )
        if p["precio"] is None:
            raise OrdenRechazada("Esa línea de la oferta no tiene precio: no se puede usar.")
        if con.execute(
            "SELECT 1 FROM cambio_modificado WHERE modificado_id = ? AND tipo = 'nueva'"
            " AND partida_id = ?",
            (self.modificado_id, self.partida_id),
        ).fetchone():
            raise OrdenRechazada("Esa línea de la oferta ya está añadida a este modificado.")
        return [_fila_cambio(self, "nueva", cantidad, justificacion, con)]


def _fila_cambio(
    orden, tipo: str, cantidad: float, justificacion: str, con: sqlite3.Connection
) -> Delta:
    return Delta(
        "cambio_modificado",
        None,
        {
            "id": orden.id,
            "modificado_id": orden.modificado_id,
            "orden": _siguiente_orden(con, orden.modificado_id),
            "tipo": tipo,
            "partida_id": orden.partida_id,
            "cantidad": cantidad,
            "motivo": orden.motivo,
            "justificacion": justificacion,
            "creado": ahora(),
        },
    )


@dataclass
class QuitarCambio(Orden):
    cambio_id: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        antes = leer(con, "cambio_modificado", {"id": self.cambio_id})
        if antes is None:
            raise OrdenRechazada("Ese cambio no existe.")
        return [Delta("cambio_modificado", antes, None)]


@dataclass
class BorrarModificado(Orden):
    modificado_id: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        mod = _modificado(con, self.modificado_id)
        cambios = [
            dict(r)
            for r in con.execute(
                "SELECT * FROM cambio_modificado WHERE modificado_id = ? ORDER BY orden",
                (self.modificado_id,),
            )
        ]
        return [Delta("cambio_modificado", c, None) for c in cambios] + [
            Delta("modificado", mod, None)
        ]
