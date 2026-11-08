"""Salida a AutoCAD de una red de aire: DXF R2013 releído y LISP comprobado (sintaxis,
funciones de AutoLISP 2013, página de códigos). Red de tests/integration/test_redes_proyecto.py.
"""

from __future__ import annotations

import math
import re

import ezdxf
import pytest
from tests.integration.test_redes_proyecto import red  # noqa: F401 (fixture)

from traza.io import salida_autocad as sa
from traza.io.dxf import leer_dxf


def test_dxf_r2013_con_capas_etiquetas_y_xdata(red, tmp_path):  # noqa: F811
    p, red_id, _, _ = red
    dxf_ruta, lsp_ruta = p.exportar_red_autocad(red_id, tmp_path / "Red oficinas")
    assert dxf_ruta.name == "Red oficinas.dxf" and lsp_ruta.name == "Red oficinas.lsp"
    doc = ezdxf.readfile(dxf_ruta)
    assert doc.dxfversion == "AC1027" and doc.header["$INSUNITS"] == 4  # R2013, mm
    auditoria = doc.audit()
    assert not auditoria.has_errors
    capas = {c.dxf.name for c in doc.layers}
    assert {"TRAZA-IMP-EJES", "TRAZA-IMP-CONDUCTO", "TRAZA-IMP-TEXTOS"} <= capas
    msp = doc.modelspace()
    ejes = msp.query('LWPOLYLINE[layer=="TRAZA-IMP-EJES"]')
    conducto = msp.query('LWPOLYLINE[layer=="TRAZA-IMP-CONDUCTO"]')
    textos = [t.dxf.text for t in msp.query("TEXT")]
    assert len(ejes) == 3 and len(conducto) == 6  # dos líneas por tramo
    r = p.calcular_red(red_id)
    for t in r.calculo.tramos:
        etiqueta = f"{t.seccion.texto()} · {t.tramo.caudal_m3s * 3600:.0f} m³/h"
        assert etiqueta in textos
    assert any(t.startswith("D01 · ") for t in textos)
    # XDATA TRAZA con el id de la red y del tramo (ADR-0009).
    ids = {e.get_xdata("TRAZA")[0].value for e in ejes}
    assert ids == {f"{red_id}:{t.tramo.id}" for t in r.calculo.tramos}
    # Coordenadas del plano de partida (mm): el montante sale de la UTA en (45000, 10000).
    assert any((45000.0, 10000.0) in [tuple(v[:2]) for v in e.get_points()] for e in ejes)
    # En la T, el montante (500 de ancho) acaba en la cara del conducto horizontal (350):
    # y = 4000 + 175 mm. El horizontal se abre solo por arriba (a ±250 mm del eje del
    # montante) y por abajo sigue entero desde el eje.
    lineas = [[tuple(v[:2]) for v in e.get_points()] for e in conducto]
    montante = [ln for ln in lineas if ln[0][0] in (44750.0, 45250.0) and ln[-1][0] == ln[0][0]]
    assert len(montante) == 2 and all(
        min(p[1] for p in ln) == pytest.approx(4175) for ln in montante
    )
    horizontales = [ln for ln in lineas if ln not in montante]
    arriba = [ln for ln in horizontales if ln[0][1] == pytest.approx(4175)]
    abajo = [ln for ln in horizontales if ln[0][1] == pytest.approx(3825)]
    assert sorted(min(abs(p[0] - 45000) for p in ln) for ln in arriba) == pytest.approx([250, 250])
    assert sorted(min(abs(p[0] - 45000) for p in ln) for ln in abajo) == pytest.approx([0, 0])
    # Y TRAZA lo vuelve a leer (las mismas capas y longitudes).
    leido = leer_dxf(dxf_ruta)
    assert leido.capas["TRAZA-IMP-EJES"].longitud == pytest.approx(11_000)


def test_conducto_a_su_ancho_con_esquinas_a_inglete():
    # Eje en L de 10 m + 10 m; a ±0,25 m el lado exterior mide 10,25 + 10,25.
    def plano(pts):
        return [c for p in pts for c in p]

    exterior = sa._desplazada([(0, 0), (10, 0), (10, 10)], -0.25)
    assert plano(exterior) == pytest.approx(plano([(0, -0.25), (10.25, -0.25), (10.25, 10)]))
    interior = sa._desplazada([(0, 0), (10, 0), (10, 10)], 0.25)
    assert plano(interior) == pytest.approx(plano([(0, 0.25), (9.75, 0.25), (9.75, 10)]))
    assert sa._legible(math.pi) == pytest.approx(0)  # nunca boca abajo


