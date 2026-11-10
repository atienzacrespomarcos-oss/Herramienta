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


def _entero_attr(texto, defecto: int = 0) -> int:
    try:
        return int(texto)
    except (TypeError, ValueError):
        return defecto


class _Tabla(HTMLParser):
    """Hojas, filas y celdas de tablas HTML (<table><tr><td>) o de un XML de Excel 2003
    (<Worksheet><Row><Cell><Data>), que es lo que muchos ERP guardan con extensión .xls.

    Cada celda va en su columna (revisión 10-11-2026: sin esto, un importe tras celdas
    vacías se corría a la izquierda): el XML de Excel salta las vacías con `ss:Index` y
    combina con `ss:MergeAcross`; el HTML, con `colspan`. Una celda combinada en varias
    filas (`rowspan`, `ss:MergeDown`), una tabla dentro de otra o posiciones que se pisan
    descolocarían las celdas: el fichero se rechaza y se dice. Cada <Worksheet> (o cada
    <table> de un HTML) es una hoja. Los comentarios de celda del XML no son su valor. Del
    XML se guarda el tipo que declara cada dato (`ss:Type`)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hojas: list[tuple[str, list[list[tuple[str, str | None]]]]] = []
        self._celda: list[str] | None = None
        self._tipo: str | None = None
        self._extra = 0
        self._en_xml = False
        self._tablas_abiertas = 0
        self._en_comentario = 0

    @property
    def _filas(self):
        if not self.hojas:
            self.hojas.append(("Hoja", []))
        return self.hojas[-1][1]

    def _cerrar_celda(self) -> None:
        if self._celda is not None:
            texto = " ".join("".join(self._celda).split())
            self._filas[-1].append((texto, self._tipo))
            self._filas[-1].extend([("", None)] * self._extra)
            self._celda, self._tipo, self._extra = None, None, 0

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "worksheet":
            self._en_xml = True
            self.hojas.append((a.get("ss:name") or f"Hoja{len(self.hojas) + 1}", []))
        elif tag == "table":
            self._tablas_abiertas += 1
            if self._tablas_abiertas > 1:
                raise HojaNoLegible(
                    "tiene una tabla dentro de otra: sus celdas no tienen una posición clara."
                )
            if not self._en_xml:
                self.hojas.append((f"Tabla{len(self.hojas) + 1}", []))
        elif tag == "comment":
            self._en_comentario += 1
        elif tag in ("tr", "row"):
            self._cerrar_celda()  # una <td> sin cerrar no se pierde
            filas = self._filas
            indice = _entero_attr(a.get("ss:index"))
            if indice and indice - 1 < len(filas):
                raise HojaNoLegible("tiene filas en posiciones que se pisan.")
            while indice and len(filas) < indice - 1:
                filas.append([])
            filas.append([])
        elif tag in ("td", "th", "cell"):
            self._cerrar_celda()
            if not self._filas:
                self._filas.append([])
            if _entero_attr(a.get("rowspan"), 1) > 1 or _entero_attr(a.get("ss:mergedown")) > 0:
                raise HojaNoLegible(
                    "tiene celdas combinadas en varias filas, que descolocarían las de debajo. "
                    "Ábrelo en Excel y guárdalo como .xlsx."
                )
            fila = self._filas[-1]
            indice = _entero_attr(a.get("ss:index"))
            if indice:
                if indice - 1 < len(fila):
                    raise HojaNoLegible("tiene celdas en posiciones que se pisan.")
                fila.extend([("", None)] * (indice - 1 - len(fila)))
            self._celda, self._tipo = [], None
            self._extra = max(
                _entero_attr(a.get("colspan"), 1) - 1, _entero_attr(a.get("ss:mergeacross"))
            )
        elif tag == "data" and self._celda is not None and not self._en_comentario:
            self._tipo = a.get("ss:type") or None
        elif tag == "br" and self._celda is not None:
            self._celda.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th", "cell"):
            self._cerrar_celda()
        elif tag == "comment":
            self._en_comentario = max(0, self._en_comentario - 1)
        elif tag == "table":
            self._cerrar_celda()
            self._tablas_abiertas = max(0, self._tablas_abiertas - 1)

    def close(self):
        super().close()
        self._cerrar_celda()  # un fichero cortado no pierde su última celda

    def handle_data(self, data):
        if self._celda is not None and not self._en_comentario:
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
        try:
            tabla.feed(texto)
            tabla.close()
        except HojaNoLegible as exc:
            raise HojaNoLegible(f"«{ruta.name}» {exc}") from exc
        hojas = [(n, f) for n, f in tabla.hojas if any(f)]
        if not hojas:
            raise HojaNoLegible(f"«{ruta.name}» no tiene ninguna tabla.")
        separador = ""
    else:
        separador = _separador(texto)
        filas = csv.reader(io.StringIO(texto), delimiter=separador)
        hojas = [(ruta.stem, [[(v, None) for v in f] for f in filas])]
    wb = Workbook()
    wb.remove(wb.active)
    usados: set[str] = set()
    for nombre, filas in hojas:
        _a_hoja(wb.create_sheet(_titulo(nombre, usados)), filas, separador)
    return wb


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
        and not re.match(r"^\d{1,3}([.,]\d{3}){2,}$", t)  # 1.234.567: miles (ambiguo, aceptado)
    )


#: Títulos de columna de identificadores: sus valores nunca son cantidades ni votan la
#: convención decimal (revisión 10-11-2026: «1.10», código de capítulo, votaba «punto
#: decimal» y «1.250» pasaba a 1,25). Palabra entera al principio del título: «Cantidad
#: partida», «Noviembre», «Capacidad», «Refrigeración» o «Nº uds.» no lo son.
_FIN = r"(?![a-zñáéíóúü])"
_TITULO_DE_CODIGOS = re.compile(
    rf"^(c[oó]d(igo)?{_FIN}|c[oó]d\.|ref(erencia)?{_FIN}|ref\.|cap([ií]tulo)?{_FIN}|cap\."
    rf"|partida{_FIN}(?!\s+alzada)|n\.?[º°](?!\s*(de\s+)?(ud|unid|uds))|n\.?\s*o\.?{_FIN}"
    rf"|n[uú]m(ero)?{_FIN}(?!\s*(de\s+)?(ud|unid|uds))|n[uú]m\.(?!\s*(de\s+)?(ud|unid|uds))"
    rf"|[ií]tem{_FIN}|id{_FIN}|nif{_FIN}|cif{_FIN}|c\.?p\.?{_FIN}|tel[eé]fono{_FIN}"
    rf"|factura{_FIN}|pos(ici[oó]n)?{_FIN}|pos\.|orden{_FIN}|l[ií]nea{_FIN}|art[ií]culo{_FIN}"
    rf"|art\.)",
    re.IGNORECASE,
)


def _filas_de_titulos(filas, limpios) -> list[int]:
    """Las de las 15 primeras con al menos dos textos que no son números: candidatas a fila
    de títulos. Se miran todas: delante de los títulos suele haber filas de cabecera del
    documento («Obra:;Nave 3», «Cliente:;X;Fecha:;03/11/2026»; revisión 10-11-2026)."""
    salida = []
    for r, f in enumerate(filas[:15]):
        textos = sum(
            1
            for c, (v, t) in enumerate(f)
            if v.strip() and _heuristico(t) and limpios[r][c][0] is None
        )
        if textos >= 2:
            salida.append(r)
    return salida


def _columnas_de_codigos(filas, limpios, ancho: int) -> set[int]:
    """Una columna es de códigos si su título (en una fila de títulos) lo dice o si al menos
    el 30 % de sus valores con cifras tienen forma de código. Una celda suelta («01», nº
    de certificación encima de los importes) no convierte en texto una columna de
    importes."""
    codigos = set()
    candidatas = _filas_de_titulos(filas, limpios)
    for c in range(ancho):
        titulos = [filas[r][c][0].strip() for r in candidatas if c < len(filas[r])]
        if any(t and len(t) <= 30 and _TITULO_DE_CODIGOS.match(t) for t in titulos):
            codigos.add(c)
            continue
        con_cifras = [f[c] for f in limpios if c < len(f) and f[c][0] is not None]
        forma = sum(1 for t, _n, pct in con_cifras if not pct and _es_codigo(t))
        if forma and forma >= 0.3 * len(con_cifras):
            codigos.add(c)
    return codigos


def _decimales(t: str, decimal: str) -> int:
    return len(t) - t.rfind(decimal) - 1 if decimal in t else 0


def _codigos_por_choque(limpios, ancho: int, codigos: set[int], decimal: str, ambiguos) -> set[int]:
    """Columnas donde dos textos distintos darían el mismo número con distinto número de
    decimales («1.1» y «1.10»): son códigos (capítulo 1.1 y capítulo 1.10), no cantidades
    (revisión 10-11-2026: los dos se leían 1,1 y se rompía el cruce por código)."""
    nuevos = set()
    for c in range(ancho):
        if c in codigos:
            continue
        vistos: dict[float, set[int]] = {}
        for f in limpios:
            if c >= len(f) or f[c][0] is None or f[c][2]:
                continue
            n = _numero(f[c][0], decimal, ambiguos)
            if n is None:
                continue
            vistos.setdefault(float(n), set()).add(_decimales(f[c][0], decimal))
        if any(len(d) > 1 for d in vistos.values()):
            nuevos.add(c)
    return nuevos


def _convencion(textos: list[str], separador: str) -> tuple[str, bool]:
    """(«,» si la coma es el decimal o «.» si lo es el punto; si los valores ambiguos como
    «1.250» —mil doscientos cincuenta o uno con veinticinco— se pueden leer).

    Lo que el fichero demuestra, solo con las columnas que no son de códigos:
    1. Números con punto y coma a la vez («1.234,56» o «1,234.56»): el último es el
       decimal. Prueba fuerte: los ambiguos se leen.
    2. Coma con 1-2 o 4+ cifras detrás («12,5»): coma decimal, y los ambiguos se leen (un
       código no lleva comas). Punto igual («12.50»): punto decimal, pero los ambiguos
       quedan como texto: «1.10» puede ser un código de capítulo sin título que lo diga
       (revisión 10-11-2026: «12.500» se leía 12,5).
    3. Sin prueba: con «;» (o una tabla HTML), la coma, como Excel en España, y los
       ambiguos se leen; con otro separador, el punto, y quedan como texto. Con pruebas
       que se contradicen, igual pero los ambiguos quedan siempre como texto.
    """
    votos = {",": 0, ".": 0}
    for t in textos:
        if "," in t and "." in t and _CON_AMBOS.match(t):
            votos["," if t.rfind(",") > t.rfind(".") else "."] += 1
    if votos[","] != votos["."]:
        return ("," if votos[","] > votos["."] else "."), True
    coma = any(_COMA_DECIMAL.match(t) for t in textos)
    punto = any(_PUNTO_DECIMAL.match(t) for t in textos)
    if coma and not punto:
        return ",", True
    if punto and not coma:
        return ".", False
    espanola = separador in (";", "")
    return ("," if espanola else "."), espanola and not (coma and punto)


_AMBIGUO = re.compile(r"^[+-]?[1-9]\d{0,2}[.,]\d{3}$")


def _numero(t: str, decimal: str, ambiguos: bool = True):
    """None si el texto no encaja con la convención del fichero: el separador de miles
    solo va de 3 en 3, el primer grupo no empieza por 0 («0,125» con coma de miles no es
    125) y el decimal va una vez («1234.56» en un fichero con coma decimal se queda como
    texto; leerlo como 123456 sería inventar una cifra). Sin `ambiguos`, «1.250» queda
    como texto."""
    if not ambiguos and _AMBIGUO.match(t):
        return None
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
    """Solo con el año de 4 cifras: «01.02.03» es un código de partida, no una fecha.
    Siempre día/mes/año (convención española)."""
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


def _tipado(texto: str, tipo: str):
    """Un dato del XML de Excel con su tipo declarado: número con punto, fecha ISO."""
    if tipo == "Number":
        try:
            v = float(texto)
        except ValueError:
            return texto
        return _entero_si_lo_es(v) if v == v and abs(v) != float("inf") else texto
    if tipo == "DateTime":
        try:
            return datetime.fromisoformat(texto[:19])
        except ValueError:
            return texto
    if tipo == "Boolean":
        return texto.strip() == "1"
    return texto  # String: texto tal cual


def _heuristico(tipo: str | None) -> bool:
    """Sin tipo declarado (CSV, HTML) o declarado texto (un ERP que escribe los importes
    como texto en el XML): se interpreta con las reglas de este módulo."""
    return tipo in (None, "String")


def _a_hoja(ws, filas: list[list[tuple[str, str | None]]], separador: str) -> None:
    limpios = [
        [_limpio(v) if v.strip() and _heuristico(t) else (None, False, False) for v, t in f]
        for f in filas
    ]
    ancho = max((len(f) for f in filas), default=0)
    codigos = _columnas_de_codigos(filas, limpios, ancho)

    def convencion():
        return _convencion(
            [x[0] for f in limpios for c, x in enumerate(f) if x[0] and c not in codigos],
            separador,
        )

    decimal, ambiguos = convencion()
    choques = _codigos_por_choque(limpios, ancho, codigos, decimal, ambiguos)
    if choques:
        codigos |= choques
        decimal, ambiguos = convencion()  # sin sus votos
    for r, fila in enumerate(filas, start=1):
        for c, (crudo, tipo) in enumerate(fila):
            texto = crudo.strip()
            if not texto:
                continue
            if not _heuristico(tipo):
                _poner(ws, r, c + 1, _tipado(texto, tipo))
            elif c in codigos:
                _poner(ws, r, c + 1, texto)
            else:
                valor, formato = _convertir(texto, limpios[r - 1][c], decimal, ambiguos)
                _poner(ws, r, c + 1, valor, formato)


def _convertir(texto: str, limpio, decimal: str, ambiguos: bool = True):
    t, negativo, pct = limpio
    fecha = None if pct else _fecha(texto)
    if fecha is not None:
        return fecha, None
    if t is not None:
        n = _numero(t, decimal, ambiguos)
        if n is not None:
            n = -n if negativo else n
            if pct:
                return round(n / 100, 12), FORMATO_PCT
            return n, None
    return texto, None
