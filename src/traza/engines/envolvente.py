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


def _cubierto(intervalos: list[tuple[float, float]]) -> float:
    total, fin = 0.0, -math.inf
    for a, b in sorted(intervalos):
        if b <= fin:
            continue
        total += b - max(a, fin)
        fin = b
    return total


def fachadas(
    espacios: list[Planta], norte: float = 0.0, tolerancia: float = TOLERANCIA_MURO_M
) -> dict[str, dict[str, float]]:
    """Longitud de fachada (m) por sector de cada espacio de UN nivel.

    `norte`: dirección del norte en el dibujo, en grados desde el eje Y (arriba) en sentido
    horario (0 si el norte está arriba).
    """
    cajas = {e.id: _caja(e.puntos, tolerancia) for e in espacios}
    resultado: dict[str, dict[str, float]] = {}
    for e in espacios:
        pts = e.puntos
        antihorario = _area_con_signo(pts) > 0
        vecinos = [o for o in espacios if o.id != e.id and _se_tocan(cajas[e.id], cajas[o.id])]
        lados_vecinos = [lado for o in vecinos for lado in _lados(o.puntos)]
        por_sector: dict[str, float] = {}
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
            expuesto = largo - _cubierto(intervalos)
            if expuesto > 1e-6:
                azimut = math.degrees(math.atan2(nx, ny)) - norte
                s = sector(azimut)
                por_sector[s] = por_sector.get(s, 0.0) + expuesto
        resultado[e.id] = por_sector
    return resultado
