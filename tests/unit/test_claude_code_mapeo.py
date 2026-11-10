"""La pregunta «qué columna es qué» a Claude Code (docs/modules/obra.md, bloque 2b): solo
transporta; lo que proponga se comprueba contra el fichero (io/certificacion_excel)."""

from __future__ import annotations

import json

import pytest

from traza.ai import claude_code


def test_salida_con_columnas_se_acepta_y_sin_ellas_no():
    salida = {"hoja": "H", "fila_titulos": 2, "columnas": {"codigo": "A"}}
    ok = json.dumps({"is_error": False, "structured_output": salida})
    assert claude_code.interpretar_salida(0, ok, "", "columnas") == salida
    sin = json.dumps({"is_error": False, "structured_output": {"hoja": "H"}})
    with pytest.raises(claude_code.IaError, match="estructurada"):
        claude_code.interpretar_salida(0, sin, "", "columnas")


def test_las_instrucciones_no_piden_cifras():
    assert "no leas ni devuelvas ninguna cifra" in claude_code.INSTRUCCIONES_MAPEO
    roles = set(claude_code.ESQUEMA_MAPEO["properties"]["columnas"]["properties"])
    from traza.io.certificacion_excel import ROLES

    assert roles == set(ROLES)  # el esquema y el lector hablan de los mismos datos


def test_facturas_mismos_roles_que_el_lector_y_sin_cifras():
    """El esquema de la pregunta y el lector de facturas hablan de los mismos datos
    (vocabulario atado entre IA y lector, CLAUDE.md)."""
    assert "no leas ni devuelvas ninguna cifra" in claude_code.INSTRUCCIONES_MAPEO_FACTURAS
    roles = set(claude_code.ESQUEMA_MAPEO_FACTURAS["properties"]["columnas"]["properties"])
    from traza.io.facturas_erp import ROLES

    assert roles == set(ROLES)
