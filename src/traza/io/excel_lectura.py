"""Lectura de hojas Excel (.xlsx/.xlsm) para la lectura asistida por IA.

La IA no lee el fichero: recibe un volcado de texto con la referencia de cada celda
(«Hoja!B12: valor»). Las comprobaciones vuelven después a la celda citada y comparan con
el valor real guardado en el fichero, que es exacto (no hay que interpretar texto).

Se leen los valores guardados (data_only): si una celda es una fórmula, se usa el último
resultado que Excel guardó. Un fichero que nunca se abrió en Excel puede no tenerlo; esas
celdas aparecen vacías y se avisa.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils.cell import coordinate_from_string

EXTENSIONES = (".xlsx", ".xlsm")


def volcar(ruta: Path) -> tuple[str, list[str]]:
    """Texto «Hoja!Celda: valor» de todas las celdas con contenido, y avisos."""
    avisos: list[str] = []
    wb_val = load_workbook(ruta, data_only=True)
    wb_form = load_workbook(ruta, data_only=False)
    lineas: list[str] = []
    try:
        for ws in wb_val.worksheets:
            formulas = wb_form[ws.title]
            lineas.append(f"=== Hoja «{ws.title}» ===")
            for fila_v, fila_f in zip(ws.iter_rows(), formulas.iter_rows(), strict=False):
                for cv, cf in zip(fila_v, fila_f, strict=False):
                    if cv.value is None:
                        if isinstance(cf.value, str) and cf.value.startswith("="):
                            avisos.append(
                                f"{ws.title}!{cv.coordinate}: fórmula sin resultado guardado "
                                "(abre y guarda el fichero en Excel para que conste)."
                            )
                        continue
                    lineas.append(f"{ws.title}!{cv.coordinate}: {cv.value}")
    finally:
        wb_val.close()
        wb_form.close()
    return "\n".join(lineas), avisos


def valor_celda(ruta: Path, referencia: str) -> Any:
    """Valor guardado en «Hoja!B12». KeyError si la hoja o la referencia no existen."""
    if "!" not in referencia:
        raise KeyError(f"Referencia sin hoja: «{referencia}».")
    hoja, celda = referencia.rsplit("!", 1)
    hoja = hoja.strip("'")
    coordinate_from_string(celda)  # valida la referencia (ValueError si no lo es)
    wb = load_workbook(ruta, data_only=True)
    try:
        if hoja not in wb.sheetnames:
            raise KeyError(f"No existe la hoja «{hoja}».")
        return wb[hoja][celda].value
    finally:
        wb.close()


def celdas(ruta: Path) -> dict[str, Any]:
    """Todas las celdas con valor guardado: {"Hoja!B12": valor}."""
    wb = load_workbook(ruta, data_only=True)
    try:
        return {
            f"{ws.title}!{c.coordinate}": c.value
            for ws in wb.worksheets
            for fila in ws.iter_rows()
            for c in fila
            if c.value is not None
        }
    finally:
        wb.close()
