"""Geometría plana de contornos: superficie, perímetro y «está dentro».

Un contorno es una polilínea cerrada en planta cuyos tramos pueden ser rectos o arcos. Los
arcos se dan como en DXF, con el «bulge» de cada vértice (Autodesk, DXF Reference, VERTEX,
código 42): «la tangente de un cuarto del ángulo incluido del arco, negativa si el arco va en
sentido horario del punto inicial al final; 0 es un tramo recto y 1 un semicírculo».

Superficie y perímetro se calculan EXACTOS (sin aproximar los arcos por cuerdas):
- ángulo incluido θ = 4·atan(bulge), con signo (positivo = antihorario);
- radio r = c / (2·sen(|θ|/2)), con c la cuerda;
- longitud del arco = r·|θ|;
- superficie: la del polígono de las cuerdas (fórmula del área de Gauss, con signo) más, por
  cada arco, el segmento circular con signo (r²/2)·(θ − sen θ). Con signo, un arco que
  sobresale del contorno suma y uno que entra resta, sea cual sea el sentido de recorrido.

«Está dentro» (para saber en qué espacio cae un texto o un bloque) sí aproxima los arcos por
cuerdas, con una flecha máxima declarada (`FLECHA_MAX`): solo se usa para clasificar puntos,
nunca para medir.

Puro: sin dependencias de fuera del núcleo. Las magnitudes son metros (y m²): quien convierte
desde las unidades del dibujo es el lector, con la unidad que confirma el usuario.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Flecha máxima (m) al aproximar un arco por cuerdas para clasificar puntos: 1 mm.
FLECHA_MAX = 0.001


class ContornoInvalido(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Vertice:
    x: float
    y: float
    bulge: float = 0.0  # del tramo que empieza en este vértice


def _arco(p: Vertice, q: Vertice) -> tuple[float, float, float]:
    """(cuerda, ángulo incluido con signo, radio) del tramo p→q. Radio inf si es recto."""
    c = math.hypot(q.x - p.x, q.y - p.y)
    if p.bulge == 0 or c == 0:
        return c, 0.0, math.inf
    theta = 4.0 * math.atan(p.bulge)
    return c, theta, c / (2.0 * math.sin(abs(theta) / 2.0))


# Con un bulge diminuto el radio es enorme y r²·(θ − sen θ) da inf·0 = NaN (lo encontró
# hypothesis). Las dos medidas se escriben sin pasar por el radio:
#   longitud = c · (|θ|/2) / sen(|θ|/2)
#   segmento = (c²/8) · (θ − sen θ) / sen²(θ/2), y para |θ| < 1e-6 su límite c²·θ/12
#   (error relativo del orden de θ², despreciable).
def _longitud_tramo(c: float, theta: float) -> float:
    if not theta:
        return c
    medio = abs(theta) / 2.0
    return c * medio / math.sin(medio)


def _segmento(c: float, theta: float) -> float:
    if not theta:
        return 0.0
    if abs(theta) < 1e-6:
        return c * c * theta / 12.0
    return c * c / 8.0 * (theta - math.sin(theta)) / math.sin(theta / 2.0) ** 2


@dataclass(frozen=True, slots=True)
class Contorno:
    vertices: tuple[Vertice, ...]

    def __post_init__(self) -> None:
        if len(self.vertices) < 2:
            raise ContornoInvalido("Un contorno necesita al menos dos vértices.")
        for v in self.vertices:
            if not all(math.isfinite(t) for t in (v.x, v.y, v.bulge)):
                raise ContornoInvalido("Coordenadas o bulge no finitos.")
        if len(self.vertices) == 2 and all(v.bulge == 0 for v in self.vertices):
            raise ContornoInvalido("Dos vértices sin arcos no encierran superficie.")

    def _tramos(self):
        n = len(self.vertices)
        for i in range(n):
            yield self.vertices[i], self.vertices[(i + 1) % n]

    @property
    def area_con_signo(self) -> float:
        """Positiva si el contorno se recorre en sentido antihorario."""
        # Coordenadas relativas al primer vértice: con un plano georreferenciado (UTM en mm,
        # del orden de 1e9) los productos x·y se cancelan y se pierden las cifras de la
        # superficie (lo encontró hypothesis con solo 3 km de desplazamiento).
        x0, y0 = self.vertices[0].x, self.vertices[0].y
        total = 0.0
        for p, q in self._tramos():
            total += ((p.x - x0) * (q.y - y0) - (q.x - x0) * (p.y - y0)) / 2.0
            c, theta, _ = _arco(p, q)
            total += _segmento(c, theta)
        return total

    @property
    def area(self) -> float:
        return abs(self.area_con_signo)

    @property
    def perimetro(self) -> float:
        total = 0.0
        for p, q in self._tramos():
            c, theta, _ = _arco(p, q)
            total += _longitud_tramo(c, theta)
        return total

    def aplanado(self, flecha: float = FLECHA_MAX) -> list[tuple[float, float]]:
        """Vértices con los arcos sustituidos por cuerdas de flecha ≤ `flecha`."""
        return aplanar(list(self.vertices), True, flecha)

    def contiene(self, x: float, y: float) -> bool:
        """Punto estrictamente dentro (regla par-impar sobre el contorno aplanado)."""
        dentro = False
        pts = self.aplanado()
        j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if (yi > y) != (yj > y):
                xc = xi + (y - yi) * (xj - xi) / (yj - yi)
                if x < xc:
                    dentro = not dentro
            j = i
        return dentro

    def escalado(self, factor: float) -> Contorno:
        """Mismo contorno con las coordenadas multiplicadas por `factor` (el bulge, que es
        un ángulo, no cambia)."""
        return Contorno(tuple(Vertice(v.x * factor, v.y * factor, v.bulge) for v in self.vertices))


def aplanar(
    vertices: list[Vertice], cerrada: bool, flecha: float = FLECHA_MAX
) -> list[tuple[float, float]]:
    """Puntos de una polilínea, abierta o cerrada, con los arcos sustituidos por cuerdas de
    flecha ≤ `flecha`. Una abierta termina en su último vértice; una cerrada no repite el
    primero."""
    puntos: list[tuple[float, float]] = []
    n = len(vertices)
    for i in range(n if cerrada else n - 1):
        p, q = vertices[i], vertices[(i + 1) % n]
        puntos.append((p.x, p.y))
        c, theta, r = _arco(p, q)
        # Un arco cuya flecha total ya es menor que la admitida es, a estos efectos, su
        # cuerda (y así no se calcula un centro a distancia casi infinita).
        if not theta or r * (1.0 - math.cos(theta / 2.0)) <= flecha:
            continue
        # Flecha de una cuerda que abarca un ángulo α: r·(1 − cos(α/2)).
        if flecha >= r:
            pasos = 2
        else:
            alfa_max = 2.0 * math.acos(1.0 - flecha / r)
            pasos = max(2, math.ceil(abs(theta) / alfa_max))
        # Centro: sobre la mediatriz de la cuerda, a distancia r·cos(|θ|/2) del punto medio;
        # a la izquierda del avance si el arco es antihorario. En un arco mayor que media
        # vuelta el coseno es negativo y el centro pasa solo al otro lado.
        mx, my = (p.x + q.x) / 2.0, (p.y + q.y) / 2.0
        ux, uy = (q.x - p.x) / c, (q.y - p.y) / c
        d = r * math.cos(abs(theta) / 2.0)
        lado = 1.0 if theta > 0 else -1.0
        cx, cy = mx - uy * d * lado, my + ux * d * lado
        a0 = math.atan2(p.y - cy, p.x - cx)
        for k in range(1, pasos):
            a = a0 + theta * k / pasos
            puntos.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    if not cerrada and vertices:
        puntos.append((vertices[-1].x, vertices[-1].y))
    return puntos


def longitud_polilinea(vertices: list[Vertice], cerrada: bool) -> float:
    """Longitud de una polilínea abierta o cerrada, con arcos exactos."""
    n = len(vertices)
    total = 0.0
    tramos = n if cerrada else n - 1
    for i in range(max(tramos, 0)):
        c, theta, _ = _arco(vertices[i], vertices[(i + 1) % n])
        total += _longitud_tramo(c, theta)
    return total
