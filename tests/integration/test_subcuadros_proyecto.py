"""Subcuadros de clima en el proyecto: orden, cálculo, propuestas desde los equipos y
unifilar DXF (docs/modules/electricidad.md)."""

from __future__ import annotations

import ezdxf
import pytest
from tests.integration.test_hidronica_proyecto import _circuitos, red  # noqa: F401

from traza.app.ordenes import OrdenRechazada
from traza.io import unifilar_dxf as ud

SALIDAS = [
    {"nombre": "Enfriadora", "potencia_kw": 45.0, "fases": 3, "longitud_m": 15.0,
     "motor": True, "variador": True},
    {"nombre": "Fancoils", "potencia_kw": 1.2, "fases": 1, "longitud_m": 40.0,
     "motor": False, "cos_phi": 0.95},
]  # fmt: skip


def test_subcuadro_calculado_y_unifilar(red, tmp_path):  # noqa: F811
    p, _, _, _ = red
    sid = p.definir_subcuadro(titulo="SC Clima", salidas=SALIDAS, longitud_alimentacion_m=30.0)
    guardado = p.subcuadro(sid)
    assert guardado["salidas"][1]["metodo"] == "E" and guardado["salidas"][0]["cos_phi"] == 0.85
    r = p.calcular_subcuadro(sid)
    assert r.cumple and len(r.salidas) == 2 and r.limite_pct == 5.0
    ruta = p.exportar_unifilar(sid, tmp_path / "Unifilar")
    doc = ezdxf.readfile(ruta)
    assert doc.dxfversion == "AC1027" and not doc.audit().has_errors
    texto = "\n".join(t.dxf.text for t in doc.modelspace().query("TEXT"))
    for s in r.salidas:
        assert s.nombre in texto and ud.cable(s) in texto
        assert f"{s.curva}{s.calibre_a} {ud.polos(s)}" in texto
        assert f"{s.diferencial_ma} mA tipo {s.diferencial_tipo}" in texto
    assert all(t.dxf.style == ud.ESTILO for t in doc.modelspace().query("TEXT"))
    assert all(e.get_xdata("TRAZA")[0].value == f"{sid}:unifilar" for e in doc.modelspace())


def test_propuestas_desde_el_sistema_hidraulico(red):  # noqa: F811
    p, _, _, _ = red
    p.definir_sistema_hidraulico(titulo="Clima", tipo="2_tubos", circuitos=_circuitos(p))
    nombres = [s["nombre"] for s in p.salidas_propuestas()]
    assert "Bomba de calor Clima" in nombres and "Bomba primario Clima" in nombres
    assert any(n.startswith("Bomba Oficinas") for n in nombres)
    assert any(n.startswith("Unidades Nave") for n in nombres)
    assert len(nombres) == len(set(nombres))
    # La red de aire propone su ventilador; la potencia, la de su ficha (0 = la pone el usuario).
    vent = [s for s in p.salidas_propuestas() if s["nombre"].startswith("Ventilador")]
    assert vent and vent[0]["potencia_kw"] == 0
    assert not any("ud)" in n for n in nombres)  # sin el número de unidades en el nombre


def test_la_orden_rechaza_y_se_deshace(red):  # noqa: F811
    p, _, _, _ = red
    with pytest.raises(OrdenRechazada, match="al menos una salida"):
        p.definir_subcuadro(titulo="X", salidas=[])
    with pytest.raises(OrdenRechazada, match="potencia eléctrica"):
        p.definir_subcuadro(titulo="X", salidas=[{**SALIDAS[0], "potencia_kw": 0}])
    with pytest.raises(OrdenRechazada, match="1 o 3 fases"):
        p.definir_subcuadro(titulo="X", salidas=[{**SALIDAS[0], "fases": 2}])
    with pytest.raises(OrdenRechazada, match="nombre propio"):
        p.definir_subcuadro(titulo="X", salidas=[SALIDAS[0], SALIDAS[0]])
    sid = p.definir_subcuadro(titulo="SC", salidas=SALIDAS)
    with pytest.raises(OrdenRechazada, match="Ya hay un subcuadro"):
        p.definir_subcuadro(titulo="SC", salidas=SALIDAS)
    # Una salida imposible (2 km) se explica, no rompe.
    p.definir_subcuadro(
        titulo="SC", salidas=[{**SALIDAS[0], "longitud_m": 1000.0, "potencia_kw": 400.0}], id=sid
    )
    with pytest.raises(OrdenRechazada, match="300 mm²"):
        p.calcular_subcuadro(sid)
    p.deshacer()
    p.deshacer()
    assert p.subcuadros() == []