def _llamadas(texto: str) -> set[str]:
    sin_cadenas = re.sub(r'"(?:\\.|[^"\\])*"', '""', texto)
    sin_comentarios = re.sub(r";[^\n]*", "", sin_cadenas)
    # Las listas de parámetros de defun y lambda no son llamadas.
    sin_parametros = re.sub(r"\((defun\s+\S+|lambda)\s*\([^)]*\)", r"(\1", sin_comentarios)
    return set(re.findall(r"\(\s*([A-Za-z_:][\w:\-]*)", sin_parametros))


def test_lisp_solo_con_funciones_de_autolisp_2013(red, tmp_path):  # noqa: F811
    p, red_id, _, _ = red
    _dxf, lsp = p.exportar_red_autocad(red_id, tmp_path / "Red")
    crudo = lsp.read_bytes()
    texto = crudo.decode("cp1252")  # ANSI: lo que lee AutoCAD 2013
    assert "m³/h" in texto and "×" in texto
    # Paréntesis equilibrados fuera de cadenas y comentarios.
    limpio = re.sub(r";[^\n]*", "", re.sub(r'"(?:\\.|[^"\\])*"', '""', texto))
    assert limpio.count("(") == limpio.count(")")
    usadas = _llamadas(texto)
    ajenas = usadas - sa.FUNCIONES_LISP - sa.PROPIAS_LISP
    assert not ajenas, f"Funciones fuera de la lista blanca de AutoLISP 2013: {ajenas}"
    assert "(defun c:TRAZA_RED" in texto and texto.count("(traza-pol ") >= 9
    assert '(regapp "TRAZA")' in texto


def test_red_sin_calcular_no_se_exporta(red, tmp_path):  # noqa: F811
    from traza.app.ordenes import OrdenRechazada

    p, red_id, plano_id, nivel_id = red
    p.definir_red(
        id=red_id,
        titulo="Impulsión oficinas",
        tipo="impulsion",
        plano_id=plano_id,
        capa_ejes="A-TEXTOS",
        bloques_terminales=["DIFUSOR"],
        nivel_id=nivel_id,
    )
    with pytest.raises(OrdenRechazada, match="no se ha podido calcular"):
        p.exportar_red_autocad(red_id, tmp_path / "X")


def test_nombre_con_comillas_y_barra_no_rompe_el_lisp(red, tmp_path):  # noqa: F811
    p, red_id, plano_id, nivel_id = red
    p.definir_red(
        id=red_id,
        titulo='Impulsión "norte" \\ zona',
        tipo="impulsion",
        plano_id=plano_id,
        capa_ejes="M-IMPULSION",
        bloques_terminales=["DIFUSOR"],
        bloque_equipo="UTA",
        nivel_id=nivel_id,
    )
    _dxf, lsp = p.exportar_red_autocad(red_id, tmp_path / "R")
    texto = lsp.read_bytes().decode("cp1252")
    assert '\\"norte\\" \\\\ zona' in texto
    limpio = re.sub(r";[^\n]*", "", re.sub(r'"(?:\\.|[^"\\])*"', '""', texto))
    assert limpio.count("(") == limpio.count(")")


def test_etiquetas_centradas_y_fuera_del_conducto(red, tmp_path):  # noqa: F811
    p, red_id, _, _ = red
    r = p.calcular_red(red_id)
    lineas, textos = sa.entidades(r)
    calc = {t.tramo.id: t for t in r.calculo.tramos}
    for tx in textos:
        tid = tx.ident.split(":")[1]
        if tid not in calc:
            continue  # etiqueta de terminal
        geo = next(g for g in r.topologia.tramos if g.tramo.id == tid)
        (x0, y0), (x1, y1) = geo.puntos[0], geo.puntos[-1]
        largo = math.hypot(x1 - x0, y1 - y0)
        distancia = abs((x1 - x0) * (y0 - tx.y) - (x0 - tx.x) * (y1 - y0)) / largo
        assert distancia >= calc[tid].seccion.a_m / 2 + sa.ALTURA_TEXTO_M - 1e-9
        assert -math.pi / 2 < tx.angulo_rad <= math.pi / 2  # nunca boca abajo
    doc = ezdxf.readfile(p.exportar_red_autocad(red_id, tmp_path / "C")[0])
    for t in doc.modelspace().query("TEXT"):
        assert (t.dxf.halign, t.dxf.valign) == (1, 2)  # centrado en su punto


