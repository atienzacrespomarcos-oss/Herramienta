"""De ejes dibujados a árbol de tramos: casos de geometría conocida."""

from __future__ import annotations

import math

import pytest

from traza.engines import conductos as cd
from traza.engines.topologia_conductos import Terminal, TopologiaInvalida, leer


def _por_terminal(top):
    return {t.tramo.terminal: t.tramo for t in top.tramos if t.tramo.terminal}


def test_t_con_paso_y_ramal():
    # Tronco de 20 m dibujado como una sola línea; el ramal arranca en su interior (T).
    top = leer(
        [[(0, 0), (20, 0)], [(10, 0), (10, 5)]],
        [Terminal("D1", 20, 0, 0.4), Terminal("D2", 10, 5.3, 0.2)],
        equipo=(0, 0),
    )
    raiz = next(t.tramo for t in top.tramos if t.tramo.padre is None)
    assert raiz.longitud_m == pytest.approx(10) and raiz.caudal_m3s == pytest.approx(0.6)
    assert raiz.clase == "principal"
    t = _por_terminal(top)
    assert t["D1"].es_paso and not t["D2"].es_paso
    assert t["D1"].padre == raiz.id == t["D2"].padre
    assert t["D2"].longitud_m == pytest.approx(5) and t["D1"].clase == "terminal"
    assert not top.avisos and top.origen == (0, 0)


def test_codo_en_angulo_y_dibujado_como_arco():
    recto = leer([[(0, 0), (5, 0), (5, 5)]], [Terminal("D", 5, 5, 0.1)], equipo=(0, 0))
    assert recto.tramos[0].tramo.codos == (90.0,)
    # Arco de radio 0,4 m aproximado por cuerdas cortas entre dos rectas largas: un codo.
    arco = [(0.0, 0.0), (5.0, 0.0)]
    arco += [
        (5 + 0.4 * math.sin(a), 0.4 - 0.4 * math.cos(a))
        for a in (math.pi / 2 * k / 8 for k in range(1, 9))
    ]
    arco.append((5.4, 5.0))
    top = leer([arco], [Terminal("D", 5.4, 5, 0.1)], equipo=(0, 0))
    [codo] = top.tramos[0].tramo.codos
    assert codo == pytest.approx(90, abs=1)


def test_equipo_sin_marcar_anillo_y_terminal_lejano():
    # Un solo extremo libre sin terminal: es el equipo.
    top = leer([[(0, 0), (8, 0)]], [Terminal("D", 8, 0, 0.1)], equipo=None)
    assert top.origen == (0, 0)
    with pytest.raises(TopologiaInvalida, match="equipo"):
        leer([[(0, 0), (8, 0)], [(4, 0), (4, 3)]], [Terminal("D", 8, 0, 0.1)], equipo=None)
    with pytest.raises(TopologiaInvalida, match="anillo"):
        leer(
            [[(0, 0), (5, 0), (5, 5), (0, 5), (0, 0)], [(0, 0), (-3, 0)]],
            [Terminal("D", 5, 5, 0.1)],
            equipo=(-3, 0),
        )
    top = leer(
        [[(0, 0), (8, 0)]], [Terminal("D", 8, 0, 0.1), Terminal("X", 30, 30, 0.1)], equipo=(0, 0)
    )
    assert any("X" in a for a in top.avisos)
    with pytest.raises(TopologiaInvalida, match="No hay ejes"):
        leer([], [], equipo=None)


def test_difusor_sobre_el_conducto_no_suma_a_los_de_aguas_abajo():
    # D1 está encima del conducto, a mitad; D2 al final.
    top = leer(
        [[(0, 0), (20, 0)]],
        [Terminal("D1", 10, 0.3, 0.2), Terminal("D2", 20, 0, 0.2)],
        equipo=(0, 0),
    )
    t = _por_terminal(top)
    assert t["D1"].longitud_m == 0 and not t["D1"].es_paso
    r = cd.calcular_red([x.tramo for x in top.tramos], "impulsion", 0.8, 0.4)
    calc = {x.tramo.id: x for x in r.tramos}
    # El camino a D2 suma una sola pérdida de terminal (la suya), no la de D1.
    terminales = [calc[i].perdida_terminal_pa for i in calc if calc[i].perdida_terminal_pa]
    assert len(terminales) == 2
    camino_d2 = 0.0
    actual = t["D2"]
    while actual is not None:
        camino_d2 += calc[actual.id].perdida_pa
        actual = next((x.tramo for x in top.tramos if x.tramo.id == actual.padre), None)
    assert r.caminos["D2"] == pytest.approx(camino_d2)
    assert sum(calc[i].perdida_terminal_pa for i in calc if i != t["D1"].id) == 40


def test_rama_sin_terminal_se_avisa():
    top = leer([[(0, 0), (10, 0)], [(5, 0), (5, 4)]], [Terminal("D", 10, 0, 0.1)], equipo=(0, 0))
    assert any("no lleva caudal" in a for a in top.avisos)
    assert all(t.tramo.caudal_m3s > 0 for t in top.tramos)


def test_dibujo_grande_en_poco_tiempo():
    # 400 ramales en T sobre un tronco de una sola línea: 2000 segmentos. Antes de la
    # rejilla espacial tardaba 97 s; ahora, décimas. Margen amplio para la CI de Windows.
    import time

    pl = [[(0.0, 0.0), (1200.0, 0.0)]]  # hasta el último ramal: sin cola muerta
    terminales = []
    for i in range(400):
        x = 3.0 + 3.0 * i
        pl.append([(x, 0.0)] + [(x, -1.0 * (k + 1)) for k in range(5)])
        terminales.append(Terminal(f"D{i}", x, -5.0, 0.05))
    inicio = time.perf_counter()
    top = leer(pl, terminales, equipo=(0.0, 0.0))
    assert time.perf_counter() - inicio < 10
    # 399 derivaciones con dos hijos (798 tramos) más el tramo del equipo; el último ramal
    # sale del extremo del tronco: es un codo, no una derivación.
    assert len(top.tramos) == 799 and not top.avisos
