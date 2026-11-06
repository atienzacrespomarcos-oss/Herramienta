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


# --- Modificados --------------------------------------------------------------------------

COLUMNAS_MODIFICADO = [
    ("Tipo", 14),
    ("Capítulo", 26),
    ("Código", 12),
    ("Descripción", 46),
    ("Ud", 6),
    ("Cant. contrato", 13),
    ("Cant. modificada", 14),
    ("Dif. cantidad", 12),
    ("Precio", 12),
    ("Importe contrato", 15),
    ("Importe modificado", 16),
    ("Dif. importe", 14),
    ("Motivo", 18),
    ("Justificación", 50),
    ("Origen del precio", 40),
]
TIPOS_MODIFICADO = {
    "sin_cambio": "Sin cambio",
    "aumento": "Aumento",
    "disminucion": "Disminución",
    "anulacion": "Anulación",
    "nueva": "Partida nueva",
}


def _hoja_modificado(ws, lineas, titulo_total: bool, resumen) -> None:
    ws.append([c for c, _ in COLUMNAS_MODIFICADO])
    for celda in ws[1]:
        celda.font = Font(bold=True)
    for i, (_, ancho) in enumerate(COLUMNAS_MODIFICADO, start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho
    for x in lineas:
        ws.append(
            [
                _texto(v)
                for v in [
                    TIPOS_MODIFICADO[x.tipo],
                    _capitulo(x.capitulo),
                    x.codigo,
                    x.resumen,
                    x.unidad,
                    x.cantidad_contrato,
                    x.cantidad_modificada,
                    x.diferencia_cantidad,
                    x.precio,
                    x.importe_contrato,
                    x.importe_modificado,
                    x.diferencia_importe,
                    x.motivo,
                    x.justificacion,
                    x.origen_precio,
                ]
            ]
        )
        _sin_formulas(ws)
        for col in range(6, 13):
            ws.cell(row=ws.max_row, column=col).number_format = FORMATO_NUMERO
    if titulo_total:
        ws.append([])
        # Cada total bajo su columna: Importe contrato (J), Importe modificado (K) y
        # Dif. importe (L). Revisión 06-11-2026: los tres iban en la L.
        filas = []
        if len(lineas) != len(resumen.lineas):
            filas.append(("Suma de estas líneas", *_sumas(lineas)))
        filas.append(
            (
                "Presupuesto completo" + (" (parcial)" if resumen.parcial else ""),
                resumen.total_contrato,
                resumen.total_modificado,
                resumen.diferencia,
            )
        )
        for etiqueta, contrato, modificado, diferencia in filas:
            ws.append([etiqueta] + [None] * 8 + [contrato, modificado, diferencia])
            ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
            for col in (10, 11, 12):
                ws.cell(row=ws.max_row, column=col).number_format = FORMATO_NUMERO
                ws.cell(row=ws.max_row, column=col).font = Font(bold=True)
        for nota in resumen.notas():
            ws.append([_texto(nota)])
    ws.freeze_panes = "A2"


def _sumas(lineas) -> tuple[float, float, float]:
    """Sumas de los importes que constan (lo que no consta no se suma como 0: se dice en
    las notas)."""
    contrato = sum(x.importe_contrato for x in lineas if x.importe_contrato is not None)
    modificado = sum(x.importe_modificado for x in lineas if x.importe_modificado is not None)
    diferencia = sum(x.diferencia_importe for x in lineas if x.diferencia_importe is not None)
    return contrato, modificado, diferencia


def exportar_modificado(destino: Path, proyecto: str, modificado: dict, resumen) -> Path:
    """Excel del modificado: hoja de cambios (con totales) y presupuesto completo actualizado."""
    if destino.suffix.lower() != ".xlsx":
        destino = destino.with_name(destino.name + ".xlsx")
    wb = Workbook()
    ws = wb.active
    ws.title = f"Modificado nº {modificado['numero']}"
    _hoja_modificado(ws, resumen.cambios, True, resumen)
    wc = wb.create_sheet("Presupuesto actualizado")
    _hoja_modificado(wc, resumen.lineas, True, resumen)
    wi = wb.create_sheet("Información")
    for fila in (
        ["Proyecto", proyecto],
        ["Modificado", f"nº {modificado['numero']} — {modificado['titulo']}"],
        ["Base", modificado["base_nombre"]],
        ["Generado por", "TRAZA"],
        ["Nota", "Celdas vacías = no consta (no es cero). Los importes son cantidad × precio."],
    ):
        wi.append([_texto(v) for v in fila])
        _sin_formulas(wi)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".xlsx.parcial")
    wb.save(temporal)
    temporal.replace(destino)
    return destino
