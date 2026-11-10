"""Facturas desde el listado que exporta el ERP del usuario (docs/modules/obra.md, bloque 4b).

Usuario (10-11-2026): «Facturas las exporto de mi ERP y te las subo»; «lo que yo te pase, sea
lo que sea, te valga». Sin plantilla fija, como las certificaciones (io/certificacion_excel):

1. **Columnas por sus títulos** (`mapas`): proveedor, nº de factura, fecha, base imponible,
   total, cuota de IVA, retención, obra o centro de coste y concepto. Lo específico antes
   que lo general («fecha factura» es la fecha, no el número). Si no se reconocen, Claude
   Code dice qué columna es qué (solo letras; `mapa_de_ia` lo comprueba con las mismas
   reglas).
2. **Cifras de las celdas** (`leer`). El coste de una factura es su **base imponible** (sin
   IVA, como el resto del coste de la obra). Sin columna de base: total − cuota de IVA
   (+ retención, que se resta del total pero no es menos coste), y se dice. Una fila sin
   proveedor, número, fecha o importe no se importa: se lista con el motivo.

Qué facturas son nuevas y a qué paquete van lo decide quien llama (app/obra.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl.utils import column_index_from_string, get_column_letter

from traza.io import hoja_calculo
from traza.io.certificacion_excel import _tiene, normalizar

LECTOR = "facturas_erp"
VERSION = "1.0.0"

ROLES = (
    "proveedor",
    "numero",
    "fecha",
    "base",
    "total",
    "cuota_iva",
    "retencion",
    "obra",
    "concepto",
)
NOMBRES_ROL = {
    "proveedor": "proveedor",
    "numero": "nº de factura",
    "fecha": "fecha",
    "base": "base imponible",
    "total": "total",
    "cuota_iva": "cuota de IVA",
    "retencion": "retención",
    "obra": "obra o centro de coste",
    "concepto": "concepto",
}
#: Títulos por rol, normalizados (io/certificacion_excel.normalizar: «Nº» → «no»). Se
#: recorren en orden y se compara por «contiene» (palabra entera si es de una palabra): lo
#: específico antes que lo general. Un título solo vale para un rol.
SINONIMOS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("retencion", ("retencion", "irpf", "ret")),
    ("cuota_iva", ("cuota iva", "importe iva", "iva importe", "cuota", "iva")),
    (
        "base",
        (
            "base imponible",
            "base",
            "importe neto",
            "neto",
            "importe sin iva",
            "sin iva",
            "subtotal",
        ),
    ),  # fmt: skip
    ("total", ("total factura", "importe total", "total", "liquido", "a pagar")),
    (
        "fecha",
        (
            "fecha factura",
            "fecha fra",
            "fecha emision",
            "fecha expedicion",
            "f factura",
            "fecha documento",
            "fecha",
        ),
    ),  # fmt: skip
    (
        "numero",
        (
            "no factura",
            "numero factura",
            "num factura",
            "n factura",
            "no fra",
            "numero fra",
            "factura",
            "fra",
            "no documento",
            "numero documento",
            "documento",
            "su factura",
            "referencia",
            "ref",
        ),
    ),  # fmt: skip
    (
        "proveedor",
        (
            "razon social",
            "nombre proveedor",
            "proveedor",
            "acreedor",
            "tercero",
            "emisor",
            "nombre",
        ),
    ),  # fmt: skip
    ("obra", ("centro de coste", "centro coste", "proyecto", "obra", "cc")),
    ("concepto", ("concepto", "descripcion", "observaciones", "detalle", "texto")),
)


def _vale_para(rol: str, t: str) -> bool:
    """Un «% IVA» o un «tipo de IVA» no es la cuota; «base IVA» o «importe sin IVA» no es
    la cuota; una fecha de vencimiento, de pago o contable no es la de la factura."""
    if rol in ("cuota_iva", "retencion", "base", "total") and (
        _tiene(t, ("%", "tipo", "porcentaje")) or "% " in t
    ):
        return False
    con_iva = "con iva" in t or "iva incl" in t
    if rol == "cuota_iva" and (_tiene(t, ("base", "sin")) or con_iva):
        return False  # «Total IVA» sí es la cuota; «Total con IVA», no
    if rol == "total" and _tiene(t, ("iva",)) and not con_iva:
        return False
    if rol == "base" and _tiene(t, ("pagar", "liquido")):
        return False  # «Neto a pagar» es lo que se paga (con IVA y retención)
    if rol == "proveedor" and _tiene(t, ("cod", "codigo", "nif", "cif", "obra", "proyecto")):
        return False  # «Cód. proveedor», «Nombre obra»
    if rol == "fecha" and _tiene(t, ("vencimiento", "vto", "pago", "contable", "registro",
                                     "contabilizacion", "entrada")):  # fmt: skip
        return False
    return not (rol == "numero" and _tiene(t, ("fecha", "total", "importe", "base")))


class FacturasNoReconocidas(ValueError):
    pass


@dataclass
class Mapa:
    hoja: str
    fila_titulos: int
    columnas: dict[str, str]
    origen: str  # «títulos» o «IA»
    titulos: dict[str, str] = field(default_factory=dict)

    def completo(self) -> bool:
        c = set(self.columnas)
        return {"proveedor", "numero", "fecha"} <= c and (
            "base" in c or {"total", "cuota_iva"} <= c
        )


@dataclass(frozen=True)
class FacturaLeida:
    fila: int
    proveedor: str
    numero: str
    fecha: str  # AAAA-MM-DD
    importe: float  # base imponible, al céntimo
    obra: str
    concepto: str
    base_calculada: bool  # True: total − IVA (+ retención), no había columna de base


@dataclass
class Leido:
    mapa: Mapa
    facturas: list[FacturaLeida]
    descartadas: list[tuple[int, str]] = field(default_factory=list)  # (fila, motivo)
    avisos: list[str] = field(default_factory=list)

    @property
    def obras(self) -> list[str]:
        """Valores distintos de la columna de obra (si la hay), en orden de aparición."""
        return list(dict.fromkeys(f.obra for f in self.facturas if f.obra))


def _libros(ruta: Path):
    try:
        return hoja_calculo.abrir(ruta)
    except Exception as exc:  # noqa: BLE001
        raise FacturasNoReconocidas(f"No se puede abrir «{ruta.name}»: {exc}") from exc


def _numero(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    return float(v) if isinstance(v, int | float) else None


def _titulo_vale(rol: str, t: str, sinonimos: tuple[str, ...]) -> bool:
    if not _vale_para(rol, t):
        return False
    return any(s == t or (" " in s and s in t) or _tiene(t, (s,)) for s in sinonimos)


def mapas(ruta: Path) -> list[Mapa]:
    """Columnas por sus títulos: el mejor mapa completo de cada hoja."""
    wv, _ = _libros(Path(ruta))
    salida = []
    for ws in wv.worksheets:
        mejor: Mapa | None = None
        for r in range(1, min(ws.max_row, 40) + 1):
            columnas: dict[str, str] = {}
            titulos: dict[str, str] = {}
            for c in range(1, min(ws.max_column, 60) + 1):
                valor = ws.cell(r, c).value
                if not isinstance(valor, str):
                    continue
                t = normalizar(valor)
                for rol, sinonimos in SINONIMOS:
                    if rol not in columnas and _titulo_vale(rol, t, sinonimos):
                        columnas[rol] = get_column_letter(c)
                        titulos[rol] = valor.strip()
                        break
            m = Mapa(ws.title, r, columnas, "títulos", titulos)
            if m.completo() and (mejor is None or len(columnas) > len(mejor.columnas)):
                mejor = m
        if mejor is not None:
            salida.append(mejor)
    return salida


def volcado_titulos(ruta: Path, filas: int = 25) -> str:
    from traza.io.certificacion_excel import volcado_titulos as volcado

    return volcado(ruta, filas)


def mapa_de_ia(ruta: Path, propuesta: dict[str, Any]) -> Mapa:
    """Lo que propone la IA, comprobado contra el fichero con las mismas reglas que los
    títulos (ADR-0013): hoja y fila existen; cada columna tiene título y vale para su dato;
    dos datos no comparten columna; una columna de importe tiene números debajo y la de
    fecha, fechas. Lo que no cuadra se descarta."""
    wv, _ = _libros(Path(ruta))
    if propuesta.get("hoja") not in wv.sheetnames:
        raise FacturasNoReconocidas(f"La hoja «{propuesta.get('hoja')}» no está en el fichero.")
    ws = wv[propuesta["hoja"]]
    fila = int(propuesta.get("fila_titulos") or 0)
    if not 1 <= fila <= ws.max_row:
        raise FacturasNoReconocidas("La fila de títulos propuesta no existe.")
    columnas, titulos = {}, {}
    usadas: set[int] = set()
    for rol, letra in (propuesta.get("columnas") or {}).items():
        if rol not in ROLES or not letra:
            continue
        try:
            c = column_index_from_string(str(letra).strip().upper())
        except ValueError:
            continue
        titulo = ws.cell(fila, c).value
        if titulo in (None, "") or c in usadas or not _vale_para(rol, normalizar(titulo)):
            continue
        debajo = [ws.cell(r, c).value for r in range(fila + 1, ws.max_row + 1)]
        if rol in ("base", "total", "cuota_iva", "retencion") and not any(
            _numero(v) is not None for v in debajo
        ):
            continue
        if rol == "fecha" and not any(isinstance(v, datetime | date) for v in debajo):
            continue
        usadas.add(c)
        columnas[rol], titulos[rol] = get_column_letter(c), str(titulo).strip()
    m = Mapa(ws.title, fila, columnas, "IA", titulos)
    if not m.completo():
        raise FacturasNoReconocidas(
            "No se ha podido saber qué columnas tienen el proveedor, el nº de factura, la "
            "fecha y la base imponible (o el total y la cuota de IVA)."
        )
    return m


def _texto(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)  # nº de factura guardado como número: «123», no «123.0»
    return " ".join(str(v).split())


def _fecha(v: Any) -> str | None:
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return None


def leer(ruta: Path, mapa: Mapa) -> Leido:
    wv, _ = _libros(Path(ruta))
    ws = wv[mapa.hoja]
    col = {rol: column_index_from_string(letra) for rol, letra in mapa.columnas.items()}

    def valor(r: int, rol: str) -> Any:
        return ws.cell(r, col[rol]).value if rol in col else None

    leido = Leido(mapa, [])
    calculadas = 0
    for r in range(mapa.fila_titulos + 1, ws.max_row + 1):
        proveedor = _texto(valor(r, "proveedor"))
        numero = _texto(valor(r, "numero"))
        base = _numero(valor(r, "base"))
        total, cuota = _numero(valor(r, "total")), _numero(valor(r, "cuota_iva"))
        retencion = _numero(valor(r, "retencion")) or 0.0
        if not any((proveedor, numero, base, total)):
            continue  # fila vacía
        if normalizar(proveedor).startswith(("total", "suma")) or (
            not numero and normalizar(_texto(valor(r, "concepto"))).startswith("total")
        ):
            continue  # fila de total del listado
        calculada = False
        if base is None and total is not None and cuota is not None:
            # La retención (IRPF) se resta del total a pagar, no del coste.
            base, calculada = total - cuota + abs(retencion), True
        fecha = _fecha(valor(r, "fecha"))
        falta = [
            n
            for n, v in (
                ("proveedor", proveedor),
                ("nº de factura", numero),
                ("fecha", fecha),
                ("importe", base),
            )
            if v in (None, "")
        ]
        if falta:
            leido.descartadas.append((r, "falta " + ", ".join(falta)))
            continue
        importe = round(base, 2)
        if importe == 0:
            leido.descartadas.append((r, "importe 0"))
            continue
        calculadas += calculada
        leido.facturas.append(
            FacturaLeida(
                r,
                proveedor,
                numero,
                fecha,
                importe,
                _texto(valor(r, "obra")),
                _texto(valor(r, "concepto")),
                calculada,
            )
        )
    if calculadas:
        leido.avisos.append(
            f"Sin columna de base imponible: la de {calculadas} factura(s) es el total menos "
            "la cuota de IVA" + (" más la retención." if "retencion" in col else ".")
        )
    if leido.descartadas:
        leido.avisos.append(
            f"{len(leido.descartadas)} fila(s) no se importan: "
            + "; ".join(f"fila {n}, {m}" for n, m in leido.descartadas[:8])
            + ("…" if len(leido.descartadas) > 8 else "")
        )
    if not leido.facturas:
        raise FacturasNoReconocidas("No hay ninguna factura con proveedor, nº, fecha e importe.")
    return leido


def descripcion(mapa: Mapa) -> str:
    return (
        "; ".join(
            f"{NOMBRES_ROL[r]} en {mapa.columnas[r]} («{mapa.titulos.get(r, '')}»)"
            for r in ROLES
            if r in mapa.columnas
        )
        + f" (hoja «{mapa.hoja}», títulos en la fila {mapa.fila_titulos})."
    )
