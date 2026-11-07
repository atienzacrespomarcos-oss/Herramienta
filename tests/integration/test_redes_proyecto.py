"""Redes de aire en el proyecto: ejes y bloques de un DXF, caudales desde las cargas (o el
atributo CAUDAL), cálculo, listado Excel y protección del nivel.

Nave de tests/integration/test_cargas_proyecto.py más una capa de ejes de impulsión: la UTA
(bloque) fuera de las oficinas, un montante hasta y = 4 m y una T con dos difusores.
"""

from __future__ import annotations

import ezdxf
import pytest
from openpyxl import load_workbook
from tests.integration.test_cargas_proyecto import ESTACION

from traza.app.ordenes import CrearNivel, OrdenRechazada, QuitarDePlano
from traza.app.redes import CALOR_SENSIBLE_AIRE


def _nave_con_conductos(tmp_path, caudal_attrib: str | None = None):
    doc = ezdxf.new("R2013")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    for capa in ("A-ESPACIOS", "A-TEXTOS", "M-IMPULSION", "M-DIFUSORES"):
        doc.layers.add(capa)
    esp = {"layer": "A-ESPACIOS"}
    msp.add_lwpolyline([(0, 0), (40000, 0), (40000, 25000), (0, 25000)], close=True, dxfattribs=esp)
    msp.add_lwpolyline(
        [(40200, 0), (50000, 0), (50000, 8000), (40200, 8000)], close=True, dxfattribs=esp
    )
    for texto, xy in (("ALMACÉN", (20000, 12000)), ("OFICINAS", (45000, 6000))):
        msp.add_text(texto, dxfattribs={"layer": "A-TEXTOS", "height": 300}).set_placement(xy)
    dif = doc.blocks.new("DIFUSOR")
    dif.add_circle((0, 0), 300)
    dif.add_attdef("CAUDAL", (0, 0))
    doc.blocks.new("UTA").add_lwpolyline([(0, 0), (1000, 0), (1000, 1000), (0, 1000)], close=True)
    ejes = {"layer": "M-IMPULSION"}
    msp.add_lwpolyline([(45000, 10000), (45000, 4000)], dxfattribs=ejes)
    msp.add_line((42500, 4000), (47500, 4000), dxfattribs=ejes)
    msp.add_blockref("UTA", (45000, 10000), dxfattribs={"layer": "M-DIFUSORES"})
    for i, x in enumerate((42500, 47500)):
        ref = msp.add_blockref("DIFUSOR", (x, 4000), dxfattribs={"layer": "M-DIFUSORES"})
        if caudal_attrib and i == 0:
            ref.add_auto_attribs({"CAUDAL": caudal_attrib})
    ruta = tmp_path / "Nave.dxf"
    doc.saveas(ruta)
    return ruta


@pytest.fixture
def red(proyecto, tmp_path, pdf_3_paginas):
    p = proyecto
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
    p.lector_guia = lambda ruta: [ESTACION]
    p.fijar_cargas(
        guia_documento_id=guia,
        estacion_pagina=2,
        provincia="Madrid",
        altitud_obra=650,
        tipo_construccion="cte",
    )
    red_id = p.definir_red(
        titulo="Impulsión oficinas",
        tipo="impulsion",
        plano_id=plano_id,
        capa_ejes="m-impulsion",
        bloques_terminales=["DIFUSOR"],
        bloque_equipo="UTA",
        nivel_id=nivel.id,
    )
    return p, red_id, plano_id, nivel.id


def test_red_calculada_desde_las_cargas(red):
    p, red_id, _, _ = red
    r = p.calcular_red(red_id)
    cargas = {c.nombre: c for c in p.calcular_cargas().espacios}
    ofi = cargas["OFICINAS"]
    presion = p.calcular_cargas().condiciones["normal"].presion_pa
    # Carga del local sin la del aire exterior (que trata el equipo).
    local = sum(p.sensible_w for p in ofi.verano.partidas if p.concepto != "Ventilación")
    q = max(ofi.aire_exterior_m3h, local / (CALOR_SENSIBLE_AIRE * presion / 101_325 * 10) * 3600)
    assert r.caudal_total_m3h == pytest.approx(q)
    assert [t.caudal_m3h for t in r.terminales] == pytest.approx([q / 2, q / 2])
    assert all("OFICINAS" in t.espacio for t in r.terminales)
    c = r.calculo
    assert len(c.tramos) == 3 and c.terminal_critico in ("D01", "D02")
    raiz = next(t for t in c.tramos if t.tramo.padre is None)
    assert raiz.tramo.longitud_m == pytest.approx(6.0)
    assert raiz.tramo.caudal_m3s * 3600 == pytest.approx(q)
    assert c.presion_necesaria_pa > 40  # al menos el difusor (RITE)
    assert r.sfp_exigida == 4 and 0 < r.rendimiento_minimo < 1
    assert sum(m.longitud_m for m in r.medicion) == pytest.approx(11.0)


