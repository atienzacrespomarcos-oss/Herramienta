"""Excel de control de la obra (docs/modules/obra.md, «Salidas»).

En pantalla, lo que decide; aquí, todo el detalle: resumen (contrato y objetivo, real a hoy,
tu previsión y con futuribles), venta frente a objetivo por partida, paquetes y facturas,
certificaciones (y lo certificado de cada partida en cada una) y futuribles.

Las mismas reglas que el resto de Excel de TRAZA (io/excel.py): números como números, lo que
no consta vacío (nunca 0), textos ajenos nunca como fórmula, guardado atómico. Puro: recibe
lo ya calculado por la capa de aplicación (app/obra.py).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from traza.io.excel import FORMATO_NUMERO, _sin_formulas, _texto

FORMATO_PCT = '0.0" %"'
FORMATO_FECHA = "dd/mm/yyyy"


def _fecha(iso: str | None) -> date | None:
    return date.fromisoformat(iso[:10]) if iso else None


def _hoja(wb: Workbook, titulo: str, columnas: list[tuple[str, int]], primera: bool = False):
    ws = wb.active if primera else wb.create_sheet(titulo)
    ws.title = titulo
    ws.append([c for c, _ in columnas])
    for celda in ws[1]:
        celda.font = Font(bold=True)
    for i, (_, ancho) in enumerate(columnas, start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho
    ws.freeze_panes = "A2"
    return ws


def _fila(ws, valores: Iterable[Any], dinero=(), pct=(), fechas=()) -> None:
    ws.append([_texto(v) for v in valores])
    _sin_formulas(ws)
    fila = ws.max_row
    for col in dinero:
        ws.cell(row=fila, column=col).number_format = FORMATO_NUMERO
    for col in pct:
        ws.cell(row=fila, column=col).number_format = FORMATO_PCT
    for col in fechas:
        ws.cell(row=fila, column=col).number_format = FORMATO_FECHA


def _pct(parte: float | None, total: float | None) -> float | None:
    return None if parte is None or not total else round(100 * parte / total, 1)


def _redondeo(pct: float | None) -> float | None:
    return None if pct is None else round(pct, 1)


def exportar_control(
    destino: Path,
    proyecto: str,
    *,
    resumen: Any,
    foto: Any,
    escenario: Any,
    venta_por_codigo: dict[str, tuple[str, str, float | None]],
    certificaciones: list[dict[str, Any]],
    facturas: list[dict[str, Any]],
) -> Path:
    """`resumen`, `foto` y `escenario`: app/obra (ResumenObra, Foto, Escenario).
    `venta_por_codigo`: clave → (código, resumen, venta), en el orden del presupuesto.
    `certificaciones`: Proyecto.certificaciones() (con `del_mes` y `nota`)."""
    destino = Path(destino)
    if destino.suffix.lower() != ".xlsx":
        destino = destino.with_name(destino.name + ".xlsx")
    wb = Workbook()
    p = foto.prevision

    # --- Resumen: los cuatro números que deciden, en las cuatro miradas ---------------
    ws = _hoja(
        wb,
        "Resumen",
        [
            ("", 14),
            ("Contrato y objetivo", 20),
            ("Real a hoy", 16),
            ("Tu previsión", 16),
            ("Con futuribles marcados", 24),
        ],
        primera=True,
    )
    margen_obj = resumen.margen
    _fila(
        ws,
        [
            "Venta",
            foto.venta,
            foto.certificado,
            p["venta_total"] if p else None,
            escenario.venta,
        ],
        dinero=(2, 3, 4, 5),
    )
    _fila(
        ws,
        ["Coste", foto.objetivo, foto.facturado, p["coste_total"] if p else None, escenario.coste],
        dinero=(2, 3, 4, 5),
    )
    _fila(
        ws,
        ["Margen", margen_obj, foto.margen_real, foto.margen_previsto, escenario.margen],
        dinero=(2, 3, 4, 5),
    )
    _fila(
        ws,
        [
            "Margen (%)",
            _redondeo(resumen.margen_pct),
            _pct(foto.margen_real, foto.certificado),
            _redondeo(foto.margen_previsto_pct),
            _redondeo(escenario.margen_pct),
        ],
        pct=(2, 3, 4, 5),
    )
    ws.append([])
    notas = [
        "Real a hoy: venta = certificado a origen (última certificación); coste = facturado.",
        "Tu previsión: la tuya, a fin de obra"
        + (f" (actualizada el {_fecha(p['fecha']):%d/%m/%Y})" if p else " (aún no la has puesto)")
        + ". No incluye ampliaciones ni modificados pendientes.",
        "Con futuribles marcados: tu previsión más la venta y el coste estimado de los "
        f"futuribles marcados ({len(escenario.marcados)}).",
        "Celdas vacías = no consta (no es cero).",
    ]
    if p and p.get("nota"):
        notas.insert(2, f"Nota de tu previsión: {p['nota']}")
    for n in [*notas, *(f"Aviso: {a}" for a in resumen.avisos)]:
        _fila(ws, [n])

    # --- Venta frente a objetivo, por partida -------------------------------------------
    ws = _hoja(
        wb,
        "Venta y objetivo",
        [("Código", 14), ("Descripción", 50), ("Venta", 15), ("Objetivo", 15), ("Margen", 15)],
    )
    for x in resumen.lineas:
        _fila(ws, [x.codigo, x.resumen, x.venta, x.objetivo, x.margen], dinero=(3, 4, 5))
    ws.auto_filter.ref = ws.dimensions

    # --- Paquetes y facturas --------------------------------------------------------------
    ws = _hoja(
        wb,
        "Paquetes",
        [
            ("Paquete", 32),
            ("Objetivo", 15),
            ("Facturado", 15),
            ("Objetivo − facturado", 20),
            ("Facturas", 10),
            ("Cerrado", 10),
        ],
    )
    for x in foto.paquetes:
        _fila(
            ws,
            [
                x.nombre + ("" if x.en_objetivo else " (no está en el coste objetivo)"),
                x.objetivo if x.en_objetivo else None,
                x.facturado,
                x.diferencia if x.en_objetivo else None,
                x.facturas,
                "Sí" if x.cerrado else "No",
            ],
            dinero=(2, 3, 4),
        )
    ws = _hoja(
        wb,
        "Facturas",
        [("Paquete", 32), ("Proveedor", 30), ("Nº", 16), ("Fecha", 12), ("Importe", 15)],
    )
    for f in facturas:
        _fila(
            ws,
            [f["paquete"], f["proveedor"], f["numero"], _fecha(f["fecha"]), f["importe"]],
            dinero=(5,),
            fechas=(4,),
        )
    ws.auto_filter.ref = ws.dimensions

    # --- Certificaciones -----------------------------------------------------------------
    ws = _hoja(
        wb,
        "Certificaciones",
        [
            ("Nº", 6),
            ("Fecha", 12),
            ("Documento", 34),
            ("A origen", 15),
            ("De esta certificación", 20),
            ("% de la venta", 13),
            ("Nota", 60),
        ],
    )
    for c in certificaciones:
        _fila(
            ws,
            [
                c["numero"],
                _fecha(c["fecha"]),
                c["documento_nombre"],
                c["total_origen"],
                c["del_mes"],
                _pct(c["total_origen"], foto.venta),
                c["nota"] or None,
            ],
            dinero=(4, 5),
            pct=(6,),
            fechas=(2,),
        )
    # Lo certificado a origen de cada partida en cada certificación: dónde va la obra.
    columnas = [("Código", 14), ("Descripción", 46), ("Venta", 15)]
    columnas += [(f"Nº {c['numero']} a origen", 15) for c in certificaciones]
    columnas += [("% certificado", 13)]
    ws = _hoja(wb, "Certificado por partida", columnas)
    n = len(certificaciones)
    for clave, (codigo, texto, venta) in venta_por_codigo.items():
        origenes = [
            (c["partidas"][clave][2] if clave in c["partidas"] else None) for c in certificaciones
        ]
        ultimo = origenes[-1] if origenes else None
        _fila(
            ws,
            [codigo, texto, venta, *origenes, _pct(ultimo, venta)],
            dinero=tuple(range(3, 4 + n)),
            pct=(4 + n,),
        )
    ws.auto_filter.ref = ws.dimensions

    # --- Futuribles -------------------------------------------------------------------------
    ws = _hoja(
        wb,
        "Futuribles",
        [
            ("Futurible", 36),
            ("Venta", 15),
            ("Coste estimado", 15),
            ("Margen", 15),
            ("En el escenario", 15),
            ("Venta: de dónde sale", 36),
            ("Nota", 40),
            ("Avisos", 50),
        ],
    )
    for f in escenario.futuribles:
        _fila(
            ws,
            [
                f.titulo,
                f.venta,
                f.coste,
                f.margen,
                "Sí" if f.marcado else "No",
                f.origen,
                f.nota,
                "; ".join(f.avisos) or None,
            ],
            dinero=(2, 3, 4),
        )

    wi = wb.create_sheet("Información")
    _fila(wi, ["Obra", proyecto])
    _fila(wi, ["Generado por", "TRAZA"])
    _fila(wi, ["Fecha", date.today()], fechas=(2,))
    wi.column_dimensions["A"].width = 14
    wi.column_dimensions["B"].width = 60

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".xlsx.parcial")
    wb.save(temporal)
    temporal.replace(destino)
    return destino
