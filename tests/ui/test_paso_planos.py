"""Paso «Planos y espacios» recorrido desde la ventana, con las preguntas preparadas.

Se usa la nave de prueba de tests/integration/test_planos.py (medidas conocidas).
"""

from __future__ import annotations

import pytest
from openpyxl import load_workbook
from tests.integration.test_planos import SUP_OFICINAS, _nave
from tests.ui.test_ventana import PreguntasPreparadas

from traza.app.proyecto import Proyecto
from traza.ui.dialogos_planos import (
    CapaInfo,
    DatosCapas,
    DatosContorno,
    DialogoAltura,
    DialogoCapasPlano,
    DialogoContorno,
    DialogoNivel,
    InfoPlano,
)
from traza.ui.ventana import VentanaPrincipal

pytestmark = pytest.mark.ui


@pytest.fixture
def ventana(qtbot, tmp_path):
    q = PreguntasPreparadas()
    v = VentanaPrincipal(q)
    qtbot.addWidget(v)
    v._usar_proyecto(Proyecto.crear(tmp_path / "Nave", "Nave", "diseno"))
    yield v, q
    if v.proyecto is not None:
        v.proyecto.cerrar()


def _pasos(v) -> list[str]:
    return [v.lista_pasos.item(i).data(0x0100) for i in range(v.lista_pasos.count())]


def test_paso_planos_solo_en_encargos_con_diseno(ventana):
    v, q = ventana
    assert "planos" in _pasos(v)
    from traza.app.ordenes import CambiarEncargo

    v.proyecto.ejecutar(CambiarEncargo("presupuesto"))
    v.refrescar()
    assert "planos" not in _pasos(v)


def test_recorrido_completo(ventana, tmp_path):
    v, q = ventana
    pp = v.pagina_planos
    v.ir_a_paso("planos")
    # Sin DXF incorporado: se explica qué hacer.
    pp.a_leer.trigger()
    assert any("Incorpora antes el plano" in a for a in q.avisos)

    v.proyecto.incorporar_documento(_nave(tmp_path))
    v.refrescar()
    vista: dict = {}

    def capas(info):
        vista["info"] = info
        return DatosCapas("mm", ["A-ESPACIOS"], ["E-PILARES"], ["A-TEXTOS"])

    q.preparar("elegir", 0)
    q.preparar("capas_plano", capas)
    pp.a_leer.trigger()
    info = vista["info"]
    # El usuario ve la unidad propuesta y la medida con cada unidad para comprobarla.
    assert info.unidad_propuesta == "mm"
    ancho, fondo = info.medidas["mm"]
    assert 50 < ancho < 70 and 30 < fondo < 70
    capa = next(c for c in info.capas if c.nombre == "A-ESPACIOS")
    assert (capa.contornos, capa.textos) == (3, 0)
    assert pp.tabla_propuestas.rowCount() == 6

    # Confirmar sin nivel: se pide crearlo antes, y después se confirma con el texto del plano.
    fila = next(
        i
        for i in range(pp.tabla_propuestas.rowCount())
        if pp.tabla_propuestas.item(i, 3).text() == "ALMACÉN"
    )
    pp.pestanas.setCurrentWidget(pp.tabla_propuestas)
    pp.tabla_propuestas.setCurrentCell(fila, 0)
    q.preparar("nuevo_nivel", ("Planta baja", 0.0, 9.5))

    def confirmar(propuesta, niveles):
        assert propuesta["rol"] == "espacio" and propuesta["superficie"] == pytest.approx(1000)
        [(handle, texto)] = propuesta["textos"]
        return DatosContorno(niveles[0]["id"], None, handle)

    q.preparar("confirmar_contorno", confirmar)
    pp.a_confirmar.trigger()
    assert any("cuelgan de un nivel" in i for i in q.informaciones)
    assert pp.tabla_espacios.rowCount() == 1
    assert pp.tabla_espacios.item(0, 1).text() == "ALMACÉN"
    assert pp.tabla_espacios.item(0, 6).text() == "del nivel"

    # Oficinas con nombre propio y altura propia.
    fila = next(
        i
        for i in range(pp.tabla_propuestas.rowCount())
        if pp.tabla_propuestas.item(i, 3).text() == "OFICINAS"
    )
    pp.pestanas.setCurrentWidget(pp.tabla_propuestas)
    pp.tabla_propuestas.setCurrentCell(fila, 0)
    q.preparar("confirmar_contorno", lambda p, n: DatosContorno(n[0]["id"], "Oficinas", None))
    pp.a_confirmar.trigger()
    pp.pestanas.setCurrentWidget(pp.tabla_espacios)
    pp.tabla_espacios.setCurrentCell(1, 0)
    q.preparar("altura_espacio", ("propia", 3.0, None, None))
    pp.a_altura.trigger()
    alturas = {e["nombre"]: (e["altura"], e["altura_origen"]) for e in v.proyecto.espacios()}
    assert alturas == {"ALMACÉN": (9.5, "del nivel"), "Oficinas": (3.0, "propia")}

    # Descartar la corbata; bloques y longitudes; Excel.
    pp.pestanas.setCurrentWidget(pp.tabla_propuestas)
    corbata = next(
        i
        for i in range(pp.tabla_propuestas.rowCount())
        if "se corta" in pp.tabla_propuestas.item(i, 4).text()
    )
    pp.tabla_propuestas.setCurrentCell(corbata, 0)
    pp.a_descartar.trigger()
    assert pp.tabla_propuestas.rowCount() == 3  # quedan los tres pilares
    assert pp.tabla_bloques.rowCount() == 3
    destino = tmp_path / "plano.xlsx"
    q.preparar("destino_excel", destino)
    pp.a_exportar.trigger()
    ws = load_workbook(destino)["Espacios"]
    assert ws.cell(row=3, column=4).value == pytest.approx(SUP_OFICINAS)

    # Quitar y deshacer.
    pp.pestanas.setCurrentWidget(pp.tabla_espacios)
    pp.tabla_espacios.setCurrentCell(0, 0)
    q.preparar("confirmar", True)
    pp.a_quitar.trigger()
    assert pp.tabla_espacios.rowCount() == 1
    v.a_deshacer.trigger()
    assert pp.tabla_espacios.rowCount() == 2
    assert [t for t in q.titulos if t.startswith("Error")] == [], q.avisos


