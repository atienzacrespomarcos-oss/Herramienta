"""Fachadas automáticas a partir de los contornos en planta."""

from __future__ import annotations

import pytest

from traza.engines.envolvente import Planta, fachadas, sector


def _rect(id_, x0, y0, x1, y1, horario=False):
    pts = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    return Planta(id_, tuple(reversed(pts)) if horario else pts)


def test_local_aislado_tiene_cuatro_fachadas():
    f = fachadas([_rect("a", 0, 0, 10, 5)])["a"]
    assert f == pytest.approx({"S": 10, "E": 5, "N": 10, "O": 5})


def test_dos_locales_separados_por_un_muro_y_sentido_de_giro():
    # Muro de 0,3 m entre x = 10 y x = 10,3; el segundo dibujado en sentido horario.
    f = fachadas([_rect("a", 0, 0, 10, 5), _rect("b", 10.3, 0, 20, 5, horario=True)])
    assert "E" not in f["a"] and "O" not in f["b"]
    assert f["a"]["N"] == pytest.approx(10) and f["b"]["E"] == pytest.approx(5)


def test_solape_parcial_y_separacion_mayor_que_un_muro():
    # «b» solo cubre 2 de los 5 m del lado este de «a»; «c» está a 3 m: no es vecino.
    f = fachadas([_rect("a", 0, 0, 10, 5), _rect("b", 10.2, 3, 15, 8), _rect("c", -13, 0, -3, 5)])
    assert f["a"]["E"] == pytest.approx(3)
    assert f["a"]["O"] == pytest.approx(5)


def test_norte_girado_del_plano():
    # Norte del plano apuntando a la derecha (+X): la cara +X es la norte.
    f = fachadas([_rect("a", 0, 0, 10, 5)], norte=90)["a"]
    assert f == pytest.approx({"O": 10, "N": 5, "E": 10, "S": 5})
    assert sector(-10) == "N" and sector(200) == "S" and sector(337.6) == "N"
