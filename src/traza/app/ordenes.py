"""Órdenes: la ÚNICA vía para modificar el modelo (ADR-0010, línea roja 8).

Una orden no escribe: lee el estado y devuelve los `Delta` que quiere aplicar.
`Proyecto.ejecutar` los aplica en una transacción, comprueba el bloqueo de lo aprobado,
los anota en el registro de cambios y los apila para deshacer. Por eso ninguna orden
puede saltarse ni el registro ni el bloqueo.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from traza.core.estados import Estado, transicion_permitida
from traza.core.geometria import MOTOR as MOTOR_GEOMETRIA
from traza.core.geometria import VERSION as VERSION_GEOMETRIA
from traza.core.geometria import Contorno, ContornoInvalido, Vertice, mismo_contorno
from traza.core.procedencia import Origen, Procedencia
from traza.core.tipos import TIPOS_DE_PLANO, Clase, tipo, validar_valor
from traza.io.pdf import pagina_citada
from traza.persistence.filas import Delta, Fila, leer
from traza.rules import cerramientos, ventilacion
from traza.rules.usos import POR_CLAVE


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
        if t.nombre in TIPOS_DE_PLANO:
            raise OrdenRechazada(
                f"Los elementos de tipo «{t.etiqueta}» se crean desde el paso «Planos», con su "
                "geometría."
            )
        if self.padre_id is not None:
            padre = _elemento(con, self.padre_id)
            if padre["tipo"] in TIPOS_DE_PLANO:
                raise OrdenRechazada(
                    "Un equipo no cuelga de un nivel, espacio u obstáculo en esta versión."
                )
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
        _no_es_calculo(antes)
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
        _no_es_calculo(antes)
        return [Delta("propiedad", antes, None)]


def _no_es_calculo(fila: Fila | None) -> None:
    """Un resultado de cálculo no se pisa ni se borra a mano: dejaría el valor sin su
    registro, o con uno que ya no lo explica (revisión 07-11-2026: la superficie de un
    espacio, calculada de su contorno, se podía sustituir por otra cifra)."""
    if fila is not None and fila["origen"] == Origen.CALCULO:
        raise OrdenRechazada(
            f"«{fila['clave']}» es un resultado de cálculo: cambia sus datos de partida (p. ej. "
            "el contorno) y se recalcula."
        )


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

#: Tipos de encargo (decisión del usuario, 09-11-2026; docs/modules/flujo.md). Sustituyen a
#: «diseño + presupuesto + instalación», «presupuesto + instalación» y «solo instalación»;
#: la migración V10 pasa los dos últimos a «oferta».
ENCARGOS = {
    "diseno": "Diseño (plano del cliente)",
    "oferta": "Oferta de un proyecto ajeno",
    "ampliacion": "Ampliación de una instalación existente",
    # Obra (09-11-2026, docs/modules/obra.md): control de venta, coste, certificaciones y
    # previsión. Nace desde cero o pasando una Oferta a Obra (cambiar el tipo de encargo).
    "obra": "Obra (venta, costes y certificaciones)",
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


@dataclass
class FijarVentaContratada(Orden):
    """La medición leída que es el presupuesto contratado de la obra (docs/modules/obra.md,
    «Venta»). Sale de Presto (BC3 o Excel) o del PDF del cliente."""

    medicion_id: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        if leer(con, "medicion", {"id": self.medicion_id}) is None:
            raise OrdenRechazada("Esa medición no está leída en el proyecto.")
        antes = leer(con, "meta", {"clave": "venta_medicion"})
        despues = {"clave": "venta_medicion", "valor": self.medicion_id}
        if antes == despues:
            raise OrdenRechazada("Ya es el presupuesto contratado.")
        return [Delta("meta", antes, despues)]


@dataclass
class QuitarVentaContratada(Orden):
    """Deja la obra sin presupuesto contratado (p. ej. para volver a leer su documento)."""

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        antes = leer(con, "meta", {"clave": "venta_medicion"})
        if antes is None:
            raise OrdenRechazada("La obra no tiene presupuesto contratado.")
        return [Delta("meta", antes, None)]


@dataclass
class ImportarCosteObjetivo(Orden):
    """El coste objetivo de la obra, leído del Excel de Presto del usuario (io/coste_presto).
    Uno por obra: importar otro (la versión nueva del Excel) sustituye al anterior, y se
    puede deshacer."""

    documento_id: str
    hoja: str
    paquetes: list[str]
    partidas: list[dict[str, Any]]
    avisos: list[str]
    lector: str
    version_lector: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        doc = leer(con, "documento", {"id": self.documento_id})
        if doc is None:
            raise OrdenRechazada("El documento no está incorporado al proyecto.")
        if not self.partidas:
            raise OrdenRechazada("El coste objetivo no tiene ninguna partida.")
        antes = leer(con, "coste_objetivo", {"id": 1})
        despues = {
            "id": 1,
            "documento_id": self.documento_id,
            "hoja": self.hoja,
            "paquetes": json.dumps(self.paquetes, ensure_ascii=False),
            "partidas": json.dumps(self.partidas, ensure_ascii=False),
            "avisos": json.dumps(self.avisos, ensure_ascii=False),
            "lector": self.lector,
            "version_lector": self.version_lector,
            "leido": ahora(),
        }
        return [Delta("coste_objetivo", antes, despues)]


def _paquetes(con: sqlite3.Connection) -> list[str]:
    fila = leer(con, "coste_objetivo", {"id": 1})
    if fila is None:
        raise OrdenRechazada(
            "Importa antes el coste objetivo: las facturas se apuntan a sus paquetes."
        )
    return json.loads(fila["paquetes"])


def _fecha(texto: str) -> str:
    """AAAA-MM-DD (la interfaz la escribe así)."""
    try:
        return datetime.strptime(texto.strip(), "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise OrdenRechazada(f"Fecha no válida: «{texto}» (AAAA-MM-DD).") from None


@dataclass
class RegistrarFactura(Orden):
    """Una factura de un paquete de coste (docs/modules/obra.md, «Coste real»). Importe sin
    IVA; negativo si es un abono. Con `id` de una existente, la corrige."""

    paquete: str
    proveedor: str
    numero: str
    fecha: str
    importe: float
    documento_id: str | None = None
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        if self.paquete not in _paquetes(con):
            raise OrdenRechazada(f"«{self.paquete}» no es un paquete del coste objetivo.")
        if leer(con, "paquete_cerrado", {"paquete": self.paquete}) is not None:
            raise OrdenRechazada(
                f"El paquete «{self.paquete}» está cerrado: reábrelo antes de apuntarle facturas."
            )
        proveedor, numero = self.proveedor.strip(), self.numero.strip()
        if not proveedor or not numero:
            raise OrdenRechazada("La factura necesita proveedor y número.")
        if isinstance(self.importe, bool) or not isinstance(self.importe, int | float):
            raise OrdenRechazada("El importe tiene que ser un número.")
        # Al céntimo, como la venta y el coste objetivo (revisión 09-11-2026).
        importe = round(float(self.importe), 2) if math.isfinite(self.importe) else 0.0
        if importe == 0:
            raise OrdenRechazada("El importe no puede ser 0 (un abono va en negativo).")
        if self.documento_id and leer(con, "documento", {"id": self.documento_id}) is None:
            raise OrdenRechazada("El documento de la factura no está incorporado.")
        # El mismo proveedor y número aunque cambien mayúsculas o espacios: «ACME» y «Acme»
        # contarían dos veces la misma factura (revisión 09-11-2026).
        clave = (" ".join(proveedor.split()).casefold(), " ".join(numero.split()).casefold())
        otra = next(
            (
                r[0]
                for r in con.execute(
                    "SELECT id, proveedor, numero FROM factura WHERE id <> ?", (self.id,)
                )
                if (" ".join(r[1].split()).casefold(), " ".join(r[2].split()).casefold()) == clave
            ),
            None,
        )
        if otra:
            raise OrdenRechazada(f"Ya está apuntada la factura {numero} de {proveedor}.")
        antes = leer(con, "factura", {"id": self.id})
        despues = {
            "id": self.id,
            "paquete": self.paquete,
            "proveedor": proveedor,
            "numero": numero,
            "fecha": _fecha(self.fecha),
            "importe": importe,
            "documento_id": self.documento_id,
            "creado": antes["creado"] if antes else ahora(),
        }
        if antes is not None:
            if leer(con, "paquete_cerrado", {"paquete": antes["paquete"]}) is not None:
                raise OrdenRechazada(
                    f"La factura es del paquete cerrado «{antes['paquete']}»: reábrelo antes."
                )
            if antes == despues:
                raise OrdenRechazada("No hay cambios en la factura.")
        return [Delta("factura", antes, despues)]


@dataclass
class ImportarFacturas(Orden):
    """Varias facturas de una vez, del listado del ERP (docs/modules/obra.md, bloque 4b):
    las mismas reglas que una a una (RegistrarFactura) y, además, ninguna repetida dentro
    del listado. Deshacer las quita todas."""

    facturas: list[dict[str, Any]]  # paquete, proveedor, numero, fecha, importe
    documento_id: str | None = None

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        if not self.facturas:
            raise OrdenRechazada("No hay ninguna factura que importar.")
        vistas: set[tuple[str, str]] = set()
        deltas: list[Delta] = []
        for f in self.facturas:
            clave = (
                " ".join(str(f["proveedor"]).split()).casefold(),
                " ".join(str(f["numero"]).split()).casefold(),
            )
            if clave in vistas:
                raise OrdenRechazada(
                    f"La factura {f['numero']} de {f['proveedor']} está dos veces en el listado."
                )
            vistas.add(clave)
            try:
                deltas += RegistrarFactura(
                    paquete=f["paquete"],
                    proveedor=f["proveedor"],
                    numero=f["numero"],
                    fecha=f["fecha"],
                    importe=f["importe"],
                    documento_id=self.documento_id,
                ).planificar(con)
            except OrdenRechazada as exc:
                raise OrdenRechazada(f"{f['proveedor']}, {f['numero']}: {exc}") from exc
        return deltas


@dataclass
class QuitarFactura(Orden):
    factura_id: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        f = leer(con, "factura", {"id": self.factura_id})
        if f is None:
            raise OrdenRechazada("Esa factura no existe.")
        if leer(con, "paquete_cerrado", {"paquete": f["paquete"]}) is not None:
            raise OrdenRechazada(f"El paquete «{f['paquete']}» está cerrado: reábrelo antes.")
        return [Delta("factura", f, None)]


@dataclass
class CerrarPaquete(Orden):
    """El paquete está liquidado: lo facturado es su coste final. Reabrir es otra orden
    (queda en el registro de cambios, línea roja 5)."""

    paquete: str
    cerrar: bool = True

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        antes = leer(con, "paquete_cerrado", {"paquete": self.paquete})
        if self.cerrar:
            if self.paquete not in _paquetes(con):
                raise OrdenRechazada(f"«{self.paquete}» no es un paquete del coste objetivo.")
            if antes is not None:
                raise OrdenRechazada("Ese paquete ya está cerrado.")
            return [Delta("paquete_cerrado", None, {"paquete": self.paquete, "fecha": ahora()})]
        if antes is None:
            raise OrdenRechazada("Ese paquete no está cerrado.")
        return [Delta("paquete_cerrado", antes, None)]


@dataclass
class FijarPrevision(Orden):
    """La previsión del usuario: dos totales a fin de obra (docs/modules/obra.md). TRAZA no
    la estima: la guarda tal cual, con su fecha."""

    coste_total: float
    venta_total: float
    nota: str = ""

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        for nombre, v in (("coste", self.coste_total), ("venta", self.venta_total)):
            if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
                raise OrdenRechazada(f"La {nombre} prevista tiene que ser un número.")
            if v < 0:
                raise OrdenRechazada(f"La {nombre} prevista no puede ser negativa.")
        antes = leer(con, "prevision", {"id": 1})
        despues = {
            "id": 1,
            "coste_total": float(self.coste_total),
            "venta_total": float(self.venta_total),
            "nota": self.nota.strip() or None,
            "fecha": ahora(),
        }
        if antes is not None and {**antes, "fecha": None} == {**despues, "fecha": None}:
            raise OrdenRechazada("La previsión no cambia.")
        return [Delta("prevision", antes, despues)]


@dataclass
class ImportarCertificacion(Orden):
    """Una certificación (la hace el usuario; TRAZA la registra): importe a origen por
    partida de la venta, leído de su Excel (io/certificacion_excel + app/obra)."""

    numero: int
    fecha: str
    documento_id: str
    partidas: dict[str, list[Any]]  # clave → [código, resumen, importe a origen]
    total_origen: float
    mapa: dict[str, Any]
    avisos: list[str]
    lector: str
    version_lector: str
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        if leer(con, "documento", {"id": self.documento_id}) is None:
            raise OrdenRechazada("El documento no está incorporado al proyecto.")
        if isinstance(self.numero, bool) or not isinstance(self.numero, int) or self.numero < 1:
            raise OrdenRechazada("El número de certificación es un entero desde 1.")
        if con.execute("SELECT 1 FROM certificacion WHERE numero = ?", (self.numero,)).fetchone():
            raise OrdenRechazada(f"Ya hay una certificación nº {self.numero}.")
        if not self.partidas:
            raise OrdenRechazada("La certificación no tiene ninguna partida de la venta.")
        return [
            Delta(
                "certificacion",
                None,
                {
                    "id": self.id,
                    "numero": self.numero,
                    "fecha": _fecha(self.fecha),
                    "documento_id": self.documento_id,
                    "total_origen": round(float(self.total_origen), 2),
                    "partidas": json.dumps(self.partidas, ensure_ascii=False),
                    "mapa": json.dumps(self.mapa, ensure_ascii=False),
                    "avisos": json.dumps(self.avisos, ensure_ascii=False),
                    "lector": self.lector,
                    "version_lector": self.version_lector,
                    "leido": ahora(),
                },
            )
        ]


@dataclass
class QuitarCertificacion(Orden):
    certificacion_id: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        c = leer(con, "certificacion", {"id": self.certificacion_id})
        if c is None:
            raise OrdenRechazada("Esa certificación no existe.")
        return [Delta("certificacion", c, None)]


def _importe_futurible(nombre: str, valor) -> float:
    if isinstance(valor, bool) or not isinstance(valor, int | float) or not math.isfinite(valor):
        raise OrdenRechazada(f"{nombre} tiene que ser un número.")
    # Al céntimo, como el resto de importes de la obra. Puede ser negativo: un modificado
    # o una oferta pueden quitar alcance (y coste).
    return round(float(valor), 2)


@dataclass
class GuardarFuturible(Orden):
    """Una oferta o un modificado pendiente de aprobar (docs/modules/obra.md, bloque 3),
    con su venta y su coste estimado. La venta, o la escribe el usuario, o es la de un
    modificado de TRAZA sobre el presupuesto contratado (se calcula siempre al día). El
    coste lo estima el usuario: TRAZA no lo inventa. Con `id` de uno existente, lo corrige
    (conserva si está marcado)."""

    titulo: str
    coste: float
    venta: float | None = None
    modificado_id: str | None = None
    nota: str | None = ""
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        titulo = " ".join(self.titulo.split())
        if not titulo:
            raise OrdenRechazada("El futurible necesita un título.")
        if (self.venta is None) == (self.modificado_id is None):
            raise OrdenRechazada(
                "La venta del futurible, o la escribes tú, o es la de un modificado: una de "
                "las dos."
            )
        coste = _importe_futurible("El coste estimado", self.coste)
        venta = None if self.venta is None else _importe_futurible("La venta", self.venta)
        if self.modificado_id is not None:
            mod = leer(con, "modificado", {"id": self.modificado_id})
            if mod is None:
                raise OrdenRechazada("Ese modificado no existe.")
            contratada = leer(con, "meta", {"clave": "venta_medicion"})
            if contratada is None or contratada["valor"] != mod["medicion_id"]:
                raise OrdenRechazada(
                    f"El modificado «{mod['titulo']}» no es del presupuesto contratado: su "
                    "venta no es una ampliación de esta obra."
                )
            otro = con.execute(
                "SELECT titulo FROM futurible WHERE modificado_id = ? AND id <> ?",
                (self.modificado_id, self.id),
            ).fetchone()
            if otro:
                raise OrdenRechazada(
                    f"El modificado «{mod['titulo']}» ya es el futurible «{otro['titulo']}»."
                )
        antes = leer(con, "futurible", {"id": self.id})
        despues = {
            "id": self.id,
            "titulo": titulo,
            "modificado_id": self.modificado_id,
            "venta": venta,
            "coste": coste,
            "marcado": antes["marcado"] if antes else 0,
            "nota": (self.nota or "").strip() or None,
            "creado": antes["creado"] if antes else ahora(),
        }
        if antes == despues:
            raise OrdenRechazada("No hay cambios en el futurible.")
        return [Delta("futurible", antes, despues)]


@dataclass
class MarcarFuturible(Orden):
    """Sí/no: entra o no en el escenario «con futuribles» (decisión del usuario: sin
    probabilidades)."""

    futurible_id: str
    marcado: bool

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        antes = leer(con, "futurible", {"id": self.futurible_id})
        if antes is None:
            raise OrdenRechazada("Ese futurible no existe.")
        valor = 1 if self.marcado else 0
        if antes["marcado"] == valor:
            raise OrdenRechazada(
                "Ya está en el escenario." if valor else "Ya está fuera del escenario."
            )
        return [Delta("futurible", antes, {**antes, "marcado": valor})]


@dataclass
class QuitarFuturible(Orden):
    """Aprobado (pasa a tu previsión) o descartado: se quita de la lista."""

    futurible_id: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        f = leer(con, "futurible", {"id": self.futurible_id})
        if f is None:
            raise OrdenRechazada("Ese futurible no existe.")
        return [Delta("futurible", f, None)]


#: Los pasos que pueden quedar desactualizados (app/flujo.DEPENDE; un test lo vigila).
PASOS_CON_DEPENDENCIAS = ("cargas", "redes", "hidronica", "subcuadros")


@dataclass
class DarPorRevisado(Orden):
    """El usuario ha revisado un paso que estaba desactualizado (docs/modules/flujo.md)."""

    paso: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        if self.paso not in PASOS_CON_DEPENDENCIAS:
            raise OrdenRechazada("Ese paso no depende de otros: no hay nada que revisar.")
        # La marca es el último número del registro de cambios en el momento de revisar:
        # lo anterior queda revisado. Se guarda en la tabla (no se lee del registro)
        # porque el registro solo crece y deshacer la revisión también escribe en él.
        ultimo = con.execute("SELECT COALESCE(MAX(n), 0) FROM cambio").fetchone()[0]
        antes = leer(con, "paso_revisado", {"paso": self.paso})
        return [Delta("paso_revisado", antes, {"paso": self.paso, "marca": str(ultimo)})]


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
        venta = leer(con, "meta", {"clave": "venta_medicion"})
        if venta is not None and venta["valor"] == self.medicion_id:
            raise OrdenRechazada(
                "Es el presupuesto contratado de la obra: quítalo antes como contratado "
                "(«Obra → Quitar presupuesto contratado») o elige otro."
            )
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
    if abs(round(cantidad, 6) - cantidad) > 1e-12:
        # El BC3 se escribe con 6 decimales: con más, el fichero diría otra cantidad (y una
        # cantidad diminuta se escribiría 0, que en BC3 es «anulada», pág. 2).
        raise OrdenRechazada("La cantidad admite como máximo 6 decimales.")
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
        # El número no se reutiliza nunca: se cuenta también lo que hubo y se borró (el
        # registro de cambios lo guarda). Un «nº 2» ya exportado y borrado no puede volver a
        # ser otro «nº 2» distinto (revisión 06-11-2026).
        numero = con.execute(
            "SELECT coalesce(max(n), 0) + 1 FROM ("
            " SELECT numero AS n FROM modificado WHERE medicion_id = :m"
            " UNION ALL"
            " SELECT json_extract(antes, '$.numero') FROM cambio"
            "  WHERE entidad = 'modificado' AND json_extract(antes, '$.medicion_id') = :m"
            " UNION ALL"
            " SELECT json_extract(despues, '$.numero') FROM cambio"
            "  WHERE entidad = 'modificado' AND json_extract(despues, '$.medicion_id') = :m)",
            {"m": self.medicion_id},
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
        mod = _modificado(con, self.modificado_id)
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
        if p["medicion_id"] == mod["medicion_id"]:
            # Si la base es una oferta, sus propias líneas ya están en el presupuesto: se
            # varían, no se añaden como nuevas.
            raise OrdenRechazada(
                "Esa línea es de la propia base del modificado: cambia su cantidad en lugar "
                "de añadirla como nueva."
            )
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
        futurible = con.execute(
            "SELECT titulo FROM futurible WHERE modificado_id = ?", (self.modificado_id,)
        ).fetchone()
        if futurible:
            # Su venta sale de este modificado: sin él, el futurible no tendría venta.
            raise OrdenRechazada(
                f"No se puede borrar: es el futurible «{futurible['titulo']}» de la obra. "
                "Quita antes el futurible."
            )
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


# --- Planos: niveles, espacios y obstáculos (Etapa 3, ADR-0014) --------------------------

UNIDADES_PLANO = ("mm", "cm", "dm", "m")
#: Prefijo y ancho del código visible de cada tipo de elemento de plano.
_CODIGOS = {"nivel": ("NIV-", 2), "espacio": ("ESP-", 3), "obstaculo": ("OBS-", 3)}


def _siguiente_codigo(con: sqlite3.Connection, tipo_elemento: str) -> str:
    prefijo, ancho = _CODIGOS[tipo_elemento]
    usados = {
        r[0]
        for r in con.execute("SELECT codigo FROM elemento WHERE codigo LIKE ?", (prefijo + "%",))
    }
    n = 1
    while f"{prefijo}{n:0{ancho}d}" in usados:
        n += 1
    return f"{prefijo}{n:0{ancho}d}"


def _plano(con: sqlite3.Connection, plano_id: str) -> Fila:
    p = leer(con, "plano", {"id": plano_id})
    if p is None:
        raise OrdenRechazada("Ese plano no está leído en el proyecto.")
    if p["sustituido_por"]:
        raise OrdenRechazada("Ese plano está sustituido por su versión revisada.")
    return p


def _capas(nombres: list[str] | tuple[str, ...]) -> list[str]:
    if any(not isinstance(c, str) or not c.strip() for c in nombres):
        raise OrdenRechazada("Hay una capa sin nombre.")
    limpias = sorted(c.strip() for c in nombres)
    # AutoCAD no distingue mayúsculas en los nombres de capa.
    if len({c.casefold() for c in limpias}) != len(limpias):
        raise OrdenRechazada("Una capa aparece repetida.")
    return limpias


def _filas_plano(unidad, espacios, obstaculos, textos) -> tuple[list[str], list[str], list[str]]:
    if unidad not in UNIDADES_PLANO:
        raise OrdenRechazada(f"Unidad del dibujo no prevista: «{unidad}».")
    e, o, t = _capas(espacios), _capas(obstaculos), _capas(textos)
    if not e and not o:
        raise OrdenRechazada("Elige al menos una capa de espacios o de obstáculos.")
    comunes = {c.casefold() for c in e} & {c.casefold() for c in o}
    if comunes:
        raise OrdenRechazada(
            f"La capa «{sorted(comunes)[0]}» no puede ser a la vez de espacios y de obstáculos."
        )
    return e, o, t


@dataclass
class LeerPlano(Orden):
    """El usuario dice cómo se lee un DXF del proyecto: la unidad (confirmada viendo la
    medida total) y qué capas son espacios, obstáculos y nombres (planos ajenos)."""

    documento_id: str
    unidad: str
    capas_espacios: list[str]
    capas_obstaculos: list[str]
    capas_textos: list[str]
    lector: str
    version_lector: str
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        doc = leer(con, "documento", {"id": self.documento_id})
        if doc is None:
            raise OrdenRechazada("El documento no está incorporado al proyecto.")
        if doc["extension"].lower() != ".dxf":
            raise OrdenRechazada(f"«{doc['nombre_original']}» no es un DXF.")
        if con.execute(
            "SELECT 1 FROM plano WHERE documento_id = ?", (self.documento_id,)
        ).fetchone():
            raise OrdenRechazada(
                f"«{doc['nombre_original']}» ya está leído: cambia sus capas en lugar de leerlo "
                "otra vez."
            )
        e, o, t = _filas_plano(
            self.unidad,
            self.capas_espacios,
            self.capas_obstaculos,
            self.capas_textos,
        )
        return [
            Delta(
                "plano",
                None,
                {
                    "id": self.id,
                    "documento_id": self.documento_id,
                    "unidad": self.unidad,
                    "capas_espacios": json.dumps(e, ensure_ascii=False),
                    "capas_obstaculos": json.dumps(o, ensure_ascii=False),
                    "capas_textos": json.dumps(t, ensure_ascii=False),
                    "descartados": "[]",
                    "lector": self.lector,
                    "version_lector": self.version_lector,
                    "leido": ahora(),
                    # Todas las columnas: deshacer compara la fila entera (V10).
                    "sustituido_por": None,
                },
            )
        ]


@dataclass
class CambiarPlano(Orden):
    """Cambia la unidad o las capas. La unidad no se cambia si ya hay geometría confirmada
    con ella: sus superficies quedarían mal (habría que quitarla y confirmarla otra vez)."""

    plano_id: str
    unidad: str
    capas_espacios: list[str]
    capas_obstaculos: list[str]
    capas_textos: list[str]

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        antes = _plano(con, self.plano_id)
        e, o, t = _filas_plano(
            self.unidad,
            self.capas_espacios,
            self.capas_obstaculos,
            self.capas_textos,
        )
        if self.unidad != antes["unidad"]:
            n = con.execute(
                "SELECT count(*) FROM geometria WHERE plano_id = ?", (self.plano_id,)
            ).fetchone()[0]
            if n:
                raise OrdenRechazada(
                    f"Hay {n} elemento(s) confirmados con la unidad «{antes['unidad']}»: quítalos "
                    "antes de cambiarla, o sus superficies no corresponderían al plano."
                )
        despues = {
            **antes,
            "unidad": self.unidad,
            "capas_espacios": json.dumps(e, ensure_ascii=False),
            "capas_obstaculos": json.dumps(o, ensure_ascii=False),
            "capas_textos": json.dumps(t, ensure_ascii=False),
        }
        if despues == antes:
            raise OrdenRechazada("No hay cambios en el plano.")
        return [Delta("plano", antes, despues)]


@dataclass
class DescartarPropuesta(Orden):
    """El usuario rechaza un contorno propuesto: no se vuelve a proponer."""

    plano_id: str
    handle: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        antes = _plano(con, self.plano_id)
        descartados = json.loads(antes["descartados"])
        if self.handle in descartados:
            raise OrdenRechazada("Esa propuesta ya está descartada.")
        if con.execute(
            "SELECT 1 FROM geometria WHERE plano_id = ? AND handle = ?",
            (self.plano_id, self.handle),
        ).fetchone():
            raise OrdenRechazada("Ese contorno ya está confirmado: quita el elemento si sobra.")
        nuevos = sorted([*descartados, self.handle])
        return [Delta("plano", antes, {**antes, "descartados": json.dumps(nuevos)})]


@dataclass
class RecuperarPropuesta(Orden):
    plano_id: str
    handle: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        antes = _plano(con, self.plano_id)
        descartados = json.loads(antes["descartados"])
        if self.handle not in descartados:
            raise OrdenRechazada("Esa propuesta no está descartada.")
        nuevos = [h for h in descartados if h != self.handle]
        return [Delta("plano", antes, {**antes, "descartados": json.dumps(nuevos)})]


def _fila_propiedad(elemento_id: str, clave: str, valor, unidad, p: Procedencia) -> Fila:
    return {
        "elemento_id": elemento_id,
        "clave": clave,
        "valor": json.dumps(valor, ensure_ascii=False),
        "unidad": unidad,
        "origen": str(p.origen),
        "documento_id": p.documento_id,
        "localizador": p.localizador,
        "registro_calculo_id": p.registro_calculo_id,
        "nota": p.nota,
        "confirmado": 1,
        "modificado": ahora(),
    }


def _fila_elemento(elemento_id: str, tipo_elemento: str, codigo: str, padre_id) -> Fila:
    t = tipo(tipo_elemento)
    momento = ahora()
    return {
        "id": elemento_id,
        "codigo": codigo,
        "tipo": t.nombre,
        "tipo_version": t.version,
        "disciplina": str(t.disciplina),
        "estado": str(Estado.BORRADOR),
        "padre_id": padre_id,
        "creado": momento,
        "modificado": momento,
    }


def _numero_positivo(nombre: str, valor, admite_cero: bool = False) -> float:
    if isinstance(valor, bool) or not isinstance(valor, int | float) or valor != valor:
        raise OrdenRechazada(f"«{nombre}» tiene que ser un número.")
    if valor in (float("inf"), float("-inf")) or valor < 0 or (valor == 0 and not admite_cero):
        raise OrdenRechazada(f"«{nombre}» tiene que ser un número {'≥' if admite_cero else '>'} 0.")
    return float(valor)


@dataclass
class CrearNivel(Orden):
    # «titulo» y no «nombre»: `nombre` es la propiedad de Orden con que se anota la orden.
    titulo: str
    cota: float  # m
    altura_libre: float  # m
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        if not self.titulo.strip():
            raise OrdenRechazada("El nivel necesita un nombre (p. ej. «Planta baja»).")
        if isinstance(self.cota, bool) or not isinstance(self.cota, int | float):
            raise OrdenRechazada("La cota tiene que ser un número.")
        if not math.isfinite(self.cota):
            raise OrdenRechazada("La cota tiene que ser un número finito.")
        altura = _numero_positivo("Altura libre", self.altura_libre)
        usuario = Procedencia(Origen.USUARIO)
        return [
            Delta(
                "elemento",
                None,
                _fila_elemento(self.id, "nivel", _siguiente_codigo(con, "nivel"), None),
            ),
            Delta(
                "propiedad",
                None,
                _fila_propiedad(self.id, "nombre", self.titulo.strip(), None, usuario),
            ),
            Delta(
                "propiedad", None, _fila_propiedad(self.id, "cota", float(self.cota), "m", usuario)
            ),
            Delta(
                "propiedad", None, _fila_propiedad(self.id, "altura_libre", altura, "m", usuario)
            ),
        ]


@dataclass
class ConfirmarContorno(Orden):
    """El usuario confirma un contorno propuesto como ESPACIO u OBSTÁCULO de un nivel.

    La geometría viene del DXF (la lee Proyecto) en metros, con la unidad del plano. La
    superficie y el perímetro los calcula aquí el motor de geometría exacta y quedan con
    origen «cálculo» y su registro (motor, versión, entradas y fórmula). El nombre, si sale
    de un texto del plano, cita ese texto; si lo escribe el usuario, es suyo.
    """

    tipo_elemento: str  # espacio | obstaculo
    plano_id: str
    handle: str
    capa: str
    nivel_id: str
    vertices: tuple[tuple[float, float, float], ...]  # (x, y, bulge) en metros
    titulo: str | None = None  # el nombre del elemento (ver CrearNivel)
    nombre_procedencia: Procedencia | None = None
    altura: float | None = None  # obstáculo: si no consta, toda la del nivel
    cota_inferior: float | None = None  # obstáculo: sobre el suelo del nivel
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        if self.tipo_elemento not in ("espacio", "obstaculo"):
            raise OrdenRechazada(f"Tipo de contorno no previsto: «{self.tipo_elemento}».")
        plano = _plano(con, self.plano_id)
        nivel = _elemento(con, self.nivel_id)
        if nivel["tipo"] != "nivel":
            raise OrdenRechazada("Los espacios y obstáculos cuelgan de un nivel.")
        if self.handle in json.loads(plano["descartados"]):
            raise OrdenRechazada("Ese contorno está descartado: recupéralo antes de confirmarlo.")
        if con.execute(
            "SELECT 1 FROM geometria WHERE plano_id = ? AND handle = ?",
            (self.plano_id, self.handle),
        ).fetchone():
            raise OrdenRechazada("Ese contorno ya está confirmado.")
        try:
            contorno = Contorno(tuple(Vertice(x, y, b) for x, y, b in self.vertices))
        except (ContornoInvalido, TypeError, ValueError) as exc:
            raise OrdenRechazada(f"Contorno no válido: {exc}") from None
        if contorno.autointersecante():
            raise OrdenRechazada(
                "Ese contorno se corta a sí mismo: su superficie no tiene sentido físico. "
                "Corrígelo en el plano (o dibuja el contorno bueno en otra polilínea)."
            )
        doc = leer(con, "documento", {"id": plano["documento_id"]})
        assert doc is not None
        registro = _registro_contorno(doc["sha256"], plano, self.handle, contorno)
        cita = Procedencia(Origen.CALCULO, registro_calculo_id=registro["id"])
        codigo = _siguiente_codigo(con, self.tipo_elemento)
        deltas = [
            Delta("registro_calculo", None, registro),
            Delta(
                "elemento", None, _fila_elemento(self.id, self.tipo_elemento, codigo, self.nivel_id)
            ),
            Delta(
                "geometria",
                None,
                {
                    "elemento_id": self.id,
                    "plano_id": self.plano_id,
                    "handle": self.handle,
                    "capa": self.capa,
                    "contorno": json.dumps([[v.x, v.y, v.bulge] for v in contorno.vertices]),
                },
            ),
            Delta(
                "propiedad",
                None,
                _fila_propiedad(self.id, "superficie", contorno.area, "m**2", cita),
            ),
        ]
        if self.tipo_elemento == "espacio":
            deltas.append(
                Delta(
                    "propiedad",
                    None,
                    _fila_propiedad(self.id, "perimetro", contorno.perimetro, "m", cita),
                )
            )
        nombre = (self.titulo or "").strip()
        if self.tipo_elemento == "espacio" and not nombre:
            raise OrdenRechazada("El espacio necesita un nombre (el del plano o uno tuyo).")
        if nombre:
            p = self.nombre_procedencia or Procedencia(Origen.USUARIO)
            if p.origen not in (Origen.USUARIO, Origen.DOCUMENTO):
                raise OrdenRechazada("El nombre lo da el plano o el usuario.")
            if p.origen is Origen.DOCUMENTO and p.documento_id != plano["documento_id"]:
                raise OrdenRechazada("El nombre tiene que citar un texto de este mismo plano.")
            deltas.append(
                Delta("propiedad", None, _fila_propiedad(self.id, "nombre", nombre, None, p))
            )
        usuario = Procedencia(Origen.USUARIO)
        if self.altura is not None:
            if self.tipo_elemento != "obstaculo":
                raise OrdenRechazada(
                    "La altura de un espacio se pone después, si no es la del nivel."
                )
            h = _numero_positivo("Altura", self.altura)
            deltas.append(
                Delta("propiedad", None, _fila_propiedad(self.id, "altura", h, "m", usuario))
            )
        if self.cota_inferior is not None:
            if self.tipo_elemento != "obstaculo":
                raise OrdenRechazada("La cota inferior solo la tienen los obstáculos.")
            c = _numero_positivo("Cota inferior", self.cota_inferior, admite_cero=True)
            deltas.append(
                Delta("propiedad", None, _fila_propiedad(self.id, "cota_inferior", c, "m", usuario))
            )
        return deltas


def _registro_contorno(sha_documento: str, plano: Fila, handle: str, contorno: Contorno) -> Fila:
    entradas = {
        "documento_sha256": sha_documento,
        "handle": handle,
        "unidad_dibujo": plano["unidad"],
        "vertices_m": [[v.x, v.y, v.bulge] for v in contorno.vertices],
    }
    texto = json.dumps(entradas, sort_keys=True)
    contenido = {
        "metodo": (
            "Superficie: polígono de cuerdas (fórmula de Gauss) más segmentos circulares "
            "(c²/8)·(θ−sen θ)/sen²(θ/2), θ = 4·atan(bulge). Perímetro: cuerdas y arcos "
            "c·(|θ|/2)/sen(|θ|/2). Exactos, sin aproximar los arcos (core/geometria.py)."
        ),
        "fuente_bulge": (
            "Autodesk, DXF Reference (AutoCAD 2018), LWPOLYLINE y VERTEX, código 42; "
            "consultada el 06-11-2026 (docs/modules/geometria.md)"
        ),
        "aproximaciones": [],
        "entradas": entradas,
        "resultados": {"superficie_m2": contorno.area, "perimetro_m": contorno.perimetro},
    }
    return {
        "id": nuevo_id(),
        "motor": MOTOR_GEOMETRIA,
        "version": VERSION_GEOMETRIA,
        "fecha": ahora(),
        "hash_entradas": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
        "contenido": json.dumps(contenido, ensure_ascii=False, sort_keys=True),
        "obsoleto": 0,
    }


@dataclass
class QuitarDePlano(Orden):
    """Quita un nivel, espacio u obstáculo confirmado (para corregirlo y confirmarlo otra
    vez). Un nivel con espacios u obstáculos no se quita: primero ellos."""

    elemento_id: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        el = _elemento(con, self.elemento_id)
        if el["tipo"] not in ("nivel", "espacio", "obstaculo"):
            raise OrdenRechazada("Solo se quitan aquí niveles, espacios y obstáculos.")
        if el["estado"] == Estado.APROBADO:
            raise OrdenRechazada(
                f"«{el['codigo']}» está aprobado. Para quitarlo hay que reabrirlo indicando el "
                "motivo."
            )
        hijos = con.execute(
            "SELECT count(*) FROM elemento WHERE padre_id = ?", (self.elemento_id,)
        ).fetchone()[0]
        if hijos:
            raise OrdenRechazada(
                f"«{el['codigo']}» tiene {hijos} espacio(s) u obstáculo(s): quítalos antes."
            )
        redes = con.execute(
            "SELECT nombre FROM red_aire WHERE nivel_id = ?", (self.elemento_id,)
        ).fetchall()
        if redes:
            raise OrdenRechazada(
                f"«{el['codigo']}» lo usa la red de aire «{redes[0][0]}»: bórrala o cámbiala "
                "de nivel antes."
            )
        for tabla, que in (("decision", "decisiones registradas"), ("pendiente", "pendientes")):
            n = con.execute(
                f"SELECT count(*) FROM {tabla} WHERE elemento_id = ?", (self.elemento_id,)
            ).fetchone()[0]
            if n:
                raise OrdenRechazada(
                    f"«{el['codigo']}» tiene {n} {que}: forman parte de su historia y no se "
                    "borran. Corrígelo con sus propiedades en lugar de quitarlo."
                )
        props = [
            dict(r)
            for r in con.execute(
                "SELECT * FROM propiedad WHERE elemento_id = ? ORDER BY clave", (self.elemento_id,)
            )
        ]
        deltas = [Delta("propiedad", p, None) for p in props]
        cargas = leer(con, "cargas_espacio", {"elemento_id": self.elemento_id})
        if cargas is not None:
            deltas.append(Delta("cargas_espacio", cargas, None))
        geo = leer(con, "geometria", {"elemento_id": self.elemento_id})
        if geo is not None:
            deltas.append(Delta("geometria", geo, None))
        deltas.append(Delta("elemento", el, None))
        return deltas


@dataclass
class RevisarPlano(Orden):
    """Sustituye un plano por su versión revisada (docs/modules/flujo.md, 1c).

    Usuario (09-11-2026): «quiero poder yo proponer planos de ampliación o modificación y
    que se recalcule todo». El emparejamiento lo hace Proyecto con el DXF (app/planos.py);
    aquí se aplica de una vez: plano nuevo con las mismas capas, cada elemento a su
    contorno revisado (superficie y perímetro recalculados, con su registro), los que ya
    no están se quitan y las redes de aire pasan al plano nuevo. Lo que depende (cargas,
    redes, hidráulica, cuadros) se calcula siempre de lo guardado y queda marcado para
    revisar (app/flujo.py).
    """

    plano_id: str
    documento_id: str
    #: (elemento_id, handle, capa, vértices (x, y, bulge) en metros) en el plano revisado.
    parejas: tuple[tuple[str, str, str, tuple[tuple[float, float, float], ...]], ...]
    desaparecidos: tuple[str, ...]
    descartados: tuple[str, ...]  # los descartes del plano anterior que siguen estando
    lector: str
    version_lector: str
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        antes = _plano(con, self.plano_id)
        doc = leer(con, "documento", {"id": self.documento_id})
        if doc is None or doc["extension"].lower() != ".dxf":
            raise OrdenRechazada("El plano revisado tiene que ser un DXF incorporado.")
        if con.execute(
            "SELECT 1 FROM plano WHERE documento_id = ?", (self.documento_id,)
        ).fetchone():
            raise OrdenRechazada(f"«{doc['nombre_original']}» ya está leído como plano.")
        geos = {
            r["elemento_id"]: dict(r)
            for r in con.execute("SELECT * FROM geometria WHERE plano_id = ?", (self.plano_id,))
        }
        tratados = [p[0] for p in self.parejas] + list(self.desaparecidos)
        if sorted(tratados) != sorted(geos):
            raise OrdenRechazada(
                "La revisión no recoge todos los elementos del plano: vuelve a compararlo."
            )
        nuevo = {
            **antes,
            "id": self.id,
            "documento_id": self.documento_id,
            "descartados": json.dumps(sorted(self.descartados)),
            "lector": self.lector,
            "version_lector": self.version_lector,
            "leido": ahora(),
            "sustituido_por": None,
        }
        deltas = [
            Delta("plano", None, nuevo),
            Delta("plano", antes, {**antes, "sustituido_por": self.id}),
        ]
        for elemento_id, handle, capa, vertices in self.parejas:
            deltas += self._mover(con, nuevo, doc, geos[elemento_id], handle, capa, vertices)
        for elemento_id in self.desaparecidos:
            el = _elemento(con, elemento_id)
            nombre = leer(con, "propiedad", {"elemento_id": elemento_id, "clave": "nombre"})
            rotulo = f"{el['codigo']} {json.loads(nombre['valor']) if nombre else ''}".strip()
            try:
                deltas += QuitarDePlano(elemento_id).planificar(con)
            except OrdenRechazada as exc:
                raise OrdenRechazada(
                    f"«{rotulo}» ya no está en el plano revisado y no se puede quitar: {exc}"
                ) from None
        for r in con.execute("SELECT * FROM red_aire WHERE plano_id = ?", (self.plano_id,)):
            deltas.append(Delta("red_aire", dict(r), {**dict(r), "plano_id": self.id}))
        return deltas

    @staticmethod
    def _mover(con, plano: Fila, doc: Fila, geo: Fila, handle, capa, vertices) -> list[Delta]:
        try:
            contorno = Contorno(tuple(Vertice(x, y, b) for x, y, b in vertices))
        except (ContornoInvalido, TypeError, ValueError) as exc:
            raise OrdenRechazada(f"Contorno no válido: {exc}") from None
        elemento_id = geo["elemento_id"]
        el = _elemento(con, elemento_id)
        deltas = [
            Delta(
                "geometria",
                geo,
                {
                    **geo,
                    "plano_id": plano["id"],
                    "handle": handle,
                    "capa": capa,
                    "contorno": json.dumps([[v.x, v.y, v.bulge] for v in contorno.vertices]),
                },
            )
        ]
        props = {
            clave: leer(con, "propiedad", {"elemento_id": elemento_id, "clave": clave})
            for clave in ("superficie", "perimetro")
        }
        valores = {"superficie": (contorno.area, "m**2"), "perimetro": (contorno.perimetro, "m")}
        anterior = Contorno(tuple(Vertice(*v) for v in json.loads(geo["contorno"])))
        # Misma forma en el mismo sitio (a 1 mm): no se recalcula nada, y su registro sigue
        # explicando el valor. Un contorno movido o girado SÍ cambia aunque conserve
        # superficie y perímetro (revisión 09-11-2026). Mismo criterio que el resumen
        # (app/planos.Pareja.cambia).
        if mismo_contorno(anterior, contorno):
            return deltas
        if contorno.autointersecante():
            raise OrdenRechazada(
                f"«{el['codigo']}»: su contorno en el plano revisado se corta a sí mismo. "
                "Corrígelo en el plano."
            )
        if el["estado"] == Estado.APROBADO:
            raise OrdenRechazada(
                f"«{el['codigo']}» está aprobado y cambia en el plano revisado: reábrelo "
                "indicando el motivo antes de revisar el plano."
            )
        registro = _registro_contorno(doc["sha256"], plano, handle, contorno)
        cita = Procedencia(Origen.CALCULO, registro_calculo_id=registro["id"])
        deltas.append(Delta("registro_calculo", None, registro))
        viejos = {f["registro_calculo_id"] for f in props.values() if f is not None}
        for rid in sorted(r for r in viejos if r):
            reg = leer(con, "registro_calculo", {"id": rid})
            if reg is not None and not reg["obsoleto"]:
                deltas.append(Delta("registro_calculo", reg, {**reg, "obsoleto": 1}))
        for clave, fila in props.items():
            if fila is None:
                continue
            valor, unidad = valores[clave]
            deltas.append(
                Delta("propiedad", fila, _fila_propiedad(elemento_id, clave, valor, unidad, cita))
            )
        return deltas


#: Cómo se da la altura de un espacio (decisión del usuario, 06-11-2026).
MODOS_ALTURA = {
    "nivel": "La del nivel",
    "propia": "Altura propia",
    "inclinada": "Cubierta inclinada (mínima y máxima)",
}


@dataclass
class FijarAlturaEspacio(Orden):
    """Altura de un espacio en uno de tres modos, coherentes entre sí: la del nivel (sin
    valores propios), una altura propia, o mínima y máxima (cubierta inclinada). Cambiar de
    modo quita los valores del modo anterior: un espacio no puede tener a la vez altura
    propia e inclinada (revisión 07-11-2026)."""

    espacio_id: str
    modo: str
    altura: float | None = None
    minima: float | None = None
    maxima: float | None = None

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        el = _elemento(con, self.espacio_id)
        if el["tipo"] != "espacio":
            raise OrdenRechazada("La altura por modos es de los espacios.")
        if self.modo not in MODOS_ALTURA:
            raise OrdenRechazada(f"Modo de altura no previsto: «{self.modo}».")
        nuevos: dict[str, float] = {}
        if self.modo == "propia":
            nuevos["altura_libre"] = _numero_positivo("Altura", self.altura)
        elif self.modo == "inclinada":
            mi = _numero_positivo("Altura mínima", self.minima)
            ma = _numero_positivo("Altura máxima", self.maxima)
            if mi >= ma:
                raise OrdenRechazada(
                    "En cubierta inclinada la altura mínima tiene que ser menor que la máxima "
                    "(si son iguales, es una altura propia)."
                )
            nuevos = {"altura_minima": mi, "altura_maxima": ma}
        usuario = Procedencia(Origen.USUARIO)
        definicion = tipo("espacio")
        deltas = []
        for clave in ("altura_libre", "altura_minima", "altura_maxima"):
            antes = leer(con, "propiedad", {"elemento_id": self.espacio_id, "clave": clave})
            if clave in nuevos:
                try:
                    validar_valor(definicion.propiedad(clave), nuevos[clave], "m")
                except ValueError as exc:
                    raise OrdenRechazada(str(exc)) from None
                despues = _fila_propiedad(self.espacio_id, clave, nuevos[clave], "m", usuario)
                # Se omite solo si ya es el mismo valor, del usuario y confirmado: repetir el
                # valor de una propuesta de la IA la hace suya (revisión 07-11-2026).
                igual = (
                    antes is not None
                    and json.loads(antes["valor"]) == nuevos[clave]
                    and antes["origen"] == Origen.USUARIO
                    and antes["confirmado"] == 1
                    and antes["unidad"] == "m"
                )
                if not igual:
                    deltas.append(Delta("propiedad", antes, despues))
            elif antes is not None:
                deltas.append(Delta("propiedad", antes, None))
        return deltas


# --- Cargas y ventilación (Etapa 4, docs/modules/cargas.md) ---------------------------

#: Lo que el usuario puede cambiar de la propuesta del uso de un espacio: clave → (etiqueta,
#: admite negativo). Lo que no esté aquí sale del catálogo del uso.
AJUSTES_CARGAS = {
    "personas": ("Ocupación (personas)", False),
    "sensible_persona_w": ("Calor sensible por persona (W)", False),
    "latente_persona_w": ("Calor latente por persona (W)", False),
    "iluminacion_w_m2": ("Iluminación (W/m²)", False),
    "equipos_w_m2": ("Equipos (W/m²)", False),
    # Proceso con signo: un mueble frigorífico abierto resta carga.
    "proceso_sensible_w": ("Proceso, sensible (W)", True),
    "proceso_latente_w": ("Proceso, latente (W)", True),
    "t_invierno_c": ("Temperatura de invierno (°C)", True),
    "t_verano_c": ("Temperatura de verano (°C)", True),
    "aire_exterior_m3h": ("Aire exterior (m³/h)", False),
    "huecos": ("Huecos en fachada (fracción 0–1)", False),
}
#: Rangos físicos (los usan también los diálogos, para que no se pierda lo tecleado).
#: −60 °C cubre el ultracongelado y 60 °C cualquier local de proceso; España va del nivel
#: del mar a 3715 m (Teide).
RANGO_TEMPERATURA_C = (-60.0, 60.0)
RANGO_ALTITUD_M = (-100.0, 4000.0)
#: Sin calefacción (cámaras, almacenes sin calefactar): se marca aparte.
AJUSTE_SIN_CALEFACCION = "sin_calefaccion"
SECTORES_FACHADA = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")
COLORES = ("claro", "oscuro")


def _finito(nombre: str, valor) -> float:
    if isinstance(valor, bool) or not isinstance(valor, int | float) or not math.isfinite(valor):
        raise OrdenRechazada(f"«{nombre}» tiene que ser un número.")
    return float(valor)


@dataclass
class FijarCargasProyecto(Orden):
    """Clima y obra del proyecto: la guía del IDAE (documento del proyecto) y la página de
    su estación, provincia y altitud de la obra, y las hipótesis de conjunto. La guía la
    valida Proyecto antes (que la página sea de verdad una estación)."""

    guia_documento_id: str
    estacion_pagina: int
    provincia: str
    altitud_obra: float
    tipo_construccion: str
    norte: float = 0.0
    mes: int = 7
    color: str = "oscuro"
    recuperacion: float = 0.0

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        doc = leer(con, "documento", {"id": self.guia_documento_id})
        if doc is None or doc["paginas"] is None:
            raise OrdenRechazada("La guía del IDAE tiene que ser un PDF incorporado al proyecto.")
        if (
            isinstance(self.estacion_pagina, bool)
            or not 1 <= self.estacion_pagina <= doc["paginas"]
        ):
            raise OrdenRechazada("Esa página no existe en la guía.")
        try:
            cerramientos.zona_climatica(self.provincia, 0)
        except KeyError as exc:
            raise OrdenRechazada(str(exc).strip('"')) from None
        if self.tipo_construccion not in cerramientos.TIPOS:
            raise OrdenRechazada(f"Tipo de construcción no previsto: «{self.tipo_construccion}».")
        if self.mes not in range(1, 13) or isinstance(self.mes, bool):
            raise OrdenRechazada("El mes de proyecto va de 1 a 12.")
        if self.color not in COLORES:
            raise OrdenRechazada(f"Color de cerramientos no previsto: «{self.color}».")
        altitud = _finito("Altitud de la obra", self.altitud_obra)
        if not RANGO_ALTITUD_M[0] <= altitud <= RANGO_ALTITUD_M[1]:
            raise OrdenRechazada("La altitud de la obra tiene que estar entre −100 y 4000 m.")
        rec = _finito("Recuperador", self.recuperacion)
        if not 0 <= rec < 1:
            raise OrdenRechazada("La eficiencia del recuperador va de 0 a 1 (sin llegar a 1).")
        despues = {
            "id": 1,
            "guia_documento_id": self.guia_documento_id,
            "estacion_pagina": int(self.estacion_pagina),
            "provincia": self.provincia,
            "altitud_obra": altitud,
            "tipo_construccion": self.tipo_construccion,
            "norte": _finito("Norte del plano", self.norte) % 360.0,
            "mes": int(self.mes),
            "color": self.color,
            "recuperacion": rec,
        }
        antes = leer(con, "cargas_proyecto", {"id": 1})
        if antes == despues:
            raise OrdenRechazada("No hay cambios en los datos de cargas del proyecto.")
        return [Delta("cargas_proyecto", antes, despues)]


@dataclass
class FijarCargasEspacio(Orden):
    """Uso de un espacio, lo que el usuario cambia de su propuesta y sus correcciones de
    fachada por sector (True: es fachada aunque el plano no lo diga; False: no lo es)."""

    espacio_id: str
    uso: str
    ajustes: dict = field(default_factory=dict)
    fachadas: dict = field(default_factory=dict)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        el = _elemento(con, self.espacio_id)
        if el["tipo"] != "espacio":
            raise OrdenRechazada("Los datos de cargas son de los espacios.")
        if self.uso not in POR_CLAVE:
            raise OrdenRechazada(f"Uso no previsto: «{self.uso}».")
        ajustes: dict = {}
        for clave, valor in self.ajustes.items():
            if clave == AJUSTE_SIN_CALEFACCION:
                if not isinstance(valor, bool):
                    raise OrdenRechazada("«Sin calefacción» es sí o no.")
                if valor:
                    ajustes[clave] = True
                continue
            if clave not in AJUSTES_CARGAS:
                raise OrdenRechazada(f"Dato de cargas no previsto: «{clave}».")
            etiqueta, negativo = AJUSTES_CARGAS[clave]
            v = _finito(etiqueta, valor)
            if v < 0 and not negativo:
                raise OrdenRechazada(f"«{etiqueta}» no admite valores negativos.")
            if clave == "huecos" and v > 1:
                raise OrdenRechazada("Los huecos son una fracción de la fachada, de 0 a 1.")
            lo, hi = RANGO_TEMPERATURA_C
            if clave in ("t_invierno_c", "t_verano_c") and not lo <= v <= hi:
                # Un −300 °C tecleado de más rompía el cálculo de todo el proyecto (revisión
                # 07-11-2026).
                raise OrdenRechazada(f"«{etiqueta}» tiene que estar entre −60 y 60 °C.")
            ajustes[clave] = v
        if AJUSTE_SIN_CALEFACCION in ajustes and "t_invierno_c" in ajustes:
            raise OrdenRechazada("Un espacio sin calefacción no tiene temperatura de invierno.")
        fachadas = {}
        for s, v in self.fachadas.items():
            if s not in SECTORES_FACHADA or not isinstance(v, bool):
                raise OrdenRechazada(f"Corrección de fachada no válida: «{s}».")
            fachadas[s] = v
        despues = {
            "elemento_id": self.espacio_id,
            "uso": self.uso,
            "ajustes": json.dumps(ajustes, sort_keys=True, ensure_ascii=False),
            "fachadas": json.dumps(fachadas, sort_keys=True),
        }
        antes = leer(con, "cargas_espacio", {"elemento_id": self.espacio_id})
        if antes == despues:
            raise OrdenRechazada("No hay cambios en los datos de cargas del espacio.")
        return [Delta("cargas_espacio", antes, despues)]


# --- Redes de aire (Etapa 5, docs/modules/redes_aire.md) -------------------------------

TIPOS_RED = {"impulsion": "Impulsión", "retorno": "Retorno", "extraccion": "Extracción"}
FORMAS_CONDUCTO = ("rectangular", "circular")
#: Caudal de cada espacio (docs/modules/redes_aire.md, «Ventilación»).
CRITERIOS_CAUDAL = {
    "cargas": "De las cargas (aire exterior / carga sensible)",
    "volumen": "Renovaciones/h según volumen (S&P, tabla 3.6)",
    "renovaciones": "Renovaciones/h fijas",
}


@dataclass
class DefinirRed(Orden):
    """Crea una red de aire o cambia la que tiene `id`. La capa y los bloques los comprueba
    Proyecto contra el DXF antes (la orden no lee ficheros)."""

    titulo: str  # «titulo» y no «nombre» (ver CrearNivel)
    tipo: str
    plano_id: str
    capa_ejes: str
    bloques_terminales: list[str]
    bloque_equipo: str | None = None
    nivel_id: str | None = None
    climatizacion: bool = True
    friccion_objetivo: float = 0.8
    alto_maximo: float | None = 0.4
    forma: str = "rectangular"
    salto_impulsion: float = 10.0
    criterio_caudal: str = "cargas"
    renovaciones: float | None = None
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        titulo = self.titulo.strip()
        if not titulo:
            raise OrdenRechazada("La red necesita un nombre (p. ej. «Impulsión UTA-1»).")
        if self.criterio_caudal not in CRITERIOS_CAUDAL:
            raise OrdenRechazada(f"Criterio de caudal no previsto: «{self.criterio_caudal}».")
        renovaciones = None
        if self.criterio_caudal != "cargas":
            # Las renovaciones son de ventilación: el retorno sale de la impulsión, y la
            # impulsión de climatización, de la carga del local.
            if self.tipo == "retorno":
                raise OrdenRechazada("El retorno sale de la impulsión: su caudal es de las cargas.")
            if self.tipo == "impulsion" and self.climatizacion:
                raise OrdenRechazada(
                    "En climatización la impulsión sale de la carga del local; las "
                    "renovaciones por hora son para redes de ventilación."
                )
        if self.criterio_caudal == "renovaciones":
            if self.renovaciones is None:
                raise OrdenRechazada("Escribe las renovaciones por hora.")
            renovaciones = _finito("Renovaciones por hora", self.renovaciones)
            if not ventilacion.RENOVACIONES_MIN <= renovaciones <= ventilacion.RENOVACIONES_MAX:
                raise OrdenRechazada(
                    "Las renovaciones por hora van de 0,5 a 60 (tabla 3.5 del manual de S&P)."
                )
        if self.tipo not in TIPOS_RED:
            raise OrdenRechazada(f"Tipo de red no previsto: «{self.tipo}».")
        _plano(con, self.plano_id)
        if self.nivel_id is not None and _elemento(con, self.nivel_id)["tipo"] != "nivel":
            raise OrdenRechazada("La red se asocia a un nivel.")
        if not self.capa_ejes.strip():
            raise OrdenRechazada("Elige la capa de los ejes de conductos.")
        bloques = sorted({b.strip() for b in self.bloques_terminales if b and b.strip()})
        if not bloques:
            raise OrdenRechazada("Elige al menos un bloque de difusor o rejilla.")
        if self.forma not in FORMAS_CONDUCTO:
            raise OrdenRechazada(f"Forma de conducto no prevista: «{self.forma}».")
        r = _finito("Pérdida de carga objetivo", self.friccion_objetivo)
        if not 0.1 <= r <= 5:
            raise OrdenRechazada("La pérdida de carga objetivo va de 0,1 a 5 Pa/m.")
        alto = None
        if self.alto_maximo is not None:
            alto = _finito("Alto máximo", self.alto_maximo)
            if not 0.1 <= alto <= 3:
                raise OrdenRechazada("El alto máximo del conducto va de 0,1 a 3 m.")
        salto = _finito("Salto térmico de impulsión", self.salto_impulsion)
        if not 3 <= salto <= 20:
            raise OrdenRechazada("El salto térmico de impulsión va de 3 a 20 K.")
        otra = con.execute(
            "SELECT id FROM red_aire WHERE nombre = ? AND id <> ?", (titulo, self.id)
        ).fetchone()
        if otra:
            raise OrdenRechazada(f"Ya hay una red llamada «{titulo}».")
        antes = leer(con, "red_aire", {"id": self.id})
        despues = {
            "id": self.id,
            "nombre": titulo,
            "tipo": self.tipo,
            "plano_id": self.plano_id,
            "nivel_id": self.nivel_id,
            "capa_ejes": self.capa_ejes.strip(),
            "bloques_terminales": json.dumps(bloques, ensure_ascii=False),
            "bloque_equipo": (self.bloque_equipo or "").strip() or None,
            "climatizacion": 1 if self.climatizacion else 0,
            "friccion_objetivo": r,
            "alto_maximo": alto,
            "forma": self.forma,
            "salto_impulsion": salto,
            "criterio_caudal": self.criterio_caudal,
            "renovaciones": renovaciones,
            "creado": antes["creado"] if antes else ahora(),
        }
        if antes == despues:
            raise OrdenRechazada("No hay cambios en la red.")
        return [Delta("red_aire", antes, despues)]


TIPOS_SISTEMA = {"2_tubos": "2 tubos (frío / calor)", "4_tubos": "4 tubos (frío y calor)"}


@dataclass
class DefinirSistemaHidraulico(Orden):
    """Crea un sistema hidráulico o cambia el que tiene `id` (docs/modules/hidronica.md).
    `circuitos`: [{nombre, espacios: [id], unidades, longitud_m, perdida_terminal_kpa,
    exterior}]."""

    titulo: str
    tipo: str
    circuitos: list[dict]
    material: str = "acero"
    frio_impulsion: float = 7.0
    frio_retorno: float = 12.0
    calor_impulsion: float = 45.0
    calor_retorno: float = 40.0
    altura_m: float = 0.0
    longitud_primario_m: float = 10.0
    volumen_minimo_l_kw: float = 3.5
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        from traza.rules.hidraulica import MATERIALES

        titulo = self.titulo.strip()
        if not titulo:
            raise OrdenRechazada("El sistema necesita un nombre (p. ej. «Climatización planta 1»).")
        if self.tipo not in TIPOS_SISTEMA:
            raise OrdenRechazada(f"Tipo de sistema no previsto: «{self.tipo}».")
        if self.material not in MATERIALES:
            raise OrdenRechazada(f"Material no previsto: «{self.material}».")
        fi, fr = (
            _finito("Frío, impulsión", self.frio_impulsion),
            _finito("Frío, retorno", self.frio_retorno),
        )
        ci, cr = (
            _finito("Calor, impulsión", self.calor_impulsion),
            _finito("Calor, retorno", self.calor_retorno),
        )
        if not 1 <= fi < fr <= 25:
            raise OrdenRechazada("Frío: impulsión menor que retorno, entre 1 y 25 °C.")
        if not 25 <= cr < ci <= 90:
            raise OrdenRechazada("Calor: retorno menor que impulsión, entre 25 y 90 °C.")
        altura = _finito("Altura de la instalación", self.altura_m)
        primario = _finito("Longitud del primario", self.longitud_primario_m)
        minimo = _finito("Volumen mínimo", self.volumen_minimo_l_kw)
        if not 0 <= altura <= 100 or not 0 <= primario <= 500 or not 0 < minimo <= 50:
            raise OrdenRechazada("Altura 0–100 m, primario 0–500 m y volumen mínimo hasta 50 l/kW.")
        if not self.circuitos:
            raise OrdenRechazada("El sistema necesita al menos un circuito.")
        circuitos, nombres = [], set()
        de_quien: dict[str, str] = {}  # espacio → circuito: su carga no se suma dos veces
        for c in self.circuitos:
            nombre = str(c.get("nombre", "")).strip()
            if not nombre or nombre.casefold() in nombres:
                raise OrdenRechazada("Cada circuito necesita un nombre propio.")
            nombres.add(nombre.casefold())
            espacios = sorted(set(c.get("espacios") or []))
            if not espacios:
                raise OrdenRechazada(f"{nombre}: elige los espacios a los que da servicio.")
            for e in espacios:
                el = _elemento(con, e)
                if el["tipo"] != "espacio":
                    raise OrdenRechazada(f"{nombre}: «{e}» no es un espacio.")
                if e in de_quien:
                    raise OrdenRechazada(
                        f"El espacio {el['codigo']} está en «{de_quien[e]}» y en «{nombre}»: su "
                        "carga se sumaría dos veces."
                    )
                de_quien[e] = nombre
            unidades = c.get("unidades")
            if (
                isinstance(unidades, bool)
                or not isinstance(unidades, int)
                or not 1 <= unidades <= 500
            ):
                raise OrdenRechazada(f"{nombre}: las unidades van de 1 a 500.")
            longitud = _finito(f"{nombre}, longitud", c.get("longitud_m"))
            perdida = _finito(f"{nombre}, pérdida de la unidad", c.get("perdida_terminal_kpa"))
            if not 0 <= longitud <= 2000 or not 0 <= perdida <= 200:
                raise OrdenRechazada(f"{nombre}: longitud 0–2000 m y pérdida 0–200 kPa.")
            circuitos.append(
                {
                    "nombre": nombre,
                    "espacios": espacios,
                    "unidades": unidades,
                    "longitud_m": longitud,
                    "perdida_terminal_kpa": perdida,
                    "exterior": bool(c.get("exterior", False)),
                }
            )
        otro = con.execute(
            "SELECT id FROM sistema_hidraulico WHERE nombre = ? AND id <> ?", (titulo, self.id)
        ).fetchone()
        if otro:
            raise OrdenRechazada(f"Ya hay un sistema llamado «{titulo}».")
        antes = leer(con, "sistema_hidraulico", {"id": self.id})
        despues = {
            "id": self.id,
            "nombre": titulo,
            "tipo": self.tipo,
            "material": self.material,
            "frio_impulsion": fi,
            "frio_retorno": fr,
            "calor_impulsion": ci,
            "calor_retorno": cr,
            "altura_m": altura,
            "longitud_primario_m": primario,
            "volumen_minimo_l_kw": minimo,
            "circuitos": json.dumps(circuitos, ensure_ascii=False),
            "creado": antes["creado"] if antes else ahora(),
        }
        if antes == despues:
            raise OrdenRechazada("No hay cambios en el sistema.")
        return [Delta("sistema_hidraulico", antes, despues)]


@dataclass
class BorrarSistemaHidraulico(Orden):
    sistema_id: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        antes = leer(con, "sistema_hidraulico", {"id": self.sistema_id})
        if antes is None:
            raise OrdenRechazada("Ese sistema no existe.")
        return [Delta("sistema_hidraulico", antes, None)]


@dataclass
class DefinirSubcuadro(Orden):
    """Crea un subcuadro de clima o cambia el que tiene `id` (docs/modules/electricidad.md).
    `salidas`: [{nombre, potencia_kw, fases, longitud_m, motor, variador, cos_phi, metodo}]."""

    titulo: str
    salidas: list[dict]
    suministro: str = "compania"
    longitud_alimentacion_m: float = 20.0
    metodo_alimentacion: str = "E"
    id: str = field(default_factory=nuevo_id)

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        from traza.rules import electricidad as re

        titulo = self.titulo.strip()
        if not titulo:
            raise OrdenRechazada("El subcuadro necesita un nombre (p. ej. «SC Clima»).")
        if self.suministro not in re.SUMINISTROS:
            raise OrdenRechazada(f"Suministro no previsto: «{self.suministro}».")
        if self.metodo_alimentacion not in re.METODOS:
            raise OrdenRechazada("Método de instalación de la alimentación no previsto.")
        alim = _finito("Longitud de la alimentación", self.longitud_alimentacion_m)
        if not 0 < alim <= 1000:
            raise OrdenRechazada("La alimentación mide de 0 a 1.000 m.")
        if not self.salidas:
            raise OrdenRechazada("El subcuadro necesita al menos una salida.")
        salidas, nombres = [], set()
        for s in self.salidas:
            nombre = str(s.get("nombre", "")).strip()
            if not nombre or nombre.casefold() in nombres:
                raise OrdenRechazada("Cada salida necesita un nombre propio.")
            nombres.add(nombre.casefold())
            potencia = _finito(f"{nombre}, potencia", s.get("potencia_kw"))
            longitud = _finito(f"{nombre}, longitud", s.get("longitud_m"))
            cos_phi = _finito(f"{nombre}, cos φ", s.get("cos_phi", re.COS_PHI_DEFECTO))
            fases = s.get("fases")
            if fases not in (1, 3) or isinstance(fases, bool):
                raise OrdenRechazada(f"{nombre}: 1 o 3 fases.")
            if not 0 < potencia <= 1000:
                raise OrdenRechazada(
                    f"{nombre}: pon la potencia eléctrica de la ficha del equipo (0–1.000 kW)."
                )
            if not 0 < longitud <= 1000 or not 0.5 <= cos_phi <= 1:
                raise OrdenRechazada(f"{nombre}: longitud 0–1.000 m y cos φ 0,5–1.")
            metodo = s.get("metodo", "E")
            if metodo not in re.METODOS:
                raise OrdenRechazada(f"{nombre}: método de instalación no previsto.")
            salidas.append(
                {
                    "nombre": nombre,
                    "potencia_kw": potencia,
                    "fases": fases,
                    "longitud_m": longitud,
                    "motor": bool(s.get("motor", True)),
                    "variador": bool(s.get("variador", False)),
                    "cos_phi": cos_phi,
                    "metodo": metodo,
                }
            )
        otro = con.execute(
            "SELECT id FROM subcuadro WHERE nombre = ? AND id <> ?", (titulo, self.id)
        ).fetchone()
        if otro:
            raise OrdenRechazada(f"Ya hay un subcuadro llamado «{titulo}».")
        antes = leer(con, "subcuadro", {"id": self.id})
        despues = {
            "id": self.id,
            "nombre": titulo,
            "suministro": self.suministro,
            "longitud_alimentacion_m": alim,
            "metodo_alimentacion": self.metodo_alimentacion,
            "salidas": json.dumps(salidas, ensure_ascii=False),
            "creado": antes["creado"] if antes else ahora(),
        }
        if antes == despues:
            raise OrdenRechazada("No hay cambios en el subcuadro.")
        return [Delta("subcuadro", antes, despues)]


@dataclass
class BorrarSubcuadro(Orden):
    subcuadro_id: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        antes = leer(con, "subcuadro", {"id": self.subcuadro_id})
        if antes is None:
            raise OrdenRechazada("Ese subcuadro no existe.")
        return [Delta("subcuadro", antes, None)]


@dataclass
class BorrarRed(Orden):
    red_id: str

    def planificar(self, con: sqlite3.Connection) -> list[Delta]:
        antes = leer(con, "red_aire", {"id": self.red_id})
        if antes is None:
            raise OrdenRechazada("Esa red no existe.")
        return [Delta("red_aire", antes, None)]
