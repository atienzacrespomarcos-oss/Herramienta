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


def test_rehacer_tras_deshacer(red, tmp_path):  # noqa: F811
    p, red_id, plano_id, _ = red
    doc = p.incorporar_documento(
        _revisado(tmp_path, [("ALMACÉN", ALMACEN), ("OFICINAS", OFICINAS_GRANDES)])
    )
    p.revisar_plano(plano_id, doc)
    p.deshacer()
    p.rehacer()
    assert _superficies(p)["OFICINAS"] == pytest.approx(11.8 * 8)
    assert p.planos()[0]["documento_id"] == doc
    assert p.red(red_id)["plano_id"] == p.planos()[0]["id"]


def test_aprobado_que_cambia_o_se_mueve_no_se_revisa_sin_reabrir(red, tmp_path):  # noqa: F811
    from traza.app.ordenes import Aprobar

    p, _, plano_id, _ = red
    ofi = next(e for e in p.espacios() if e["nombre"] == "OFICINAS")
    p.ejecutar(Aprobar(ofi["id"], "Medido"))
    # Oficinas desplazadas 1 m: misma superficie y perímetro, otra posición.
    movidas = [(x, y + 1000) for x, y in [(40200, 0), (50000, 0), (50000, 8000), (40200, 8000)]]
    doc = p.incorporar_documento(_revisado(tmp_path, [("ALMACÉN", ALMACEN), ("OFICINAS", movidas)]))
    r, _ = p.comparar_plano_revisado(plano_id, doc)
    assert [c.nombre for c in r.aprobados_que_cambian] == ["OFICINAS"]
    with pytest.raises(OrdenRechazada, match="OFICINAS.*Reábrelos"):
        p.revisar_plano(plano_id, doc)
    # Sin cambios (el mismo dibujo guardado otra vez), el aprobado no impide revisar.
    igual = p.incorporar_documento(
        _revisado(
            tmp_path,
            [
                ("ALMACÉN", ALMACEN),
                ("OFICINAS", [(40200, 0), (50000, 0), (50000, 8000), (40200, 8000)]),
            ],
            nombre="Nave rev C.dxf",
        )
    )
    r = p.revisar_plano(plano_id, igual)
    assert len(r.iguales) == 2 and not r.cambiados


def test_descartes_que_siguen_y_avisos_de_las_redes(red, tmp_path):  # noqa: F811
    p, _, plano_id, _ = red
    # Un pilar dibujado en la capa de espacios, descartado en el plano original.
    pilar = [(10000, 10000), (10400, 10000), (10400, 10400), (10000, 10400)]
    original = p.plano(plano_id)
    assert original["descartados"] == []
    doc = p.incorporar_documento(
        _revisado(tmp_path, [("ALMACÉN", ALMACEN), ("OFICINAS", OFICINAS_GRANDES), ("", pilar)])
    )
    r, siguen = p.comparar_plano_revisado(plano_id, doc)
    assert siguen == [] and len(r.nuevas) == 1  # el original no tenía el pilar
    assert not r.avisos
    sin_ejes = tmp_path / "sin_ejes"
    sin_ejes.mkdir()
    d = ezdxf.new("R2013")
    d.header["$INSUNITS"] = 4
    for capa in ("A-ESPACIOS", "A-TEXTOS"):
        d.layers.add(capa)
    d.modelspace().add_lwpolyline(ALMACEN, close=True, dxfattribs={"layer": "A-ESPACIOS"})
    d.saveas(sin_ejes / "Nave rev D.dxf")
    r, _ = p.comparar_plano_revisado(plano_id, p.incorporar_documento(sin_ejes / "Nave rev D.dxf"))
    assert r.avisos and "Impulsión oficinas" in r.avisos[0] and "m-impulsion" in r.avisos[0]


def test_descarte_del_plano_anterior_se_conserva(proyecto, tmp_path):
    from traza.app.ordenes import CrearNivel

    p = proyecto
    pilar = [(10000, 10000), (10400, 10000), (10400, 10400), (10000, 10400)]
    v1 = tmp_path / "v1"
    v1.mkdir()
    plano_id = p.leer_plano(
        p.incorporar_documento(_revisado(v1, [("ALMACÉN", ALMACEN), ("", pilar)], "N.dxf")),
        "mm",
        ["A-ESPACIOS"],
        [],
        ["A-TEXTOS"],
    )
    nivel = CrearNivel("Planta baja", 0.0, 3.0)
    p.ejecutar(nivel)
    props = p.propuestas(plano_id)
    alm = next(x for x in props if x.nombre_sugerido and x.nombre_sugerido.texto == "ALMACÉN")
    p.confirmar_contorno(plano_id, alm.handle, nivel.id, nombre="ALMACÉN")
    p.descartar_propuesta(plano_id, next(x for x in props if x is not alm).handle)
    doc = p.incorporar_documento(
        _revisado(tmp_path, [("ALMACÉN", ALMACEN), ("", pilar), ("ARCHIVO", ARCHIVO)])
    )
    p.revisar_plano(plano_id, doc)
    nuevo = p.planos()[0]
    assert len(nuevo["descartados"]) == 1
    assert [x.nombre_sugerido.texto for x in p.propuestas(nuevo["id"])] == ["ARCHIVO"]
