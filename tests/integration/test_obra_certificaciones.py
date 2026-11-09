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


def sin_ia(_texto):
    """Las pruebas nunca llaman a la IA real: si hiciera falta, «no disponible»."""
    from traza.ai.claude_code import IaNoDisponible

    raise IaNoDisponible("IA no disponible en las pruebas")


@pytest.fixture
def venta(obra):  # noqa: F811
    p, med_id = obra
    p.fijar_venta_contratada(med_id)
    p.mapeador_ia = sin_ia
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
    p.mapeador_ia = sin_ia
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


# --- Revisión independiente (09-11-2026) ------------------------------------------------


def test_titulos_con_porcentaje_no_son_euros(venta, tmp_path):
    """«% anterior», «% actual», «Origen %» o «% del mes» no son importes."""
    pct = [
        ["Código", "Resumen", "Presupuesto", "% Anterior", "% Actual", "% Origen"],
        ["UTA01", "UTA", 20000, 0.3, 0.2, 0.5],
        ["CND01", "Conducto", 6000, 0.25, 0.1, 0.35],
    ]
    mapa, r = _leer(venta, excel(tmp_path / "P.xlsx", pct))
    assert "importe_anterior" not in mapa.columnas and "importe_mes" not in mapa.columnas
    assert r.total == 10000 + 2100  # % origen × presupuesto, no 0,30 + 0,20 €
    otros = [
        ["Código", "Resumen", "Presupuesto", "Origen %", "% del mes", "Uds. a origen"],
        ["UTA01", "UTA", 20000, 50, 20, 1],
    ]
    mapa, r = _leer(venta, excel(tmp_path / "O.xlsx", otros))
    assert set(mapa.columnas) == {"codigo", "resumen", "importe_presupuesto", "porcentaje_origen"}
    assert r.total == 10000  # ni «% del mes» ni «Uds. a origen» pasan por importes
    solo_pct = [["Código", "Resumen", "% del mes", "Uds. a origen"], ["UTA01", "UTA", 20, 1]]
    with pytest.raises(OrdenRechazada, match="no ha podido preguntar a la IA"):
        _leer(venta, excel(tmp_path / "SP.xlsx", solo_pct))  # sin importes: no se inventa


def test_lineas_sin_codigo_se_listan(venta, tmp_path):
    sin = [
        ["Código", "Descripción", "Importe a origen"],
        ["UTA01", "UTA", 10000],
        [None, "Partida añadida a mano", 8000],
        [None, "TOTAL", 18000],
    ]
    _, r = _leer(venta, excel(tmp_path / "S.xlsx", sin))
    assert r.total == 10000
    assert r.no_casan == [(3, "«Partida añadida a mano»", "Partida añadida a mano", 8000)]
    assert any("8000,00 €" in a for a in r.avisos)


def test_varias_hojas_lee_la_que_casa_con_la_venta(venta, tmp_path):
    wb = Workbook()
    resumen = wb.active
    resumen.title = "Resumen"
    for f in (["Código", "Descripción", "Importe a origen"], ["01", "Climatización", 12100]):
        resumen.append(f)
    detalle = wb.create_sheet("Detalle")
    for f in (["Código", "Descripción", "Importe a origen"], ["UTA01", "UTA", 10000],
              ["CND01", "Conducto", 2100]):  # fmt: skip
        detalle.append(f)
    wb.save(tmp_path / "Hojas.xlsx")
    mapa, r = _leer(venta, tmp_path / "Hojas.xlsx")
    assert mapa.hoja == "Detalle" and r.total == 12100
    assert any("«Resumen»" in a for a in r.avisos)


def test_total_en_la_columna_de_codigo_y_total_con_iva(venta, tmp_path):
    filas = [
        ["Código", "Descripción", "Importe a origen"],
        ["UTA01", "UTA", 10000],
        ["TOTAL", None, 10000],
        [None, "Total con IVA", 12100],
    ]
    _, r = _leer(venta, excel(tmp_path / "T.xlsx", filas))
    assert r.total_excel == (3, 10000) and not r.no_casan
    assert not any("no coincide" in a for a in r.avisos)


def test_porcentaje_con_formato_de_celda(venta, tmp_path):
    ruta = excel(tmp_path / "F.xlsx", [
        ["Código", "Resumen", "Presupuesto", "% a origen"],
        ["UTA01", "UTA", 20000, 0.01],  # 1 % con formato de porcentaje
    ])  # fmt: skip
    from openpyxl import load_workbook

    wb = load_workbook(ruta)
    wb.active["D2"].number_format = "0%"
    wb.save(ruta)
    _, r = _leer(venta, ruta)
    assert r.total == 200  # no 20000 × 1 / 1 = 20000


def test_mapa_de_la_ia_se_comprueba_con_las_mismas_reglas(venta, tmp_path):
    raro = [["A", "B", "Ritmo %", "D"], ["UTA01", "UTA", 50, 8000]]
    ruta = excel(tmp_path / "R.xlsx", raro)
    doc = venta.incorporar_documento(ruta)
    # Un «%» como importe, o el mismo código e importe en una columna: se descartan.
    for columnas in (
        {"codigo": "A", "importe_origen": "C"},
        {"codigo": "A", "importe_origen": "A"},
    ):
        venta.mapeador_ia = lambda t, c=columnas: {"hoja": "Cert", "fila_titulos": 1, "columnas": c}
        with pytest.raises(OrdenRechazada, match="importe certificado a origen"):
            venta.leer_certificacion(doc)
    venta.mapeador_ia = lambda t: {"hoja": "Cert", "fila_titulos": 1,
                                   "columnas": {"codigo": "A", "importe_origen": "D"}}  # fmt: skip
    _, r = venta.leer_certificacion(doc)
    assert r.total == 8000


def test_todo_a_cero_se_rechaza(venta, tmp_path):
    cero = [["Código", "Descripción", "Importe a origen"], ["UTA01", "UTA", 0], ["CND01", "C", 0]]
    with pytest.raises(OrdenRechazada, match="fórmulas sin el resultado guardado"):
        _leer(venta, excel(tmp_path / "Z.xlsx", cero))


def test_numeros_saltados_y_bajadas_se_anotan(venta, tmp_path):
    p = venta
    for n, filas, nombre in ((1, CLIENTE, "A"), (3, PORCENTAJE, "B")):
        doc = p.incorporar_documento(excel(tmp_path / f"{nombre}.xlsx", filas))
        mapa, r = p.leer_certificacion(doc)
        p.importar_certificacion(doc, n, "2026-11-30", mapa, r)
    c1, c3 = p.certificaciones()
    assert c1["nota"] == ""
    assert "incluye lo de las que faltan" in c3["nota"] and "menor que la anterior" in c3["nota"]
    assert c3["del_mes"] == 12100 - 12600


def test_formato_y_palabras():
    from traza.io.certificacion_excel import _formato_porcentaje, _tiene

    assert _formato_porcentaje("0%") and _formato_porcentaje("0.00%")
    assert not _formato_porcentaje('0"%"') and not _formato_porcentaje("0\\%")
    assert not _tiene("longitud total", ("ud",)) and _tiene("uds a origen", ("uds",))
    assert not _tiene("total relativa", ("iva",)) and _tiene("total con iva", ("iva",))
