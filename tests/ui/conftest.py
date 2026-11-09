"""Pruebas de interfaz: ninguna lee ni escribe los ajustes reales del equipo."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _ajustes_aislados(tmp_path: Path, monkeypatch):
    """La plantilla de Word se guarda en un fichero temporal, no en los ajustes del equipo."""
    from PySide6.QtCore import QSettings

    from traza.ui import paso_entregables

    monkeypatch.setattr(
        paso_entregables,
        "ajustes_por_defecto",
        lambda: QSettings(str(tmp_path / "ajustes_traza.ini"), QSettings.IniFormat),
    )
