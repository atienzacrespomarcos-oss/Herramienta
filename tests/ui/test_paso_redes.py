"""Paso «Redes de aire» recorrido desde la ventana y diálogo real. Nave con conductos de
tests/integration/test_redes_proyecto.py."""

from __future__ import annotations

import pytest
from openpyxl import load_workbook
from tests.integration.test_cargas_proyecto import ESTACION
from tests.integration.test_redes_proyecto import _nave_con_conductos
from tests.ui.test_ventana import PreguntasPreparadas

from traza.app.ordenes import CrearNivel
from traza.app.proyecto import Proyecto
from traza.ui.dialogos_redes import SIN_BLOQUE, DialogoRed
from traza.ui.ventana import VentanaPrincipal

pytestmark = pytest.mark.ui


@pytest.fixture
def ventana(qtbot, tmp_path, pdf_3_paginas):
    q = PreguntasPreparadas()
    v = VentanaPrincipal(q)
    qtbot.addWidget(v)
    p = Proyecto.crear(tmp_path / "Nave", "Nave", "diseno")
    p.lector_guia = lambda ruta: [ESTACION]
    plano_id = p.leer_plano(
        p.incorporar_documento(_nave_con_conductos(tmp_path)),
        "mm",
        ["A-ESPACIOS"],
        [],
        ["A-TEXTOS"],
    )
    nivel = CrearNivel("Planta baja", 0.0, 3.0)
    p.ejecutar(nivel)
    for prop in p.propuestas(plano_id):
        p.confirmar_contorno(plano_id, prop.handle, nivel.id, nombre=prop.nombre_sugerido.texto)
    guia = p.incorporar_documento(pdf_3_paginas)
    p.fijar_cargas(
        guia_documento_id=guia,
        estacion_pagina=2,
        provincia="Madrid",
        altitud_obra=650,
        tipo_construccion="cte",
    )
    v._usar_proyecto(p)
    yield v, q
    if v.proyecto is not None:
        v.proyecto.cerrar()


def test_recorrido_completo(ventana, tmp_path):
    v, q = ventana
    pr = v.pagina_redes
    v.ir_a_paso("redes")
    assert "Crea una red" in pr.resumen.text()
    assert not pr.a_excel.isEnabled()

    def definir(planos, niveles, info, actual):
        capas, bloques = info(planos[0]["id"])
        assert "M-IMPULSION" in capas and {"DIFUSOR", "UTA"} <= set(bloques)
        return {
            "titulo": "Impulsión oficinas",
            "tipo": "impulsion",
            "plano_id": planos[0]["id"],
            "nivel_id": niveles[0]["id"],
            "capa_ejes": "M-IMPULSION",
            "bloques_terminales": ["DIFUSOR"],
            "bloque_equipo": "UTA",
        }

    q.preparar("red_aire", definir)
    pr.a_nueva.trigger()
    assert pr.tabla_tramos.rowCount() == 3 and pr.tabla_terminales.rowCount() == 2
    assert "Pa en la red" in pr.resumen.text() and "SFP 4" in pr.resumen.text()
    assert pr.a_excel.isEnabled()
    pr.tabla_tramos.setCurrentCell(1, 0)  # dibuja el tramo elegido sin error

    q.preparar(
        "red_aire",
        lambda planos, niveles, info, actual: {
            **{
                "titulo": actual["nombre"],
                "tipo": "retorno",
                "plano_id": actual["plano_id"],
                "nivel_id": actual["nivel_id"],
                "capa_ejes": actual["capa_ejes"],
                "bloques_terminales": actual["bloques_terminales"],
                "bloque_equipo": actual["bloque_equipo"],
            },
            "id": actual["id"],
        },
    )
    pr.a_cambiar.trigger()
    assert "(Retorno)" in pr.selector.currentText()

    q.preparar("destino_dxf", tmp_path / "red.dxf")
    pr.a_autocad.trigger()
    assert (tmp_path / "red.dxf").exists() and (tmp_path / "red.lsp").exists()
    assert any("TRAZA_RED" in i for i in q.informaciones)
    q.preparar("destino_excel", tmp_path / "red.xlsx")
    pr.a_excel.trigger()
    assert load_workbook(tmp_path / "red.xlsx")["Tramos"].max_row == 4
    q.preparar("confirmar", True)
    pr.a_borrar.trigger()
    assert pr.selector.count() == 0
    assert not [t for t in q.titulos if t.startswith("Error")]