def test_esquina_entre_dos_tramos_cerrada():
    from types import SimpleNamespace

    from traza.engines import conductos as cd
    from traza.engines.topologia_conductos import Terminal, leer

    # Un difusor en la esquina parte el codo en dos tramos: la esquina tiene que cerrarse.
    top = leer(
        [[(0, 0), (10, 0), (10, 10)]],
        [Terminal("D1", 10, 0, 0.2), Terminal("D2", 10, 10, 0.2)],
        equipo=(0, 0),
    )
    calc = cd.calcular_red([t.tramo for t in top.tramos], "impulsion", 0.8, 0.4)
    r = SimpleNamespace(
        red={"id": "r", "tipo": "impulsion", "nombre": "R"},
        calculo=calc,
        topologia=top,
        terminales=[],
    )
    lineas, _ = sa.entidades(r)
    conducto = [ln.puntos for ln in lineas if ln.capa.endswith("CONDUCTO")]
    assert len(conducto) == 4
    finales = {ln[-1] for ln in conducto}
    iniciales = {ln[0] for ln in conducto}
    # Cada lado de un tramo acaba donde empieza el del otro (la esquina, cerrada).
    assert len(finales & iniciales) == 2


def _red_ficticia(tramos: list[tuple[str, list, float]]):
    """Red ya «calculada» con la geometría y el ancho (m) que se pidan, para probar el
    dibujo sin depender del dimensionado."""
    from types import SimpleNamespace as N

    calc = [
        N(
            tramo=N(id=tid, caudal_m3s=0.1),
            seccion=N(a_m=ancho, texto=lambda a=ancho: f"{a * 1000:.0f}×300"),
        )
        for tid, _pts, ancho in tramos
    ]
    geo = [N(tramo=N(id=tid, longitud_m=1.0), puntos=pts) for tid, pts, _ancho in tramos]
    return N(
        red={"id": "r", "tipo": "impulsion", "nombre": "R"},
        calculo=N(tramos=calc, caminos={}),
        topologia=N(tramos=geo),
        terminales=[],
    )


def _conducto(r) -> dict[str, list[list]]:
    lineas, _ = sa.entidades(r)
    salida: dict[str, list[list]] = {}
    for ln in lineas:
        if ln.capa.endswith("CONDUCTO"):
            salida.setdefault(ln.ident.split(":")[1], []).append(list(ln.puntos))
    return salida


def _cerca(p, q) -> bool:
    return math.dist(p, q) < 1e-6


def test_esquina_cerrada_con_anchos_distintos():
    # 500 mm hasta la esquina y 400 mm después (revisión: con anchos distintos los lados no
    # casaban y la esquina quedaba abierta). Exterior: x = 10,20 e y = −0,25.
    c = _conducto(_red_ficticia([("A", [(0, 0), (10, 0)], 0.5), ("B", [(10, 0), (10, 10)], 0.4)]))
    a_der = next(ln for ln in c["A"] if ln[0][1] < 0)
    b_der = next(ln for ln in c["B"] if ln[0][0] > 10)
    assert _cerca(a_der[-1], b_der[0]) and _cerca(a_der[-1], (10.2, -0.25))
    a_izq = next(ln for ln in c["A"] if ln[0][1] > 0)
    b_izq = next(ln for ln in c["B"] if ln[0][0] < 10)
    assert _cerca(a_izq[-1], b_izq[0]) and _cerca(a_izq[-1], (9.8, 0.25))


def test_dos_tramos_que_salen_del_mismo_punto():
    # Dos salidas del equipo en L: los dos tramos empiezan en el nodo y la esquina se cierra
    # igual (izquierda de uno con derecha del otro).
    c = _conducto(_red_ficticia([("A", [(0, 0), (10, 0)], 0.5), ("B", [(0, 0), (0, 10)], 0.5)]))
    puntas = [ln[0] for lns in c.values() for ln in lns]
    assert sum(_cerca(p, (-0.25, -0.25)) for p in puntas) == 2  # exterior
    assert sum(_cerca(p, (0.25, 0.25)) for p in puntas) == 2  # interior


def test_giro_muy_cerrado_se_achaflana():
    # Vuelta a la izquierda de 170°: el inglete exterior (al este del nodo) saldría a unos
    # 11 semianchos; se achaflana uniendo las dos puntas. Los lados interiores sí se cortan
    # detrás del nodo, dentro del conducto, que es lo correcto.
    ang = math.radians(170)
    fin = (10 + 10 * math.cos(ang), 10 * math.sin(ang))
    c = _conducto(_red_ficticia([("A", [(0, 0), (10, 0)], 0.5), ("B", [(10, 0), fin], 0.5)]))
    puntos = [p for lns in c.values() for ln in lns for p in ln]
    assert max(p[0] for p in puntos) <= 10 + sa.INGLETE_MAXIMO * 0.25 + 1e-9
    a_der = next(ln for ln in c["A"] if ln[0][1] < 0)  # exterior de A (sur)
    b_der = next(ln for ln in c["B"] if ln[-1][1] > fin[1])  # exterior de B (norte)
    assert _cerca(a_der[-1], b_der[0])  # cerrado por el chaflán


