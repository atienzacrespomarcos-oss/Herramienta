"""Cualquier hoja de cálculo, abierta igual para todos los lectores (docs/modules/obra.md,
bloque 4a).

Usuario (10-11-2026): «lo que yo te pase, sea lo que sea, te valga». Los lectores de TRAZA
(presupuesto en Excel, comparativo de Presto, certificaciones, facturas del ERP) trabajan
sobre un libro de openpyxl. Aquí se abre lo que llegue y se entrega siempre así:

- .xlsx / .xlsm: tal cual (valores guardados y fórmulas).
- .xls (Excel 97-2003): con xlrd, celda a celda en la misma posición (las referencias
  «Hoja!B12» que citan los lectores siguen valiendo), con su formato de número (para
  reconocer porcentajes) y las fechas como fechas. Un .xls guarda el resultado de cada
  fórmula, no la fórmula: libro de valores y de fórmulas son el mismo.
- .csv (exportaciones de un ERP o de otro programa): codificación UTF-8 o Windows-1252,
  separador detectado (; , tabulador o |), y cada texto que es un número, una fecha o un
  porcentaje, convertido. La convención decimal se decide **por fichero**, con lo que el
  propio fichero demuestra (ver `_convencion`); no se adivina número a número.

Un texto ajeno que empieza por «=» se guarda como texto: nunca se convierte en fórmula.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook

EXTENSIONES = (".xlsx", ".xlsm", ".xls", ".csv")
FORMATO_PCT = "0.00%"


class HojaNoLegible(ValueError):
    """El fichero no se puede abrir como hoja de cálculo."""


def es_hoja(ruta_o_extension: Path | str) -> bool:
    """Por la ruta («obra.xls») o por la extensión sola («.xls»)."""
    texto = str(ruta_o_extension)
    ext = texto if texto.startswith(".") else Path(texto).suffix
    return ext.lower() in EXTENSIONES


def abrir(ruta: Path) -> tuple[Workbook, Workbook]:
    """(libro con los valores guardados, libro con las fórmulas). El llamador los cierra."""
    ruta = Path(ruta)
    ext = ruta.suffix.lower()
    try:
        if ext in (".xlsx", ".xlsm"):
            return load_workbook(ruta, data_only=True), load_workbook(ruta, data_only=False)
        if ext == ".xls":
            wb = _desde_xls(ruta)
        elif ext == ".csv":
            wb = _desde_csv(ruta)
        else:
            raise HojaNoLegible(
                f"«{ruta.name}» no es una hoja de cálculo (.xlsx, .xlsm, .xls o .csv)."
            )
    except HojaNoLegible:
        raise
    except Exception as exc:  # noqa: BLE001 — fichero dañado o de otro tipo: se dice
        raise HojaNoLegible(f"«{ruta.name}» no se puede abrir como hoja de cálculo: {exc}") from exc
    return wb, wb


def _poner(ws, fila: int, col: int, valor, formato: str | None = None) -> None:
    c = ws.cell(row=fila, column=col)
    c.value = valor
    if isinstance(valor, str) and valor.startswith("="):
        c.data_type = "s"  # texto, nunca fórmula
    if formato:
        c.number_format = formato


_NO_PERMITIDO_EN_HOJA = re.compile(r"[\\/*?:\[\]]")


def _titulo(texto: str, usados: set[str]) -> str:
    base = (_NO_PERMITIDO_EN_HOJA.sub("_", texto).strip() or "Hoja")[:31]
    titulo, n = base, 2
    while titulo in usados:
        sufijo = f" ({n})"
        titulo, n = base[: 31 - len(sufijo)] + sufijo, n + 1
    usados.add(titulo)
    return titulo


# --- .xls ----------------------------------------------------------------------------------


def _desde_xls(ruta: Path) -> Workbook:
    import xlrd

    libro = xlrd.open_workbook(str(ruta), formatting_info=True)
    wb = Workbook()
    wb.remove(wb.active)
    usados: set[str] = set()
    for hoja in libro.sheets():
        ws = wb.create_sheet(_titulo(hoja.name, usados))
        for r in range(hoja.nrows):
            for c in range(hoja.ncols):
                celda = hoja.cell(r, c)
                valor = _valor_xls(libro, celda)
                if valor is None:
                    continue
                formato = None
                try:
                    xf = libro.xf_list[celda.xf_index]
                    formato = libro.format_map[xf.format_key].format_str
                except (IndexError, KeyError, AttributeError):
                    pass
                _poner(ws, r + 1, c + 1, valor, formato if formato != "General" else None)
    return wb


def _valor_xls(libro, celda):
    import xlrd

    t = celda.ctype
    if t in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return None
    if t == xlrd.XL_CELL_NUMBER:
        v = celda.value
        # Como openpyxl: un entero guardado sin decimales se lee como entero.
        return int(v) if float(v).is_integer() and abs(v) < 2**53 else v
    if t == xlrd.XL_CELL_DATE:
        return xlrd.xldate_as_datetime(celda.value, libro.datemode)
    if t == xlrd.XL_CELL_BOOLEAN:
        return bool(celda.value)
    if t == xlrd.XL_CELL_ERROR:
        return xlrd.error_text_from_code.get(celda.value, "#ERROR")
    texto = str(celda.value)
    return texto if texto.strip() else None


# --- .csv ----------------------------------------------------------------------------------

_SOBRA = re.compile(r"\s|€|EUR|eur", re.UNICODE)
_CON_AMBOS = re.compile(r"^[+-]?\d{1,3}([.,]\d{3})*[.,]\d+$")
_COMA_DECIMAL = re.compile(r"^[+-]?\d+,\d+$")
_PUNTO_DECIMAL = re.compile(r"^[+-]?\d+\.(\d{1,2}|\d{4,})$")
_ENTERO = re.compile(r"^[+-]?\d+$")
_FECHA_DMA = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})$")
_FECHA_AMD = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")


def _texto_csv(ruta: Path) -> str:
    datos = ruta.read_bytes()
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return datos.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return datos.decode("latin-1")


def _limpio(texto: str) -> tuple[str, bool, bool]:
    """(número sin adornos, negativo por paréntesis o signo final, porcentaje)."""
    t = texto.strip()
    pct = t.endswith("%")
    t = _SOBRA.sub("", t.rstrip("%"))
    negativo = False
    if t.startswith("(") and t.endswith(")"):
        t, negativo = t[1:-1], True
    elif t.endswith("-") and t[:-1].replace(".", "").replace(",", "").isdigit():
        t, negativo = t[:-1], True
    return t, negativo, pct


def _convencion(textos: list[str], separador: str) -> str:
    """«," si la coma es el decimal (convención española) o «.» si lo es el punto.

    Por orden, lo que el fichero demuestra:
    1. Números con punto y coma a la vez («1.234,56» o «1,234.56»): el último es el decimal.
    2. Si no, «12,5» (coma seguida de cifras) solo puede ser decimal con coma.
    3. Si no, «12.5» o «12.50» (punto con 1-2 o 4+ cifras) solo puede ser decimal con punto.
    4. Si solo hay enteros o «1.234» (ambiguo: mil o uno con 234): el separador de campos
       decide, como hace Excel en España (con «;» la coma es el decimal).
    """
    votos = {",": 0, ".": 0}
    for t in textos:
        if "," in t and "." in t and _CON_AMBOS.match(t):
            votos["," if t.rfind(",") > t.rfind(".") else "."] += 1
    if votos[","] != votos["."]:
        return "," if votos[","] > votos["."] else "."
    if any(_COMA_DECIMAL.match(t) for t in textos):
        return ","
    if any(_PUNTO_DECIMAL.match(t) for t in textos):
        return "."
    return "," if separador == ";" else "."


def _numero(t: str, decimal: str):
    """None si el texto no encaja con la convención del fichero: el separador de miles
    solo va de 3 en 3 y el decimal, una vez («1234.56» en un fichero con coma decimal se
    queda como texto; leerlo como 123456 sería inventar una cifra)."""
    miles = "." if decimal == "," else ","
    d, m = re.escape(decimal), re.escape(miles)
    valido = rf"^[+-]?(\d+|\d{{1,3}}({m}\d{{3}})+)({d}\d+)?$"
    if not re.match(valido, t):
        return None
    normal = t.replace(miles, "").replace(decimal, ".")
    if _ENTERO.match(normal):
        return int(normal)
    try:
        v = float(normal)
    except ValueError:
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _fecha(t: str):
    m = _FECHA_AMD.match(t)
    try:
        if m:
            return datetime(int(m[1]), int(m[2]), int(m[3]))
        m = _FECHA_DMA.match(t)
        if m:
            a = int(m[3])
            return datetime(a + 2000 if a < 100 else a, int(m[2]), int(m[1]))
    except ValueError:
        return None
    return None


def _desde_csv(ruta: Path) -> Workbook:
    texto = _texto_csv(ruta)
    muestra = texto[:20000]
    try:
        separador = csv.Sniffer().sniff(muestra, delimiters=";,\t|").delimiter
    except csv.Error:
        separador = ";" if muestra.count(";") >= muestra.count(",") else ","
    filas = list(csv.reader(io.StringIO(texto), delimiter=separador))
    numericos = [
        _limpio(v)[0]
        for f in filas
        for v in f
        if v.strip() and re.fullmatch(r"[\d.,+\-]+", _limpio(v)[0] or "x")
    ]
    decimal = _convencion(numericos, separador)
    wb = Workbook()
    ws = wb.active
    ws.title = _titulo(ruta.stem, set())
    for r, fila in enumerate(filas, start=1):
        for c, crudo in enumerate(fila, start=1):
            if not crudo.strip():
                continue
            valor, formato = _convertir(crudo, decimal)
            _poner(ws, r, c, valor, formato)
    return wb


def _convertir(crudo: str, decimal: str):
    t, negativo, pct = _limpio(crudo)
    # Una fecha antes que un número: «03.11.2026» (día y mes de 1-2 cifras) no es un
    # número con separador de miles, que van de 3 en 3.
    fecha = None if pct else _fecha(crudo.strip())
    if fecha is not None:
        return fecha, None
    if t and re.fullmatch(r"[+-]?[\d.,]+", t) and any(ch.isdigit() for ch in t):
        n = _numero(t, decimal)
        if n is not None:
            n = -n if negativo else n
            if pct:
                return n / 100, FORMATO_PCT
            return n, None
    return crudo.strip(), None
