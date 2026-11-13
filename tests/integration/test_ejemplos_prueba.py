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
        # Como manda la guía: primero ALMACÉN y luego OFICINAS.
        propuestas = {x.nombre_sugerido.texto: x for x in p.propuestas(plano)}
        for nombre in ("ALMACÉN", "OFICINAS"):
            prop = propuestas[nombre]
            p.confirmar_contorno(plano, prop.handle, nivel.id, nombre=nombre)
        # Los códigos que la guía manda escribir en los circuitos del sistema hidráulico.
        assert {e["nombre"]: e["codigo"] for e in p.espacios()} == {
            "ALMACÉN": "ESP-001",
            "OFICINAS": "ESP-002",
        }
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
    """Vocabulario atado: lo que la guía manda pulsar existe en la ventana con ese texto y
    **en ese menú** («**Planos → Nuevo nivel…**»: «Nuevo nivel…» dentro del menú Planos).
    Toda negrita de la guía que no es una ruta de menú tiene que ser un menú, una acción,
    un paso o un botón conocido. Revisión 13-11-2026: la primera versión miraba un conjunto
    plano y dejaba pasar negritas sin flecha."""
    from tests.ui.test_ventana import PreguntasPreparadas

    from traza.ui.ventana import PASOS, VentanaPrincipal

    v = VentanaPrincipal(PreguntasPreparadas())
    qtbot.addWidget(v)
    menus: dict[str, set[str]] = {}  # título del menú → textos de sus acciones

    def limpio(texto: str) -> str:
        return " ".join(texto.replace("&", "").split())

    def recorrer(menu):
        textos = menus.setdefault(limpio(menu.title()), set())
        for a in menu.actions():
            if a.menu():
                textos.add(limpio(a.menu().title()))
                recorrer(a.menu())
            elif a.text():
                textos.add(limpio(a.text()))

    for a in v.menuBar().actions():
        if a.menu():
            recorrer(a.menu())
    acciones = set().union(*menus.values())
    pasos = {nombre for _, nombre, _ in PASOS}
    # Botones dentro de una página o un diálogo (no son menús), con dónde están.
    botones = {"Calcular": "Cargas y ventilación", "Proponer desde los equipos": "Nuevo subcuadro…"}
    guia = (RAIZ / "docs" / "GUIA_DE_PRUEBA.md").read_text(encoding="utf-8")
    negritas = [limpio(m) for m in re.findall(r"\*\*([^*]+)\*\*", guia)]
    rutas = [n for n in negritas if "→" in n]
    assert len(rutas) > 20
    faltan = []
    for ruta in rutas:
        trozos = [x.strip() for x in ruta.split("→")]
        if trozos[0] in pasos and trozos[0] not in menus:
            trozos = trozos[1:]  # «Paso → Menú → Acción» (Control es paso y menú a la vez)
        for a, b in zip(trozos, trozos[1:], strict=False):
            if a in menus:
                if b not in menus[a]:
                    faltan.append(f"{ruta}: «{b}» no está en el menú {a}")
            elif botones.get(b) != a:
                faltan.append(f"{ruta}: «{a} → {b}» no es un menú ni un botón conocido")
        if trozos and trozos[0] not in menus:
            faltan.append(f"{ruta}: «{trozos[0]}» no es un menú")
    # Negritas sin flecha: lo que parece una acción (termina en «…») o un paso tiene que
    # existir; el resto es énfasis («todos», «No me envíes documentos reales.»).
    for n in negritas:
        if "→" in n or not (n.endswith("…") or n in pasos):
            continue
        if n not in menus and n not in acciones and n not in pasos and n not in botones:
            faltan.append(f"«{n}» no existe en la ventana")
    assert faltan == []


def test_la_guia_en_word_no_pierde_texto(tmp_path):
    """El conversor (scripts/guia_docx.py) conserva todas las palabras de la guía, en orden."""
    from docx import Document
    from scripts.guia_docx import convertir

    md = (RAIZ / "docs" / "GUIA_DE_PRUEBA.md").read_text(encoding="utf-8")
    ruta = convertir(RAIZ / "docs" / "GUIA_DE_PRUEBA.md", tmp_path / "Guía.docx")
    palabras_md = [
        w for w in re.sub(r"^\s*(#+|-|\d+\.)\s", " ", md.replace("**", ""), flags=re.M).split()
    ]
    texto_docx = " ".join(p.text for p in Document(str(ruta)).paragraphs).replace("• ", " ")
    palabras_docx = [w for w in re.sub(r"(^|\s)\d+\.\s", " ", texto_docx).split()]
    assert palabras_docx == [w for w in palabras_md if not re.fullmatch(r"\d+\.", w)]
