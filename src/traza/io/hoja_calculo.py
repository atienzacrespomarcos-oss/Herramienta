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
- Lo que se llama .xls pero no lo es (muchos ERP exportan una tabla HTML, XML o texto con
  esa extensión, o un .xlsx renombrado): se mira el contenido, no el nombre.
- .csv y texto con separadores: ver «Texto» más abajo.

Un texto ajeno que empieza por «=» se guarda como texto: nunca se convierte en fórmula.

Texto (CSV y tablas HTML/XML). Lo que manda es no inventar una cifra: un texto solo se
convierte en número o en fecha si es **inequívoco**; si no, se queda como texto y los
lectores lo tratan como «no consta». En concreto (revisión 10-11-2026):
- Un código no es un número: con un cero delante («01», «08001», «0001234») o con varios
  separadores que no son de miles («01.02.03», «1.10.2»), se queda como texto, y **toda
  su columna** también (una columna de códigos no se convierte a medias: «1.001» junto a
  «01.002» es un código, no mil uno).
- Fechas solo con el año de 4 cifras (dd/mm/aaaa, dd-mm-aaaa, dd.mm.aaaa, aaaa-mm-dd):
  «01.02.03» es un código, no el 1 de febrero de 2003.
- La convención decimal se decide **por fichero**, con lo que el fichero demuestra (ver
  `_convencion`); un número que la contradice se queda como texto.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

EXTENSIONES = (".xlsx", ".xlsm", ".xls", ".csv")
FORMATO_PCT = "0.00%"

_FIRMA_ZIP = b"PK\x03\x04"  # .xlsx/.xlsm (también renombrado a .xls)
_FIRMA_OLE = b"\xd0\xcf\x11\xe0"  # Excel 97-2003 de verdad


class HojaNoLegible(ValueError):
    """El fichero no se puede abrir como hoja de cálculo."""


def es_hoja(ruta_o_extension: Path | str) -> bool:
    """Por la ruta («obra.xls») o por la extensión sola («.xls»)."""
    texto = str(ruta_o_extension)
    ext = texto if texto.startswith(".") else Path(texto).suffix
    return ext.lower() in EXTENSIONES


def abrir(ruta: Path) -> tuple[Workbook, Workbook]:
    """(libro con los valores guardados, libro con las fórmulas). El llamador los cierra.
    En los formatos sin fórmulas (.xls, texto) los dos son el mismo libro: `es_sin_formulas`."""
    ruta = Path(ruta)
    if not es_hoja(ruta):
        raise HojaNoLegible(f"«{ruta.name}» no es una hoja de cálculo (.xlsx, .xlsm, .xls o .csv).")
    try:
        inicio = ruta.read_bytes()[:8]
        if inicio.startswith(_FIRMA_ZIP):
            if ruta.suffix.lower() in (".xlsx", ".xlsm"):
                return load_workbook(ruta, data_only=True), load_workbook(ruta, data_only=False)
            # Un .xlsx con otra extensión: openpyxl mira la extensión; se le da el contenido.
            datos = ruta.read_bytes()
            return (
                load_workbook(io.BytesIO(datos), data_only=True),
                load_workbook(io.BytesIO(datos), data_only=False),
            )
        wb = _desde_xls(ruta) if inicio.startswith(_FIRMA_OLE) else _desde_texto(ruta)
    except HojaNoLegible:
        raise
    except Exception as exc:  # noqa: BLE001 — fichero dañado o de otro tipo: se dice
        raise HojaNoLegible(f"«{ruta.name}» no se puede abrir como hoja de cálculo: {exc}") from exc
    return wb, wb


def es_sin_formulas(valores: Workbook, formulas: Workbook) -> bool:
    """El formato no guarda fórmulas (.xls, texto): no se puede distinguir un precio
    escrito de uno calculado."""
    return valores is formulas


def _poner(ws, fila: int, col: int, valor, formato: str | None = None) -> None:
    if isinstance(valor, str):
        valor = ILLEGAL_CHARACTERS_RE.sub("", valor)
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


def _entero_si_lo_es(v: float):
    # Como openpyxl: un entero guardado sin decimales se lee como entero.
    return int(v) if float(v).is_integer() and abs(v) < 2**53 else v


def _valor_xls(libro, celda):
    import xlrd

    t = celda.ctype
    if t in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return None
    if t == xlrd.XL_CELL_NUMBER:
        return _entero_si_lo_es(celda.value)
    if t == xlrd.XL_CELL_DATE:
        try:
            return xlrd.xldate_as_datetime(celda.value, libro.datemode)
        except (xlrd.xldate.XLDateError, ValueError, OverflowError):
            return _entero_si_lo_es(celda.value)  # fuera de rango: el número tal cual
    if t == xlrd.XL_CELL_BOOLEAN:
        return bool(celda.value)
    if t == xlrd.XL_CELL_ERROR:
        return xlrd.error_text_from_code.get(celda.value, "#ERROR")
    texto = str(celda.value)
    return texto if texto.strip() else None


