"""Fachadas de cada espacio a partir de los contornos en planta (motor puro).

Decisión del usuario (07-11-2026): «automático y reviso». Un lado de un espacio es fachada
si no tiene enfrente, a menos de un grueso de muro, un lado de otro espacio del mismo nivel.
Su orientación es la de la normal exterior, girada según el norte del plano, y se agrupa en
8 sectores de 45° (N, NE, E…). El usuario corrige por sector lo que el dibujo no diga bien
(un patio, un local vecino que no está dibujado…).

Criterio de «enfrente»: lados paralelos (±5°), el otro espacio del lado exterior y a una
distancia de 0 a TOLERANCIA_MURO_M (el grueso de un muro o tabique; los contornos de
locales se dibujan por la cara interior). La parte solapada en proyección es interior; el
resto, fachada.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

SECTORES = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")
AZIMUT_SECTOR = {s: 45.0 * i for i, s in enumerate(SECTORES)}
TOLERANCIA_MURO_M = 0.6
_SEN_PARALELO = math.sin(math.radians(5))


@dataclass(frozen=True)
class Planta:
    id: str
    puntos: tuple[tuple[float, float], ...]  # contorno aplanado, en metros, sin repetir el 1.º


def sector(azimut: float) -> str:
    return SECTORES[int(((azimut % 360.0) + 22.5) // 45.0) % 8]


def _area_con_signo(pts) -> float:
    return 0.5 * sum(
        pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
        for i in range(len(pts))
    )


def _lados(pts):
    return [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def _caja(pts, margen):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs) - margen, min(ys) - margen, max(xs) + margen, max(ys) + margen


def _se_tocan(a, b) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _descubiertos(intervalos: list[tuple[float, float]], largo: float):
    """Tramos de [0, largo] que no cubre ningún intervalo."""
    libres, inicio = [], 0.0
    for a, b in sorted(intervalos):
        if a > inicio + 1e-6:
            libres.append((inicio, a))
        inicio = max(inicio, b)
    if largo > inicio + 1e-6:
        libres.append((inicio, largo))
    return libres


Punto = tuple[float, float]


@dataclass(frozen=True)
class Tramo:
    sector: str
    inicio: Punto
    fin: Punto

    @property
    def largo(self) -> float:
        return math.hypot(self.fin[0] - self.inicio[0], self.fin[1] - self.inicio[1])


def tramos(
    espacios: list[Planta], norte: float = 0.0, tolerancia: float = TOLERANCIA_MURO_M
) -> dict[str, list[Tramo]]:
    """Tramos de fachada de cada espacio de UN nivel (para medirlos y dibujarlos).

    `norte`: dirección del norte en el dibujo, en grados desde el eje Y (arriba) en sentido
    horario (0 si el norte está arriba).
    """
    cajas = {e.id: _caja(e.puntos, tolerancia) for e in espacios}
    resultado: dict[str, list[Tramo]] = {}
    for e in espacios:
        pts = e.puntos
        antihorario = _area_con_signo(pts) > 0
        vecinos = [o for o in espacios if o.id != e.id and _se_tocan(cajas[e.id], cajas[o.id])]
        lados_vecinos = [lado for o in vecinos for lado in _lados(o.puntos)]
        propios: list[Tramo] = []
        for p, q in _lados(pts):
            dx, dy = q[0] - p[0], q[1] - p[1]
            largo = math.hypot(dx, dy)
            if largo < 1e-9:
                continue
            ux, uy = dx / largo, dy / largo
            nx, ny = (uy, -ux) if antihorario else (-uy, ux)
            intervalos = []
            for a, b in lados_vecinos:
                vx, vy = b[0] - a[0], b[1] - a[1]
                lv = math.hypot(vx, vy)
                if lv < 1e-9 or abs(ux * vy - uy * vx) / lv > _SEN_PARALELO:
                    continue
                da = (a[0] - p[0]) * nx + (a[1] - p[1]) * ny
                db = (b[0] - p[0]) * nx + (b[1] - p[1]) * ny
                if not (-1e-3 <= da <= tolerancia and -1e-3 <= db <= tolerancia):
                    continue
                ta = (a[0] - p[0]) * ux + (a[1] - p[1]) * uy
                tb = (b[0] - p[0]) * ux + (b[1] - p[1]) * uy
                lo, hi = max(min(ta, tb), 0.0), min(max(ta, tb), largo)
                if hi > lo:
                    intervalos.append((lo, hi))
            s = sector(math.degrees(math.atan2(nx, ny)) - norte)
            for lo, hi in _descubiertos(intervalos, largo):
                propios.append(
                    Tramo(s, (p[0] + ux * lo, p[1] + uy * lo), (p[0] + ux * hi, p[1] + uy * hi))
                )
        resultado[e.id] = propios
    return resultado


def longitudes(lista: list[Tramo]) -> dict[str, float]:
    por_sector: dict[str, float] = {}
    for t in lista:
        por_sector[t.sector] = por_sector.get(t.sector, 0.0) + t.largo
    return por_sector


def fachadas(
    espacios: list[Planta], norte: float = 0.0, tolerancia: float = TOLERANCIA_MURO_M
) -> dict[str, dict[str, float]]:
    """Longitud de fachada (m) por sector de cada espacio de UN nivel."""
    return {k: longitudes(v) for k, v in tramos(espacios, norte, tolerancia).items()}
