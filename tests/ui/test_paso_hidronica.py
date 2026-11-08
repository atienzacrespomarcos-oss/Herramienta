"""Paso «Sistema hidráulico» desde la ventana y diálogo real (docs/modules/hidronica.md)."""

from __future__ import annotations

import pytest
from openpyxl import load_workbook
from PySide6.QtCore import Qt
from tests.ui.test_paso_redes import ventana  # noqa: F401 (fixture)

from traza.app.ordenes import TIPOS_SISTEMA
from traza.rules.hidraulica import MATERIALES
from traza.ui.dialogos_hidronica import DialogoSistema

pytestmark = pytest.mark.ui


def test_recorrido_completo(ventana, tmp_path):  # noqa: F811
    v, q = ventana
    ph = v.pagina_hidronica
    v.ir_a_paso("hidronica")
    assert "Crea un sistema" in ph.resumen.text()
    assert not ph.a_excel.isEnabled()

    def definir(espacios, actual):
        codigos = {e["nombre"]: e["id"] for e in espacios}
        return {
            "titulo": "Clima",
            "tipo": "4_tubos",
            "circuitos": [
                {
                    "nombre": "Oficinas",
                    "espacios": [codigos["OFICINAS"]],
                    "unidades": 3,
                    "longitud_m": 25.0,
                    "perdida_terminal_kpa": 15.0,
                }
            ],
        }

    q.preparar("sistema_hidraulico", definir)
    ph.a_nuevo.trigger()
    # 4 tubos: frío y calor, cada uno con su sala de máquinas y su circuito.
    assert ph.tabla_circuitos.rowCount() == 2
    assert ph.tabla_resumen.rowCount() == 12
    assert ph.tabla_elementos.rowCount() > 60
    # DN y cantidad se ven (la tabla espera texto: con números salían vacías).
    assert ph.tabla_elementos.item(0, 3).text().startswith("DN")
    assert ph.tabla_elementos.item(0, 4).text() == "1"
    assert "1 circuito + reserva" in ph.tabla_resumen.item(2, 2).text()
    assert "elementos en el esquema" in ph.resumen.text()
    assert ph.a_excel.isEnabled()
    q.preparar("destino_excel", tmp_path / "Clima")
    ph.a_excel.trigger()
    assert any("Guardado" in t for t in q.informaciones)
    wb = load_workbook(tmp_path / "Clima.xlsx")
    assert "Elementos" in wb.sheetnames


def test_un_rechazo_reabre_el_dialogo_con_lo_escrito(ventana):  # noqa: F811
    v, q = ventana
    ph = v.pagina_hidronica
    v.ir_a_paso("hidronica")
    vistos = []

    def primero(espacios, actual):
        ids = {e["nombre"]: e["id"] for e in espacios}
        c = {
            "nombre": "C1",
            "espacios": [ids["OFICINAS"]],
            "unidades": 2,
            "longitud_m": 20.0,
            "perdida_terminal_kpa": 15.0,
        }
        return {"titulo": "Clima", "tipo": "2_tubos", "circuitos": [c, {**c, "nombre": "C2"}]}

    def segundo(espacios, actual):
        vistos.append(actual)  # vuelve con lo escrito, sin id (es nuevo)
        return {"titulo": actual["titulo"], "tipo": "2_tubos", "circuitos": actual["circuitos"][:1]}

    q.preparar("sistema_hidraulico", primero, segundo)
    ph.a_nuevo.trigger()
    assert any("dos veces" in a for a in q.avisos)
    assert vistos[0]["nombre"] == "Clima" and len(vistos[0]["circuitos"]) == 2
    assert ph.selector.count() == 1


def test_espacio_borrado_no_sale_como_id(qtbot):
    espacios = [{"id": "e1", "codigo": "ESP-001", "nombre": "Oficinas"}]
    actual = {
        "id": "s1",
        "nombre": "Clima",
        "tipo": "2_tubos",
        "material": "acero",
        "circuitos": [
            {
                "nombre": "C1",
                "espacios": ["e1", "borrado-uuid"],
                "unidades": 1,
                "longitud_m": 10.0,
                "perdida_terminal_kpa": 15.0,
                "exterior": False,
            }
        ],
    }
    d = DialogoSistema(None, espacios, actual)
    qtbot.addWidget(d)
    assert d.tabla.item(0, 1).text() == "ESP-001"
    assert "ya no existen" in d.error.text()
    d._aceptar()
    assert d.resultado["circuitos"][0]["espacios"] == ["e1"]


def test_dialogo_real(qtbot):
    espacios = [{"id": "e1", "codigo": "ESP-001", "nombre": "Oficinas"}]
    d = DialogoSistema(None, espacios, None)
    qtbot.addWidget(d)
    # Vocabulario atado al de la orden y las reglas.
    assert [d.tipo.itemData(i) for i in range(d.tipo.count())] == list(TIPOS_SISTEMA)
    assert [d.material.itemData(i) for i in range(d.material.count())] == list(MATERIALES)
    d.nombre.setText("Clima")
    d.tabla.item(0, 1).setText("ESP-999")
    d._aceptar()
    assert d.resultado is None and "ESP-999" in d.error.text()
    d.tabla.item(0, 1).setText("esp-001")
    d.tabla.item(0, 2).setText("2,5")
    d._aceptar()
    assert d.resultado is None and "entero" in d.error.text()
    d.tabla.item(0, 2).setText("4")
    d.tabla.item(0, 3).setText("32,5")
    d.tabla.item(0, 5).setCheckState(Qt.Checked)
    d.frio.setText("6/11")
    d._aceptar()
    r = d.resultado
    assert r["circuitos"] == [
        {
            "nombre": "C1",
            "espacios": ["e1"],
            "unidades": 4,
            "longitud_m": 32.5,
            "perdida_terminal_kpa": 15.0,
            "exterior": True,
        }
    ]
    assert (r["frio_impulsion"], r["frio_retorno"]) == (6.0, 11.0)
    # Al editar, vuelve con sus circuitos y sus códigos.
    actual = {**r, "id": "s1", "nombre": "Clima"}
    d2 = DialogoSistema(None, espacios, actual)
    qtbot.addWidget(d2)
    assert d2.tabla.rowCount() == 1 and d2.tabla.item(0, 1).text() == "ESP-001"
    d2._aceptar()
    assert d2.resultado["id"] == "s1" and d2.resultado["circuitos"] == r["circuitos"]