# --- Texto: CSV, tablas HTML y XML ----------------------------------------------------------

_MONEDA = re.compile(r"€|\bEUR\b|\beur\b")
_MILES_CON_ESPACIO = re.compile(r"^[+-]?\d{1,3}( \d{3})+([.,]\d+)?$")
_CON_AMBOS = re.compile(r"^[+-]?\d{1,3}([.,]\d{3})*[.,]\d+$")
#: Coma o punto seguidos de 1-2 o de 4 o más cifras: solo pueden ser el decimal (con 3
#: cifras, «1,234» o «1.234», puede ser el separador de miles: no demuestra nada).
_COMA_DECIMAL = re.compile(r"^[+-]?\d+,(\d{1,2}|\d{4,})$")
_PUNTO_DECIMAL = re.compile(r"^[+-]?\d+\.(\d{1,2}|\d{4,})$")
_ENTERO = re.compile(r"^[+-]?\d+$")
_CERO_DELANTE = re.compile(r"^[+-]?0\d")
_VARIOS_SEPARADORES = re.compile(r"^\d+([.,]\d+){2,}$")
_SOLO_CIFRAS = re.compile(r"^[+-]?[\d.,]+$")
_FECHA_DMA = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$")
_FECHA_AMD = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")


def _texto_de(ruta: Path) -> str:
    datos = ruta.read_bytes()
    if b"\x00" in datos[:8192]:
        # Binario que no es Excel (un PDF o una imagen renombrados): no es una tabla.
        raise HojaNoLegible(f"«{ruta.name}» no es una hoja de cálculo ni un texto con columnas.")
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return datos.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return datos.decode("latin-1")


