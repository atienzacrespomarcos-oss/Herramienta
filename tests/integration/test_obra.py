"""Obra, bloque 1: crear obra, venta y coste objetivo (docs/modules/obra.md).

El coste objetivo es el Excel que el usuario exporta de Presto y reparte en paquetes. Aquí
se construye uno inventado con la misma estructura (títulos, grupos CanObj · PrObj ·
ImpObj, capítulos, partidas con su descompuesto y filas de cierre, una línea añadida a
mano y un precio «NO INCLUIDO»); los documentos reales del usuario no van al repositorio.
"""

from __future__ import annotations

import pytest
from openpyxl import Workbook

from traza.app.ordenes import CambiarEncargo, OrdenRechazada, QuitarMedicion
from traza.io import coste_presto

BC3_VENTA = (
    "~V|AUTOR|FIEBDC-3/2016|PRUEBA||ANSI|Prueba|2|\n"
    "~C|OBRA##||Nave|0||0|\n~C|01#||Climatización|0||0|\n"
    "~C|UTA01|ud|Unidad de tratamiento de aire|20000||0|\n"
    "~C|CND01|m2|Conducto de chapa galvanizada|60||0|\n"
    "~C|EXTRA|ud|Partida solo de venta|500||0|\n"
    "~D|OBRA##|01#\\1\\1\\|\n~D|01#|UTA01\\1\\1\\CND01\\1\\100\\EXTRA\\1\\1\\|\n"
)

#: Grupos: OBJETIVO y los paquetes «EQUIPOS», «CHAPA» y «MANO DE OBRA».
GRUPOS = ("OBJETIVO", "EQUIPOS", "CHAPA", "MANO DE OBRA")


