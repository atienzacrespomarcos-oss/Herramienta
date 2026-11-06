"""Exportación a Excel (openpyxl).

«Excel con todo» (decisión del usuario, 06-11-2026): los pedidos los hace en su ERP; TRAZA
le entrega en una hoja todas las partidas leídas, con su origen, listas para filtrar,
copiar o importar.

Reglas:
- Los números van como números (no como texto) para que Excel los sume y filtre.
- Lo que no consta se deja **vacío**, nunca 0: un 0 es una cantidad, un vacío es «no consta».
- El importe solo se calcula si constan cantidad y precio.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

COLUMNAS = [
    ("Documento", 28),
    ("Tipo", 12),
    ("Proveedor", 20),
    ("Capítulo", 30),
    ("Código", 14),
    ("Etiqueta", 10),
    ("Ud", 6),
    ("Descripción", 50),
    ("Cantidad", 12),
    ("Precio", 12),
    ("Importe", 14),
    ("Origen en el documento", 36),
    ("Estado de la lectura", 18),
    ("Motivo", 60),
]
ESTADOS = {
    "exacta": "Exacta (BC3)",
    "comprobada": "Comprobada",
    "a_revisar": "A revisar",
    "confirmada": "Confirmada por el usuario",
}
FORMATO_NUMERO = "#,##0.00"
RELLENO_REVISAR = PatternFill("solid", fgColor="FFE0B2")
CLASES = {"medicion": "Medición", "oferta": "Oferta", "presupuesto": "Presupuesto"}


def _capitulo(cap: list[list[str]]) -> str:
    return " / ".join(f"{c} {r}".strip() for c, r in cap)


def _texto(v: Any) -> Any:
    """Quita caracteres de control (openpyxl los rechaza al guardar)."""
    return ILLEGAL_CHARACTERS_RE.sub("", v) if isinstance(v, str) else v


def _sin_formulas(ws) -> None:
    """Un texto que empieza por «=» se guarda como texto, no como fórmula.

    openpyxl convierte en fórmula cualquier cadena que empiece por «=»; una descripción de
    un documento ajeno nunca debe ejecutarse como fórmula en el Excel del usuario.
    """
    for celda in ws[ws.max_row]:
        if isinstance(celda.value, str) and celda.value.startswith("="):
            celda.data_type = "s"


def exportar_partidas(
    destino: Path, proyecto: str, bloques: list[tuple[dict[str, Any], list[dict[str, Any]]]]
) -> Path:
    if destino.suffix.lower() != ".xlsx":
        # with_suffix cambiaría «Nave 2.1» por «Nave 2.xlsx»: se añade, no se sustituye.
        destino = destino.with_name(destino.name + ".xlsx")
    wb = Workbook()
    ws = wb.active
    ws.title = "Partidas"
    ws.append([c for c, _ in COLUMNAS])
    for celda in ws[1]:
        celda.font = Font(bold=True)
    for i, (_, ancho) in enumerate(COLUMNAS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho

    avisos_filas = []
    for med, partidas in bloques:
        for p in partidas:
            ws.append(
                [
                    _texto(x)
                    for x in [
                        med["documento_nombre"],
                        CLASES.get(med["clase"], med["clase"]),
                        med["proveedor"],
                        _capitulo(p["capitulo"]),
                        p["codigo"],
                        p["etiqueta"],
                        p["unidad"],
                        p["resumen"],
                        p["cantidad"],
                        p["precio"],
                        p["importe"],
                        p["localizador"],
                        ESTADOS.get(p["estado"], p["estado"]),
                        "; ".join(p["motivos"]) or None,
                    ]
                ]
            )
            _sin_formulas(ws)
            if p["estado"] == "a_revisar":
                # Que una partida dudosa no pase desapercibida al sumar en Excel.
                for celda in ws[ws.max_row]:
                    celda.fill = RELLENO_REVISAR
            for col in (9, 10, 11):
                ws.cell(row=ws.max_row, column=col).number_format = FORMATO_NUMERO
        avisos_filas += [(med["documento_nombre"], a) for a in med["avisos"]]

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    wa = wb.create_sheet("Avisos de lectura")
    wa.append(["Documento", "Aviso"])
    for celda in wa[1]:
        celda.font = Font(bold=True)
    wa.column_dimensions["A"].width = 30
    wa.column_dimensions["B"].width = 120
    for fila in avisos_filas or [("—", "Sin avisos.")]:
        wa.append([_texto(x) for x in fila])
        _sin_formulas(wa)

    wi = wb.create_sheet("Información")
    wi.append(["Proyecto", _texto(proyecto)])
    _sin_formulas(wi)
    wi.append(["Generado por", "TRAZA"])
    wi.append(["Nota", "Celdas vacías = no consta en el documento (no es cero)."])

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".xlsx.parcial")
    wb.save(temporal)
    temporal.replace(destino)
    return destino
