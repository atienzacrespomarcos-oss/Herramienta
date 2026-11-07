"""Psicrometría frente a los valores publicados en ASHRAE Handbook – Fundamentals (2017),
capítulo 1 (tabla 3 de propiedades del agua saturada y ejemplo 2 resuelto)."""

from __future__ import annotations

import pytest

from traza.core import psicrometria as ps


@pytest.mark.parametrize(
    "t,pws",
    [
        (-10.0, 259.9),  # sobre hielo
        (0.0, 611.2),
        (25.0, 3169.9),
        (40.0, 7384.9),
    ],
)
def test_presion_de_saturacion(t, pws):
    assert ps.presion_saturacion(t) == pytest.approx(pws, rel=2e-3)


def test_aire_a_40_de_seca_y_20_de_humeda():
    # Comprobación a mano con las ecuaciones de ASHRAE (gas ideal):
    #   Ws(20 °C) = 0,621945·2339,3/(101 325 − 2339,3) = 0,014698
    #   W = ((2501 − 2,326·20)·0,014698 − 1,006·20)/(2501 + 1,86·40 − 4,186·20) = 0,00640
    # (≈ 6,4 g/kg, lo que da cualquier diagrama psicrométrico a nivel del mar), y
    #   h = 1,006·40 + 0,00640·(2501 + 1,86·40) = 56,7 kJ/kg.
    # Las ecuaciones de gas ideal se apartan menos del 1 % de las tablas de ASHRAE
    # (que incluyen el factor de mejora); para cargas térmicas es irrelevante.
    p = 101_325.0
    assert ps.humedad_especifica_saturacion(20, p) == pytest.approx(0.014698, rel=1e-3)
    w = ps.humedad_especifica_bulbo_humedo(40, 20, p)
    assert w == pytest.approx(0.00640, abs=2e-5)
    assert ps.entalpia(40, w) == pytest.approx(56.7, abs=0.1)
    assert ps.temperatura_humeda(40, w, p) == pytest.approx(20, abs=1e-3)


def test_presion_atmosferica_idae():
    assert ps.presion_atmosferica(0) == pytest.approx(101_325)
    # Madrid-Barajas, 582 m: ~94,4 kPa.
    assert ps.presion_atmosferica(582) == pytest.approx(94_400, rel=2e-3)


def test_humedad_relativa_ida_y_vuelta():
    p = 98_000.0
    w = ps.humedad_especifica_relativa(30, 0.55, p)
    assert ps.humedad_relativa(30, w, p) == pytest.approx(0.55)
