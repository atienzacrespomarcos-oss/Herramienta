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


def texto_paginas(ruta: Path) -> list[str]:
    """Texto de cada página (índice 0 = página 1). Cadena vacía si la página es imagen."""
    with pymupdf.open(ruta) as doc:
        return [p.get_text() for p in doc]


def renderizar_paginas(ruta: Path, carpeta: Path, ppp: int = 150) -> list[Path]:
    """Imágenes PNG de cada página, para PDF escaneados (sin texto que extraer)."""
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = []
    with pymupdf.open(ruta) as doc:
        for i, p in enumerate(doc, start=1):
            destino = carpeta / f"pagina_{i:03d}.png"
            p.get_pixmap(dpi=ppp).save(destino)
            rutas.append(destino)
    return rutas
