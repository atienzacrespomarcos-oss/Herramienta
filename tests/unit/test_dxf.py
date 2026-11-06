"""Lector DXF: planos construidos con ezdxf (R2013, la versión de AutoCAD 2013–2017 del
usuario) con resultado conocido. Fuente de los códigos: Autodesk, DXF Reference."""

from __future__ import annotations

import math
from pathlib import Path

import ezdxf
import pytest

from traza.io.dxf import DxfError, leer_dxf


def _nuevo(insunits: int = 4):
    doc = ezdxf.new("R2013")
    doc.header["$INSUNITS"] = insunits
    doc.header["$MEASUREMENT"] = 1
    return doc, doc.modelspace()


def _guardar(doc, tmp_path: Path, nombre="plano.dxf") -> Path:
    ruta = tmp_path / nombre
    doc.saveas(ruta)
    return ruta


def test_unidades_propuestas_y_medida_total(tmp_path):
    doc, msp = _nuevo(4)
    msp.add_lwpolyline([(0, 0), (80000, 0), (80000, 40000), (0, 40000)], close=True)
    p = leer_dxf(_guardar(doc, tmp_path))
    assert p.unidad_propuesta == "mm" and p.medicion == 1
    # Con la unidad buena, la nave mide 80 x 40 m; con una mala, salta a la vista.
    assert p.medida_total("mm") == pytest.approx((80, 40))
    assert p.medida_total("m") == pytest.approx((80000, 40000))


def test_sin_unidad_declarada_se_avisa(tmp_path):
    doc, msp = _nuevo(0)
    msp.add_line((0, 0), (1, 0))
    p = leer_dxf(_guardar(doc, tmp_path))
    assert p.unidad_propuesta is None
    assert any("no declara una unidad métrica" in a for a in p.avisos)


def test_contorno_rectangular_en_mm(tmp_path):
    doc, msp = _nuevo(4)
    doc.layers.add("A-ESPACIOS")
    msp.add_lwpolyline(
        [(0, 0), (40000, 0), (40000, 25000), (0, 25000)],
        close=True,
        dxfattribs={"layer": "A-ESPACIOS"},
    )
    p = leer_dxf(_guardar(doc, tmp_path))
    [c] = p.contornos
    assert c.capa == "A-ESPACIOS" and c.entidad == "LWPOLYLINE" and c.marcada_cerrada
    m = c.contorno.escalado(0.001)
    assert m.area == pytest.approx(1000) and m.perimetro == pytest.approx(130)
    assert p.capas["A-ESPACIOS"].longitud == pytest.approx(130000)


def test_contorno_con_arco_y_en_espejo(tmp_path):
    # Nave 20 x 10 m (en m) con un lado en semicírculo hacia fuera (bulge 1, código 42).
    doc, msp = _nuevo(6)
    puntos = [(0, 0, 0, 0, 0), (20, 0, 0, 0, 1.0), (20, 10, 0, 0, 0), (0, 10, 0, 0, 0)]
    msp.add_lwpolyline(puntos, format="xyseb", close=True)
    # La misma figura dibujada con extrusión (0,0,-1) (espejo): en WCS la x cambia de
    # signo y el arco de sentido, pero la superficie es la misma.
    msp.add_lwpolyline(puntos, format="xyseb", close=True, dxfattribs={"extrusion": (0, 0, -1)})
    p = leer_dxf(_guardar(doc, tmp_path))
    normal, espejo = p.contornos
    esperado = 200 + math.pi * 25 / 2
    assert normal.contorno.area == pytest.approx(esperado)
    assert espejo.contorno.area == pytest.approx(esperado)
    # El semicírculo sobresale hacia x > 20 en el normal y hacia x < -20 en el espejo.
    assert normal.contorno.contiene(24, 5) and not normal.contorno.contiene(-24, 5)
    assert espejo.contorno.contiene(-24, 5) and not espejo.contorno.contiene(24, 5)


def test_polilinea_abierta_que_cierra_de_hecho(tmp_path):
    doc, msp = _nuevo(6)
    msp.add_lwpolyline([(0, 0), (5, 0), (5, 4), (0, 4), (0, 0)])  # sin bit «Closed»
    msp.add_lwpolyline([(0, 0), (5, 0), (5, 4)])  # abierta de verdad
    p = leer_dxf(_guardar(doc, tmp_path))
    [c] = p.contornos
    assert not c.marcada_cerrada and c.contorno.area == pytest.approx(20)
    assert len(c.contorno.vertices) == 4