class _Tabla(HTMLParser):
    """Filas y celdas de una tabla HTML (<tr><td>) o de un XML de Excel 2003
    (<Row><Cell><Data>), que es lo que muchos ERP guardan con extensión .xls."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.filas: list[list[str]] = []
        self._celda: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag in ("tr", "row"):
            self.filas.append([])
        elif tag in ("td", "th", "cell") and self.filas:
            self._celda = []
        elif tag == "br" and self._celda is not None:
            self._celda.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th", "cell") and self._celda is not None and self.filas:
            self.filas[-1].append(" ".join("".join(self._celda).split()))
            self._celda = None

    def handle_data(self, data):
        if self._celda is not None:
            self._celda.append(data)


def _separador(texto: str) -> str:
    """El que da a casi todas las líneas el mismo número de campos (2 o más). No se usa
    csv.Sniffer: con «1,00» en cada línea de un fichero con «;» elegía la coma y partía
    los importes (revisión 10-11-2026). A igualdad, «;» (lo habitual en España)."""
    lineas = [x for x in texto.splitlines()[:300] if x.strip()]
    mejor, mejor_nota = ";", (-1.0, 0)
    for sep in (";", "\t", "|", ","):
        cuentas = [len(f) for f in csv.reader(lineas, delimiter=sep)]
        if not cuentas:
            continue
        moda = max(set(cuentas), key=cuentas.count)
        if moda < 2:
            continue
        nota = (cuentas.count(moda) / len(cuentas), moda)
        if nota[0] > mejor_nota[0] + 1e-9:
            mejor, mejor_nota = sep, nota
    return mejor


def _desde_texto(ruta: Path) -> Workbook:
    texto = _texto_de(ruta)
    if texto.lstrip()[:1] == "<":
        tabla = _Tabla()
        tabla.feed(texto)
        filas, separador = tabla.filas, ""
        if not filas:
            raise HojaNoLegible(f"«{ruta.name}» no tiene ninguna tabla.")
    else:
        separador = _separador(texto)
        filas = list(csv.reader(io.StringIO(texto), delimiter=separador))
    return _desde_filas(filas, _titulo(ruta.stem, set()), separador)


def _limpio(texto: str) -> tuple[str | None, bool, bool]:
    """(número sin adornos o None si no puede serlo, negativo por paréntesis o por el signo
    detrás, porcentaje). Los espacios solo valen como separador de miles («1 234,56»):
    «912 345 678» o «2026 0001» no son un importe."""
    t = _MONEDA.sub("", texto).strip()
    pct = t.endswith("%")
    t = t.rstrip("%").strip()
    negativo = False
    if t.startswith("(") and t.endswith(")"):
        t, negativo = t[1:-1].strip(), True
    elif t.endswith("-") and _SOLO_CIFRAS.match(t[:-1] or "x"):
        t, negativo = t[:-1].strip(), True
    if " " in t:
        if not _MILES_CON_ESPACIO.match(t):
            return None, False, False
        t = t.replace(" ", "")
    if not t or not _SOLO_CIFRAS.match(t) or not any(ch.isdigit() for ch in t):
        return None, False, False
    return t, negativo, pct


def _es_codigo(t: str | None) -> bool:
    """«01», «08001», «01.02.03», «1.10.2»: identificadores, no cantidades."""
    if t is None or _fecha(t) is not None:  # «03.11.2026» es una fecha, no un código
        return False
    if _CERO_DELANTE.match(t):
        return True
    return (
        bool(_VARIOS_SEPARADORES.match(t.lstrip("+-")))
        and not _CON_AMBOS.match(t)
        and not (
            re.match(r"^\d{1,3}([.,]\d{3}){2,}$", t)  # 1.234.567: miles
        )
    )


def _convencion(textos: list[str], separador: str) -> str:
    """«,» si la coma es el decimal (convención española) o «.» si lo es el punto.

    Por orden, lo que el fichero demuestra (solo con las columnas que no son de códigos):
    1. Números con punto y coma a la vez («1.234,56» o «1,234.56»): el último es el decimal.
    2. Si no, coma con 1-2 o 4+ cifras detrás («12,5») solo puede ser decimal con coma;
       punto igual («12.50»), decimal con punto. Si aparecen las dos (contradicción), o
       ninguna (solo enteros o «1.234»), decide el separador de campos, como Excel en
       España: con «;», coma decimal. Lo que contradice la convención elegida queda como
       texto (`_numero`), no se reinterpreta.
    """
    votos = {",": 0, ".": 0}
    for t in textos:
        if "," in t and "." in t and _CON_AMBOS.match(t):
            votos["," if t.rfind(",") > t.rfind(".") else "."] += 1
    if votos[","] != votos["."]:
        return "," if votos[","] > votos["."] else "."
    coma = any(_COMA_DECIMAL.match(t) for t in textos)
    punto = any(_PUNTO_DECIMAL.match(t) for t in textos)
    if coma != punto:
        return "," if coma else "."
    return "," if separador in (";", "") else "."


def _numero(t: str, decimal: str):
    """None si el texto no encaja con la convención del fichero: el separador de miles
    solo va de 3 en 3, el primer grupo no empieza por 0 («0,125» con coma de miles no es
    125) y el decimal va una vez («1234.56» en un fichero con coma decimal se queda como
    texto; leerlo como 123456 sería inventar una cifra)."""
    miles = "." if decimal == "," else ","
    d, m = re.escape(decimal), re.escape(miles)
    entera = rf"(0|[1-9]\d*|[1-9]\d{{0,2}}({m}\d{{3}})+)"
    if not re.match(rf"^[+-]?{entera}({d}\d+)?$", t):
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
    """Solo con el año de 4 cifras: «01.02.03» es un código de partida, no una fecha."""
    try:
        m = _FECHA_AMD.match(t)
        if m:
            return datetime(int(m[1]), int(m[2]), int(m[3]))
        m = _FECHA_DMA.match(t)
        if m:
            return datetime(int(m[3]), int(m[2]), int(m[1]))
    except ValueError:
        return None
    return None


def _desde_filas(filas: list[list[str]], titulo: str, separador: str) -> Workbook:
    limpios = [[_limpio(v) if v.strip() else (None, False, False) for v in f] for f in filas]
    ancho = max((len(f) for f in filas), default=0)
    codigos = {c for c in range(ancho) if any(c < len(f) and _es_codigo(f[c][0]) for f in limpios)}
    decimal = _convencion(
        [x[0] for f in limpios for c, x in enumerate(f) if x[0] and c not in codigos],
        separador,
    )
    wb = Workbook()
    ws = wb.active
    ws.title = titulo
    for r, fila in enumerate(filas, start=1):
        for c, crudo in enumerate(fila):
            texto = crudo.strip()
            if not texto:
                continue
            if c in codigos:
                _poner(ws, r, c + 1, texto)
                continue
            valor, formato = _convertir(texto, limpios[r - 1][c], decimal)
            _poner(ws, r, c + 1, valor, formato)
    return wb


def _convertir(texto: str, limpio, decimal: str):
    t, negativo, pct = limpio
    fecha = None if pct else _fecha(texto)
    if fecha is not None:
        return fecha, None
    if t is not None:
        n = _numero(t, decimal)
        if n is not None:
            n = -n if negativo else n
            if pct:
                return round(n / 100, 12), FORMATO_PCT
            return n, None
    return texto, None
