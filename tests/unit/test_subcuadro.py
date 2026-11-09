"""Subcuadro de clima contra las guías técnicas del REBT (docs/modules/electricidad.md)."""

from __future__ import annotations

import math

import pytest

from traza.engines import subcuadro as sc
from traza.rules import electricidad as re


def test_intensidad_ejemplo_guia_anexo_2():
    # GUÍA-BT Anexo 2: 145 kW, 400 V, cos φ 0,90 → 232,5 A.
    assert sc.intensidad(145, 3, 0.90) == pytest.approx(232.5, abs=0.05)
    assert sc.intensidad(1.2, 1, 0.95) == pytest.approx(1200 / (230 * 0.95))


def test_tabla_a_y_columnas():
    # Tabla A de la GUÍA-BT-19: 2,5 mm² en E con 3×XLPE (columna 10) = 26,5 A; 16 mm² en
    # B2 con 3×PVC (columna 4) = 54 A; 1,5 mm² en C con 2×XLPE (columna 11) = 21 A.
    assert re.intensidad_admisible(2.5, "E", 3) == 26.5
    assert re.intensidad_admisible(16, "B2", 3, "PVC") == 54
    assert re.intensidad_admisible(1.5, "C", 2) == 21
    assert re.intensidad_admisible(35, "A2", 3, "PVC") is None


def test_agrupamiento_tabla_e():
    assert re.factor_agrupamiento("E", 1) == 1.0
    assert re.factor_agrupamiento("E", 4) == 0.75
    assert re.factor_agrupamiento("E", 5) == 0.75  # 5 → la de 6, del lado de la seguridad
    assert re.factor_agrupamiento("E", 30) == 0.70  # sin más reducción por encima de 9
    assert re.factor_agrupamiento("C", 2) == 0.85


def test_caida_de_tension_formulas_anexo_2():
    # Trifásica sin reactancia: e = P·L/(γ·S·U), γ90 = 44.
    e = re.caida_tension_v(10_000, 50, 4, 3, 0.85)
    assert e == pytest.approx(10_000 * 50 / (44 * 4 * 400))
    # Monofásica: el doble, con 230 V.
    e1 = re.caida_tension_v(2_000, 30, 2.5, 1, 1.0)
    assert e1 == pytest.approx(2 * 2_000 * 30 / (44 * 2.5 * 230))
    # 240 mm²: X = 0,25·R, con tg φ.
    r = 100 / (44 * 240)
    tg = math.sqrt(1 - 0.8**2) / 0.8
    assert re.caida_tension_v(100_000, 100, 240, 3, 0.8) == pytest.approx(
        (r + 0.25 * r * tg) * 100_000 / 400
    )


def test_conductor_de_proteccion_y_calibres():
    assert re.seccion_proteccion(10) == 10
    assert re.seccion_proteccion(25) == 16
    assert re.seccion_proteccion(70) == 35
    assert re.calibre(95.5) == 100 and re.calibre(6) == 6 and re.calibre(161) is None


def _ejemplo():
    return sc.calcular(
        [
            sc.Salida("Enfriadora", 45, 3, 15, variador=True),
            sc.Salida("Bomba primario", 2.2, 3, 8, variador=True),
            sc.Salida("Bomba C1", 1.5, 3, 10, variador=True),
            sc.Salida("Fancoils planta 1", 1.2, 1, 40, motor=False, cos_phi=0.95),
        ],
        longitud_alimentacion_m=30,
    )


def test_subcuadro_calculado_a_mano():
    r = _ejemplo()
    enf = r.salidas[0]
    # 45 kW, cos φ 0,85 → 76,4 A; ×1,25 (ITC-BT-47) = 95,5 A → 100 A curva D. Cuatro
    # circuitos en bandeja (factor 0,75): 25 mm² = 110·0,75 = 82,5 A < 100; 35 mm² = 102,75.
    assert enf.intensidad_a == pytest.approx(76.4, abs=0.1)
    assert enf.calibre_a == 100 and enf.curva == "D" and enf.seccion == 35
    assert enf.admisible_a == pytest.approx(137 * 0.75)
    assert enf.seccion_pe == 16
    assert (enf.diferencial_ma, enf.diferencial_tipo) == (300, "B")
    fc = r.salidas[3]
    assert (fc.diferencial_ma, fc.diferencial_tipo, fc.curva) == (30, "A", "C")
    # Alimentación: suma de intensidades + 25 % de la del motor mayor.
    a = r.alimentacion
    suma = sum(s.intensidad_a for s in r.salidas)
    assert a.intensidad_diseno_a == pytest.approx(suma + 0.25 * enf.intensidad_a)
    assert a.calibre_a == 125 and a.seccion == 35
    # Todas cumplen el 5 % sumando la caída de la alimentación.
    assert all(s.caida_total_pct == pytest.approx(a.caida_pct + s.caida_pct) for s in r.salidas)
    assert all(s.caida_total_pct <= 5.0 for s in r.salidas) and r.cumple


def test_larga_distancia_sube_seccion_y_ct_relaja():
    s = [sc.Salida("Rooftop", 30, 3, 180)]
    compania = sc.calcular(s, "compania", 20)
    ct = sc.calcular(s, "ct", 20)
    assert compania.salidas[0].seccion > ct.salidas[0].seccion  # 5 % frente a 6,5 %
    assert compania.salidas[0].caida_total_pct <= 5.0


def test_errores():
    with pytest.raises(ValueError, match="al menos una salida"):
        sc.calcular([])
    with pytest.raises(ValueError, match="1 o 3 fases"):
        sc.calcular([sc.Salida("X", 1, 2, 10)])
    with pytest.raises(ValueError, match="300 mm²"):
        sc.calcular([sc.Salida("Lejos", 200, 3, 2000)])
