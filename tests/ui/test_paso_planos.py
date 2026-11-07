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


# --- Revisión independiente del bloque C (07-11-2026) -------------------------------------


def _leer_nave(v, q, tmp_path):
    v.proyecto.incorporar_documento(_nave(tmp_path))
    v.refrescar()
    q.preparar("elegir", 0)
    q.preparar("capas_plano", DatosCapas("mm", ["A-ESPACIOS"], ["E-PILARES"], ["A-TEXTOS"]))
    v.pagina_planos.a_leer.trigger()


def test_quitar_un_nivel_desde_su_pestana(ventana):
    v, q = ventana
    pp = v.pagina_planos
    q.preparar("nuevo_nivel", ("Entreplanta mal creada", 4.0, 3.0))
    pp.a_nivel.trigger()
    pp.pestanas.setCurrentWidget(pp.tabla_niveles)
    pp.tabla_niveles.setCurrentCell(0, 0)
    assert pp.a_quitar.isEnabled()
    q.preparar("confirmar", True)
    pp.a_quitar.trigger()
    assert v.proyecto.niveles() == []


def test_varios_textos_dentro_no_se_preselecciona_ninguno(qtbot):
    d = DialogoContorno(
        None,
        {
            "rol": "espacio",
            "capa": "E",
            "superficie": 20,
            "textos": [("1A", "OFICINAS"), ("1B", "WC")],
        },
        [{"id": "n1", "codigo": "NIV-01", "nombre": "PB"}],
    )
    qtbot.addWidget(d)
    d._aceptar()
    assert d.resultado is None and "Elige el nombre" in d.error.text()
    d.nombre.setCurrentIndex(2)
    d._aceptar()
    assert d.resultado == DatosContorno("n1", None, "1B")


def test_sin_unidad_declarada_hay_que_elegirla(qtbot):
    info = InfoPlano("X.dxf", (CapaInfo("E", 1, 0, 1, True),), None, {"mm": (1.0, 1.0)})
    d = DialogoCapasPlano(None, info)
    qtbot.addWidget(d)
    d.marcar("E", "espacios")
    d._aceptar()
    assert d.resultado is None and "Elige la unidad" in d.error.text()
    d.unidad.setCurrentIndex(d.unidad.findData("m"))
    d._aceptar()
    assert d.resultado.unidad == "m"


def test_tras_descartar_no_queda_elegida_otra_propuesta(ventana, tmp_path):
    v, q = ventana
    pp = v.pagina_planos
    _leer_nave(v, q, tmp_path)
    pp.pestanas.setCurrentWidget(pp.tabla_propuestas)
    pp.tabla_propuestas.setCurrentCell(0, 0)
    pp.a_descartar.trigger()
    # La fila elegida desaparece: no se elige otra en su lugar (no confirmar a ciegas).
    assert pp.tabla_propuestas.currentRow() == -1
    assert not pp.a_confirmar.isEnabled()
    # Y una elegida que sigue existiendo, sigue elegida tras refrescar.
    pp.tabla_propuestas.setCurrentCell(2, 0)
    elegida = pp.tabla_propuestas.item(2, 0).data(0x0100)
    v.refrescar()
    assert pp.tabla_propuestas.item(pp.tabla_propuestas.currentRow(), 0).data(0x0100) == elegida


def test_menu_planos_solo_en_encargos_con_diseno(ventana):
    v, q = ventana
    from traza.app.ordenes import CambiarEncargo

    assert v.menu_planos.menuAction().isVisible()
    v.proyecto.ejecutar(CambiarEncargo("instalacion"))
    v.refrescar()
    assert not v.menu_planos.menuAction().isVisible()
    assert not v.pagina_planos.a_leer.isEnabled() and not v.pagina_planos.a_nivel.isEnabled()


def test_plano_que_ya_no_se_puede_leer_no_deja_la_ventana_a_medias(ventana, tmp_path):
    v, q = ventana
    _leer_nave(v, q, tmp_path)
    p = v.proyecto
    doc_id = p.planos()[0]["documento_id"]
    ruta = p.ruta_documento(doc_id)
    ruta.chmod(0o644)
    ruta.write_bytes(b"esto ya no es un dxf")
    p._planos_dxf.clear()  # como en una sesión nueva
    v.refrescar()
    assert "No se puede leer el plano" in v.pagina_planos.resumen.text()
    assert v.pagina_planos.tabla_propuestas.rowCount() == 0
    assert v.tabla_historial.rowCount() > 0  # el resto de la ventana sí se refrescó


def test_unidades_atadas_entre_lector_ordenes_y_dialogo():
    from traza.app.ordenes import UNIDADES_PLANO
    from traza.io.dxf import UNIDADES
    from traza.ui.dialogos_planos import UNIDADES as UNIDADES_DIALOGO

    assert tuple(UNIDADES) == UNIDADES_PLANO == UNIDADES_DIALOGO
