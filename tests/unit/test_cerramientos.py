"""Cerramientos típicos frente a los valores publicados en el CTE y su Catálogo de
Elementos Constructivos (CEC v06.3), y casos calculados a mano."""

from __future__ import annotations

import math

import pytest

from traza.rules import cerramientos as c


@pytest.mark.parametrize(
    "fm,u,f",
    [
        # CEC 4.3.1.1.1, marco metálico sin RPT (U_m 5,7), doble 4-12-4 normal (U_v 2,8,
        # g 0,76): U_H 3,4 y 4,0; F_H 0,64 y 0,53 con fracción de marco del 20 % y 40 %.
        (0.20, 3.4, 0.64),
        (0.40, 4.0, 0.53),
    ],
)
def test_hueco_reproduce_las_tablas_del_cec(fm, u, f):
    h = c.hueco("doble", "metalico", fraccion_marco=fm)
    assert h.u == pytest.approx(u, abs=0.05)
    assert h.factor_solar == pytest.approx(f, abs=0.005)


def test_hueco_sencillo_y_bajo_emisivo_frente_al_cec():
    # Vidrio sencillo (g 0,85) con marco metálico: U_H 5,7; F_H 0,72 (20 %) y 0,58 (40 %).
    assert c.hueco("sencillo", "metalico", 0.2).u == pytest.approx(5.7)
    assert c.hueco("sencillo", "metalico", 0.2).factor_solar == pytest.approx(0.72, abs=0.005)
    assert c.hueco("sencillo", "metalico", 0.4).factor_solar == pytest.approx(0.58, abs=0.005)
    # Bajo emisivo (g 0,63): F_H 0,54 (20 %) y 0,45 (40 %).
    assert c.hueco("doble_be", "metalico", 0.2).factor_solar == pytest.approx(0.54, abs=0.005)
    assert c.hueco("doble_be", "metalico", 0.4).factor_solar == pytest.approx(0.45, abs=0.005)
    with pytest.raises(ValueError):
        c.hueco("doble", "metalico", 1.5)


def test_panel_sandwich_y_chapa():
    # 40 mm de PUR (λ 0,024) en fachada: 1/(0,13 + 1,6667 + 0,04) = 0,5445.
    assert c.u_panel_sandwich(40) == pytest.approx(0.5445, abs=1e-4)
    # 30 mm en cubierta, Rsi hacia arriba: 1/(0,10 + 1,25 + 0,04) = 0,7194.
    assert c.u_panel_sandwich(30, cubierta=True) == pytest.approx(0.7194, abs=1e-4)
    chapa = c.envolvente("nave_chapa", "D3")
    assert chapa.u_muro == pytest.approx(1 / 0.17) and chapa.u_cubierta == pytest.approx(1 / 0.14)
    with pytest.raises(ValueError):
        c.u_panel_sandwich(0)


def test_solera_iso_13370():
    # Nave de 50 × 100 m: B' = 5000/(0,5·300) = 33,33 m; dt = 0,3 + 2·(0,17 + 0,04) = 0,72.
    # U = 2·2/(π·33,33 + 0,72)·ln(π·33,33/0,72 + 1) = 0,1898 W/m²K.
    b, dt = 5000 / 150, 0.72
    esperado = 4 / (math.pi * b + dt) * math.log(math.pi * b / dt + 1)
    assert c.u_solera(5000, 300) == pytest.approx(esperado)
    assert esperado == pytest.approx(0.190, abs=1e-3)
    # Muy aislada (dt ≥ B'): rama λ/(0,457·B' + dt).
    assert c.u_solera(4, 8, r_suelo=5) == pytest.approx(2 / (0.457 * 1 + 0.3 + 2 * 5.21))


def test_cte_por_zona():
    e = c.envolvente("cte", "D3")
    assert (e.u_muro, e.u_cubierta, e.u_terreno, e.hueco.u) == (0.41, 0.35, 0.65, 1.8)
    assert c.envolvente("cte", "α3").u_muro == 0.80
    assert "3.1.1.a" in e.fuente
    with pytest.raises(ValueError):
        c.envolvente("cte", "Z9")
    with pytest.raises(ValueError):
        c.envolvente("iglu", "D3")


def test_zona_climatica_con_nombres_de_la_guia_del_idae():
    # CTE DB HE, Anejo B: Madrid capital (≈ 650 m) D3; Bilbao (Bizkaia, < 250 m) C1.
    assert c.zona_climatica("Madrid", 650) == "D3"
    assert c.zona_climatica("Madrid", 500) == "C3"
    assert c.zona_climatica("Madrid", 500.5) == "D3"  # la columna «501–550»
    assert c.zona_climatica("Vizcaya", 30) == c.zona_climatica("Bizkaia", 30)
    with pytest.raises(KeyError):
        c.zona_climatica("Atlántida", 0)


def test_todos_los_tipos_tienen_fuente_y_valores_positivos():
    for tipo in c.TIPOS:
        e = c.envolvente(tipo, "C2")
        assert e.fuente and e.hueco.fuente
        assert e.u_muro > 0 and e.u_cubierta > 0 and 0 < e.hueco.factor_solar < 1
