"""Cualquier hoja de cálculo (io/hoja_calculo.py; docs/modules/obra.md, bloque 4a).

Ficheros inventados con las formas típicas de una exportación: CSV de un ERP español
(«;», coma decimal, Windows-1252), CSV «a la inglesa» («,», punto decimal) y Excel 97-2003.
"""

from __future__ import annotations

from datetime import datetime

import pytest
import xlwt

from traza.io import hoja_calculo
from traza.io.hoja_calculo import HojaNoLegible, abrir, es_hoja


def _filas(ruta):
    ws = abrir(ruta)[0].worksheets[0]
    return [[c.value for c in f] for f in ws.iter_rows()]


def test_csv_de_un_erp_espanol(tmp_path):
    ruta = tmp_path / "Facturas Señalización.csv"
    ruta.write_bytes(
        (
            "Proveedor;Nº factura;Fecha;Base imponible;IVA %;Total\r\n"
            "Climatización Pérez SL;F-001;03/11/2026;1.234,56;21 %;1.493,82 €\r\n"
            "Abonos García;A-7;4.11.2026;(150,00);21%;-181,50\r\n"
            '=HYPERLINK("x");F-2;2026-11-05;12;;\r\n'
        ).encode("cp1252")
    )
    f = _filas(ruta)
    assert f[0][:2] == ["Proveedor", "Nº factura"]
    assert f[1] == [
        "Climatización Pérez SL",
        "F-001",
        datetime(2026, 11, 3),
        1234.56,
        0.21,
        1493.82,
    ]
    assert f[2][2:] == [datetime(2026, 11, 4), -150.0, 0.21, -181.5]
    assert f[3][:4] == ['=HYPERLINK("x")', "F-2", datetime(2026, 11, 5), 12]
    ws = abrir(ruta)[0].worksheets[0]
    assert ws["A4"].data_type == "s"  # texto, nunca fórmula
    assert ws["E2"].number_format == hoja_calculo.FORMATO_PCT  # el % se reconoce
    assert ws.title == "Facturas Señalización"


def test_csv_con_punto_decimal_y_utf8(tmp_path):
    ruta = tmp_path / "export.csv"
    ruta.write_text(
        'Code,Description,Amount\nUTA01,Unidad «interior»,"20,000.50"\nCND01,Conducto,1234.5\n',
        encoding="utf-8-sig",
    )
    f = _filas(ruta)
    assert f[1] == ["UTA01", "Unidad «interior»", 20000.5]
    assert f[2][2] == 1234.5


def test_lo_que_contradice_la_convencion_queda_como_texto(tmp_path):
    """En un fichero con coma decimal, «1234.56» no se lee como 123456: queda como texto
    (inventar una cifra es peor que no leerla)."""
    ruta = tmp_path / "mezcla.csv"
    ruta.write_text("A;B\n1.234,5;1234.56\n", encoding="utf-8")
    assert _filas(ruta)[1] == [1234.5, "1234.56"]


def test_solo_enteros_ambiguos_decide_el_separador(tmp_path):
    con_punto_y_coma = tmp_path / "a.csv"
    con_punto_y_coma.write_text("Importe;X\n1.234;1\n", encoding="utf-8")
    assert _filas(con_punto_y_coma)[1][0] == 1234  # como Excel en España
    con_coma = tmp_path / "b.csv"
    con_coma.write_text("Importe,X\n1.234,1\n", encoding="utf-8")
    assert _filas(con_coma)[1][0] == 1.234


def test_xls_antiguo(tmp_path):
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Certificación")
    for c, t in enumerate(["Código", "Importe a origen", "% a origen", "Fecha"]):
        ws.write(0, c, t)
    ws.write(1, 0, "UTA01")
    ws.write(1, 1, 10000.0)
    ws.write(1, 2, 0.5, xlwt.easyxf(num_format_str="0%"))
    ws.write(1, 3, datetime(2026, 10, 31), xlwt.easyxf(num_format_str="dd/mm/yyyy"))
    ws.write(2, 0, "=TEXTO")
    ws.write(3, 1, 2100.75)
    ruta = tmp_path / "cert.xls"
    wb.save(str(ruta))
    valores, formulas = abrir(ruta)
    hoja = valores["Certificación"]
    assert hoja["B2"].value == 10000 and isinstance(hoja["B2"].value, int)
    assert hoja["C2"].value == 0.5 and hoja["C2"].number_format == "0%"
    assert hoja["D2"].value == datetime(2026, 10, 31)
    assert hoja["A3"].value == "=TEXTO" and hoja["A3"].data_type == "s"
    assert hoja["B4"].value == 2100.75
    assert formulas is valores  # un .xls guarda resultados, no fórmulas


def test_no_es_hoja(tmp_path):
    assert es_hoja(".XLS") and es_hoja("obra.csv") and not es_hoja("plano.dxf")
    roto = tmp_path / "roto.xls"
    roto.write_bytes(b"\xd0\xcf\x11\xe0" + b"\x00" * 600)  # firma de Excel 97, dañado
    with pytest.raises(HojaNoLegible, match="no se puede abrir"):
        abrir(roto)
    pdf = tmp_path / "pdf.xls"
    pdf.write_bytes(b"%PDF-1.7\n\x00\x01\x02 binario")
    with pytest.raises(HojaNoLegible, match="ni un texto con columnas"):
        abrir(pdf)
    with pytest.raises(HojaNoLegible, match="no es una hoja de cálculo"):
        abrir(tmp_path / "plano.dxf")


