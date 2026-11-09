"""Emparejamiento de un plano revisado (app/planos.py) y comparación de contornos
(core/geometria.mismo_contorno). Casos de resultado conocido construidos a mano."""

from __future__ import annotations

from traza.app.planos import Confirmado, Propuesta, emparejar, punto_interior
from traza.core.geometria import Contorno, Vertice, mismo_contorno


def _c(puntos, bulge=0.0):
    return Contorno(tuple(Vertice(x, y, bulge) for x, y in puntos))


CUADRADO = [(0, 0), (10, 0), (10, 10), (0, 10)]


def _prop(handle, puntos, rol="espacio"):
    return Propuesta(handle, "A", rol, "LWPOLYLINE", _c(puntos), True, False, ())


def _conf(eid, puntos, rol="espacio"):
    return Confirmado(eid, eid, eid, rol, _c(puntos))


def test_mismo_contorno_empiece_donde_empiece_y_en_cualquier_sentido():
    a = _c(CUADRADO)
    assert mismo_contorno(a, _c(CUADRADO[2:] + CUADRADO[:2]))
    assert mismo_contorno(a, _c(list(reversed(CUADRADO))))
    assert mismo_contorno(a, _c([(x + 0.0005, y) for x, y in CUADRADO]))  # 0,5 mm: redondeo


def test_movido_o_girado_no_es_el_mismo_aunque_conserve_superficie():
    a = _c(CUADRADO)
    movido = _c([(x + 3, y) for x, y in CUADRADO])
    assert movido.area == a.area and movido.perimetro == a.perimetro
    assert not mismo_contorno(a, movido)
    assert not mismo_contorno(a, _c([(x + 0.002, y) for x, y in CUADRADO]))  # 2 mm
    assert not mismo_contorno(a, _c(CUADRADO, bulge=0.1))  # con arcos


def test_punto_interior_de_una_u():
    # U de 30 × 20 m con hueco de 10 m centrado arriba: el centroide (15; 8,3) cae en el
    # hueco (10 < x < 20, y > 5).
    u = _c([(0, 0), (30, 0), (30, 20), (20, 20), (20, 5), (10, 5), (10, 20), (0, 20)])
    x, y = punto_interior(u)
    assert u.contiene(x, y)


def test_emparejar_cambios_desaparecidos_nuevas_y_papel():
    viejos = [
        _conf("A", CUADRADO),
        _conf("B", [(20, 0), (30, 0), (30, 10), (20, 10)]),
        _conf("P", [(4, 4), (5, 4), (5, 5), (4, 5)], rol="obstaculo"),
    ]
    revisado = [
        _prop("1", CUADRADO),  # A igual
        _prop("2", [(4, 4), (5, 4), (5, 5), (4, 5)]),  # mismo sitio que P pero es espacio
        _prop("3", [(40, 0), (50, 0), (50, 10), (40, 10)]),  # nuevo
    ]
    r = emparejar(viejos, revisado)
    assert [(x.antes.elemento_id, x.despues.handle) for x in r.iguales] == [("A", "1")]
    assert not r.cambiados
    assert [c.elemento_id for c in r.desaparecidos] == ["B", "P"]
    assert [p.handle for p in r.nuevas] == ["2", "3"]


def test_un_espacio_partido_en_dos_se_queda_con_el_mas_parecido():
    viejos = [_conf("A", [(0, 0), (10, 0), (10, 10), (0, 10)])]
    revisado = [
        _prop("izq", [(0, 0), (7, 0), (7, 10), (0, 10)]),  # 70 m²
        _prop("der", [(7, 0), (10, 0), (10, 10), (7, 10)]),  # 30 m²: no contiene el centro
    ]
    r = emparejar(viejos, revisado)
    assert [(x.antes.elemento_id, x.despues.handle) for x in r.cambiados] == [("A", "izq")]
    assert [p.handle for p in r.nuevas] == ["der"]


def test_mismos_puntos_en_otro_orden_no_son_el_mismo_contorno():
    # Una L de 6 vértices y la misma con dos vértices contiguos intercambiados.
    l_ = [(0, 0), (20, 0), (20, 10), (10, 10), (10, 20), (0, 20)]
    otra = [(0, 0), (20, 0), (10, 10), (20, 10), (10, 20), (0, 20)]
    assert not mismo_contorno(_c(l_), _c(otra))


def test_arco_en_sentido_contrario_es_el_mismo():
    # Un solo tramo curvo (del primer al segundo vértice), recorrido al revés.
    ida = Contorno((Vertice(0, 0, 0.5), Vertice(10, 0, 0), Vertice(10, 10, 0), Vertice(0, 10, 0)))
    vuelta = Contorno(
        (Vertice(0, 10, 0), Vertice(10, 10, 0), Vertice(10, 0, -0.5), Vertice(0, 0, 0))
    )
    assert vuelta.area == ida.area
    assert mismo_contorno(ida, vuelta)
    assert not mismo_contorno(ida, Contorno(tuple(Vertice(v.x, v.y, 0) for v in ida.vertices)))
