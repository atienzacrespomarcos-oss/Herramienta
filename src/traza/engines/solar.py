"""Radiación solar de cielo despejado sobre cualquier superficie (motor puro).

Fuentes:
- Modelo de cielo despejado de ASHRAE (Handbook – Fundamentals, ediciones de 1972 a 2001):
  - directa normal I_DN = A·exp(−B/sen β);
  - difusa sobre horizontal C·I_DN;
  - A, B, C el día 21 de cada mes.
  La tabla se ha contrastado con la serie ajustada que usa EnergyPlus (DOE/NREL,
  WeatherManager.cc, «CalculateDailySolarCoeffs»): coinciden en menos del 0,2 % (07-11-2026).
- Geometría solar: Duffie y Beckman, «Solar Engineering of Thermal Processes»:
  - declinación de Cooper δ = 23,45°·sen(360·(284 + n)/365);
  - ángulo horario ω = 15°·(hora solar − 12).
- Difusa del cielo isótropa (1 + cos Σ)/2 y reflejada por el suelo ρ·(1 − cos Σ)/2, con
  ρ = 0,2 (el valor habitual de ASHRAE para terreno corriente).

Convenio de orientación: azimut de la normal EXTERIOR desde el norte y en sentido horario
(N 0°, E 90°, S 180°, O 270°); inclinación Σ desde la horizontal (cubierta 0°, fachada 90°).
Las horas son SOLARES (12 h = mediodía solar).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: ASHRAE, cielo despejado, día 21 de cada mes: A (W/m²), B, C.
ABC = {
    1: (1230.0, 0.142, 0.058),
    2: (1215.0, 0.144, 0.060),
    3: (1186.0, 0.156, 0.071),
    4: (1136.0, 0.180, 0.097),
    5: (1104.0, 0.196, 0.121),
    6: (1088.0, 0.205, 0.134),
    7: (1085.0, 0.207, 0.136),
    8: (1107.0, 0.201, 0.122),
    9: (1151.0, 0.177, 0.092),
    10: (1192.0, 0.160, 0.073),
    11: (1221.0, 0.149, 0.063),
    12: (1233.0, 0.142, 0.057),
}
_DIAS_MES = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
REFLECTANCIA_SUELO = 0.2


def dia_del_anyo(mes: int, dia: int = 21) -> int:
    return sum(_DIAS_MES[: mes - 1]) + dia


def declinacion_rad(n: int) -> float:
    return math.radians(23.45 * math.sin(2 * math.pi * (284 + n) / 365))


def direccion_sol(latitud: float, mes: int, hora_solar: float) -> tuple[float, float, float]:
    """Vector unitario hacia el sol en ejes (este, norte, arriba)."""
    phi = math.radians(latitud)
    d = declinacion_rad(dia_del_anyo(mes))
    w = math.radians(15.0 * (hora_solar - 12.0))
    este = -math.cos(d) * math.sin(w)
    norte = math.sin(d) * math.cos(phi) - math.cos(d) * math.sin(phi) * math.cos(w)
    arriba = math.sin(phi) * math.sin(d) + math.cos(phi) * math.cos(d) * math.cos(w)
    return este, norte, arriba


@dataclass(frozen=True)
class Irradiancia:
    directa: float  # W/m²
    difusa: float
    reflejada: float

    @property
    def total(self) -> float:
        return self.directa + self.difusa + self.reflejada


def irradiancia(
    latitud: float,
    mes: int,
    hora_solar: float,
    azimut: float,
    inclinacion: float,
    reflectancia: float = REFLECTANCIA_SUELO,
) -> Irradiancia:
    """Irradiancia de cielo despejado sobre una superficie (W/m²)."""
    este, norte, sen_altura = direccion_sol(latitud, mes, hora_solar)
    if sen_altura <= 0:
        return Irradiancia(0.0, 0.0, 0.0)
    a, b, c = ABC[mes]
    i_dn = a * math.exp(-b / sen_altura)
    s, z = math.radians(inclinacion), math.radians(azimut)
    normal = (math.sin(s) * math.sin(z), math.sin(s) * math.cos(z), math.cos(s))
    cos_inc = normal[0] * este + normal[1] * norte + normal[2] * sen_altura
    return Irradiancia(
        i_dn * max(cos_inc, 0.0),
        c * i_dn * (1 + math.cos(s)) / 2,
        reflectancia * i_dn * (sen_altura + c) * (1 - math.cos(s)) / 2,
    )
