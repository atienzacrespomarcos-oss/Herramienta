"""Certificación de obra desde un Excel cualquiera (docs/modules/obra.md, bloque 2b).

Usuario (09-11-2026): «al final debes ser capaz de interpretar un Excel»; «yo puedo tener una
plantilla pero un cliente funcione con otra». Por eso no hay plantilla fija:

1. **Columnas por sus títulos** (`mapear`): se busca, en las primeras filas de cada hoja, la
   fila con un título de código y uno de descripción, y se reconoce cada columna por su
   título (lo específico antes que lo general: «certificado anterior» antes que
   «certificado»). Si no se reconocen, Claude Code dice qué columna es qué (`ai.claude_code
   .mapear_columnas`): solo letras de columna, ninguna cifra.
2. **Cifras de las celdas** (`leer`): con el mapa de columnas, TRAZA lee cada fila. El
   importe a origen sale de su columna; si no la hay, de anterior + mes; si tampoco, del %
   a origen por el importe de presupuesto. Se usan los resultados que Excel guardó.

Qué filas cuentan lo decide quien llama (app/obra), cruzando con la venta por código: así un
capítulo o un subtotal no se suman dos veces.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, get_column_letter

LECTOR = "certificacion_excel"
VERSION = "1.0.0"

ROLES = (
    "codigo",
    "resumen",
    "naturaleza",
    "importe_origen",
    "importe_anterior",
    "importe_mes",
    "porcentaje_origen",
    "importe_presupuesto",
)
NOMBRES_ROL = {
    "codigo": "código",
    "resumen": "descripción",
    "naturaleza": "naturaleza",
    "importe_origen": "importe a origen",
    "importe_anterior": "importe anterior",
    "importe_mes": "importe de esta certificación",
    "porcentaje_origen": "% a origen",
    "importe_presupuesto": "importe de presupuesto",
}

#: Títulos reconocidos por rol, normalizados (minúsculas, sin acentos ni puntos). Se recorren
#: en orden y se compara por «contiene»: lo específico antes que lo general (como en
#: coherencia/importador: el término largo quedaría inalcanzable). Un título solo vale para
#: un rol.
SINONIMOS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "porcentaje_origen",
        (
            "% origen",
            "% a origen",
            "origen %",
            "porcentaje origen",
            "% acumulado",
            "acumulado %",
            "% ejecutado",
            "ejecutado %",
            "% total",
            "porcentaje ejecutado",
        ),
    ),  # fmt: skip
    (
        "importe_anterior",
        (
            "certificado anterior",
            "cert anterior",
            "importe anterior",
            "anterior",
            "origen anterior",
        ),
    ),  # fmt: skip
    (
        "importe_origen",
        ("a origen", "origen", "acumulado", "certificado total", "total certificado"),
    ),  # fmt: skip
    (
        "importe_mes",
        (
            "esta certificacion",
            "certificacion actual",
            "certificado actual",
            "importe actual",
            "importe del mes",
            "importe mes",
            "cert mes",
            "actual",
            "del mes",
            "mes",
            "periodo",
        ),
    ),  # fmt: skip
    (
        "importe_presupuesto",
        ("importe presupuesto", "presupuesto", "importe contrato", "contrato", "importe proyecto"),
    ),  # fmt: skip
    ("naturaleza", ("naturaleza", "nat")),
    ("codigo", ("codigo", "cod", "referencia", "ref")),
    (
        "resumen",
        ("resumen", "descripcion", "concepto", "denominacion", "designacion", "unidad de obra"),
    ),  # fmt: skip
)


#: Un título con estas palabras es de cantidades, unidades, precios o porcentajes, no de
#: importes en euros: «Cantidad a origen», «Uds. a origen» o «% anterior» no son el importe
#: (revisión 09-11-2026: «% anterior» y «% actual» se leían como euros).
NO_IMPORTE = ("%", "cantidad", "cant ", "medicion", "precio", "unitario", "unidades", "uds ",
              "ud ", "porcentaje")  # fmt: skip


def _vale_para(rol: str, titulo_normalizado: str) -> bool:
    t = titulo_normalizado + " "
    if rol.startswith("importe") and any(n in t for n in NO_IMPORTE):
        return False
    # Un % a origen tiene que decir que es un porcentaje.
    return rol != "porcentaje_origen" or "%" in t or "porcentaje" in t


class CertificacionNoReconocida(ValueError):
    pass


def normalizar(texto: Any) -> str:
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(t.lower().replace(".", " ").replace("_", " ").split())


@dataclass
class Mapa:
    """Dónde está cada dato: hoja, fila de títulos y {rol: letra de columna}."""

    hoja: str
    fila_titulos: int
    columnas: dict[str, str]
    origen: str  # «títulos» o «IA»
    titulos: dict[str, str] = field(default_factory=dict)  # rol → título leído

    def completo(self) -> bool:
        c = self.columnas
        cifra = (
            "importe_origen" in c
            or {"importe_anterior", "importe_mes"} <= set(c)
            or {"porcentaje_origen", "importe_presupuesto"} <= set(c)
        )
        return "codigo" in c and cifra


@dataclass(frozen=True)
class Fila:
    fila: int
    codigo: str  # «» en una línea sin código (se lista, no se descarta)
    resumen: str
    naturaleza: str
    importe_origen: float | None  # None: la fila no tiene importe


@dataclass
class Leido:
    mapa: Mapa
    filas: list[Fila]
    total_excel: tuple[int, float] | None  # (fila, importe a origen) de la fila TOTAL
    avisos: list[str] = field(default_factory=list)


def _numero(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int | float):
        return float(v)
    return None


def _libros(ruta: Path):
    try:
        return load_workbook(ruta, data_only=True), load_workbook(ruta, data_only=False)
    except Exception as exc:  # noqa: BLE001 — cualquier fallo de apertura se explica igual
        raise CertificacionNoReconocida(
            f"No se puede abrir «{ruta.name}» como Excel: {exc}"
        ) from exc


def mapas(ruta: Path) -> list[Mapa]:
    """Columnas por sus títulos: el mejor mapa completo de cada hoja (puede haber varias,
    p. ej. resumen y detalle; quien llama elige la que casa con la venta)."""
    wv, _ = _libros(Path(ruta))
    salida = []
    for ws in wv.worksheets:
        mejor: Mapa | None = None
        for r in range(1, min(ws.max_row, 40) + 1):
            columnas: dict[str, str] = {}
            titulos: dict[str, str] = {}
            for c in range(1, min(ws.max_column, 60) + 1):
                t = normalizar(ws.cell(r, c).value)
                if not t:
                    continue
                for rol, sinonimos in SINONIMOS:
                    if rol in columnas or not _vale_para(rol, t):
                        continue
                    if any(s == t or (len(s) > 3 and s in t) for s in sinonimos):
                        columnas[rol] = get_column_letter(c)
                        titulos[rol] = str(ws.cell(r, c).value).strip()
                        break
            m = Mapa(ws.title, r, columnas, "títulos", titulos)
            if m.completo() and (mejor is None or len(columnas) > len(mejor.columnas)):
                mejor = m
        if mejor is not None:
            salida.append(mejor)
    return salida


def mapear(ruta: Path) -> Mapa | None:
    """El primer mapa completo (compatibilidad); `mapas` da todos."""
    todos = mapas(ruta)
    return todos[0] if todos else None


def volcado_titulos(ruta: Path, filas: int = 25) -> str:
    """Las primeras filas de cada hoja con la referencia de cada celda, para que la IA diga
    qué columna es qué (solo títulos y unas filas de muestra)."""
    wv, _ = _libros(Path(ruta))
    lineas = []
    for ws in wv.worksheets:
        lineas.append(f"=== Hoja «{ws.title}» ===")
        for r in range(1, min(ws.max_row, filas) + 1):
            celdas = [
                f"{get_column_letter(c)}{r}: {str(ws.cell(r, c).value)[:60]}"
                for c in range(1, min(ws.max_column, 40) + 1)
                if ws.cell(r, c).value not in (None, "")
            ]
            if celdas:
                lineas.append(" | ".join(celdas))
    return "\n".join(lineas)


def mapa_de_ia(ruta: Path, propuesta: dict[str, Any]) -> Mapa:
    """Comprueba lo que propone la IA contra el fichero, con las mismas reglas que los
    títulos (ADR-0013: la IA propone, TRAZA comprueba): la hoja y la fila existen; cada
    columna tiene título en esa fila y vale para su dato (un «%» o una cantidad no es un
    importe); dos datos no comparten columna; una columna de importe tiene números debajo.
    Lo que no cuadra se descarta (no se adivina)."""
    wv, _ = _libros(Path(ruta))
    if propuesta.get("hoja") not in wv.sheetnames:
        raise CertificacionNoReconocida(f"La hoja «{propuesta.get('hoja')}» no está en el Excel.")
    ws = wv[propuesta["hoja"]]
    fila = int(propuesta.get("fila_titulos") or 0)
    if not 1 <= fila <= ws.max_row:
        raise CertificacionNoReconocida("La fila de títulos propuesta no existe.")
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
        if rol.startswith(("importe", "porcentaje")) and not any(
            _numero(ws.cell(r, c).value) is not None for r in range(fila + 1, ws.max_row + 1)
        ):
            continue  # una columna de importe sin ningún número no es de importes
        usadas.add(c)
        columnas[rol], titulos[rol] = get_column_letter(c), str(titulo).strip()
    m = Mapa(ws.title, fila, columnas, "IA", titulos)
    if not m.completo():
        raise CertificacionNoReconocida(
            "No se ha podido saber qué columna tiene el código y el importe certificado a "
            "origen (o anterior y mes, o % y presupuesto)."
        )
    return m


#: Filas de total que NO son el total certificado de la obra.
_OTROS_TOTALES = ("iva", "capitulo", "cap ", "con impuestos", "liquido", "a pagar")


def leer(ruta: Path, mapa: Mapa) -> Leido:
    wv, wf = _libros(Path(ruta))
    ws, wsf = wv[mapa.hoja], wf[mapa.hoja]
    col = {rol: column_index_from_string(letra) for rol, letra in mapa.columnas.items()}

    def valor(r: int, rol: str) -> Any:
        return ws.cell(r, col[rol]).value if rol in col else None

    def sin_resultado(r: int, rol: str) -> bool:
        if rol not in col or valor(r, rol) is not None:
            return False
        celda = wsf.cell(r, col[rol]).value
        return isinstance(celda, str) and celda.startswith("=")

    escala = _escala_porcentaje(ws, col, mapa)
    filas: list[Fila] = []
    total_excel = None
    avisos: list[str] = []
    for r in range(mapa.fila_titulos + 1, ws.max_row + 1):
        codigo = str(valor(r, "codigo") or "").strip()
        resumen = str(valor(r, "resumen") or "").strip()
        usados: tuple[str, ...]
        if "importe_origen" in col:
            usados = ("importe_origen",)
            origen = _numero(valor(r, "importe_origen"))
        elif "importe_anterior" in col and "importe_mes" in col:
            usados = ("importe_anterior", "importe_mes")
            ant, mes = _numero(valor(r, "importe_anterior")), _numero(valor(r, "importe_mes"))
            origen = None if ant is None and mes is None else (ant or 0.0) + (mes or 0.0)
        else:
            usados = ("porcentaje_origen", "importe_presupuesto")
            pct = _numero(valor(r, "porcentaje_origen"))
            pres = _numero(valor(r, "importe_presupuesto"))
            origen = None if pct is None or pres is None else pres * pct / escala
        # TOTAL: sin código (o con «TOTAL» en la columna de código), con importe, y que no
        # sea un total de capítulo ni con IVA (revisión 09-11-2026).
        texto = normalizar(codigo or resumen)
        es_total = texto.startswith("total") and (
            not codigo or normalizar(codigo).startswith("total")
        )
        if es_total and origen is not None:
            if not any(o in texto + " " for o in _OTROS_TOTALES):
                total_excel = (r, origen)
            continue
        malas = [rol for rol in usados if sin_resultado(r, rol)]
        if malas:
            avisos.append(
                f"{codigo or resumen} (fila {r}): fórmula sin resultado guardado (cuenta 0)."
            )
        if not codigo and not origen:
            continue  # sin código ni importe: un título, una línea en blanco…
        filas.append(Fila(r, codigo, resumen, str(valor(r, "naturaleza") or "").strip(), origen))
    if not any(f.codigo for f in filas):
        raise CertificacionNoReconocida("No hay ninguna fila con código bajo los títulos.")
    return Leido(mapa, filas, total_excel, avisos)


def _escala_porcentaje(ws, col: dict[str, int], mapa: Mapa) -> float:
    """% en tanto por uno o por ciento: manda el formato de la celda («0%» es tanto por
    uno); sin formato, el mayor valor de las filas con código (> 1,5 → por ciento)."""
    if "porcentaje_origen" not in col:
        return 1.0
    valores = []
    for r in range(mapa.fila_titulos + 1, ws.max_row + 1):
        celda = ws.cell(r, col["porcentaje_origen"])
        if _numero(celda.value) is None or not ws.cell(r, col["codigo"]).value:
            continue
        if "%" in (celda.number_format or ""):
            return 1.0
        valores.append(celda.value)
    return 100.0 if max(valores, default=0.0) > 1.5 else 1.0


def descripcion(mapa: Mapa) -> str:
    """«código en A («Código»), importe a origen en H («A origen»)…», para confirmarlo."""
    partes = [
        f"{NOMBRES_ROL[rol]} en {mapa.columnas[rol]} («{mapa.titulos.get(rol, '')}»)"
        for rol in ROLES
        if rol in mapa.columnas
    ]
    return f"Hoja «{mapa.hoja}», títulos en la fila {mapa.fila_titulos}: " + ", ".join(partes) + "."
