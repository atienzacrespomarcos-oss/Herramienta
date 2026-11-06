"""Lectura de PDF (PyMuPDF, ADR-0012)."""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf

# «p. 14», «p.14», «pág. 14», «página 14», seguido opcionalmente de más detalle
# («p. 14, tabla 3»). Lo específico antes que lo general: «página» antes de «p».
_PAGINA = re.compile(r"^\s*(?:página|pág\.?|p\.?)\s*(\d+)\b", re.IGNORECASE)


def contar_paginas(ruta: Path) -> int:
    with pymupdf.open(ruta) as doc:
        return doc.page_count


def pagina_citada(localizador: str) -> int | None:
    """Número de página que cita el localizador, o None si no cita página."""
    m = _PAGINA.match(localizador)
    return int(m.group(1)) if m else None
