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
cuerdas, con una flecha máxima declarada (`FLECHA_MAX` = 1 mm, **en metros**: el contorno
tiene que estar ya en metros, con `escalado`). Solo se usa para clasificar puntos, nunca para
medir. Un punto exactamente sobre el borde puede quedar dentro o fuera.

Un contorno que se corta a sí mismo (un «8», una corbata) no tiene una superficie con sentido
físico: la fórmula da la diferencia de sus lóbulos. `autointersecante` lo detecta para que se
avise en lugar de proponerlo como espacio.

Puro: sin dependencias de fuera del núcleo. Las unidades son las de las coordenadas que se
den; quien pasa de las del dibujo a metros es el lector, con la unidad que confirma el usuario.
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass

#: Flecha máxima (m) al aproximar un arco por cuerdas para clasificar puntos: 1 mm.
FLECHA_MAX = 0.001
#: Motor y versión con que se anotan en el registro de cálculo la superficie y el
#: perímetro. Si cambian las fórmulas, cambia la versión.
MOTOR = "geometria.contorno"
VERSION = "1.0.0"


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
#   segmento = (c²/8) · (θ − sen θ) / sen²(θ/2)
# Para |θ| pequeño, «θ − sen θ» resta dos números casi iguales y pierde cifras (revisión
# 06-11-2026: error relativo de 1e-3 con θ = 1e-6). Por eso:
#   |θ| < 1e-6:  su límite c²·θ/12 (error relativo del orden de θ²);
#   |θ| < 1e-2:  θ − sen θ por su serie θ³/6 − θ⁵/120 + θ⁷/5040 (error del orden de θ⁹).
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
    if abs(theta) < 1e-2:
        t3 = theta**3
        diferencia = t3 / 6.0 - t3 * theta**2 / 120.0 + t3 * theta**4 / 5040.0
    else:
        diferencia = theta - math.sin(theta)
    return c * c / 8.0 * diferencia / math.sin(theta / 2.0) ** 2


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

    def contiene(self, x: float, y: float, flecha: float = FLECHA_MAX) -> bool:
        """Punto dentro (regla par-impar sobre el contorno aplanado con `flecha`, en las
        unidades de las coordenadas: 1 mm si el contorno está en metros). Un punto sobre el
        borde puede dar cualquiera de los dos resultados."""
        dentro = False
        pts = _aplanado_guardado(self.vertices, flecha)
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

    def autointersecante(self, flecha: float = FLECHA_MAX) -> bool:
        """¿Se corta a sí mismo? Se comprueba sobre el aplanado: dos tramos no contiguos que
        se cruzan o se tocan. Tramos contiguos que se solapan en sentido contrario (ida y
        vuelta sobre la misma línea) también cuentan."""
        # Sin puntos repetidos seguidos: un tramo de longitud cero haría que sus vecinos, que
        # se tocan en ese punto, parecieran cortarse.
        pts = []
        for p in _aplanado_guardado(self.vertices, flecha):
            if not pts or p != pts[-1]:
                pts.append(p)
        while len(pts) > 1 and pts[0] == pts[-1]:
            pts.pop()
        if len(pts) < 3:
            return False
        tramos = [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
        n = len(tramos)
        # Barrido por x: solo se comparan tramos cuyas cajas se solapan en x. Con todos los
        # pares, un contorno de miles de vértices (parcela digitalizada) costaba millones de
        # comprobaciones (revisión 06-11-2026).
        orden = sorted(range(n), key=lambda k: min(tramos[k][0][0], tramos[k][1][0]))
        activos: list[int] = []
        for i in orden:
            (ax, ay), (bx, by) = tramos[i]
            x0 = min(ax, bx)
            activos = [k for k in activos if max(tramos[k][0][0], tramos[k][1][0]) >= x0]
            for j in activos:
                (cx, cy), (dx, dy) = tramos[j]
                if max(ay, by) < min(cy, dy) or max(cy, dy) < min(ay, by):
                    continue  # sus cajas no se solapan en y
                a, b = min(i, j), max(i, j)
                contiguos = b == a + 1 or (a == 0 and b == n - 1)
                if _se_cortan(*tramos[a], *tramos[b], contiguos):
                    return True
            activos.append(i)
        return False

    def escalado(self, factor: float) -> Contorno:
        """Mismo contorno con las coordenadas multiplicadas por `factor` (el bulge, que es
        un ángulo, no cambia)."""
        return Contorno(tuple(Vertice(v.x * factor, v.y * factor, v.bulge) for v in self.vertices))


#: Dos vértices a menos de esto son el mismo (1 mm con el contorno en metros): lo que un
#: DXF guardado otra vez mueve por redondeo, muy por debajo de lo que se dibuja a propósito.
TOLERANCIA_VERTICE = 0.001


def mismo_contorno(a: Contorno, b: Contorno, tol: float = TOLERANCIA_VERTICE) -> bool:
    """Misma forma en el mismo sitio: la misma SECUENCIA de vértices (a menos de `tol`) y de
    arcos, empiece donde empiece el contorno y en cualquier sentido. Un contorno desplazado
    o girado, aunque conserve superficie y perímetro, NO es el mismo (revisión 09-11-2026:
    un espacio aprobado podía cambiar de forma sin reabrirlo). Se compara en orden, no como
    conjunto de puntos: los mismos puntos unidos en otro orden son otra figura (segunda
    revisión 09-11-2026)."""
    n = len(a.vertices)
    if n != len(b.vertices):
        return False
    va = a.vertices
    vb = b.vertices
    # En sentido contrario el arco de cada tramo pasa al otro extremo y cambia de signo: el
    # tramo k del recorrido inverso va de vb[n-1-k] a vb[n-2-k], el tramo n-2-k al revés.
    inverso = tuple(
        Vertice(vb[n - 1 - k].x, vb[n - 1 - k].y, -vb[(n - 2 - k) % n].bulge) for k in range(n)
    )

    def igual(v: Vertice, w: Vertice) -> bool:
        return abs(v.x - w.x) <= tol and abs(v.y - w.y) <= tol and abs(v.bulge - w.bulge) <= 1e-6

    return any(
        all(igual(va[k], seq[(r + k) % n]) for k in range(n))
        for seq in (vb, inverso)
        for r in range(n)
    )


@functools.lru_cache(maxsize=256)  # entradas, no bytes: pocas, que un contorno grande pesa
def _aplanado_guardado(vertices: tuple[Vertice, ...], flecha: float) -> tuple:
    """El aplanado se reutiliza: clasificar N textos en M contornos no lo recalcula N·M
    veces (revisión 06-11-2026)."""
    return tuple(aplanar(list(vertices), True, flecha))


def _orientacion(ax, ay, bx, by, cx, cy) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _se_cortan(p1, p2, q1, q2, contiguos: bool) -> bool:
    """¿Se cortan los segmentos p1p2 y q1q2? Dos contiguos comparten un extremo, que no
    cuenta; solo se cortan si además se solapan (colineales y en sentido contrario)."""
    d1 = _orientacion(*q1, *q2, *p1)
    d2 = _orientacion(*q1, *q2, *p2)
    d3 = _orientacion(*p1, *p2, *q1)
    d4 = _orientacion(*p1, *p2, *q2)
    if contiguos:
        if d1 == d2 == d3 == d4 == 0:
            # Colineales con un extremo común: se solapan si el otro extremo de alguno cae
            # dentro del otro tramo (el contorno vuelve sobre sí mismo).
            comun = p1 if p1 in (q1, q2) else p2
            otro_p = p2 if comun == p1 else p1
            otro_q = q2 if comun == q1 else q1
            return (_en_segmento(p1, p2, otro_q) and otro_q != comun) or (
                _en_segmento(q1, q2, otro_p) and otro_p != comun
            )
        return False
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and 0 not in (d1, d2, d3, d4):
        return True
    return (
        (d1 == 0 and _en_segmento(q1, q2, p1))
        or (d2 == 0 and _en_segmento(q1, q2, p2))
        or (d3 == 0 and _en_segmento(p1, p2, q1))
        or (d4 == 0 and _en_segmento(p1, p2, q2))
    )


def _en_segmento(a, b, p) -> bool:
    return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])


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
