"""Geometría de contornos con arcos: resultados comparados con fórmulas cerradas.

Los motores se validan con casos de resultado conocido (TESTING_STRATEGY §0.2): aquí las
figuras elementales cuya superficie y perímetro da la geometría clásica (círculo, semicírculo,
segmento circular).
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from traza.core.geometria import Contorno, ContornoInvalido, Vertice, longitud_polilinea


def rect(a: float, b: float, sentido: int = 1) -> Contorno:
    vs = [Vertice(0, 0), Vertice(a, 0), Vertice(a, b), Vertice(0, b)]
    return Contorno(tuple(vs if sentido > 0 else vs[::-1]))


def test_rectangulo():
    c = rect(40, 25)
    assert c.area == 1000 and c.perimetro == 130
    assert c.area_con_signo > 0 and rect(40, 25, -1).area_con_signo < 0


def test_circulo_con_dos_semicirculos():
    # Bulge 1 = semicírculo (DXF Reference, VERTEX, código 42).
    r = 3.0
    c = Contorno((Vertice(-r, 0, 1.0), Vertice(r, 0, 1.0)))
    assert c.area == pytest.approx(math.pi * r * r, rel=1e-12)
    assert c.perimetro == pytest.approx(2 * math.pi * r, rel=1e-12)
    # El mismo círculo recorrido en sentido horario (bulge negativo): misma superficie.
    h = Contorno((Vertice(-r, 0, -1.0), Vertice(r, 0, -1.0)))
    assert h.area == pytest.approx(math.pi * r * r, rel=1e-12)


@pytest.mark.parametrize("sentido", [1, -1])
def test_rectangulo_con_un_lado_en_semicirculo_hacia_fuera_y_hacia_dentro(sentido):
    # Nave 20 x 10 con el lado de 10 m (x = 20) en semicírculo de radio 5.
    semi = math.pi * 25 / 2
    for b, esperado in ((1.0, 200 + semi), (-1.0, 200 - semi)):
        vs = [Vertice(0, 0), Vertice(20, 0, b), Vertice(20, 10), Vertice(0, 10)]
        if sentido < 0:
            # Recorrido al revés: el tramo con arco empieza ahora en (20,10) y su bulge
            # cambia de signo para describir el mismo arco.
            vs = [Vertice(0, 10), Vertice(20, 10, -b), Vertice(20, 0), Vertice(0, 0)]
        c = Contorno(tuple(vs))
        assert c.area == pytest.approx(esperado, rel=1e-12)
        assert c.perimetro == pytest.approx(50 + math.pi * 5, rel=1e-12)


def test_segmento_circular_de_90_grados():
    # Cuarto de círculo de radio 2 (tramo recto + arco de 90°: bulge = tan(90°/4)).
    r = 2.0
    c = Contorno((Vertice(0, 0), Vertice(r, 0, math.tan(math.pi / 8)), Vertice(0, r)))
    assert c.area == pytest.approx(math.pi * r * r / 4, rel=1e-12)
    assert c.perimetro == pytest.approx(2 * r + math.pi * r / 2, rel=1e-12)


def test_arco_mayor_que_media_vuelta():
    # Círculo de radio 1 hecho con un arco de 270° y otro de 90°.
    r = 1.0
    p, q = Vertice(r, 0, math.tan(3 * math.pi / 2 / 4)), Vertice(0, -r, math.tan(math.pi / 2 / 4))
    c = Contorno((p, q))
    assert c.area == pytest.approx(math.pi, rel=1e-12)
    assert c.contiene(0, 0) and not c.contiene(1.2, 0)
    # El aplanado queda sobre la circunferencia (centro en el origen).
    assert all(math.hypot(x, y) == pytest.approx(1.0, abs=1e-9) for x, y in c.aplanado())


def test_contiene_con_arco_y_flecha():
    r = 3.0
    c = Contorno((Vertice(-r, 0, 1.0), Vertice(r, 0, 1.0)))
    assert c.contiene(0, 0) and c.contiene(0, 2.99) and not c.contiene(0, 3.01)
    # Con la flecha de 1 mm, los puntos a 2 mm del arco, por dentro y por fuera, se
    # clasifican bien en cualquier dirección (la cuerda nunca se aleja más de 1 mm).
    for grados in range(1, 180, 7):
        a = math.radians(grados)
        assert c.contiene((r - 0.002) * math.cos(a), (r - 0.002) * math.sin(a))
        assert not c.contiene((r + 0.002) * math.cos(a), (r + 0.002) * math.sin(a))
    # Con una flecha de 10 cm, algún punto a 2 mm por dentro cae ya fuera (la flecha cuenta).
    assert not all(
        c.contiene(
            (r - 0.002) * math.cos(math.radians(g)), (r - 0.002) * math.sin(math.radians(g)), 0.1
        )
        for g in range(1, 180)
    )


def test_escalado_de_mm_a_m():
    c = rect(40000, 25000).escalado(0.001)
    assert c.area == pytest.approx(1000) and c.perimetro == pytest.approx(130)


def test_contornos_invalidos():
    with pytest.raises(ContornoInvalido):
        Contorno((Vertice(0, 0),))
    with pytest.raises(ContornoInvalido):
        Contorno((Vertice(0, 0), Vertice(1, 0)))
    with pytest.raises(ContornoInvalido):
        Contorno((Vertice(0, 0), Vertice(math.nan, 0), Vertice(1, 1)))


def test_longitud_polilinea_abierta_y_cerrada():
    vs = [Vertice(0, 0), Vertice(3, 0), Vertice(3, 4)]
    assert longitud_polilinea(vs, False) == 7
    assert longitud_polilinea(vs, True) == 12
    assert longitud_polilinea([Vertice(0, 0, 1.0), Vertice(2, 0)], False) == pytest.approx(math.pi)


@given(
    st.floats(0.5, 200),
    st.floats(0.5, 200),
    st.floats(-1e4, 1e4),
    st.floats(-1e4, 1e4),
    st.one_of(st.just(0.0), st.floats(0.001, 0.99), st.floats(-0.99, -0.001)),
)
def test_traslacion_no_cambia_medidas_y_bulge_suma_su_segmento(a, b, dx, dy, bulge):
    base = rect(a, b)
    vs = [Vertice(v.x + dx, v.y + dy) for v in base.vertices]
    vs[1] = Vertice(vs[1].x, vs[1].y, bulge)  # arco en el lado vertical derecho (cuerda b)
    c = Contorno(tuple(vs))
    theta = 4 * math.atan(bulge)
    if bulge:
        r = b / (2 * math.sin(abs(theta) / 2))
        segmento = r * r / 2 * (theta - math.sin(theta))
        arco = r * abs(theta)
    else:
        segmento, arco = 0.0, b
    assert c.area == pytest.approx(abs(a * b + segmento), rel=1e-9, abs=1e-9)
    assert c.perimetro == pytest.approx(2 * a + b + arco, rel=1e-9)


def test_plano_georreferenciado_en_mm():
    # Coordenadas UTM en milímetros (~4,4e9): la superficie no puede perder cifras.
    x0, y0 = 440_000_000.0, 4_470_000_000.0
    vs = [
        Vertice(x0, y0),
        Vertice(x0 + 1000, y0),
        Vertice(x0 + 1000, y0 + 1000),
        Vertice(x0, y0 + 1000),
    ]
    assert Contorno(tuple(vs)).escalado(0.001).area == pytest.approx(1.0, rel=1e-9)


@pytest.mark.parametrize("bulge", [1e-300, 1e-208, -1e-12, 1e-7, 1e-6])
def test_bulge_diminuto_da_un_resultado_finito_y_casi_recto(bulge):
    # Con la fórmula del radio salía NaN (r² enorme por 0): lo encontró hypothesis.
    vs = (Vertice(0, 0), Vertice(1, 0, bulge), Vertice(1, 1), Vertice(0, 1))
    c = Contorno(vs)
    assert math.isfinite(c.area) and math.isfinite(c.perimetro)
    # Límite del segmento para θ pequeño: c²·θ/12, con θ = 4·atan(bulge) ≈ 4·bulge.
    assert c.area == pytest.approx(1 + 4 * bulge / 12, rel=1e-12, abs=1e-15)
    assert c.perimetro == pytest.approx(4, rel=1e-12)
    assert c.aplanado() == [(0, 0), (1, 0), (1, 1), (0, 1)]


def test_segmento_con_angulo_pequeno_sin_perder_cifras():
    # θ − sen θ con θ ~ 1e-5 pierde cifras: se usa la serie (revisión 06-11-2026). Se
    # compara con la serie de r²/2·(θ − sen θ) calculada con más términos en fracciones.
    from fractions import Fraction

    from traza.core.geometria import _segmento

    for theta in (2e-6, 1e-5, 3e-4, 9e-3):
        t = Fraction(theta)
        # θ − sen θ = Σ (−1)^(k+1) θ^(2k+1)/(2k+1)!, k ≥ 1
        dif = sum(
            ((-1) ** (k + 1)) * t ** (2 * k + 1) / math.factorial(2 * k + 1) for k in range(1, 8)
        )
        esperado = float(dif) / 8 / math.sin(theta / 2) ** 2
        assert _segmento(1.0, theta) == pytest.approx(esperado, rel=1e-12)


@pytest.mark.parametrize(
    "vertices,corta",
    [
        # Corbata: (0,0) (2,2) (2,0) (0,2) se cruza en (1,1).
        ([(0, 0), (2, 2), (2, 0), (0, 2)], True),
        # Rectángulo normal, también con un vértice repetido (no se corta).
        ([(0, 0), (4, 0), (4, 3), (0, 3)], False),
        ([(0, 0), (4, 0), (4, 0), (4, 3), (0, 3)], False),
        # Vuelve sobre sí mismo: (0,0) → (4,0) → (2,0) → (2,3).
        ([(0, 0), (4, 0), (2, 0), (2, 3)], True),
        # Cerradura de «8» que se toca en un vértice: (0,0) (2,1) (4,0) (4,2) (2,1) (0,2).
        ([(0, 0), (2, 1), (4, 0), (4, 2), (2, 1), (0, 2)], True),
        # Forma de «L» (cóncava, no se corta).
        ([(0, 0), (4, 0), (4, 1), (1, 1), (1, 3), (0, 3)], False),
    ],
)
def test_autointersecante(vertices, corta):
    c = Contorno(tuple(Vertice(x, y) for x, y in vertices))
    assert c.autointersecante() is corta


def test_arcos_que_se_anulan_no_tienen_superficie_y_se_cortan():
    c = Contorno((Vertice(0, 0, 1.0), Vertice(2, 0, -1.0)))
    assert c.area == pytest.approx(0, abs=1e-12)
    assert c.autointersecante()


def test_autointersecante_con_muchos_vertices_es_rapido():
    import time

    # Polígono estrellado de 4000 vértices sin cortes, y el mismo con un cruce al final.
    n = 4000
    vs = [
        Vertice(
            (10 + (k % 2)) * math.cos(2 * math.pi * k / n),
            (10 + (k % 2)) * math.sin(2 * math.pi * k / n),
        )
        for k in range(n)
    ]
    t0 = time.perf_counter()
    assert not Contorno(tuple(vs)).autointersecante()
    cruzado = vs[:-1] + [Vertice(-20, 0)]  # último vértice al otro lado: atraviesa la estrella
    assert Contorno(tuple(cruzado)).autointersecante()
    assert time.perf_counter() - t0 < 5


def test_barrido_da_lo_mismo_que_comparar_todos_los_pares():
    import random

    from traza.core.geometria import _se_cortan

    def todos_los_pares(c):
        pts = []
        for q in c.aplanado():
            if not pts or q != pts[-1]:
                pts.append(q)
        while len(pts) > 1 and pts[0] == pts[-1]:
            pts.pop()
        if len(pts) < 3:
            return False  # degenerado: el lector lo trata como «sin superficie»
        tr = [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
        n = len(tr)
        return any(
            _se_cortan(*tr[i], *tr[j], j == i + 1 or (i == 0 and j == n - 1))
            for i in range(n)
            for j in range(i + 1, n)
        )

    azar = random.Random(20261107)
    cortes = 0
    for _ in range(400):
        n = azar.randint(3, 9)
        c = Contorno(tuple(Vertice(azar.randint(0, 6), azar.randint(0, 6)) for _ in range(n)))
        esperado = todos_los_pares(c)
        cortes += esperado
        assert c.autointersecante() == esperado
    assert 50 < cortes < 400  # la muestra tiene de los dos casos
