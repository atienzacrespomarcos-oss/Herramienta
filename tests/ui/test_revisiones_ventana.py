"""Revisiones desde la ventana: Archivo → Emitir revisión… y Comparar con una revisión…"""

from __future__ import annotations

import pytest
from tests.ui.test_paso_redes import ventana  # noqa: F401 (fixture)

pytestmark = pytest.mark.ui


def test_emitir_y_comparar_desde_el_menu(ventana, tmp_path):  # noqa: F811
    v, q = ventana
    assert v.a_emitir_revision.isEnabled() and not v.a_comparar.isEnabled()
    q.preparar("texto", "Para oferta", "")
    v.a_emitir_revision.trigger()
    assert any("Rev. 0 · Para oferta" in t for t in q.informaciones)
    assert v.a_comparar.isEnabled()
    # Rev. 0 frente al estado actual, sin cambios.
    q.preparar("elegir", 0, 0)
    q.preparar("destino_excel", tmp_path / "Comparación")
    v.a_comparar.trigger()
    assert q.avisos == []
    assert any("No hay cambios" in t for t in q.informaciones)
    assert (tmp_path / "Comparación.xlsx").is_file()
    # Sin nombre no se emite (cancelar el diálogo).
    q.preparar("texto", None)
    v.a_emitir_revision.trigger()
    assert len(v.proyecto.revisiones()) == 1
