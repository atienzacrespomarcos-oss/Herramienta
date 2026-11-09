"""Pasos «Venta» y «Coste objetivo» desde la ventana (docs/modules/obra.md, bloque 1)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from tests.integration.test_obra import BC3_VENTA, comparativo
from tests.ui.test_ventana import PreguntasPreparadas

from traza.app.ordenes import CambiarEncargo
from traza.app.proyecto import Proyecto
from traza.ui.ventana import VentanaPrincipal

pytestmark = pytest.mark.ui


@pytest.fixture
def ventana(qtbot, tmp_path):
    q = PreguntasPreparadas()
    v = VentanaPrincipal(q)
    qtbot.addWidget(v)
    p = Proyecto.crear(tmp_path / "Obra", "Obra", "obra")
    bc3 = tmp_path / "Venta.bc3"
    bc3.write_bytes(BC3_VENTA.encode("cp1252"))
    p.leer_medicion(p.incorporar_documento(bc3), "presupuesto")
    p.incorporar_documento(comparativo(tmp_path / "Costes.xlsx"))
    v._usar_proyecto(p)
    yield v, q
    if v.proyecto is not None:
        v.proyecto.cerrar()


def _claves(v):
    return [v.lista_pasos.item(i).data(Qt.UserRole) for i in range(v.lista_pasos.count())]


def test_pasos_y_menu_solo_en_obra(ventana):
    v, _ = ventana
    claves = _claves(v)
    assert claves.index("mediciones") < claves.index("venta") < claves.index("coste_objetivo")
    assert "modificados" in claves and "entregables" not in claves
    assert v.menu_obra.menuAction().isVisible()
    v.proyecto.ejecutar(CambiarEncargo("oferta"))
    v.refrescar()
    assert "venta" not in _claves(v) and not v.menu_obra.menuAction().isVisible()


def test_elegir_venta_e_importar_coste(ventana):
    v, q = ventana
    pv, pc = v.pagina_venta, v.pagina_coste_objetivo
    v.ir_a_paso("venta")
    assert "Elige el presupuesto contratado" in pv.resumen.text()
    q.preparar("elegir", 0)
    pv.a_contratado.trigger()
    assert not q.avisos, q.avisos
    assert "Venta: 26.500,00 €" in pv.resumen.text() and pv.tabla.rowCount() == 1
    assert pv.a_quitar.isEnabled()
    v.ir_a_paso("coste_objetivo")
    q.preparar("elegir", 0)
    pc.a_importar.trigger()
    assert not q.avisos, q.avisos
    texto = pc.resumen.text()
    assert "Coste objetivo (Costes.xlsx, hoja «Hoja1»): 23.200,00 €" in texto
    assert "Margen previsto: 3.300,00 € (12,5 %)" in texto
    filas = {
        pc.tabla.item(i, 0).text(): pc.tabla.item(i, 1).text() for i in range(pc.tabla.rowCount())
    }
    assert filas == {"EQUIPOS": "18.600,00 €", "CHAPA": "3.000,00 €", "MANO DE OBRA": "1.600,00 €"}
    assert "1 solo en la venta, 2 solo en el coste" in pc.avisos.text()
    item = next(
        v.lista_pasos.item(i)
        for i in range(v.lista_pasos.count())
        if v.lista_pasos.item(i).data(Qt.UserRole) == "coste_objetivo"
    )
    assert item.text().startswith("✓ ")


def test_sin_excel_avisa(ventana, tmp_path):
    v, q = ventana
    # Un proyecto de obra sin Excel incorporado.
    p = Proyecto.crear(tmp_path / "Vacia", "Vacía", "obra")
    v._usar_proyecto(p)
    v.pagina_coste_objetivo.a_importar.trigger()
    assert any("Incorpora antes" in a for a in q.avisos)
    v.pagina_venta.a_contratado.trigger()
    assert any("No hay ningún presupuesto leído" in a for a in q.avisos)


def test_objetivo_cero_con_paquetes_no_rompe_la_pantalla(ventana, monkeypatch):
    v, q = ventana
    p = v.proyecto
    q.preparar("elegir", 0)
    v.pagina_coste_objetivo.a_importar.trigger()
    original = p.coste_objetivo

    def a_cero():
        c = original()
        for x in c["partidas"]:
            x["importe"] = 0.0  # fórmulas sin resultado guardado
        return c

    monkeypatch.setattr(p, "coste_objetivo", a_cero)
    v.refrescar()  # no lanza (antes, división por cero)
    assert not q.avisos
    filas = [
        v.pagina_coste_objetivo.tabla.item(i, 0).text()
        for i in range(v.pagina_coste_objetivo.tabla.rowCount())
    ]
    assert "(sin repartir en paquetes)" in filas
