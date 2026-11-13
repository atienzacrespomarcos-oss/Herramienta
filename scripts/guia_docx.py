"""Convierte docs/GUIA_DE_PRUEBA.md en «Guía de prueba.docx» para el paquete de Windows.

Uso: uv run python scripts/guia_docx.py <origen.md> <destino.docx>

Solo lo que usa la guía: títulos (#, ##), párrafos, listas numeradas («1. »), viñetas
(«- », y «   - » para el segundo nivel) y negrita (**…**). Las líneas que continúan un
punto (sangradas) se unen a él. Los números de las listas se escriben tal cual: así no
dependen de la numeración automática de Word.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.shared import Cm, Pt

NEGRITA = re.compile(r"\*\*(.+?)\*\*")


def _texto(parrafo, texto: str) -> None:
    pos = 0
    for m in NEGRITA.finditer(texto):
        if m.start() > pos:
            parrafo.add_run(texto[pos : m.start()])
        parrafo.add_run(m.group(1)).bold = True
        pos = m.end()
    if pos < len(texto):
        parrafo.add_run(texto[pos:])


def _bloques(lineas: list[str]) -> list[tuple[str, int, str]]:
    """(tipo, nivel, texto): tipo h1, h2, num, viñeta, p o p_sangrado; continuaciones
    unidas. Una línea sangrada que sigue a una viñeta más sangrada que ella no la continúa:
    es un párrafo del punto numerado («Pulsa Calcular» tras la lista de datos)."""
    bloques: list[tuple[str, int, str, int]] = []  # + sangría del marcador
    for linea in lineas:
        if not linea.strip():
            bloques.append(("vacio", 0, "", 0))
            continue
        sangria = len(linea) - len(linea.lstrip(" "))
        t = linea.strip()
        previo = bloques[-1] if bloques else None
        if t.startswith("## "):
            bloques.append(("h2", 0, t[3:], 0))
        elif t.startswith("# "):
            bloques.append(("h1", 0, t[2:], 0))
        elif re.match(r"^\d+\. ", t):
            bloques.append(("num", sangria // 3, t, sangria))
        elif t.startswith("- "):
            bloques.append(("viñeta", (sangria + 1) // 3, t[2:], sangria))
        elif previo and previo[0] == "viñeta" and sangria <= previo[3]:
            bloques.append(("p_sangrado", previo[1] - 1, t, sangria))
        elif previo and previo[0] in ("num", "viñeta", "p", "p_sangrado"):
            tipo, nivel, texto, marca = previo
            bloques[-1] = (tipo, nivel, texto + " " + t, marca)
        else:
            bloques.append(("p", 0, t, 0))
    return [(tipo, nivel, texto) for tipo, nivel, texto, _ in bloques if tipo != "vacio"]


def convertir(origen: Path, destino: Path) -> Path:
    doc = Document()
    estilo = doc.styles["Normal"]
    estilo.font.name = "Calibri"
    estilo.font.size = Pt(11)
    for tipo, nivel, texto in _bloques(Path(origen).read_text(encoding="utf-8").splitlines()):
        if tipo == "h1":
            doc.add_heading(texto, level=0)
        elif tipo == "h2":
            doc.add_heading(texto, level=1)
        else:
            p = doc.add_paragraph()
            if tipo == "viñeta":
                texto = "• " + texto
            if tipo in ("num", "viñeta"):
                p.paragraph_format.left_indent = Cm(0.6 + 0.8 * nivel)
                p.paragraph_format.first_line_indent = Cm(-0.5)
            elif tipo == "p_sangrado":
                p.paragraph_format.left_indent = Cm(0.6 + 0.8 * max(nivel, 0))
            p.paragraph_format.space_after = Pt(3)
            _texto(p, texto)
    destino = Path(destino)
    doc.save(destino)
    return destino


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Uso: python scripts/guia_docx.py <origen.md> <destino.docx>")
    print(convertir(Path(sys.argv[1]), Path(sys.argv[2])))
