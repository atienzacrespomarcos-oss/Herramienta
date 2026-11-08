"""Ventilación sencilla (docs/modules/redes_aire.md, «Ventilación»): renovaciones por hora del
manual de Soler & Palau (tablas 3.5 y 3.6) y punto de trabajo del ventilador.

Red de tests/integration/test_redes_proyecto.py: dos difusores en OFICINAS
(9,8 × 8 m × 3 m = 235,2 m³).
"""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest
from tests.integration.test_redes_proyecto import red  # noqa: F401 (fixture)

from traza.app.ordenes import DefinirRed, OrdenRechazada
from traza.app.redes import caudal_espacio_m3h
from traza.engines.conductos import SFP
from traza.rules.ventilacion import renovaciones_por_volumen


def test_tabla_3_6_por_volumen():
    # S&P, Manual práctico de ventilación, tabla 3.6 (el límite, al tramo de menor volumen).
    assert renovaciones_por_volumen(0) == 20
    assert renovaciones_por_volumen(1000) == 20
    assert renovaciones_por_volumen(1000.1) == 15
    assert renovaciones_por_volumen(5000) == 15
    assert renovaciones_por_volumen(10000) == 10
    assert renovaciones_por_volumen(10000.1) == 6
    assert renovaciones_por_volumen(500_000) == 6
    with pytest.raises(ValueError):
        renovaciones_por_volumen(-1)


def _carga(volumen, exterior):
    return SimpleNamespace(volumen_m3=volumen, aire_exterior_m3h=exterior, verano=None)


def test_caudal_por_renovaciones_y_nunca_menos_que_el_aire_exterior():
    # Nave de 40 × 25 × 8 m = 8000 m³ → 10 renovaciones (tabla 3.6) = 80 000 m³/h.
    q, motivo = caudal_espacio_m3h("extraccion", _carga(8000, 900), 10, 101_325, "volumen")
    assert q == pytest.approx(80_000) and "10 renovaciones/h (tabla 3.6" in motivo
    q, motivo = caudal_espacio_m3h("extraccion", _carga(8000, 900), 10, 101_325, "renovaciones", 6)
    assert q == pytest.approx(48_000) and "6 renovaciones/h (fijas)" in motivo
    # Aire exterior mayor (mucha ocupación): manda el aire exterior.
    q, motivo = caudal_espacio_m3h("extraccion", _carga(100, 3000), 10, 101_325, "volumen")
    assert q == 3000 and "aire exterior" in motivo
    # Impulsión de ventilación, igual que la extracción (red equilibrada).
    q, _ = caudal_espacio_m3h("impulsion", _carga(8000, 900), 10, 101_325, "renovaciones", 6)
    assert q == pytest.approx(48_000)


def test_la_orden_solo_admite_renovaciones_en_ventilacion(red):  # noqa: F811
    p, red_id, plano_id, nivel_id = red
    base = {
        "titulo": "Extracción nave",
        "plano_id": plano_id,
        "capa_ejes": "M-IMPULSION",
        "bloques_terminales": ["DIFUSOR"],
        "nivel_id": nivel_id,
    }
    with pytest.raises(OrdenRechazada, match="retorno sale de la impulsión"):
        p.ejecutar(DefinirRed(tipo="retorno", criterio_caudal="volumen", **base))
    with pytest.raises(OrdenRechazada, match="climatización la impulsión"):
        p.ejecutar(DefinirRed(tipo="impulsion", criterio_caudal="volumen", **base))
    with pytest.raises(OrdenRechazada, match="Escribe las renovaciones"):
        p.ejecutar(DefinirRed(tipo="extraccion", criterio_caudal="renovaciones", **base))
    with pytest.raises(OrdenRechazada, match="0,5 a 60"):
        p.ejecutar(
            DefinirRed(tipo="extraccion", criterio_caudal="renovaciones", renovaciones=80, **base)
        )
    with pytest.raises(OrdenRechazada, match="Criterio de caudal"):
        p.ejecutar(DefinirRed(tipo="extraccion", criterio_caudal="otro", **base))
    # Unas renovaciones escritas con otro criterio no se guardan (no engañan al releer).
    rid = p.definir_red(tipo="extraccion", criterio_caudal="volumen", renovaciones=8, **base)
    guardada = p.red(rid)
    assert guardada["criterio_caudal"] == "volumen" and guardada["renovaciones"] is None


def test_red_de_extraccion_por_renovaciones_cableada(red, tmp_path):  # noqa: F811
    """Del diálogo al cálculo: el criterio guardado llega a los terminales y al Excel."""
    p, red_id, plano_id, nivel_id = red
    rid = p.definir_red(
        titulo="Extracción oficinas",
        tipo="extraccion",
        plano_id=plano_id,
        capa_ejes="M-IMPULSION",
        bloques_terminales=["DIFUSOR"],
        bloque_equipo="UTA",
        nivel_id=nivel_id,
        climatizacion=False,
        criterio_caudal="volumen",
    )
    r = p.calcular_red(rid)
    ofi = next(c for c in p.calcular_cargas().espacios if c.nombre == "OFICINAS")
    assert ofi.volumen_m3 == pytest.approx(235.2)
    q = max(20 * ofi.volumen_m3, ofi.aire_exterior_m3h)  # ≤ 1000 m³ → 20 renovaciones
    assert r.caudal_total_m3h == pytest.approx(q)
    assert all("tabla 3.6" in t.origen_caudal for t in r.terminales)
    # Punto de trabajo: extracción de ventilación → SFP 2 (RITE IT 1.2.4.2.5).
    assert r.sfp_exigida == 2
    assert r.potencia_maxima_w == pytest.approx(dict(SFP)[2] * q / 3600)
    # Excel: resumen con la potencia máxima e hipótesis con la fuente.
    from openpyxl import load_workbook

    wb = load_workbook(p.exportar_red_excel(rid, tmp_path / "Ext"))
    filas = {f[0].value: f[1].value for f in wb["Resumen"].iter_rows(min_row=2)}
    assert filas["Potencia eléctrica máxima del ventilador (SFP × caudal)"] == pytest.approx(
        r.potencia_maxima_w
    )
    hipotesis = " ".join(str(f[0].value) for f in wb["Hipótesis"].iter_rows(min_row=2))
    assert "tabla 3.6" in hipotesis and "Soler & Palau" in hipotesis


def test_la_base_de_datos_rechaza_un_criterio_desconocido(red):  # noqa: F811
    p, red_id, _, _ = red
    assert p.red(red_id)["criterio_caudal"] == "cargas"  # lo de antes, por defecto
    with pytest.raises(sqlite3.IntegrityError):
        p._con.execute("UPDATE red_aire SET criterio_caudal = 'otro' WHERE id = ?", (red_id,))