def test_dialogo_capas_unidad_y_exclusion(qtbot):
    info = InfoPlano(
        "Nave.dxf",
        (CapaInfo("A-ESPACIOS", 3, 0, 5, True), CapaInfo("A-TEXTOS", 0, 2, 2, True)),
        "mm",
        {"mm": (60.0, 40.0), "cm": (600.0, 400.0), "dm": (6000.0, 4000.0), "m": (60000.0, 40000.0)},
    )
    d = DialogoCapasPlano(None, info)
    qtbot.addWidget(d)
    assert d.unidad.currentData() == "mm" and "60 × 40 m" in d.medida.text()
    d.unidad.setCurrentIndex(3)
    assert "60000 × 40000 m" in d.medida.text()  # salta a la vista que no es la unidad
    d._aceptar()
    assert d.resultado is None and "al menos una capa" in d.error.text()
    d.marcar("A-ESPACIOS", "espacios")
    d.marcar("A-ESPACIOS", "obstaculos")  # una capa no puede ser las dos cosas
    d.marcar("A-TEXTOS", "textos")
    d.unidad.setCurrentIndex(0)
    d._aceptar()
    assert d.resultado == DatosCapas("mm", [], ["A-ESPACIOS"], ["A-TEXTOS"])


def test_dialogos_de_nivel_contorno_y_altura(qtbot):
    n = DialogoNivel(None)
    qtbot.addWidget(n)
    n.nombre.setText("Sótano")
    n.cota.setText("-3,5")
    n.altura.setText("3")
    n._aceptar()
    assert n.resultado == ("Sótano", -3.5, 3.0)

    c = DialogoContorno(
        None,
        {"rol": "obstaculo", "capa": "P", "superficie": 0.16, "textos": []},
        [{"id": "n1", "codigo": "NIV-01", "nombre": "PB"}],
    )
    qtbot.addWidget(c)
    c.altura.setText("2,5")
    c._aceptar()
    assert c.resultado == DatosContorno("n1", None, None, 2.5, None)

    e = DialogoContorno(None, {"rol": "espacio", "capa": "E", "superficie": 10, "textos": []}, [])
    qtbot.addWidget(e)
    e._aceptar()
    assert e.resultado is None and "nivel" in e.error.text()

    a = DialogoAltura(None, {"codigo": "ESP-001", "nombre": "A", "altura_origen": "del nivel"})
    qtbot.addWidget(a)
    a.opciones["inclinada"].setChecked(True)
    a.minima.setText("6")
    a._aceptar()
    assert a.resultado is None and "mínima y la máxima" in a.error.text()
    a.maxima.setText("10,5")
    a._aceptar()
    assert a.resultado == ("inclinada", None, 6.0, 10.5)
