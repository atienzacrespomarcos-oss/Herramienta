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
