"""Facturas desde el listado que exporta el ERP del usuario (docs/modules/obra.md, bloque 4b).

Usuario (10-11-2026): «Facturas las exporto de mi ERP y te las subo»; «lo que yo te pase, sea
lo que sea, te valga». Sin plantilla fija, como las certificaciones (io/certificacion_excel):

1. **Columnas por sus títulos** (`mapas`): proveedor, nº de factura, fecha, base imponible,
   total, cuota de IVA, retención, obra o centro de coste y concepto. Cada título vale para
   un solo dato, y entre varias columnas que valen para el mismo, gana la de título más
   específico («Fecha factura» antes que «Fecha»; revisión 10-11-2026). Si dos columnas de
   importe empatan («Base 1», «Base 2»: varios tipos de IVA), no se elige ninguna. Si no se
   reconocen, Claude Code dice qué columna es qué (solo letras; `mapa_de_ia` lo comprueba,
   y una columna cuyo título es de otro importe se rechaza).
2. **Cifras de las celdas** (`leer`). El coste de una factura es su **base imponible** (sin
   IVA, como el resto del coste de la obra). Sin columna de base: total − cuota de IVA
   ± retención (con el signo del total: un abono resta), y se comprueba que la cuota y la
   retención cuadran con un tipo legal (`TIPOS_IVA`, `TIPOS_RETENCION`): si no, es que la
   columna es el porcentaje y no el importe, y la factura no se importa (se dice).
3. Lo que no se importa se lista con el motivo. Una factura en varias líneas (una por tipo
   de IVA) se suma; una línea repetida igual no.

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
VERSION = "1.1.0"

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
IMPORTES = ("base", "total", "cuota_iva", "retencion")
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

#: Tipos de IVA en España (%): general 21, reducido 10, superreducido 4 (Ley 37/1992 del
#: IVA, arts. 90 y 91), 5 (tipo temporal de algunos productos, RDL 20/2022) y 0 (exentas,
#: e inversión del sujeto pasivo en obra, art. 84.Uno.2.f). Sin los tipos con recargo de
#: equivalencia: es régimen del comercio minorista (art. 154), no de una instaladora; y
#: 26,2 y 11,4 coinciden con 21/79 y 10/90, lo que dejaba pasar un «Total neto» tomado por
#: total con la base un 21 % corta (revisión 10-11-2026).
TIPOS_IVA = (0.0, 4.0, 5.0, 10.0, 21.0)
#: Retenciones de IRPF sobre facturas de proveedores (%): profesionales 15 y 7 (inicio de
#: actividad), arrendamientos 19, actividades en módulos 1, agrarias y forestales 2 (Ley
#: 35/2006 del IRPF y su Reglamento, RD 439/2007, arts. 95 y 101).
TIPOS_RETENCION = (1.0, 2.0, 7.0, 15.0, 19.0)
#: Margen para comparar un tipo calculado (cuota / base) con el legal: redondeos de céntimo
#: en facturas pequeñas.
MARGEN_TIPO = 0.6

#: Títulos por rol, normalizados (io/certificacion_excel.normalizar: «Nº» → «no»). Se
#: recorren en orden y se compara por «contiene» (palabra entera si es de una palabra). Un
#: título solo vale para el primer rol que encaja; dentro de cada rol, los sinónimos van del
#: más específico al más general (su posición puntúa cuando dos columnas encajan).
SINONIMOS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "retencion",
        ("importe retencion", "imp retencion", "cuota retencion", "retencion", "irpf", "ret"),
    ),  # fmt: skip
    ("cuota_iva", ("cuota iva", "importe iva", "iva importe", "total iva", "cuota", "iva")),
    (
        "base",
        (
            "base imponible",
            "importe sin iva",
            "sin iva",
            "importe neto",
            "base",
            "bi",
            "neto",
            "subtotal",
        ),
    ),  # fmt: skip
    (
        "total",
        (
            "total factura",
            "importe total",
            "total con iva",
            "total fra",
            "total",
            "liquido",
            "a pagar",
        ),
    ),  # fmt: skip
    (
        "fecha",
        (
            "fecha factura",
            "fecha fra",
            "fecha emision",
            "fecha expedicion",
            "f factura",
            "f fra",
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
            "num fra",
            "numero fra",
            "su factura",
            "su no",
            "no documento",
            "numero documento",
            "factura",
            "fra",
            "documento",
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
    """Exclusiones: un «% IVA», un «tipo», una «clave» o un «código» de IVA no son la cuota;
    «base IVA» o «importe sin IVA» no es la cuota; una fecha de vencimiento, de pago o
    contable no es la de la factura; un «tipo» o «estado» de factura no es su número."""
    if rol in IMPORTES and (
        _tiene(t, ("%", "tipo", "porcentaje", "cod", "codigo", "clave", "pct")) or "% " in t
    ):
        return False
    con_iva = "con iva" in t or "iva incl" in t
    if rol == "retencion" and _tiene(t, ("base", "garantia")):
        # «Base retención» es una base; la retención de garantía (5-10 % en subcontratas)
        # se descuenta del pago, no es IRPF ni cambia el coste.
        return False
    if rol == "cuota_iva" and (_tiene(t, ("base", "sin")) or con_iva):
        return False  # «Total IVA» sí es la cuota; «Total con IVA», no
    if rol == "total" and (_tiene(t, ("neto",)) or (_tiene(t, ("iva",)) and not con_iva)):
        return False  # «Total neto» es la base
    if rol == "base" and (
        _tiene(t, ("pagar", "liquido", "cuota", "retencion"))
        or (_tiene(t, ("total",)) and not _tiene(t, ("neto",)))
    ):
        return False  # «Neto a pagar» es lo que se paga; «Total neto» sí es la base
    if rol == "proveedor" and _tiene(t, ("cod", "codigo", "nif", "cif", "obra", "proyecto")):
        return False  # «Cód. proveedor», «Nombre obra»
    if rol == "fecha" and _tiene(t, ("vencimiento", "vto", "pago", "contable", "registro",
                                     "contabilizacion", "entrada", "recepcion")):  # fmt: skip
        return False
    return not (
        rol == "numero"
        and _tiene(t, ("fecha", "total", "importe", "base", "tipo", "estado", "clase", "serie"))
    )


def _puntuacion(rol: str, t: str) -> int | None:
    """Posición del sinónimo más específico que encaja (0 = el más específico), o None."""
    if not _vale_para(rol, t):
        return None
    for i, s in enumerate(dict(SINONIMOS)[rol]):
        if s == t or (" " in s and s in t) or _tiene(t, (s,)):
            return i
    return None


def rol_por_titulo(t: str) -> tuple[str, int] | None:
    """El primer rol cuyo sinónimo encaja con el título normalizado, y su puntuación."""
    for rol, _s in SINONIMOS:
        p = _puntuacion(rol, t)
        if p is not None:
            return rol, p
    return None


class FacturasNoReconocidas(ValueError):
    pass


@dataclass
class Mapa:
    hoja: str
    fila_titulos: int
    columnas: dict[str, str]
    origen: str  # «títulos» o «IA»
    titulos: dict[str, str] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)

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
    base_calculada: bool  # True: total − IVA ± retención (no había columna de base)
    lineas: int = 1  # una factura en varias líneas (una por tipo de IVA) se suma


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

    @property
    def sin_obra(self) -> int:
        """Facturas sin obra en un listado que sí tiene columna de obra."""
        return sum(1 for f in self.facturas if not f.obra) if "obra" in self.mapa.columnas else 0


def _libros(ruta: Path):
    try:
        return hoja_calculo.abrir(ruta)
    except Exception as exc:  # noqa: BLE001
        raise FacturasNoReconocidas(f"No se puede abrir «{ruta.name}»: {exc}") from exc


def _numero(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    return float(v) if isinstance(v, int | float) else None


def _mapa_de_fila(ws, r: int) -> Mapa:
    candidatos: dict[str, list[tuple[int, int, str]]] = {}
    for c in range(1, min(ws.max_column, 60) + 1):
        valor = ws.cell(r, c).value
        if not isinstance(valor, str):
            continue
        encaje = rol_por_titulo(normalizar(valor))
        if encaje:
            candidatos.setdefault(encaje[0], []).append((encaje[1], c, valor.strip()))
    columnas, titulos, avisos = {}, {}, []
    for rol, lista in candidatos.items():
        lista.sort()
        mejores = [x for x in lista if x[0] == lista[0][0]]
        if len(mejores) > 1 and rol in IMPORTES:
            # «Base 1», «Base 2»: elegir una dejaría el coste corto. Ninguna.
            avisos.append(
                f"Hay varias columnas de {NOMBRES_ROL[rol]} ("
                + ", ".join(f"«{t}»" for _p, _c, t in mejores)
                + "), p. ej. una por tipo de IVA: exporta el listado con el total de cada "
                "factura en una sola columna."
            )
            continue
        _p, c, t = lista[0]
        columnas[rol], titulos[rol] = get_column_letter(c), t
    return Mapa(ws.title, r, columnas, "títulos", titulos, avisos)


def mapas(ruta: Path) -> list[Mapa]:
    """Columnas por sus títulos: el mejor mapa completo de cada hoja. Si una hoja tiene una
    fila de títulos que sería completa salvo por columnas de importe repetidas, se dice."""
    wv, _ = _libros(Path(ruta))
    salida = []
    for ws in wv.worksheets:
        mejor: Mapa | None = None
        incompleto_por_repetidas: Mapa | None = None
        for r in range(1, min(ws.max_row, 40) + 1):
            m = _mapa_de_fila(ws, r)
            if m.completo():
                if mejor is None or len(m.columnas) > len(mejor.columnas):
                    mejor = m
            elif m.avisos and incompleto_por_repetidas is None:
                incompleto_por_repetidas = m
        if mejor is not None:
            salida.append(mejor)
        elif incompleto_por_repetidas is not None:
            raise FacturasNoReconocidas(incompleto_por_repetidas.avisos[0])
    return salida


def volcado_titulos(ruta: Path, filas: int = 25) -> str:
    from traza.io.certificacion_excel import volcado_titulos as volcado

    return volcado(ruta, filas)


def mapa_de_ia(ruta: Path, propuesta: dict[str, Any]) -> Mapa:
    """Lo que propone la IA, comprobado contra el fichero (ADR-0013): hoja y fila existen;
    cada columna tiene título y vale para su dato; **un título que por sí solo es de otro
    dato** («Total con IVA» propuesto como base) se rechaza; dos datos no comparten columna;
    una columna de importe tiene números debajo y la de fecha, fechas. Lo que no cuadra se
    descarta (no se adivina)."""
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
        if titulo in (None, "") or c in usadas:
            continue
        t = normalizar(titulo)
        propio = rol_por_titulo(t)
        if not _vale_para(rol, t) or (propio is not None and propio[0] != rol):
            continue
        debajo = [ws.cell(r, c).value for r in range(fila + 1, ws.max_row + 1)]
        if rol in IMPORTES and not any(_numero(v) is not None for v in debajo):
            continue
        if rol == "fecha" and not any(
            isinstance(v, datetime | date)
            or (isinstance(v, str) and hoja_calculo.fecha_de_texto(v))
            for v in debajo
        ):
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
    if isinstance(v, str):
        f = hoja_calculo.fecha_de_texto(v)
        return f.date().isoformat() if f else None
    return None


def _tipo_legal(parte: float, base: float, tipos: tuple[float, ...]) -> bool:
    if base == 0:
        return parte == 0
    tipo = abs(100 * parte / base)
    return any(abs(tipo - t) <= MARGEN_TIPO for t in tipos)


def _es_fila_de_total(proveedor: str, numero: str, concepto: str) -> bool:
    """«Total», «Suma», «Totales» como palabra entera y sin nº de factura: una factura
    siempre tiene número («Totalenergies» o «Sumasa» son proveedores; revisión 10-11-2026)."""
    if numero:
        return False
    for texto in (proveedor, concepto):
        palabras = normalizar(texto).split()
        if palabras and palabras[0] in ("total", "totales", "suma", "sumas", "subtotal"):
            return True
    return False


def leer(ruta: Path, mapa: Mapa) -> Leido:
    wv, _ = _libros(Path(ruta))
    ws = wv[mapa.hoja]
    col = {rol: column_index_from_string(letra) for rol, letra in mapa.columnas.items()}

    def valor(r: int, rol: str) -> Any:
        return ws.cell(r, col[rol]).value if rol in col else None

    leido = Leido(mapa, [], avisos=list(mapa.avisos))
    calculadas = 0
    por_clave: dict[tuple[str, str, str], int] = {}  # (proveedor, nº, fecha) → índice
    lineas_vistas: set[tuple] = set()
    for r in range(mapa.fila_titulos + 1, ws.max_row + 1):
        proveedor = _texto(valor(r, "proveedor"))
        numero = _texto(valor(r, "numero"))
        concepto = _texto(valor(r, "concepto"))
        base = _numero(valor(r, "base"))
        total, cuota = _numero(valor(r, "total")), _numero(valor(r, "cuota_iva"))
        retencion = _numero(valor(r, "retencion"))
        if not any((proveedor, numero, base, total)):
            continue  # fila vacía
        if _es_fila_de_total(proveedor, numero, concepto):
            leido.descartadas.append((r, "fila de total del listado"))
            continue
        calculada = False
        if base is None and total is not None and cuota is not None:
            # La retención (IRPF) se resta de lo que se paga, no del coste; en un abono,
            # con su signo (revisión 10-11-2026: −106 + 21 + 15 daba −70 y no −100).
            signo = -1.0 if total < 0 else 1.0
            base, calculada = total - cuota + signo * abs(retencion or 0.0), True
            # Una columna «IVA» o «IRPF» con 21 o 15 es el porcentaje, no el importe.
            if not _tipo_legal(cuota, base, TIPOS_IVA) or (
                retencion and not _tipo_legal(retencion, base, TIPOS_RETENCION)
            ):
                leido.descartadas.append(
                    (
                        r,
                        "la cuota de IVA o la retención no cuadra con un tipo legal (¿es la "
                        "columna del %?, ¿varios tipos o suplidos en la misma línea?): "
                        "apúntala a mano",
                    )
                )
                continue
        elif base is not None and total is not None and cuota is not None:
            esperado = base + cuota - abs(retencion or 0.0) * (1 if base >= 0 else -1)
            if (
                round(abs(esperado - total), 2) > 0.01
                and round(abs(base + cuota - total), 2) > 0.01
            ):
                leido.avisos.append(
                    f"Fila {r}: base + IVA − retención no da el total; se toma la base."
                )
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
        linea = (normalizar(proveedor), normalizar(numero), fecha, importe, cuota, total)
        if linea in lineas_vistas:
            leido.descartadas.append((r, "línea repetida igual que otra: no se suma dos veces"))
            continue
        lineas_vistas.add(linea)
        calculadas += calculada
        clave = (normalizar(proveedor), normalizar(numero), fecha)
        obra = _texto(valor(r, "obra"))
        if clave in por_clave:
            # La misma factura en varias líneas (una por tipo de IVA): se suma.
            i = por_clave[clave]
            previa = leido.facturas[i]
            leido.facturas[i] = FacturaLeida(
                previa.fila,
                previa.proveedor,
                previa.numero,
                previa.fecha,
                round(previa.importe + importe, 2),
                previa.obra or obra,
                previa.concepto or concepto,
                previa.base_calculada or calculada,
                previa.lineas + 1,
            )
            continue
        por_clave[clave] = len(leido.facturas)
        leido.facturas.append(
            FacturaLeida(r, proveedor, numero, fecha, importe, obra, concepto, calculada)
        )
    if calculadas:
        leido.avisos.append(
            f"Sin columna de base imponible: la de {calculadas} factura(s) es el total menos "
            "la cuota de IVA" + (" más la retención." if "retencion" in col else ".")
        )
    varias = [f for f in leido.facturas if f.lineas > 1]
    if varias:
        leido.avisos.append(
            f"{len(varias)} factura(s) en varias líneas (p. ej. una por tipo de IVA): se suman "
            "sus bases (" + ", ".join(f"{f.proveedor} {f.numero}" for f in varias[:5]) + ")."
        )
    if leido.descartadas:
        leido.avisos.append(
            f"{len(leido.descartadas)} fila(s) no se importan: "
            + "; ".join(f"fila {n}, {m}" for n, m in leido.descartadas[:8])
            + ("…" if len(leido.descartadas) > 8 else "")
        )
    if not leido.facturas:
        raise FacturasNoReconocidas(
            "No hay ninguna factura con proveedor, nº, fecha e importe."
            + (" " + leido.avisos[-1] if leido.descartadas else "")
        )
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
