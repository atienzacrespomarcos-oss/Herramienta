"""El paquete de prueba para Windows (scripts/ejemplos_prueba.py, docs/GUIA_DE_PRUEBA.md).

Lo que la Guía de prueba manda hacer con los «Ejemplos de prueba» se hace aquí con esos
mismos ficheros: diseño completo hasta entregables y revisión, oferta con modificado en BC3
y obra desde sus documentos. La guía del IDAE no se reproduce: se usa la estación de
prueba de las demás pruebas (con la guía real se comprobó a mano el 13-11-2026: 104
estaciones leídas).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from tests.integration.test_cargas_proyecto import ESTACION

from traza.app.ordenes import CrearModificado, CrearNivel, VariarPartida
from traza.app.proyecto import Proyecto

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def ejemplos(tmp_path):
    from scripts.ejemplos_prueba import generar

    return generar(tmp_path / "Ejemplos de prueba")


def test_recorrido_a_diseno_completo(ejemplos, tmp_path, pdf_3_paginas):
    p = Proyecto.crear(tmp_path / "Nave ejemplo", "Nave ejemplo", "diseno")
    try:
        p.lector_guia = lambda ruta: [ESTACION]
        plano = p.leer_plano(
            p.incorporar_documento(ejemplos["plano"]), "mm", ["A-ESPACIOS"], [], ["A-TEXTOS"]
        )
        nivel = CrearNivel("Planta baja", 0.0, 6.0)
        p.ejecutar(nivel)
        for prop in p.propuestas(plano):
            p.confirmar_contorno(plano, prop.handle, nivel.id, nombre=prop.nombre_sugerido.texto)
        assert sorted(e["nombre"] for e in p.espacios()) == ["ALMACÉN", "OFICINAS"]
        guia = p.incorporar_documento(pdf_3_paginas)
        p.fijar_cargas(
            guia_documento_id=guia,
            estacion_pagina=2,
            provincia="Madrid",
            altitud_obra=650,
            tipo_construccion="cte",
        )
        assert len(p.calcular_cargas().espacios) == 2
        red = p.definir_red(
            titulo="Impulsión oficinas",
            tipo="impulsion",
            plano_id=plano,
            capa_ejes="m-impulsion",
            bloques_terminales=["DIFUSOR"],
            bloque_equipo="UTA",
            nivel_id=nivel.id,
        )
        assert p.calcular_red(red).caudal_total_m3h > 0
        e = {x["nombre"]: x["id"] for x in p.espacios()}
        p.definir_sistema_hidraulico(
            titulo="Clima",
            tipo="2_tubos",
            circuitos=[
                {"nombre": "Oficinas", "espacios": [e["OFICINAS"]], "unidades": 4,
                 "longitud_m": 30.0, "perdida_terminal_kpa": 15.0},
                {"nombre": "Nave", "espacios": [e["ALMACÉN"]], "unidades": 6,
                 "longitud_m": 60.0, "perdida_terminal_kpa": 20.0},
            ],
        )  # fmt: skip
        salidas = p.salidas_propuestas()
        for s in salidas:
            s["potencia_kw"] = s["potencia_kw"] or 2.0  # la de la ficha, en la guía
        p.definir_subcuadro(titulo="SC Clima", salidas=salidas, longitud_alimentacion_m=30.0)
        _, avisos = p.esquema_control_desde_listado(ejemplos["puntos"], tmp_path / "Puntos")
        assert avisos == []
        carpeta, hechos = p.generar_entregables(tmp_path)
        assert [(n, err) for n, _, err in hechos if err] == []
        assert len(hechos) == 11
        p.emitir_revision("Para oferta")
        p.fijar_cargas_espacio(e["OFICINAS"], "reuniones")
        assert any(c.dato == "Uso" for c in p.comparar_revisiones(0))
    finally:
        p.cerrar()


def test_recorrido_b_oferta_y_modificado(ejemplos, tmp_path):
    p = Proyecto.crear(tmp_path / "Oferta", "Oferta", "oferta")
    try:
        m, _ = p.leer_medicion(p.incorporar_documento(ejemplos["oferta"]), "oferta", "Proveedor")
        partidas = {x["codigo"]: x["id"] for x in p.partidas(m)}
        assert {"UTA01", "CND01", "REJ01"} <= set(partidas)
        mod = CrearModificado(m, "Ampliación")
        p.ejecutar(mod)
        p.ejecutar(VariarPartida(mod.id, partidas["CND01"], 14, "medicion", "Falta un tramo"))
        ruta, _ = p.exportar_modificado_bc3(mod.id, tmp_path / "Modificado")
        assert ruta.is_file()
    finally:
        p.cerrar()


def test_recorrido_c_obra_desde_sus_documentos(ejemplos, tmp_path):
    """Lo que hace «Nueva obra desde documentos» con la carpeta «3 Obra»: cada fichero se
    reconoce por su contenido (sin IA)."""
    from traza.app import clasificar

    p = Proyecto.crear(tmp_path / "Obra", "Obra", "obra")
    try:
        docs = [
            p.incorporar_documento(ejemplos[k])
            for k in ("venta", "coste", "certificacion", "facturas")
        ]
        todos = {d["id"]: d for d in p.documentos()}
        propuestas = clasificar.clasificar(p, [todos[i] for i in docs])
        assert {x.tipo for x in propuestas} == {
            "presupuesto",
            "coste_objetivo",
            "certificacion",
            "facturas",
        }
        assert not any(x.con_ia() for x in propuestas)  # nada va a la IA
    finally:
        p.cerrar()


def test_cada_menu_y_accion_de_la_guia_existe(qtbot):
    """Vocabulario atado: lo que la guía manda pulsar («**Archivo → Nuevo proyecto…**»)
    existe en la ventana con ese mismo texto. Si cambia un menú, la guía queda desfasada y
    esta prueba lo dice."""
    from tests.ui.test_ventana import PreguntasPreparadas

    from traza.ui.ventana import PASOS, VentanaPrincipal

    v = VentanaPrincipal(PreguntasPreparadas())
    qtbot.addWidget(v)
    textos: set[str] = set()

    def recorrer(menu):
        for a in menu.actions():
            if a.menu():
                textos.add(a.menu().title().replace("&", ""))
                recorrer(a.menu())
            elif a.text():
                textos.add(a.text().replace("&", ""))

    for a in v.menuBar().actions():
        textos.add(a.text().replace("&", ""))
        if a.menu():
            recorrer(a.menu())
    textos |= {nombre for _, nombre, _ in PASOS}
    # Botones dentro de una página o un diálogo (no son menús).
    textos |= {"Calcular", "Proponer desde los equipos"}
    guia = (RAIZ / "docs" / "GUIA_DE_PRUEBA.md").read_text(encoding="utf-8")
    citadas = [m for m in re.findall(r"\*\*([^*]+)\*\*", guia) if "→" in m]
    assert len(citadas) > 15
    faltan = []
    for ruta in citadas:
        for trozo in (" ".join(x.split()) for x in ruta.split("→")):
            trozo = trozo.removeprefix("Paso ").strip()
            if trozo not in textos:
                faltan.append(f"{ruta}: «{trozo}»")
    assert faltan == []
