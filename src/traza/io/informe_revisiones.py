"""Excel de la comparación entre revisiones (RF-009, docs/modules/revisiones.md):
resumen por apartado y una fila por cambio."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from openpyxl import Workbook

from traza.io.excel import _hoja
from traza.io.informe_redes import _con_extension


def que_cambia(c) -> str:
    if c.antes is None:
        return "Nuevo"
    if c.ahora is None:
        return "Ya no está"
    return "Cambia"


def _valor(v):
    return "—" if v is None else v


def exportar_excel(destino: Path, proyecto: str, antes: str, ahora: str, cambios) -> Path:
    destino = _con_extension(destino)
    wb = Workbook()
    wb.remove(wb.active)
    por_apartado = Counter(c.apartado for c in cambios)
    resumen = [["Proyecto", proyecto], ["De", antes], ["A", ahora]]
    resumen += [[f"Cambios en {a}", n] for a, n in por_apartado.items()]
    resumen.append(["Total de cambios", len(cambios)])
    _hoja(wb, "Resumen", [("Concepto", 40), ("Valor", 40)], resumen)
    _hoja(
        wb,
        "Cambios",
        [
            ("Apartado", 20),
            ("Elemento", 40),
            ("Dato", 26),
            ("Qué", 11),
            (antes, 22),
            (ahora, 22),
            ("Diferencia", 12),
            ("Unidad", 9),
        ],
        [
            [
                c.apartado,
                c.elemento,
                c.dato,
                que_cambia(c),
                _valor(c.antes),
                _valor(c.ahora),
                _valor(c.diferencia),
                c.unidad,
            ]
            for c in cambios
        ],
        numericas=(5, 6, 7),
    )
    wb.save(destino)
    return destino
