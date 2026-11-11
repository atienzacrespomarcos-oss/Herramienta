"""Excel de la propuesta de control (docs/modules/control.md): resumen de puntos por tipo,
categorías RITE por espacio, listado de puntos y comprobaciones."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from traza.io.excel import _hoja
from traza.io.informe_redes import _con_extension
from traza.rules import control as rc


def exportar_excel(destino: Path, proyecto: str, propuesta) -> Path:
    destino = _con_extension(destino)
    r = propuesta.resultado
    wb = Workbook()
    wb.remove(wb.active)
    resumen = [["Proyecto", proyecto]]
    resumen += [[f"{t} · {rc.TIPOS_PUNTO[t]}", n] for t, n in r.resumen.items()]
    resumen.append(["Total de puntos", sum(r.resumen.values())])
    _hoja(wb, "Resumen", [("Concepto", 40), ("Puntos", 12)], resumen, numericas=(2,))
    _hoja(
        wb,
        "Categorías",
        [
            ("Espacio", 28),
            ("Uso", 28),
            ("THM-C", 9),
            ("Por qué (termohigrométrico)", 70),
            ("IDA-C", 9),
            ("Por qué (calidad del aire)", 80),
        ],
        [
            [c.espacio, c.uso, c.thm or "—", c.thm_motivo, c.ida or "—", c.ida_motivo]
            for c in r.categorias
        ],
    )
    _hoja(
        wb,
        "Puntos",
        [
            ("Sistema", 30),
            ("Equipo", 34),
            ("Señal", 46),
            ("Tipo", 6),
            ("Cantidad", 9),
            ("Exigencia o motivo", 70),
        ],
        [[p.sistema, p.equipo, p.senal, p.tipo, p.cantidad, p.motivo] for p in r.puntos],
        numericas=(5,),
    )
    _hoja(
        wb,
        "Comprobaciones",
        [("Requisito", 70), ("Norma", 22), ("Resultado", 24), ("Detalle", 80)],
        [[c.requisito, c.norma, c.resultado, c.detalle] for c in r.comprobaciones],
    )
    hipotesis = [
        "Categorías THM-C e IDA-C: RITE (RD 1027/2007, texto consolidado), IT 1.2.4.3.2 "
        "(tabla 2.4.3.1) e IT 1.2.4.3.3 (tabla 2.4.3.2).",
        "Comprobaciones: CUMPLE / NO CUMPLE se calcula con los datos del proyecto; «Incluida "
        "en la propuesta» es una exigencia del RITE que la propuesta ya recoge.",
        "Señales de cada equipo que el RITE no fija: «Propuesta (práctica habitual)»; "
        "confírmalas con el integrador de control.",
        "Válvulas de las unidades: de 2 vías (secundarios de caudal variable) e independientes "
        "de la presión por encima de 70 kW, como en el paso «Sistema hidráulico».",
        *(f"Aviso: {a}" for a in propuesta.avisos),
    ]
    _hoja(wb, "Hipótesis", [("Hipótesis, método y avisos", 140)], [[x] for x in hipotesis])
    wb.save(destino)
    return destino
