"""Obra, bloque 2b: certificaciones desde un Excel cualquiera (docs/modules/obra.md).

Usuario (09-11-2026): «debes ser capaz de interpretar un Excel»; «yo puedo tener una
plantilla pero un cliente funcione con otra». Varias disposiciones inventadas, con la venta
de tests/integration/test_obra.py: UTA01 20000, CND01 6000, EXTRA 500 (capítulo 01).
"""

from __future__ import annotations

import pytest
from openpyxl import Workbook
from tests.integration.test_obra import obra  # noqa: F401 (fixture)

from traza.app.ordenes import OrdenRechazada
from traza.io import certificacion_excel as ce


def excel(ruta, filas, titulo_en=1):
    wb = Workbook()
    ws = wb.active
    ws.title = "Cert"
    for _ in range(titulo_en - 1):
        ws.append(["CERTIFICACIÓN Nº 3 — OBRA DE PRUEBA"])
    for f in filas:
        ws.append(f)
    wb.save(ruta)
    return ruta


#: El usuario: importe a origen en su columna, con capítulo, una línea ajena y TOTAL.
SUYO = [
    ["Código", "Descripción", "Importe presupuesto", "Cantidad a origen", "Importe a origen"],
    ["01", "Climatización", 26500, None, 12100],
    ["UTA01", "UTA", 20000, 0.5, 10000],
    ["CND01", "Conducto", 6000, 35, 2100],
    ["OTRA", "Línea ajena a la venta", 0, 1, 300],
    [None, "TOTAL CERTIFICADO", None, None, 12400],
]
#: Un cliente: anterior + esta certificación, otros títulos y más filas de cabecera.
CLIENTE = [
    ["Cód.", "Concepto", "Cert. anterior", "Cert. actual"],
    ["UTA01", "UTA", 6000, 4000],
    ["CND01", "Conducto", 1000, 1100],
    ["EXTRA", "Extra", 0, 500],
]
#: Otro: solo % ejecutado (por ciento) y presupuesto.
PORCENTAJE = [
    ["Ref", "Designación", "Presupuesto", "% ejecutado"],
    ["UTA01", "UTA", 20000, 50],
    ["CND01", "Conducto", 6000, 35],
]


@pytest.fixture
def venta(obra):  # noqa: F811
    p, med_id = obra
    p.fijar_venta_contratada(med_id)
    return p


def _leer(p, ruta):
    return p.leer_certificacion(p.incorporar_documento(ruta))


def test_plantilla_del_usuario(venta, tmp_path):
    mapa, r = _leer(venta, excel(tmp_path / "C3.xlsx", SUYO, titulo_en=3))
    assert mapa.origen == "títulos" and mapa.fila_titulos == 3
    assert mapa.columnas["importe_origen"] == "E"  # no «Cantidad a origen» (D)
    assert r.total == 12100  # sin la fila de capítulo ni la ajena
    assert r.capitulos == 1 and [x[1] for x in r.no_casan] == ["OTRA"]
    # La suma no cuadra con el TOTAL del Excel (que incluye la línea ajena): se avisa.
    assert any("no coincide con el TOTAL del Excel" in a for a in r.avisos)


def test_plantilla_de_un_cliente_y_otra_con_porcentaje(venta, tmp_path):
    mapa, r = _leer(venta, excel(tmp_path / "Cli.xlsx", CLIENTE))
    assert set(mapa.columnas) >= {"codigo", "resumen", "importe_anterior", "importe_mes"}
    assert r.total == 10000 + 2100 + 500
    mapa, r = _leer(venta, excel(tmp_path / "Pct.xlsx", PORCENTAJE))
    assert r.por_partida["uta01"][2] == 10000 and r.por_partida["cnd01"][2] == 2100


def test_columnas_irreconocibles_las_dice_la_ia(venta, tmp_path):
    raro = [["A", "B", "C"], ["UTA01", "UTA", 8000], ["CND01", "Conducto", 600]]
    ruta = excel(tmp_path / "Raro.xlsx", raro)
    assert ce.mapear(ruta) is None
    pedido = []

    def ia(texto):
        pedido.append(texto)
        return {
            "hoja": "Cert",
            "fila_titulos": 1,
            "columnas": {"codigo": "A", "resumen": "B", "importe_origen": "C"},
        }

    venta.mapeador_ia = ia
    doc = venta.incorporar_documento(ruta)
    mapa, r = venta.leer_certificacion(doc)
    assert mapa.origen == "IA" and r.total == 8600
    assert "A1: A" in pedido[0] and "Hoja «Cert»" in pedido[0]  # títulos y filas de muestra
    # Una columna sin título en la fila de títulos no se acepta: no se adivina.
    venta.mapeador_ia = lambda t: {"hoja": "Cert", "fila_titulos": 1,
                                   "columnas": {"codigo": "A", "importe_origen": "F"}}  # fmt: skip
    with pytest.raises(OrdenRechazada, match="importe certificado a origen"):
        venta.leer_certificacion(doc)


def test_certificaciones_suman_la_venta_real(venta, tmp_path):
    p = venta
    doc1 = p.incorporar_documento(excel(tmp_path / "C1.xlsx", PORCENTAJE))
    mapa, r = p.leer_certificacion(doc1)
    p.importar_certificacion(doc1, 1, "2026-10-31", mapa, r)
    doc2 = p.incorporar_documento(excel(tmp_path / "C2.xlsx", CLIENTE))
    mapa, r = p.leer_certificacion(doc2)
    with pytest.raises(OrdenRechazada, match="Ya hay una certificación nº 1"):
        p.importar_certificacion(doc2, 1, "2026-11-30", mapa, r)
    p.importar_certificacion(doc2, 2, "2026-11-30", mapa, r)
    certs = p.certificaciones()
    assert [c["total_origen"] for c in certs] == [12100, 12600]
    assert [c["del_mes"] for c in certs] == [12100, 500]
    assert p.certificado_a_origen() == 12600
    assert p.foto_obra().certificado == 12600
    assert p.estado_paso("certificaciones").estado == "hecho"
    p.quitar_certificacion(certs[1]["id"])
    assert p.certificado_a_origen() == 12100
    p.deshacer()
    assert p.certificado_a_origen() == 12600


def test_rechazos(obra, tmp_path, pdf_3_paginas):  # noqa: F811
    p, med_id = obra
    ruta = excel(tmp_path / "C.xlsx", PORCENTAJE)
    with pytest.raises(OrdenRechazada, match="presupuesto contratado"):
        _leer(p, ruta)
    p.fijar_venta_contratada(med_id)
    with pytest.raises(OrdenRechazada, match="no es un Excel"):
        p.leer_certificacion(p.incorporar_documento(pdf_3_paginas))
    ajena = [["Código", "Descripción", "Importe a origen"], ["ZZZ", "Otra obra", 100]]
    with pytest.raises(OrdenRechazada, match="¿es la certificación de esta obra"):
        _leer(p, excel(tmp_path / "Ajena.xlsx", ajena))


def test_por_encima_del_100_se_avisa(venta, tmp_path):
    mas = [["Código", "Descripción", "Importe a origen"], ["UTA01", "UTA", 21000]]
    _, r = _leer(venta, excel(tmp_path / "Mas.xlsx", mas))
    assert any("UTA01" in a and "más del 100 %" in a for a in r.avisos)
