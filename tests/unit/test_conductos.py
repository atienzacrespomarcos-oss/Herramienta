"""Motor de conductos frente al ejemplo resuelto del manual Climaver y a las tablas de
accesorios (casos de resultado conocido, docs/TESTING_STRATEGY.md §0.2)."""

from __future__ import annotations

import math

import pytest

from traza.engines import conductos as cd
from traza.rules import accesorios_conductos as acc


def test_ejemplo_del_manual_climaver():
    # Manual Climaver, p. 51: 600 × 600 mm, 1,70 m³/s, 20 °C y 101,325 kPa ⇒ De = 656,3 mm
    # y 0,37 Pa/m leídos en el gráfico de rozamiento de ASHRAE. Leer un gráfico da ±5 %.
    s = cd.Seccion("rectangular", 0.6, 0.6)
    assert s.diametro_equivalente_m == pytest.approx(0.6563, abs=1e-3)
    assert cd.friccion_pa_m(1.70, s) == pytest.approx(0.37, rel=0.05)


def test_colebrook_frente_a_swamee_jain():
    # Swamee-Jain (aproximación explícita de Colebrook, < 1 %) calculada a mano.
    re, er = 2.0e5, 1.5e-4
    sj = 0.25 / math.log10(er / 3.7 + 5.74 / re**0.9) ** 2
    assert cd.factor_friccion(re, er) == pytest.approx(sj, rel=0.01)
    assert cd.factor_friccion(1000, er) == pytest.approx(64 / 1000)


def test_coeficientes_de_tabla():
    # Codo 90°, r/b = 1, a/b = 1, Re alto: C′ = 0,21 y K_Re = 1.
    assert acc.codo_radio(0.4, 0.4, 1.0, 90, 3e5) == pytest.approx(0.21)
    # Errata corregida: K_Re (r/b ≥ 0,75, Re = 6·10⁴) = 1,46, no 0,46.
    assert acc.k_reynolds(6e4, 1.0) == pytest.approx(1.46)
    # Codo de 45°: K_θ = 0,60.
    assert acc.codo_radio(0.4, 0.4, 1.0, 45, 3e5) == pytest.approx(0.21 * 0.60)
    # Interpolación entre a/b = 1 (0,21) y 1,5 (0,19) en r/b = 1.
    assert acc.codo_radio(0.5, 0.4, 1.0, 90, 3e5) == pytest.approx(0.20)
    assert acc.derivacion_ramal(3, 5, 90) == pytest.approx(1.0)
    assert acc.derivacion_ramal(0.5, 1, 45) == pytest.approx(0.45)
    assert acc.derivacion_paso(1.0, 1.0, 0.5) == pytest.approx(0.20)
    assert acc.derivacion_paso(0.5, 1.0, 0.2) == pytest.approx(0.25)


@pytest.mark.parametrize("caudal", [0.05, 0.3, 1.0, 2.5])
def test_dimensionado_rectangular_minimo_y_dentro_de_limites(caudal):
    d = cd.dimensionar(caudal, "rectangular", 0.8, 7.5, alto_max_m=0.4)
    s = d.seccion
    assert d.velocidad_m_s <= 7.5 + 1e-9 and d.friccion_pa_m <= 0.8 + 1e-9
    assert s.b_m <= 0.4 + 1e-9 and s.a_m / s.b_m <= 4 + 1e-9 and not d.avisos
    assert round(s.a_m * 1000) % 50 == 0 and round(s.b_m * 1000) % 50 == 0
    # Ninguna sección de menor perímetro (lados de 50 mm, relación ≤ 4) cumple.
    for b in range(100, 401, 50):
        for a in range(b, 4 * b + 1, 50):
            prueba = cd.Seccion("rectangular", a / 1000, b / 1000)
            if prueba.perimetro_m < s.perimetro_m - 1e-9:
                assert caudal / prueba.area_m2 > 7.5 or cd.friccion_pa_m(caudal, prueba) > 0.8


