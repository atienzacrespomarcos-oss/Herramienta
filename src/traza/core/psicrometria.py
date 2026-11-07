"""Psicrometría del aire húmedo (puro, en unidades SI: °C, Pa, kg/kg, kJ/kg).

Fuente: ASHRAE Handbook – Fundamentals (2017), capítulo 1 «Psychrometrics»:
- presión de saturación del vapor sobre agua y sobre hielo: ecuaciones de Hyland y Wexler
  (ec. 5 y 6), con temperatura absoluta en K;
- humedad específica: W = 0,621945·pw/(p − pw) (ec. 20 y 22);
- humedad específica a partir de la temperatura húmeda termodinámica (ec. 33);
- entalpía: h = 1,006·t + W·(2501 + 1,86·t) en kJ/kg de aire seco (ec. 30).

Presión atmosférica según la altitud: IDAE, «Condiciones climáticas exteriores de
proyecto», apartado 5.1: Pt = 101 325·(1 − 2,25577·10⁻⁵·z)^5,2559 Pa.
"""

from __future__ import annotations

import math

_AGUA = (-5.8002206e3, 1.3914993, -4.8640239e-2, 4.1764768e-5, -1.4452093e-8, 6.5459673)
_HIELO = (
    -5.6745359e3,
    6.3925247,
    -9.6778430e-3,
    6.2215701e-7,
    2.0747825e-9,
    -9.4840240e-13,
    4.1635019,
)
RELACION_MOLAR = 0.621945  # Mv/Mda


def presion_atmosferica(altitud_m: float) -> float:
    """Pa, a la altitud dada (IDAE, apartado 5.1)."""
    return 101_325.0 * (1.0 - 2.25577e-5 * altitud_m) ** 5.2559


def presion_saturacion(t: float) -> float:
    """Pa, presión de saturación del vapor a t °C (sobre hielo por debajo de 0 °C)."""
    T = t + 273.15
    if t >= 0:
        c8, c9, c10, c11, c12, c13 = _AGUA
        ln = c8 / T + c9 + c10 * T + c11 * T**2 + c12 * T**3 + c13 * math.log(T)
    else:
        c1, c2, c3, c4, c5, c6, c7 = _HIELO
        ln = c1 / T + c2 + c3 * T + c4 * T**2 + c5 * T**3 + c6 * T**4 + c7 * math.log(T)
    return math.exp(ln)


def humedad_especifica_saturacion(t: float, p: float) -> float:
    pws = presion_saturacion(t)
    return RELACION_MOLAR * pws / (p - pws)


def humedad_especifica_bulbo_humedo(t: float, th: float, p: float) -> float:
    """kg/kg de aire seco, a partir de la temperatura seca y la húmeda (°C) y la presión."""
    ws = humedad_especifica_saturacion(th, p)
    if th >= 0:
        return ((2501 - 2.326 * th) * ws - 1.006 * (t - th)) / (2501 + 1.86 * t - 4.186 * th)
    # Ec. 35: bulbo húmedo por debajo de 0 °C (sobre hielo).
    return ((2830 - 0.24 * th) * ws - 1.006 * (t - th)) / (2830 + 1.86 * t - 2.1 * th)


def humedad_especifica_relativa(t: float, hr: float, p: float) -> float:
    """kg/kg a partir de la humedad relativa (0–1)."""
    pw = hr * presion_saturacion(t)
    return RELACION_MOLAR * pw / (p - pw)


def humedad_relativa(t: float, w: float, p: float) -> float:
    pw = p * w / (RELACION_MOLAR + w)
    return pw / presion_saturacion(t)


def entalpia(t: float, w: float) -> float:
    """kJ/kg de aire seco."""
    return 1.006 * t + w * (2501 + 1.86 * t)


def temperatura_humeda(t: float, w: float, p: float) -> float:
    """Temperatura húmeda termodinámica (°C) del aire a t °C con humedad específica w:
    la que da esa w en `humedad_especifica_bulbo_humedo` (bisección, ±0,0001 °C)."""
    lo, hi = -40.0, t
    for _ in range(80):
        medio = (lo + hi) / 2
        if humedad_especifica_bulbo_humedo(t, medio, p) > w:
            hi = medio
        else:
            lo = medio
    return (lo + hi) / 2
