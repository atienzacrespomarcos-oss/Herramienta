"""Plano revisado (docs/modules/flujo.md, 1c): «quiero poder yo proponer planos de
ampliación o modificación y que se recalcule todo» (usuario, 09-11-2026).

Proyecto de tests/integration/test_redes_proyecto.py: ALMACÉN 40 × 25 m y OFICINAS
9,8 × 8 m con una red de impulsión. El revisado agranda las oficinas a 11,8 × 8 m y añade
un ARCHIVO de 5 × 5 m.
"""

from __future__ import annotations

import ezdxf
import pytest
from tests.integration.test_hidronica_proyecto import _circuitos
from tests.integration.test_redes_proyecto import red  # noqa: F401 (fixture)

from traza.app.flujo import DESACTUALIZADO, HECHO
from traza.app.ordenes import OrdenRechazada

ALMACEN = [(0, 0), (40000, 0), (40000, 25000), (0, 25000)]
OFICINAS_GRANDES = [(40200, 0), (52000, 0), (52000, 8000), (40200, 8000)]
ARCHIVO = [(60000, 0), (65000, 0), (65000, 5000), (60000, 5000)]


def _revisado(tmp_path, espacios, nombre="Nave rev B.dxf", desplazar=0):
    """Mismo dibujo que el original (capas, ejes y bloques) con otros espacios."""
    doc = ezdxf.new("R2013")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    for capa in ("A-ESPACIOS", "A-TEXTOS", "M-IMPULSION", "M-DIFUSORES"):
        doc.layers.add(capa)
    for texto, contorno in espacios:
        pts = [(x + desplazar, y) for x, y in contorno]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "A-ESPACIOS"})
        cx = sum(x for x, _ in pts) / 4
        cy = sum(y for _, y in pts) / 4
        msp.add_text(texto, dxfattribs={"layer": "A-TEXTOS", "height": 300}).set_placement((cx, cy))
    dif = doc.blocks.new("DIFUSOR")
    dif.add_circle((0, 0), 300)
    doc.blocks.new("UTA").add_lwpolyline([(0, 0), (1000, 0), (1000, 1000), (0, 1000)], close=True)
    ejes = {"layer": "M-IMPULSION"}
    msp.add_lwpolyline([(45000, 10000), (45000, 4000)], dxfattribs=ejes)
    msp.add_line((42500, 4000), (47500, 4000), dxfattribs=ejes)
    msp.add_blockref("UTA", (45000, 10000), dxfattribs={"layer": "M-DIFUSORES"})
    for x in (42500, 47500):
        msp.add_blockref("DIFUSOR", (x, 4000), dxfattribs={"layer": "M-DIFUSORES"})
    ruta = tmp_path / nombre
    doc.saveas(ruta)
    return ruta


def _superficies(p):
    return {e["nombre"]: e["superficie"] for e in p.espacios()}


def test_plano_revisado_recalcula_y_marca(red, tmp_path):  # noqa: F811
    p, red_id, plano_id, _ = red
    p.definir_sistema_hidraulico(titulo="Clima", tipo="2_tubos", circuitos=_circuitos(p))
    ids = {e["nombre"]: e["id"] for e in p.espacios()}
    antes = p.calcular_cargas()
    assert _superficies(p)["OFICINAS"] == pytest.approx(9.8 * 8)
    assert p.estado_paso("redes").estado == HECHO

    doc = p.incorporar_documento(
        _revisado(
            tmp_path,
            [("ALMACÉN", ALMACEN), ("OFICINAS", OFICINAS_GRANDES), ("ARCHIVO", ARCHIVO)],
        )
    )
    r, _ = p.comparar_plano_revisado(plano_id, doc)
    assert [x.antes.nombre for x in r.iguales] == ["ALMACÉN"]
    assert [x.antes.nombre for x in r.cambiados] == ["OFICINAS"]
    assert r.cambiados[0].despues.superficie == pytest.approx(11.8 * 8)
    assert [x.nombre_sugerido.texto for x in r.nuevas] == ["ARCHIVO"]
    assert not r.desaparecidos

    p.revisar_plano(plano_id, doc)
    # Mismos espacios (sus cargas, circuitos y redes siguen apuntándoles), contorno nuevo.
    assert {e["nombre"]: e["id"] for e in p.espacios()} == ids
    assert _superficies(p)["OFICINAS"] == pytest.approx(11.8 * 8)
    [nuevo] = p.planos()
    assert nuevo["documento_id"] == doc
    assert p.red(red_id)["plano_id"] == nuevo["id"]
    assert [x.nombre_sugerido.texto for x in p.propuestas(nuevo["id"])] == ["ARCHIVO"]
    # Se recalcula todo: más superficie de oficinas, más carga; la red sigue calculando.
    despues = {c.nombre: c for c in p.calcular_cargas().espacios}
    previas = {c.nombre: c for c in antes.espacios}
    assert despues["OFICINAS"].verano.total_w > previas["OFICINAS"].verano.total_w
    assert p.calcular_red(red_id).caudal_total_m3h > 0
    # Y lo que depende queda para revisar.
    for paso in ("cargas", "redes", "hidronica"):
        e = p.estado_paso(paso)
        assert e.estado == DESACTUALIZADO and "Planos" in e.texto, paso

    # Se deshace entera.
    p.deshacer()
    assert [x["id"] for x in p.planos()] == [plano_id]
    assert _superficies(p)["OFICINAS"] == pytest.approx(9.8 * 8)
    assert p.red(red_id)["plano_id"] == plano_id


def test_espacio_que_ya_no_esta_se_quita(red, tmp_path):  # noqa: F811
    p, _, plano_id, _ = red
    doc = p.incorporar_documento(_revisado(tmp_path, [("ALMACÉN", ALMACEN)]))
    r, _ = p.comparar_plano_revisado(plano_id, doc)
    assert [c.nombre for c in r.desaparecidos] == ["OFICINAS"]
    p.revisar_plano(plano_id, doc)
    assert [e["nombre"] for e in p.espacios()] == ["ALMACÉN"]


def test_dibujo_desplazado_no_se_acepta(red, tmp_path):  # noqa: F811
    p, _, plano_id, _ = red
    ruta = _revisado(tmp_path, [("ALMACÉN", ALMACEN)], desplazar=500_000)
    doc = p.incorporar_documento(ruta)
    with pytest.raises(OrdenRechazada, match="desplazado"):
        p.revisar_plano(plano_id, doc)
    assert len(p.espacios()) == 2


def test_capas_que_faltan_en_el_revisado(red, tmp_path):  # noqa: F811
    p, _, plano_id, _ = red
    d = ezdxf.new("R2013")
    d.layers.add("OTRA")
    d.saveas(tmp_path / "Otro.dxf")
    doc = p.incorporar_documento(tmp_path / "Otro.dxf")
    with pytest.raises(OrdenRechazada, match="no tiene la capa"):
        p.comparar_plano_revisado(plano_id, doc)