def test_circulo_es_contorno(tmp_path):
    doc, msp = _nuevo(6)
    doc.layers.add("PILARES")
    msp.add_circle((10, 10), 0.25, dxfattribs={"layer": "PILARES"})
    p = leer_dxf(_guardar(doc, tmp_path))
    [c] = p.contornos
    assert c.entidad == "CIRCLE" and c.contorno.area == pytest.approx(math.pi * 0.0625)
    assert c.contorno.contiene(10, 10) and not c.contorno.contiene(10.3, 10)


def test_polyline_2d_con_arco_y_3d_en_planta(tmp_path):
    doc, msp = _nuevo(6)
    pl = msp.add_polyline2d([(0, 0), (2, 0), (2, 2), (0, 2)], close=True)
    pl.vertices[1].dxf.bulge = 1.0  # semicírculo hacia fuera en el lado x = 2
    msp.add_polyline3d([(0, 0, 0), (3, 0, 5), (3, 4, 5)], dxfattribs={"layer": "TUB"})
    p = leer_dxf(_guardar(doc, tmp_path))
    [c] = p.contornos
    assert c.entidad == "POLYLINE" and c.contorno.area == pytest.approx(4 + math.pi / 2)
    # La 3D se mide en planta: 3 + 4, aunque suba 5 m.
    assert p.capas["TUB"].longitud == pytest.approx(7)


def test_longitudes_por_capa(tmp_path):
    doc, msp = _nuevo(6)
    for capa in ("CONDUCTOS", "CURVAS"):
        doc.layers.add(capa)
    msp.add_line((0, 0), (3, 4), dxfattribs={"layer": "CONDUCTOS"})
    msp.add_arc((0, 0), 2, 0, 90, dxfattribs={"layer": "CONDUCTOS"})  # π
    msp.add_lwpolyline(
        [(0, 0, 0, 0, 1.0), (4, 0, 0, 0, 0), (4, 3, 0, 0, 0)],
        format="xyseb",
        dxfattribs={"layer": "CONDUCTOS"},
    )  # semicírculo de radio 2 (2π) + 3
    msp.add_spline([(0, 0), (1, 1), (2, 0), (3, 1)], dxfattribs={"layer": "CURVAS"})
    p = leer_dxf(_guardar(doc, tmp_path))
    assert p.capas["CONDUCTOS"].longitud == pytest.approx(5 + math.pi + 2 * math.pi + 3)
    assert p.capas["CURVAS"].longitud == 0 and p.capas["CURVAS"].sin_medir == 1
    assert any("SPLINE/ELLIPSE no se miden" in a for a in p.avisos)
    assert p.capas["CONDUCTOS"].entidades == {"LINE": 1, "ARC": 1, "LWPOLYLINE": 1}


def test_textos_y_mtext(tmp_path):
    doc, msp = _nuevo(6)
    msp.add_text("ALMACÉN", dxfattribs={"height": 0.5, "layer": "TEXTOS"}).set_placement((5, 5))
    msp.add_mtext("{\\fArial|b1;OFICINAS}\\PPlanta baja", dxfattribs={"insert": (20, 8, 0)})
    msp.add_text("   ")  # vacío: no cuenta
    p = leer_dxf(_guardar(doc, tmp_path))
    textos = {t.texto: (t.x, t.y, t.capa) for t in p.textos}
    assert textos["ALMACÉN"] == (5, 5, "TEXTOS")
    assert textos["OFICINAS\nPlanta baja"][:2] == (20, 8)
    assert len(p.textos) == 2


def test_bloques_con_atributos(tmp_path):
    doc, msp = _nuevo(6)
    b = doc.blocks.new("DIFUSOR")
    b.add_circle((0, 0), 0.3)
    b.add_attdef("CAUDAL", (0, 0))
    for x in (2, 4, 6):
        ins = msp.add_blockref("DIFUSOR", (x, 1), dxfattribs={"layer": "DIF", "rotation": 90})
        ins.add_auto_attribs({"CAUDAL": "300 m3/h"})
    p = leer_dxf(_guardar(doc, tmp_path))
    assert [(x.nombre, x.capa, x.x, x.rotacion) for x in p.bloques] == [
        ("DIFUSOR", "DIF", 2, 90),
        ("DIFUSOR", "DIF", 4, 90),
        ("DIFUSOR", "DIF", 6, 90),
    ]
    assert p.bloques[0].atributos == (("CAUDAL", "300 m3/h"),)
    # El círculo de dentro del bloque no es un contorno del plano.
    assert p.contornos == []