def test_sin_plano_se_explica(qtbot, tmp_path):
    q = PreguntasPreparadas()
    v = VentanaPrincipal(q)
    qtbot.addWidget(v)
    v._usar_proyecto(Proyecto.crear(tmp_path / "N", "N", "diseno"))
    try:
        v.ir_a_paso("redes")
        v.pagina_redes.a_nueva.trigger()
        assert any("lee el plano DXF" in a for a in q.avisos)
    finally:
        v.proyecto.cerrar()


def test_dialogo_real(qtbot):
    planos = [{"id": "p1", "documento_nombre": "Nave.dxf"}]
    niveles = [{"id": "n1", "codigo": "NIV-01", "nombre": "Planta baja"}]
    d = DialogoRed(None, planos, niveles, lambda _p: (["M-IMP"], ["DIFUSOR", "UTA"]), None)
    qtbot.addWidget(d)
    d._aceptar()
    assert d.resultado is None and "nombre" in d.error.text()
    d.nombre.setText("Imp 1")
    d._aceptar()
    assert d.resultado is None and "bloque" in d.error.text()
    from PySide6.QtCore import Qt

    d.terminales.item(0).setCheckState(Qt.Checked)
    assert d.equipo.itemText(0) == SIN_BLOQUE
    d.equipo.setCurrentIndex(2)  # UTA
    d.alto.setText("350")
    d.friccion.setText("1,2")
    d._aceptar()
    r = d.resultado
    assert r["bloques_terminales"] == ["DIFUSOR"] and r["bloque_equipo"] == "UTA"
    assert r["alto_maximo"] == pytest.approx(0.35) and r["friccion_objetivo"] == 1.2
    assert "id" not in r
    assert r["criterio_caudal"] == "cargas" and r["renovaciones"] is None


def test_dialogo_renovaciones_solo_en_ventilacion(qtbot):
    from PySide6.QtCore import Qt

    from traza.app.ordenes import CRITERIOS_CAUDAL

    planos = [{"id": "p1", "documento_nombre": "Nave.dxf"}]
    d = DialogoRed(None, planos, [], lambda _p: (["M-EXT"], ["REJILLA"]), None)
    qtbot.addWidget(d)
    # Las opciones del diálogo son exactamente las que admite la orden.
    assert [d.criterio.itemData(i) for i in range(d.criterio.count())] == list(CRITERIOS_CAUDAL)
    # Impulsión de climatización (lo que sale por defecto): no se ofrecen renovaciones.
    assert not d.criterio.isEnabled() and not d.renovaciones.isEnabled()
    d.tipo.setCurrentIndex(d.tipo.findData("retorno"))
    assert not d.criterio.isEnabled()
    d.tipo.setCurrentIndex(d.tipo.findData("extraccion"))
    assert d.criterio.isEnabled() and not d.renovaciones.isEnabled()
    d.criterio.setCurrentIndex(d.criterio.findData("renovaciones"))
    assert d.renovaciones.isEnabled()
    d.nombre.setText("Extracción nave")
    d.terminales.item(0).setCheckState(Qt.Checked)
    d.renovaciones.setText("7,5")
    d._aceptar()
    assert d.resultado["criterio_caudal"] == "renovaciones"
    assert d.resultado["renovaciones"] == 7.5
    # Volver a climatización + impulsión deja el criterio en «cargas» y sin renovaciones.
    d.tipo.setCurrentIndex(d.tipo.findData("impulsion"))
    assert d.criterio.currentData() == "cargas" and not d.renovaciones.isEnabled()
    d._aceptar()
    assert d.resultado["criterio_caudal"] == "cargas" and d.resultado["renovaciones"] is None


def test_renovaciones_deshabilitadas_no_bloquean_aceptar(qtbot):
    from PySide6.QtCore import Qt

    planos = [{"id": "p1", "documento_nombre": "Nave.dxf"}]
    d = DialogoRed(None, planos, [], lambda _p: (["M-EXT"], ["REJILLA"]), None)
    qtbot.addWidget(d)
    d.tipo.setCurrentIndex(d.tipo.findData("extraccion"))
    d.criterio.setCurrentIndex(d.criterio.findData("renovaciones"))
    d.renovaciones.setText("abc")
    d.criterio.setCurrentIndex(d.criterio.findData("volumen"))
    d.nombre.setText("Extracción nave")
    d.terminales.item(0).setCheckState(Qt.Checked)
    d._aceptar()
    assert d.resultado is not None and d.resultado["criterio_caudal"] == "volumen"
    assert d.resultado["renovaciones"] is None
