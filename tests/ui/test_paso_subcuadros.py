"""Paso «Subcuadros de clima» desde la ventana y diálogo real."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from tests.ui.test_paso_redes import ventana  # noqa: F401 (fixture)

from traza.rules.electricidad import METODOS, SUMINISTROS
from traza.ui.dialogos_subcuadros import DialogoSubcuadro

pytestmark = pytest.mark.ui


def test_recorrido(ventana, tmp_path):  # noqa: F811
    v, q = ventana
    ps = v.pagina_subcuadros
    v.ir_a_paso("subcuadros")
    assert "Crea un subcuadro" in ps.resumen.text() and not ps.a_unifilar.isEnabled()
    salida = {"nombre": "Enfriadora", "potencia_kw": 45.0, "fases": 3, "longitud_m": 15.0,
              "motor": True, "variador": True}  # fmt: skip
    malo = {"titulo": "SC", "salidas": [{**salida, "fases": 2}]}
    vistos = []

    def corregir(propuestas, actual):
        vistos.append(actual)
        return {"titulo": actual["titulo"], "salidas": [salida], "longitud_alimentacion_m": 30.0}

    q.preparar("subcuadro", malo, corregir)
    ps.a_nuevo.trigger()
    assert any("1 o 3 fases" in a for a in q.avisos)  # rechazo: vuelve con lo escrito
    assert vistos[0]["nombre"] == "SC"
    assert ps.tabla.rowCount() == 1 and "CUMPLE" in ps.resumen.text()
    assert ps.tabla.item(0, 4).text() == "C100"  # con variador: curva C
    # Cambiar y aceptar sin tocar nada cierra el diálogo (antes volvía a abrirse en bucle).
    q.preparar(
        "subcuadro",
        lambda propuestas, actual: {
            "titulo": actual["nombre"],
            "salidas": actual["salidas"],
            "suministro": actual["suministro"],
            "longitud_alimentacion_m": actual["longitud_alimentacion_m"],
            "metodo_alimentacion": actual["metodo_alimentacion"],
            "id": actual["id"],
        },
    )
    ps.a_cambiar.trigger()
    q.preparar("destino_dxf", tmp_path / "Unifilar")
    ps.a_unifilar.trigger()
    assert (tmp_path / "Unifilar.dxf").exists()


def test_dialogo_real(qtbot):
    propuestas = [
        {"nombre": "Bomba C1", "potencia_kw": 0, "fases": 3, "longitud_m": 20.0, "motor": True,
         "variador": True, "cos_phi": 0.85, "metodo": "E"},
    ]  # fmt: skip
    d = DialogoSubcuadro(None, lambda: propuestas, None)
    qtbot.addWidget(d)
    assert [d.suministro.itemData(i) for i in range(d.suministro.count())] == list(SUMINISTROS)
    assert [d.metodo.itemData(i) for i in range(d.metodo.count())] == list(METODOS)
    d.nombre.setText("SC")
    d._proponer()
    assert d.tabla.rowCount() == 1 and "potencia eléctrica" in d.error.text()
    d._aceptar()
    assert d.resultado is None and "Bomba C1" in d.error.text()  # sin potencia
    d.tabla.item(0, 1).setText("2,2")
    d.tabla.item(0, 2).setText("3")
    d.tabla.item(0, 6).setCheckState(Qt.Unchecked)
    d._aceptar()
    s = d.resultado["salidas"][0]
    assert s["potencia_kw"] == 2.2 and s["variador"] is False and s["metodo"] == "E"
    d._proponer()  # ya está: no se repite
    assert d.tabla.rowCount() == 1
    d.anadir({"nombre": "Bomba C1"})  # nombre repetido: lo dice el diálogo
    d._aceptar()
    assert "nombre propio" in d.error.text()