def test_dimensionado_circular_y_limites():
    d = cd.dimensionar(0.3, "circular", 0.8, 7.5)
    assert d.seccion.texto() == "Ø315"
    anterior = cd.Seccion("circular", 0.25)
    assert cd.friccion_pa_m(0.3, anterior) > 0.8 or 0.3 / anterior.area_m2 > 7.5
    assert cd.dimensionar(20, "circular", 0.8, 10).avisos  # más que Ø1250
    # Alto máximo muy bajo: se pasa de relación 4 y se avisa.
    assert cd.dimensionar(3.0, "rectangular", 0.8, 10, alto_max_m=0.15).avisos
    with pytest.raises(ValueError):
        cd.dimensionar(0, "circular", 0.8, 10)


def test_red_en_t_camino_critico_y_equilibrado():
    tramos = [
        cd.Tramo("T1", None, 10, 0.6, "principal"),
        cd.Tramo("T2", "T1", 5, 0.3, "terminal", es_paso=True, terminal="D1"),
        cd.Tramo("T3", "T1", 3, 0.3, "terminal", es_paso=False, codos=(90,), terminal="D2"),
    ]
    r = cd.calcular_red(tramos, "impulsion", 0.8, 0.4)
    t = {x.tramo.id: x for x in r.tramos}
    assert t["T1"].velocidad_m_s <= 10 and t["T2"].velocidad_m_s <= 4
    assert t["T2"].perdida_terminal_pa == 40  # RITE: unidad terminal 40 Pa
    # Ramal a 90°: C_d = 1 con la presión dinámica del ramal.
    pv3 = 1.204 * t["T3"].velocidad_m_s ** 2 / 2
    ramal = dict((n, pa) for n, _c, pa in t["T3"].accesorios)
    assert ramal["Derivación, ramal"] == pytest.approx(pv3)
    assert r.caminos["D1"] == pytest.approx(t["T1"].perdida_pa + t["T2"].perdida_pa)
    assert r.caminos["D2"] == pytest.approx(t["T1"].perdida_pa + t["T3"].perdida_pa)
    critico = max(r.caminos, key=r.caminos.get)
    assert r.terminal_critico == critico and r.presion_necesaria_pa == r.caminos[critico]
    assert r.exceso_pa[critico] == 0 and min(r.exceso_pa.values()) >= 0


def test_red_mal_formada():
    with pytest.raises(ValueError, match="no existe"):
        cd.calcular_red([cd.Tramo("T1", "X", 1, 0.1, "principal")], "impulsion", 0.8, 0.4)
    with pytest.raises(ValueError, match="Tipo de red"):
        cd.calcular_red([], "aspiracion", 0.8, 0.4)
    with pytest.raises(ValueError, match="ciclo"):
        cd.calcular_red(
            [
                cd.Tramo("A", "B", 1, 0.1, "principal", terminal="X"),
                cd.Tramo("B", "A", 1, 0.1, "principal"),
            ],
            "impulsion",
            0.8,
            0.4,
        )


def test_potencia_especifica_rite():
    assert cd.categoria_sfp(1500) == 4 and cd.categoria_sfp(5000) == 7
    assert cd.categoria_sfp(300) == 0
    assert cd.rendimiento_minimo(1000, 4) == pytest.approx(0.5)
    assert cd.SFP_EXIGIDA[("impulsion", True)] == 4


def test_sin_alto_maximo_y_codo_con_el_ancho_en_el_plano_del_giro():
    # Sin alto máximo se puede pasar de 1 m de alto (antes se limitaba a 1 m sin decirlo).
    d = cd.dimensionar(25.0, "rectangular", 0.8, 10, alto_max_m=None)
    assert not d.avisos and d.seccion.b_m > 1.0
    # Codo de un 600 × 300 que gira en planta: lado en el plano del giro = ancho (600),
    # a/b = 300/600 = 0,5 ⇒ C′ = 0,25 con r/b = 1 (manual Climaver, p. 53).
    tramo = cd.Tramo(
        "T",
        None,
        1,
        0.7,
        "principal",
        codos=(90,),
        seccion_fija=cd.Seccion("rectangular", 0.6, 0.3),
    )
    r = cd.calcular_red([tramo], "impulsion", 0.8, 0.4)
    [(_n, c, _pa)] = r.tramos[0].accesorios
    re = cd.reynolds(0.7, cd.Seccion("rectangular", 0.6, 0.3))
    assert c == pytest.approx(0.25 * acc.k_reynolds(re, 1.0))
