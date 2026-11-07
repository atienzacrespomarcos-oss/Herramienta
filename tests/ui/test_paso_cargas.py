"""Paso «Cargas y ventilación» recorrido desde la ventana, con las preguntas preparadas, y
los diálogos reales. Nave y estación (inventada) de tests/integration/test_cargas_proyecto.py.
"""

from __future__ import annotations

import pytest
from openpyxl import load_workbook
from tests.integration.test_cargas_proyecto import ESTACION, _nave
from tests.ui.test_ventana import PreguntasPreparadas

from traza.app.cargas import propuestas
from traza.app.ordenes import AJUSTES_CARGAS, CambiarEncargo, CrearNivel
from traza.app.proyecto import Proyecto
from traza.rules.usos import POR_CLAVE
from traza.ui.dialogos_cargas import DatosEspacioCargas, DialogoClima, DialogoEspacioCargas
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
        p.incorporar_documento(_nave(tmp_path)), "mm", ["A-ESPACIOS"], [], ["A-TEXTOS"]
    )
    nivel = CrearNivel("Planta baja", 0.0, 8.0)
    p.ejecutar(nivel)
    for prop in p.propuestas(plano_id):
        p.confirmar_contorno(plano_id, prop.handle, nivel.id, nombre=prop.nombre_sugerido.texto)
    p.incorporar_documento(pdf_3_paginas)
    v._usar_proyecto(p)
    yield v, q
    if v.proyecto is not None:
        v.proyecto.cerrar()


def _pasos(v) -> list[str]:
    return [v.lista_pasos.item(i).data(0x0100) for i in range(v.lista_pasos.count())]


def _celdas(tabla, columna):
    return [tabla.item(f, columna).text() for f in range(tabla.rowCount())]


def test_recorrido_completo(ventana, tmp_path):
    v, q = ventana
    pc = v.pagina_cargas
    v.ir_a_paso("cargas")
    assert "Falta el clima" in pc.resumen.text()
    assert _celdas(pc.tabla_espacios, 3) == ["Almacén / logística (picking)", "Oficina abierta"]

    def elegir_clima(guias, cargar, actual):
        [e] = cargar(guias[0]["id"])
        return dict(
            guia_documento_id=guias[0]["id"],
            estacion_pagina=e.pagina,
            provincia="Madrid",
            altitud_obra=650,
            tipo_construccion="nave_panel",
        )

    q.preparar("clima_obra", elegir_clima)
    pc.a_clima.trigger()
    assert "zona D3" in pc.resumen.text() and "simultánea" in pc.resumen.text()
    assert all(float(t.replace(",", ".")) > 0 for t in _celdas(pc.tabla_espacios, 8))
    assert pc.a_excel.isEnabled()

    pc.tabla_espacios.setCurrentCell(1, 0)
    assert pc.tabla_partidas.rowCount() > 5 and pc.tabla_datos.rowCount() > 10

    def cambiar(espacio, uso, ajustes, fachadas, propuestas_de):
        assert espacio.endswith("OFICINAS") and uso == "oficina_abierta"
        assert propuestas_de("despacho")["personas"][0] > 0
        return DatosEspacioCargas("despacho", {"personas": 3}, {"O": True})

    q.preparar("cargas_espacio", cambiar)
    pc.a_espacio.trigger()
    assert _celdas(pc.tabla_espacios, 4)[1] == "tuyo"
    assert "O 8" in _celdas(pc.tabla_espacios, 12)[1]

    q.preparar("destino_excel", tmp_path / "cargas.xlsx")
    pc.a_excel.trigger()
    assert load_workbook(tmp_path / "cargas.xlsx")["Espacios"].max_row == 3
    q.preparar("destino_pdf", tmp_path / "cargas.pdf")
    pc.a_pdf.trigger()
    assert (tmp_path / "cargas.pdf").stat().st_size > 1000
    assert not [t for t in q.titulos if t.startswith("Error")]


def test_guia_sin_leer_pide_calcular(ventana):
    v, q = ventana
    p = v.proyecto
    guia = next(d for d in p.documentos() if d["extension"] == ".pdf")
    p.fijar_cargas(
        guia_documento_id=guia["id"],
        estacion_pagina=2,
        provincia="Madrid",
        altitud_obra=650,
        tipo_construccion="cte",
    )
    p._guias.clear()  # como al abrir el proyecto otra vez
    v.refrescar()
    assert "Pulsa «Calcular»" in v.pagina_cargas.resumen.text()
    v.pagina_cargas.a_calcular.trigger()
    assert "zona D3" in v.pagina_cargas.resumen.text()


def test_paso_solo_en_encargos_con_diseno(ventana):
    v, _ = ventana
    assert "cargas" in _pasos(v)
    v.proyecto.ejecutar(CambiarEncargo("presupuesto"))
    v.refrescar()
    assert "cargas" not in _pasos(v)
    assert not v.menu_cargas.menuAction().isVisible()


def test_dialogo_clima_real(qtbot):
    d = DialogoClima(
        None, [{"id": "g", "nombre_original": "guia.pdf"}], lambda _id: [ESTACION], None
    )
    qtbot.addWidget(d)
    # La estación está a 600 m: Madrid por encima de 500 m es D3; por debajo, C3.
    assert d.provincia.currentText() == "Madrid" and d.zona.text() == "D3"
    d.altitud.setText("450")
    assert d.zona.text() == "C3"
    d.altitud.setText("650")
    d.recuperador.setText("50")
    d._aceptar()
    assert d.resultado["estacion_pagina"] == 2 and d.resultado["recuperacion"] == 0.5
    assert d.resultado["altitud_obra"] == 650 and d.resultado["tipo_construccion"] == "cte"


def test_dialogo_clima_con_guia_que_no_se_lee(qtbot):
    def falla(_id):
        raise ValueError("Ese PDF no contiene fichas de estación")

    d = DialogoClima(None, [{"id": "g", "nombre_original": "otro.pdf"}], falla, None)
    qtbot.addWidget(d)
    assert "no contiene" in d.error.text()
    d._aceptar()
    assert d.resultado is None


def test_dialogo_espacio_real_y_vocabulario(qtbot):
    # Las claves que propone el cálculo son exactamente las que el diálogo y la orden admiten.
    assert set(propuestas(POR_CLAVE["despacho"], 50)) == set(AJUSTES_CARGAS)

    def de(clave):
        return {k: (v, f) for k, (_c, v, _u, f) in propuestas(POR_CLAVE[clave], 50).items()}

    d = DialogoEspacioCargas(None, "ESP-001", "despacho", {"personas": 4}, {"N": False}, de)
    qtbot.addWidget(d)
    assert d.campos["personas"].text() == "4"
    assert "Propuesto" in d.campos["equipos_w_m2"].placeholderText()
    assert "ASHRAE" in d.campos["equipos_w_m2"].toolTip()
    d.campos["t_verano_c"].setText("24,5")
    d.fachadas["S"].setCurrentIndex(1)
    d._aceptar()
    assert d.resultado.ajustes == {"personas": 4, "t_verano_c": 24.5}
    assert d.resultado.fachadas == {"N": False, "S": True}
    d2 = DialogoEspacioCargas(None, "ESP-001", "despacho", {}, {}, de)
    qtbot.addWidget(d2)
    d2.sin_calefaccion.setChecked(True)
    d2.campos["t_invierno_c"].setText("15")
    d2._aceptar()
    assert d2.resultado is None and "Sin calefacción" in d2.error.text()
