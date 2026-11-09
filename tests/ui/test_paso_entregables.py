"""Paso «Entregables» desde la ventana (docs/modules/flujo.md, bloque 2)."""

from __future__ import annotations

import pytest
from docx import Document
from PySide6.QtCore import QSettings, Qt
from tests.integration.test_cargas_proyecto import ESTACION
from tests.integration.test_redes_proyecto import _nave_con_conductos
from tests.ui.test_ventana import PreguntasPreparadas

from traza.app.ordenes import CambiarEncargo, CrearNivel, FijarCargasEspacio
from traza.app.proyecto import Proyecto
from traza.ui.ventana import VentanaPrincipal

pytestmark = pytest.mark.ui


@pytest.fixture
def ventana(qtbot, tmp_path, pdf_3_paginas):
    q = PreguntasPreparadas()
    ajustes = QSettings(str(tmp_path / "ajustes.ini"), QSettings.IniFormat)
    v = VentanaPrincipal(q, ajustes)
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
    p.fijar_cargas(
        guia_documento_id=p.incorporar_documento(pdf_3_paginas),
        estacion_pagina=2,
        provincia="Madrid",
        altitud_obra=650,
        tipo_construccion="cte",
    )
    p._guias.clear()  # como al abrir el proyecto: la guía se lee al generar
    v._usar_proyecto(p)
    yield v, q, ajustes
    if v.proyecto is not None:
        v.proyecto.cerrar()


def _plantilla(tmp_path):
    doc = Document()
    doc.sections[0].header.paragraphs[0].text = "ALITER"
    ruta = tmp_path / "Aliter.docx"
    doc.save(str(ruta))
    return ruta


def test_paso_solo_en_diseno_y_ampliacion(ventana):
    v, _, _ = ventana
    claves = [v.lista_pasos.item(i).data(Qt.UserRole) for i in range(v.lista_pasos.count())]
    assert claves[-1] == "entregables"
    v.proyecto.ejecutar(CambiarEncargo("oferta"))
    v.refrescar()
    claves = [v.lista_pasos.item(i).data(Qt.UserRole) for i in range(v.lista_pasos.count())]
    assert "entregables" not in claves


def test_plantilla_recordada_y_entregables_generados(ventana, tmp_path):
    v, q, ajustes = ventana
    pe = v.pagina_entregables
    v.ir_a_paso("entregables")
    assert "ninguna" in pe.plantilla_texto.text()
    assert "cargas (Excel y PDF)" in pe.resumen.text()
    q.preparar("plantilla_word", _plantilla(tmp_path))
    pe.a_plantilla.trigger()
    assert ajustes.value("memoria/plantilla") == str(tmp_path / "Aliter.docx")
    assert "Aliter.docx" in pe.plantilla_texto.text()
    destino = tmp_path / "salida"
    destino.mkdir()
    q.preparar("carpeta_entregables", destino)
    pe.a_generar.trigger()
    assert not q.avisos, q.avisos
    # Excel del plano, Excel y PDF de cargas y la justificación en Word.
    assert q.informaciones[-1].startswith("4 fichero(s)")
    [carpeta] = list(destino.iterdir())
    word = next(carpeta.glob("*.docx"))
    assert Document(str(word)).sections[0].header.paragraphs[0].text == "ALITER"


def test_desactualizado_pregunta_y_plantilla_perdida_avisa(ventana, tmp_path):
    v, q, ajustes = ventana
    p = v.proyecto
    pe = v.pagina_entregables
    p.definir_red(
        titulo="Impulsión",
        tipo="impulsion",
        plano_id=p.planos()[0]["id"],
        capa_ejes="M-IMPULSION",
        bloques_terminales=["DIFUSOR"],
        bloque_equipo="UTA",
        nivel_id=p.niveles()[0]["id"],
    )
    p.ejecutar(FijarCargasEspacio(p.espacios()[0]["id"], "almacen", {}, {}))
    ajustes.setValue("memoria/plantilla", str(tmp_path / "no_existe.docx"))
    v.refrescar()
    assert "(no se encuentra)" in pe.plantilla_texto.text()
    destino = tmp_path / "salida"
    destino.mkdir()
    q.preparar("carpeta_entregables", destino)
    q.preparar("confirmar", False)
    pe.a_generar.trigger()
    assert list(destino.iterdir()) == [], "cancelado: no genera nada"
    q.preparar("carpeta_entregables", destino)
    q.preparar("confirmar", True)
    pe.a_generar.trigger()
    assert any("No se encuentra la plantilla" in a for a in q.avisos)
    assert len(list(destino.iterdir())) == 1


def test_solo_la_justificacion(ventana, tmp_path):
    v, q, _ = ventana
    q.preparar("destino_word", tmp_path / "J.docx")
    v.pagina_entregables.a_memoria.trigger()
    assert not q.avisos, q.avisos
    assert (tmp_path / "J.docx").exists()


def test_nombres_de_los_pasos_iguales_en_pantalla_y_en_los_avisos():
    from traza.app.flujo import NOMBRES
    from traza.ui.ventana import PASOS

    rotulos = {clave: texto for clave, texto, _ in PASOS}
    assert {k: rotulos[k] for k in NOMBRES} == NOMBRES


def test_menu_entregables_oculto_en_oferta(ventana):
    v, _, _ = ventana
    assert v.menu_entregables.menuAction().isVisible()
    v.proyecto.ejecutar(CambiarEncargo("oferta"))
    v.refrescar()
    assert not v.menu_entregables.menuAction().isVisible()
    assert not v.pagina_entregables.a_generar.isEnabled()