def test_codigos_no_son_numeros_ni_fechas(tmp_path):
    """Revisión 10-11-2026: «01.02.03» se convertía en una fecha y «01» en el número 1, y el
    cruce por código con la venta dejaba de casar. Toda la columna de códigos se queda
    como texto (también «1.001», que suelto parecería mil uno)."""
    ruta = tmp_path / "cert.csv"
    ruta.write_text(
        "Código;Resumen;Importe;Cantidad\n"
        "01;Climatización;12.100,00;\n"
        "01.02.03;Conducto;2.100,50;0,125\n"
        "1.001;Rejilla;5;3\n"
        "02-05-10;Otro;1;1\n",
        encoding="utf-8",
    )
    f = _filas(ruta)
    assert [x[0] for x in f[1:]] == ["01", "01.02.03", "1.001", "02-05-10"]
    assert f[1][2] == 12100 and f[2][2:] == [2100.5, 0.125]


def test_identificadores_con_cero_delante_y_espacios(tmp_path):
    ruta = tmp_path / "erp.csv"
    ruta.write_text(
        "Fecha;CP;Referencia;Importe\n"
        "03.11.2026;08001;0001234;1 234,56\n"
        "04/11/2026;28001;2026 0001;-1.234,56\n",
        encoding="utf-8",
    )
    f = _filas(ruta)
    assert f[1] == [datetime(2026, 11, 3), "08001", "0001234", 1234.56]
    assert f[2] == [datetime(2026, 11, 4), "28001", "2026 0001", -1234.56]


def test_tres_decimales_y_miles_a_la_inglesa(tmp_path):
    """«0,125» no es 125 ni «1,234» en un fichero a la inglesa es 1,234."""
    es = tmp_path / "es.csv"
    es.write_text("A;B\n0,125;7,1%\n", encoding="utf-8")
    assert _filas(es)[1] == [0.125, 0.071]
    en = tmp_path / "en.csv"
    en.write_text('A,B\n"1,234",12.50\n"0,125",1\n', encoding="utf-8")
    assert _filas(en)[1:] == [[1234, 12.5], ["0,125", 1]]


def test_separador_con_importes_de_coma_en_cada_linea(tmp_path):
    """Con «1,00» en cada línea, csv.Sniffer elegía la coma y partía los importes."""
    ruta = tmp_path / "sin_cabecera.csv"
    ruta.write_text("F-1;Proveedor A;1,00\nF-2;Proveedor B;2,50\n", encoding="utf-8")
    assert _filas(ruta) == [["F-1", "Proveedor A", 1], ["F-2", "Proveedor B", 2.5]]


def test_xls_que_no_lo_es(tmp_path):
    """Muchos ERP guardan con extensión .xls una tabla HTML, un XML de Excel 2003, texto
    con separadores o un .xlsx: se mira el contenido, no el nombre."""
    html = tmp_path / "html.xls"
    html.write_text(
        "<html><body><table><tr><th>Proveedor</th><th>Importe</th></tr>"
        "<tr><td>Pérez &amp; Cía</td><td>1.234,56</td></tr></table></body></html>",
        encoding="cp1252",
    )
    assert _filas(html) == [["Proveedor", "Importe"], ["Pérez & Cía", 1234.56]]
    xml = tmp_path / "xml.xls"
    xml.write_text(
        '<?xml version="1.0"?><Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet">'
        "<Worksheet><Table><Row><Cell><Data>Código</Data></Cell><Cell><Data>Importe</Data>"
        "</Cell></Row><Row><Cell><Data>01.01</Data></Cell><Cell><Data>12,5</Data></Cell>"
        "</Row></Table></Worksheet></Workbook>",
        encoding="utf-8",
    )
    assert _filas(xml) == [["Código", "Importe"], ["01.01", 12.5]]
    texto = tmp_path / "texto.xls"
    texto.write_text("Código\tImporte\nA\t3,5\n", encoding="utf-8")
    assert _filas(texto) == [["Código", "Importe"], ["A", 3.5]]
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.append(["Código", 7])
    renombrado = tmp_path / "renombrado.xls"
    wb.save(renombrado)
    assert _filas(renombrado) == [["Código", 7]]


# --- Ayudas para otras pruebas: el mismo contenido en .xls y en .csv ------------------------


def a_xls(xlsx, destino, resultados=None):
    """Copia un .xlsx de prueba a Excel 97-2003. Un .xls guarda el resultado de cada
    fórmula, no la fórmula: `resultados` da el de cada una ({"F10": 42}); sin él, la celda
    queda vacía (como la ve el lector en el .xlsx sin resultado guardado)."""
    resultados = resultados or {}
    from openpyxl import load_workbook

    wb = load_workbook(xlsx)
    salida = xlwt.Workbook()
    for ws in wb.worksheets:
        hoja = salida.add_sheet(ws.title)
        for fila in ws.iter_rows():
            for c in fila:
                valor = c.value
                if isinstance(valor, str) and valor.startswith("="):
                    valor = resultados.get(c.coordinate)
                if valor is None:
                    continue
                hoja.write(c.row - 1, c.column - 1, valor)
    salida.save(str(destino))
    return destino


def a_csv(filas, destino, separador=";", decimal=","):
    """Filas a CSV como lo exporta un programa en España (o, con «,» y «.», en inglés)."""

    def texto(v):
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:.2f}".replace(".", decimal)
        return str(v)

    destino.write_bytes(
        "\r\n".join(separador.join(texto(v) for v in f) for f in filas).encode("cp1252")
    )
    return destino
