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
    roto.write_bytes(b"esto no es un xls")
    with pytest.raises(HojaNoLegible, match="no se puede abrir"):
        abrir(roto)
    with pytest.raises(HojaNoLegible, match="no es una hoja de cálculo"):
        abrir(tmp_path / "plano.dxf")


# --- Ayudas para otras pruebas: el mismo contenido en .xls y en .csv ------------------------


def a_xls(xlsx, destino):
    """Copia un .xlsx de prueba a Excel 97-2003. Una fórmula sin resultado guardado queda
    vacía, como la ve el lector en el .xlsx (un .xls real trae el resultado)."""
    from openpyxl import load_workbook

    wb = load_workbook(xlsx)
    salida = xlwt.Workbook()
    for ws in wb.worksheets:
        hoja = salida.add_sheet(ws.title)
        for fila in ws.iter_rows():
            for c in fila:
                if c.value is None or (isinstance(c.value, str) and c.value.startswith("=")):
                    continue
                hoja.write(c.row - 1, c.column - 1, c.value)
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
