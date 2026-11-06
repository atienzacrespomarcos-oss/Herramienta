from __future__ import annotations

import os
from pathlib import Path

import pymupdf
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from traza.app.proyecto import Proyecto  # noqa: E402


@pytest.fixture
def proyecto(tmp_path: Path):
    p = Proyecto.crear(tmp_path / "Nave prueba", "Nave prueba")
    yield p
    p.cerrar()


@pytest.fixture
def pdf_3_paginas(tmp_path: Path) -> Path:
    """PDF de prueba generado al vuelo (3 páginas). Solo existe dentro de los tests."""
    ruta = tmp_path / "oferta.pdf"
    doc = pymupdf.open()
    for n in range(3):
        pagina = doc.new_page()
        pagina.insert_text((72, 72), f"Página de prueba {n + 1}")
    doc.save(ruta)
    doc.close()
    return ruta