def test_atributo_caudal_manda_y_excel(proyecto, tmp_path, pdf_3_paginas):
    p = proyecto
    plano_id = p.leer_plano(
        p.incorporar_documento(_nave_con_conductos(tmp_path, "600")),
        "mm",
        ["A-ESPACIOS"],
        [],
        ["A-TEXTOS"],
    )
    nivel = CrearNivel("Planta baja", 0.0, 3.0)
    p.ejecutar(nivel)
    for prop in p.propuestas(plano_id):
        p.confirmar_contorno(plano_id, prop.handle, nivel.id, nombre=prop.nombre_sugerido.texto)
    red_id = p.definir_red(
        titulo="Imp",
        tipo="impulsion",
        plano_id=plano_id,
        capa_ejes="M-IMPULSION",
        bloques_terminales=["DIFUSOR"],
        bloque_equipo="UTA",
    )
    r = p.calcular_red(red_id)  # sin clima: solo el atributo da caudal
    assert r.avisos[0].startswith("Sin cargas")
    con = [t for t in r.terminales if t.caudal_m3h > 0]
    assert len(con) == 1 and con[0].caudal_m3h == 600 and "CAUDAL" in con[0].origen_caudal
    assert any("sin caudal" in a for a in r.avisos)
    x = p.exportar_red_excel(red_id, tmp_path / "Red 1.0")
    wb = load_workbook(x)
    assert x.name == "Red 1.0.xlsx"
    assert wb.sheetnames == [
        "Resumen",
        "Tramos",
        "Accesorios",
        "Terminales",
        "Medición",
        "Hipótesis",
    ]
    tramos = list(wb["Tramos"].iter_rows(min_row=2, values_only=True))
    assert all(isinstance(f[6], int | float) for f in tramos)  # número, no texto


def test_validaciones_y_nivel_protegido(red):
    p, red_id, plano_id, nivel_id = red
    with pytest.raises(OrdenRechazada, match="capa"):
        p.definir_red(
            titulo="X",
            tipo="retorno",
            plano_id=plano_id,
            capa_ejes="NO-EXISTE",
            bloques_terminales=["DIFUSOR"],
        )
    with pytest.raises(OrdenRechazada, match="bloque"):
        p.definir_red(
            titulo="X",
            tipo="retorno",
            plano_id=plano_id,
            capa_ejes="M-IMPULSION",
            bloques_terminales=["REJILLA"],
        )
    with pytest.raises(OrdenRechazada, match="Ya hay una red"):
        p.definir_red(
            titulo="Impulsión oficinas",
            tipo="retorno",
            plano_id=plano_id,
            capa_ejes="M-IMPULSION",
            bloques_terminales=["DIFUSOR"],
        )
    with pytest.raises(OrdenRechazada, match="0,1 a 5"):
        p.definir_red(
            titulo="Y",
            tipo="retorno",
            plano_id=plano_id,
            capa_ejes="M-IMPULSION",
            bloques_terminales=["DIFUSOR"],
            friccion_objetivo=20,
        )
    # Un nivel vacío que usa una red no se quita (su red quedaría sin nivel).
    vacio = CrearNivel("Cubierta", 6.0, 3.0)
    p.ejecutar(vacio)
    otra = p.definir_red(
        titulo="Extracción cubierta",
        tipo="extraccion",
        plano_id=plano_id,
        capa_ejes="M-IMPULSION",
        bloques_terminales=["DIFUSOR"],
        nivel_id=vacio.id,
    )
    with pytest.raises(OrdenRechazada, match="red de aire"):
        p.ejecutar(QuitarDePlano(vacio.id))
    p.borrar_red(otra)
    # Cambiar la red (mismo id) y borrarla, con deshacer.
    p.definir_red(
        id=red_id,
        titulo="Impulsión oficinas",
        tipo="extraccion",
        plano_id=plano_id,
        capa_ejes="M-IMPULSION",
        bloques_terminales=["DIFUSOR"],
        bloque_equipo="UTA",
        nivel_id=nivel_id,
    )
    r = p.calcular_red(red_id)
    ofi = {c.nombre: c for c in p.calcular_cargas().espacios}["OFICINAS"]
    assert r.caudal_total_m3h == pytest.approx(ofi.aire_exterior_m3h)  # extracción
    p.borrar_red(red_id)
    assert p.redes() == []
    p.deshacer()
    assert p.redes()[0]["tipo"] == "extraccion"


def test_espacio_sin_terminales_y_terminal_suelto(red):
    p, red_id, _, _ = red
    r = p.calcular_red(red_id)
    # El almacén tiene carga y ningún difusor de esta red: se dice.
    assert any("ALMACÉN" in a and "no tiene terminales" in a for a in r.avisos)