def comparativo(
    ruta,
    *,
    sin_repartir=False,
    formula_sin_valor=False,
    cierre_en_valores=False,
    total=23200,
    extra=None,
):
    """Un comparativo como el del usuario. Las partidas llevan sus valores escritos (en el
    del usuario son fórmulas con su resultado guardado por Excel, que se lee igual)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Hoja1"
    ws.append([])  # fila 1
    fila2 = ["", None, None, None]
    fila4 = ["Código", "Nat", "Ud", "Resumen"]
    for nombre in GRUPOS:
        fila2 += [None, nombre, None]  # el nombre encima de PrObj, como en el suyo
        fila4 += ["CanObj", "PrObj", "ImpObj"]
    ws.append(fila2)
    ws.append(["Objetivo"])
    ws.append(fila4)

    def fila(codigo, nat, ud, resumen, grupos):
        valores = [codigo, nat, ud, resumen]
        for nombre in GRUPOS:
            valores += list(grupos.get(nombre) or (None, None, None))
        ws.append(valores)

    fila("1            ", "Capítulo", "", "OBRA DE PRUEBA", {})
    fila("CAP01        ", "Capítulo", "", "Climatización", {})
    # UTA: equipo 18000 + mano de obra 400 = 18400 (repartida del todo).
    fila("UTA01        ", "Partida", "ud", "Unidad de tratamiento de aire",
         {"OBJETIVO": (1, 18400, 18400), "EQUIPOS": (1, 18000, 18000),
          "MANO DE OBRA": (1, 400, 400)})  # fmt: skip
    fila("PUTA", "Material", "", "", {"OBJETIVO": (1, 18000, 18000)})
    fila("OHO", "Mano de obra", "", "", {"OBJETIVO": (10, 40, 400)})
    if cierre_en_valores:  # el Excel pegado como valores: el cierre lleva el precio escrito
        ws.append([None, None, None, "UTA01", 1, 18400, 18400])
    else:
        ws.append([None, None, None, "UTA01", 1, "=SUM(G7:G8)", "=ROUND(F9*E9,2)"])  # cierre
    # Conducto: chapa 30 + mano de obra 12 = 42 €/m2 × 100 m2.
    mo = None if sin_repartir else (100, 12, 1200)
    fila("CND01", "Partida", "m2", "Conducto de chapa galvanizada",
         {"OBJETIVO": (100, 42, 4200), "CHAPA": (100, 30, 3000), "MANO DE OBRA": mo})  # fmt: skip
    ws.append([None, None, None, "CND01", 100, "=SUM(G11:G12)", "=ROUND(F10*E10,2)"])
    # Desmontaje no incluido: texto en lugar de precio.
    fila("DESM01", "Partida", "ud", "Desmontaje de equipos",
         {"OBJETIVO": (0, "NO INCLUIDO DESMONTAJES", 0)})  # fmt: skip
    if formula_sin_valor:
        fila("FORM01", "Partida", "ud", "Partida con fórmula sin resultado",
             {"OBJETIVO": (1, "=G99", "=ROUND(F14*E14,2)")})  # fmt: skip
    ws.append([None, None, None, "CAP01", 1, "=G6+G10", "=ROUND(F15*E15,2)"])  # total
    # Línea añadida a mano (fuera de Presto): precio escrito, en OBJETIVO y en EQUIPOS.
    ws.append([None, None, None, "ELEVACIÓN DE EQUIPOS", 1, 600, 600, 1, 600, 600])
    for fila_extra in extra or ():
        ws.append(fila_extra)
    # El TOTAL con su resultado (en el del usuario, la fórmula con el valor guardado).
    ws.append([None, None, None, "TOTAL OBRA DE PRUEBA", 1, total, total])
    wb.save(ruta)
    return ruta


def test_lector_del_comparativo(tmp_path):
    r = coste_presto.leer(comparativo(tmp_path / "Costes.xlsx"))
    assert r.paquetes == ["EQUIPOS", "CHAPA", "MANO DE OBRA"]
    por = {p.codigo or p.resumen: p for p in r.partidas}
    assert set(por) == {"UTA01", "CND01", "DESM01", "ELEVACIÓN DE EQUIPOS"}
    assert por["UTA01"].importe == 18400 and por["UTA01"].paquetes == {
        "EQUIPOS": 18000,
        "MANO DE OBRA": 400,
    }
    assert por["UTA01"].capitulo == "CAP01 Climatización" and por["UTA01"].unidad == "ud"
    assert por["DESM01"].nota == "NO INCLUIDO DESMONTAJES" and por["DESM01"].importe == 0
    # La línea añadida a mano cuenta, con su paquete (el de sus columnas).
    elev = por["ELEVACIÓN DE EQUIPOS"]
    assert elev.importe == 600 and elev.paquetes == {"EQUIPOS": 600}
    assert elev.capitulo == "Añadido fuera de Presto"
    assert r.total == pytest.approx(18400 + 4200 + 600)
    assert r.por_paquete() == {"EQUIPOS": 18600, "CHAPA": 3000, "MANO DE OBRA": 1600}
    # Toda inferencia se declara: la línea añadida a mano sale en los avisos.
    assert r.avisos == [
        "Línea añadida a mano (fila 15): «ELEVACIÓN DE EQUIPOS», 600,00 €. Cuenta en el coste "
        "objetivo."
    ]


def test_cierre_en_valores_no_se_cuenta_dos_veces(tmp_path):
    r = coste_presto.leer(comparativo(tmp_path / "C.xlsx", cierre_en_valores=True))
    assert r.total == pytest.approx(23200)
    assert not any("no coincide" in a for a in r.avisos)


def test_suma_que_no_cuadra_con_el_total_se_avisa(tmp_path):
    r = coste_presto.leer(comparativo(tmp_path / "C.xlsx", total=25000))
    assert any("no coincide con el TOTAL del Excel (25000,00 €" in a for a in r.avisos)


def test_linea_a_mano_con_codigo_y_negativa(tmp_path):
    extra = [["X1", None, None, "DESCUENTO PACTADO", 1, -300, -300, 1, -300, -300]]
    r = coste_presto.leer(comparativo(tmp_path / "C.xlsx", extra=extra, total=22900))
    x1 = next(p for p in r.partidas if p.codigo == "X1")
    assert x1.importe == -300 and x1.capitulo == "Añadido fuera de Presto"
    assert any("X1 (fila" in a and "negativo" in a for a in r.avisos)
    assert not any("no coincide" in a for a in r.avisos)


def test_objetivo_sin_repartir_y_formula_sin_valor_se_avisan(tmp_path):
    r = coste_presto.leer(
        comparativo(tmp_path / "C.xlsx", sin_repartir=True, formula_sin_valor=True)
    )
    assert any("CND01" in a and "1200,00 €" in a and "sin repartir" in a for a in r.avisos)
    assert any("sin resultado guardado" in a for a in r.avisos)


def test_nombres_de_paquete(tmp_path):
    """Nombre encima de CanObj o ImpObj, columnas vacías entre grupos, un número encima
    (no es un nombre), un grupo sin nombre y dos con el mismo."""
    from openpyxl.utils import get_column_letter as letra

    def libro(nombres_y_columnas, ruta):
        wb = Workbook()
        ws = wb.active
        cab = {1: "Código", 2: "Nat", 3: "Ud", 4: "Resumen"}
        for col, (nombre, sobre) in nombres_y_columnas.items():
            cab |= {col: "CanObj", col + 1: "PrObj", col + 2: "ImpObj"}
            if nombre is not None:
                ws[f"{letra(col + sobre)}2"] = nombre
        for c, v in cab.items():
            ws.cell(4, c, v)
        ws.append(["P1", "Partida", "ud", "Una", 1, 10, 10])
        wb.save(ruta)
        return ruta

    r = coste_presto.leer(
        libro(
            {5: ("OBJETIVO", 1), 9: ("ENCIMA DE CAN", 0), 13: ("ENCIMA DE IMP", 2), 17: (None, 0)},
            tmp_path / "A.xlsx",
        )
    )
    assert r.paquetes == ["ENCIMA DE CAN", "ENCIMA DE IMP", "Paquete 3"]
    assert any("sin nombre" in a and "Paquete 3" in a for a in r.avisos)
    r = coste_presto.leer(libro({5: ("OBJETIVO", 1), 8: ("12345.6", 0)}, tmp_path / "N.xlsx"))
    assert r.paquetes == ["Paquete 1"]
    with pytest.raises(coste_presto.CosteNoReconocido, match="«MISMO» está dos veces"):
        coste_presto.leer(
            libro({5: ("OBJETIVO", 1), 8: ("MISMO", 1), 11: ("MISMO", 1)}, tmp_path / "D.xlsx")
        )


def test_lo_que_no_es_un_comparativo_se_rechaza(tmp_path):
    wb = Workbook()
    wb.active.append(["Otra cosa", 1, 2])
    wb.save(tmp_path / "X.xlsx")
    with pytest.raises(coste_presto.CosteNoReconocido, match="Código"):
        coste_presto.leer(tmp_path / "X.xlsx")


@pytest.fixture
def obra(proyecto, tmp_path):
    p = proyecto
    p.ejecutar(CambiarEncargo("obra"))
    bc3 = tmp_path / "Venta.bc3"
    bc3.write_bytes(BC3_VENTA.encode("cp1252"))
    med_id, _ = p.leer_medicion(p.incorporar_documento(bc3), "presupuesto")
    return p, med_id


def test_venta_coste_y_margen(obra, tmp_path):
    p, med_id = obra
    assert p.estado_paso("venta").texto == "Falta: elegir el presupuesto contratado"
    assert p.estado_paso("coste_objetivo").texto == "Falta: importar el Excel de coste objetivo"
    p.fijar_venta_contratada(med_id)
    p.importar_coste_objetivo(p.incorporar_documento(comparativo(tmp_path / "Costes.xlsx")))
    assert p.estado_paso("venta").estado == p.estado_paso("coste_objetivo").estado == "hecho"
    r = p.resumen_obra()
    assert r.venta == pytest.approx(20000 + 60 * 100 + 500)
    assert r.objetivo == pytest.approx(23200)
    assert r.margen == pytest.approx(26500 - 23200)
    assert r.margen_pct == pytest.approx(100 * 3300 / 26500)
    assert r.paquetes == {"EQUIPOS": 18600, "CHAPA": 3000, "MANO DE OBRA": 1600}
    # Lo que no casa por código se lista: EXTRA solo en venta; desmontaje y elevación, solo
    # en coste.
    assert [x.codigo for x in r.solo_en_venta] == ["extra"]
    assert {x.resumen for x in r.solo_en_coste} == {"Desmontaje de equipos", "ELEVACIÓN DE EQUIPOS"}
    uta = next(x for x in r.lineas if x.codigo == "uta01")
    assert uta.venta == 20000 and uta.objetivo == 18400 and uta.margen == 1600


def test_importar_otro_sustituye_y_se_deshace(obra, tmp_path):
    p, _ = obra
    p.importar_coste_objetivo(p.incorporar_documento(comparativo(tmp_path / "C1.xlsx")))
    otra = tmp_path / "v2"
    otra.mkdir()
    p.importar_coste_objetivo(
        p.incorporar_documento(comparativo(otra / "C2.xlsx", sin_repartir=True))
    )
    assert p.coste_objetivo()["documento_nombre"] == "C2.xlsx"
    assert p.resumen_obra().objetivo == pytest.approx(23200)
    p.deshacer()
    assert p.coste_objetivo()["documento_nombre"] == "C1.xlsx"
    p.rehacer()
    assert p.coste_objetivo()["documento_nombre"] == "C2.xlsx"
    p.deshacer()
    p.deshacer()  # la incorporación del segundo Excel
    p.deshacer()  # la importación del primero
    assert p.coste_objetivo() is None


def test_rechazos(obra, tmp_path, pdf_3_paginas):
    p, med_id = obra
    with pytest.raises(OrdenRechazada, match="no es un Excel"):
        p.importar_coste_objetivo(p.incorporar_documento(pdf_3_paginas))
    wb = Workbook()
    wb.active.append(["nada"])
    wb.save(tmp_path / "Nada.xlsx")
    with pytest.raises(OrdenRechazada, match="Nada.xlsx"):
        p.importar_coste_objetivo(p.incorporar_documento(tmp_path / "Nada.xlsx"))
    p.fijar_venta_contratada(med_id)
    with pytest.raises(OrdenRechazada, match="Ya es el presupuesto contratado"):
        p.fijar_venta_contratada(med_id)
    with pytest.raises(OrdenRechazada, match="Quitar presupuesto contratado"):
        p.ejecutar(QuitarMedicion(med_id))
    # Se puede dejar sin contratado (para releer el documento) y deshacer.
    p.quitar_venta_contratada()
    assert p.venta_contratada() is None
    p.ejecutar(QuitarMedicion(med_id))
    p.deshacer()
    p.deshacer()
    assert p.venta_contratada()["id"] == med_id
    p.quitar_venta_contratada()
    with pytest.raises(OrdenRechazada, match="no tiene presupuesto contratado"):
        p.quitar_venta_contratada()


def test_avisos_de_la_venta():
    from traza.app.obra import resumir

    partidas = [
        {"codigo": "A", "resumen": "a", "importe": 100.004, "estado": "exacta"},
        {"codigo": "", "resumen": "sin código", "importe": 50.0, "estado": "a_revisar"},
        {"codigo": "C", "resumen": "c", "importe": None, "estado": "exacta"},
    ]
    r = resumir(partidas, None, {"omitidas": 2, "total_documento": 200.0})
    assert r.venta == pytest.approx(150.0)  # cada línea al céntimo
    texto = " ".join(r.avisos_venta)
    partes = (
        "1 partida(s) del presupuesto contratado sin cantidad",
        "«a revisar»",
        "sin código",
        "2 línea(s) del documento",
        "no coincide con el total",
    )
    for parte in partes:
        assert parte in texto, parte
    # Ninguna con importe: la venta no consta (no «0 €»).
    r = resumir([{"codigo": "C", "resumen": "c", "importe": None}], None)
    assert r.venta is None and r.margen is None
    assert "la venta no consta" in r.avisos_venta[0]