def test_plano_dentro_de_un_bloque_se_avisa(tmp_path):
    doc, msp = _nuevo(6)
    b = doc.blocks.new("PLANTA")
    for i in range(60):
        b.add_line((i, 0), (i, 10))
    msp.add_blockref("PLANTA", (0, 0))
    msp.add_line((0, 0), (1, 1))
    p = leer_dxf(_guardar(doc, tmp_path))
    assert any("dentro del bloque «PLANTA»" in a and "DESCOMP" in a for a in p.avisos)


def test_xref_se_avisa(tmp_path):
    doc, msp = _nuevo(6)
    doc.add_xref_def("arquitectura.dwg", "ARQ")
    msp.add_blockref("ARQ", (0, 0))
    p = leer_dxf(_guardar(doc, tmp_path))
    assert any("«ARQ» es una referencia externa" in a for a in p.avisos)


def test_entidad_que_no_esta_en_planta_se_omite(tmp_path):
    doc, msp = _nuevo(6)
    msp.add_circle((0, 0), 1, dxfattribs={"extrusion": (1, 0, 0)})  # en un alzado
    msp.add_circle((5, 5), 1)
    p = leer_dxf(_guardar(doc, tmp_path))
    assert len(p.contornos) == 1
    assert any("no están dibujadas en planta" in a for a in p.avisos)


def test_capas_apagadas_o_congeladas(tmp_path):
    doc, msp = _nuevo(6)
    doc.layers.add("APAGADA").off()
    doc.layers.add("CONGELADA").freeze()
    doc.layers.add("NORMAL")
    p = leer_dxf(_guardar(doc, tmp_path))
    assert not p.capas["APAGADA"].visible and not p.capas["CONGELADA"].visible
    assert p.capas["NORMAL"].visible


def test_fichero_que_no_es_dxf(tmp_path):
    ruta = tmp_path / "x.dxf"
    ruta.write_bytes(b"esto no es un dxf")
    with pytest.raises(DxfError):
        leer_dxf(ruta)


def test_extension_del_dibujo(tmp_path):
    doc, msp = _nuevo(6)
    msp.add_line((-5, 2), (10, 2))
    msp.add_text("X").set_placement((3, 30))
    p = leer_dxf(_guardar(doc, tmp_path))
    assert p.extension == (-5, 2, 10, 30)


# --- Revisión independiente (06-11-2026) -------------------------------------------------


def test_texto_centrado_se_situa_en_su_punto_de_alineacion(tmp_path):
    from ezdxf.enums import TextEntityAlignment

    doc, msp = _nuevo(6)
    t = msp.add_text("OFICINA", dxfattribs={"height": 0.3})
    t.set_placement((10, 5), align=TextEntityAlignment.MIDDLE_CENTER)
    t.dxf.insert = (8.5, 4.8, 0)  # lo que AutoCAD guarda: izquierda de la línea base
    a = msp.add_text("NAVE", dxfattribs={"height": 0.3})
    a.set_placement((0, 0), (20, 0), align=TextEntityAlignment.ALIGNED)
    p = leer_dxf(_guardar(doc, tmp_path))
    pos = {x.texto: (x.x, x.y) for x in p.textos}
    assert pos["OFICINA"] == (10, 5)
    assert pos["NAVE"] == (10, 0)  # entre los dos puntos


def test_linea_con_extrusion_no_se_descarta(tmp_path):
    # En LINE la extrusión es la dirección del grosor: la línea sigue en planta.
    doc, msp = _nuevo(6)
    msp.add_line((0, 0), (3, 4), dxfattribs={"extrusion": (1, 0, 0), "layer": "L"})
    p = leer_dxf(_guardar(doc, tmp_path))
    assert p.capas["L"].longitud == pytest.approx(5)
    assert not any("no están dibujadas en planta" in a for a in p.avisos)


def test_espacio_papel_se_avisa(tmp_path):
    doc, msp = _nuevo(6)
    doc.layouts.get("Layout1").add_line((0, 0), (1, 1))
    p = leer_dxf(_guardar(doc, tmp_path))
    assert any("espacio papel" in a and "«Layout1» (1)" in a for a in p.avisos)