def test_reduccion_en_linea_y_en_la_t_dibuja_el_escalon():
    # Recto 500 → 400: un escalón de 50 mm por lado en el nodo.
    c = _conducto(_red_ficticia([("A", [(0, 0), (10, 0)], 0.5), ("B", [(10, 0), (20, 0)], 0.4)]))
    for ln in c["A"]:
        assert _cerca(ln[-2], (10, math.copysign(0.25, ln[0][1])))
        assert _cerca(ln[-1], (10, math.copysign(0.2, ln[0][1])))
    # T: principal 500 → 400 con ramal hacia arriba. Por abajo (lado opuesto al ramal), el
    # escalón; por arriba, cada tramo acaba en la cara del ramal.
    c = _conducto(
        _red_ficticia(
            [
                ("A", [(0, 0), (10, 0)], 0.5),
                ("B", [(10, 0), (20, 0)], 0.4),
                ("C", [(10, 0), (10, 5)], 0.3),
            ]
        )
    )
    a_abajo = next(ln for ln in c["A"] if ln[0][1] < 0)
    assert _cerca(a_abajo[-1], (10, -0.2))
    a_arriba = next(ln for ln in c["A"] if ln[0][1] > 0)
    assert _cerca(a_arriba[-1], (9.85, 0.25))
    # El ramal arranca en la cara de cada tramo a su lado: sin hueco en el estrecho.
    b_arriba = next(ln for ln in c["B"] if ln[0][1] > 0)
    assert _cerca(b_arriba[0], (10.15, 0.2))
    c_lados = {round(ln[0][0], 6): ln[0] for ln in c["C"]}
    assert _cerca(c_lados[10.15], (10.15, 0.2)) and _cerca(c_lados[9.85], (9.85, 0.25))
    # Quiebro de 2° con reducción: también lleva el escalón (no queda abierto).
    ang = math.radians(2)
    c = _conducto(
        _red_ficticia(
            [
                ("A", [(0, 0), (10, 0)], 0.6),
                ("B", [(10, 0), (10 + 10 * math.cos(ang), 10 * math.sin(ang))], 0.4),
            ]
        )
    )
    for ln in c["A"]:
        destino = next(lb[0] for lb in c["B"] if (lb[0][1] > 0) == (ln[0][1] > 0))
        assert _cerca(ln[-1], destino)


def test_vuelta_en_u_se_cierra_sin_cruzar_el_conducto():
    # Vuelta de 179,9°: no puede tratarse como un tramo recto (unía izquierda con izquierda
    # a través del conducto). Cada lado acaba en la punta del lado que le corresponde.
    c = _conducto(_red_ficticia([("A", [(0, 0), (10, 0)], 0.5), ("B", [(10, 0), (0, 0.01)], 0.5)]))
    for ln in c["A"]:
        assert all(abs(p[0] - 10) < 0.3 or abs(p[1]) == pytest.approx(0.25) for p in ln)
    a_der = next(ln for ln in c["A"] if ln[0][1] < 0)
    assert a_der[-1][1] > 0  # el exterior (abajo) da la vuelta hasta el lado de B


def test_nombre_de_fichero_valido_en_windows():
    from traza.ui.paso_redes import _archivo

    assert _archivo('Red "norte": 1/2') == "Red -norte-- 1-2"
    assert _archivo("Impulsión.") == "Impulsión"
    assert _archivo("CON") == "red CON"
    assert _archivo("NUL .txt") == "red NUL .txt"
    assert _archivo("a\tb") == "a-b"
    assert _archivo("...") == "red"


def test_fichero_abierto_en_autocad(red, tmp_path, monkeypatch):  # noqa: F811
    from traza.app.ordenes import OrdenRechazada

    p, red_id, _, _ = red

    def bloqueado(*_a, **_k):
        raise PermissionError(13, "Permission denied", str(tmp_path / "R.dxf"))

    monkeypatch.setattr(sa, "escribir_dxf", bloqueado)
    with pytest.raises(OrdenRechazada, match="abierto en AutoCAD"):
        p.exportar_red_autocad(red_id, tmp_path / "R")