def test_polilinea_ajustada_con_spline_usa_su_curva(tmp_path):
    doc, msp = _nuevo(6)
    pl = msp.add_polyline2d([(0, 0), (4, 0), (4, 3)], dxfattribs={"layer": "P"})
    pl.dxf.flags |= 4  # ajustada con spline
    # Vértice de control (flag 16) que no es de la curva y alargaría la medida.
    pl.append_vertex((100, 100), dxfattribs={"flags": 16})
    p = leer_dxf(_guardar(doc, tmp_path))
    assert p.capas["P"].longitud == pytest.approx(7)
    assert any("ajustada" in a for a in p.avisos)


def test_contorno_que_se_corta_se_marca_y_el_nulo_no_se_propone(tmp_path):
    doc, msp = _nuevo(6)
    msp.add_lwpolyline([(0, 0), (2, 2), (2, 0), (0, 2)], close=True)  # corbata
    msp.add_lwpolyline([(0, 0), (1, 0), (2, 0)], close=True)  # en línea: sin superficie
    msp.add_circle((5, 5), 0)  # radio 0
    p = leer_dxf(_guardar(doc, tmp_path))
    [c] = p.contornos
    assert c.autointersecante
    assert any("se cortan a sí mismos" in a for a in p.avisos)
    assert any("2 contorno(s) cerrado(s) sin superficie" in a for a in p.avisos)


def test_tipos_no_leidos_se_avisan(tmp_path):
    doc, msp = _nuevo(6)
    h = msp.add_hatch(dxfattribs={"layer": "MUROS"})
    h.paths.add_polyline_path([(0, 0), (1, 0), (1, 1)], is_closed=True)
    msp.add_solid([(0, 0), (1, 0), (0, 1)])
    p = leer_dxf(_guardar(doc, tmp_path))
    assert any("HATCH (1)" in a and "SOLID (1)" in a for a in p.avisos)
    assert p.capas["MUROS"].entidades == {"HATCH": 1}


def test_plano_en_bloques_anidados_se_avisa(tmp_path):
    doc, msp = _nuevo(6)
    dentro = doc.blocks.new("MUROS")
    for i in range(60):
        dentro.add_line((i, 0), (i, 10))
    fuera = doc.blocks.new("PLANTA")
    fuera.add_blockref("MUROS", (0, 0))
    msp.add_blockref("PLANTA", (0, 0))
    p = leer_dxf(_guardar(doc, tmp_path))
    assert any("dentro del bloque «PLANTA»" in a for a in p.avisos)


def test_espejo_giro_de_bloque_cota_y_arco(tmp_path):
    doc, msp = _nuevo(6)
    doc.blocks.new("B")
    espejo = {"extrusion": (0, 0, -1)}
    msp.add_blockref("B", (2, 3), dxfattribs={"rotation": 30, **espejo})
    msp.add_lwpolyline(
        [(0, 0), (1, 0), (1, 1), (0, 1)], close=True, dxfattribs={"elevation": 4, **espejo}
    )
    msp.add_arc((0, 0), 1, 0, 90, dxfattribs={"layer": "ARC", **espejo})
    p = leer_dxf(_guardar(doc, tmp_path))
    [b] = p.bloques
    assert (b.x, b.y) == (-2, 3) and b.rotacion == pytest.approx(150)
    assert p.contornos[0].elevacion == pytest.approx(-4)  # cota en WCS
    _, pts = next(t for t in p.trazos if t[0] == "ARC")
    assert pts[0] == pytest.approx((-1, 0)) and pts[-1] == pytest.approx((0, 1), abs=1e-12)
    assert p.capas["ARC"].longitud == pytest.approx(math.pi / 2)


def test_arco_de_0_a_360_es_vuelta_entera(tmp_path):
    doc, msp = _nuevo(6)
    msp.add_arc((0, 0), 1, 0, 360, dxfattribs={"layer": "A"})
    p = leer_dxf(_guardar(doc, tmp_path))
    assert p.capas["A"].longitud == pytest.approx(2 * math.pi)


def test_circulo_abierto_con_tres_puntos_se_propone(tmp_path):
    doc, msp = _nuevo(6)
    msp.add_lwpolyline([(0, 0, 0, 0, 1.0), (2, 0, 0, 0, 1.0), (0, 0, 0, 0, 0)], format="xyseb")
    p = leer_dxf(_guardar(doc, tmp_path))
    [c] = p.contornos
    assert c.contorno.area == pytest.approx(math.pi) and not c.marcada_cerrada
