"""Listado de una red de aire en Excel (números como números, para revisar y para medir).

Hojas:
- Resumen: caudal, presión necesaria y potencia específica (RITE);
- Tramos: sección, velocidad, pérdida de carga;
- Terminales: caudal, de dónde sale y presión a disipar (equilibrado);
- Accesorios: coeficientes y pérdidas;
- Medición: metros y superficie de conducto por sección;
- Hipótesis y avisos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font

from traza.engines.conductos import FUENTE_VELOCIDAD, VELOCIDAD_MAXIMA
from traza.io.excel import FORMATO_NUMERO, _hoja
from traza.rules.accesorios_conductos import FUENTE, FUENTE_TERMINAL

TIPOS = {"impulsion": "Impulsión", "retorno": "Retorno", "extraccion": "Extracción"}
CLASES = {"principal": "Principal", "ramal": "Ramal", "terminal": "A terminal"}


def _con_extension(destino: Path) -> Path:
    destino = Path(destino)
    return (
        destino if destino.suffix.lower() == ".xlsx" else destino.with_name(destino.name + ".xlsx")
    )


def hipotesis(r: Any) -> list[str]:
    red = r.red
    return [
        "Rozamiento: Darcy-Weisbach con Colebrook, chapa galvanizada (ε = 0,09 mm); en "
        "rectangulares, diámetro equivalente de Huebscher (manual Climaver, 6.2.1).",
        f"Dimensionado: pérdida de carga constante de {red['friccion_objetivo']:g} Pa/m con "
        f"velocidad máxima {VELOCIDAD_MAXIMA['principal']:g} / {VELOCIDAD_MAXIMA['ramal']:g} / "
        f"{VELOCIDAD_MAXIMA['terminal']:g} m/s (principal / ramal / a terminal) — "
        f"{FUENTE_VELOCIDAD}.",
        "Secciones: rectangulares con lados múltiplos de 50 mm, relación ≤ 4"
        + (f" y alto ≤ {red['alto_maximo'] * 1000:.0f} mm" if red["alto_maximo"] else "")
        + "; circulares de la serie UNE-EN 1506 (80–1250 mm).",
        f"Accesorios: {FUENTE}. Codos con radio igual al lado del giro; derivaciones a 90°. "
        "En retorno y extracción (aire que converge) se usan los coeficientes de derivación "
        "divergente como aproximación.",
        f"Terminales: {FUENTE_TERMINAL}.",
        "Caudales: atributo CAUDAL del bloque si lo tiene; si no, el del espacio repartido "
        "entre sus terminales, "
        + {
            "volumen": "con las renovaciones/h de la tabla 3.6 según su volumen (Soler & "
            "Palau, Manual práctico de ventilación, cap. 3) y nunca menos que su aire exterior.",
            "renovaciones": f"con {red.get('renovaciones') or 0:g} renovaciones/h (tabla 3.5 "
            "de Soler & Palau como guía) y nunca menos que su aire exterior.",
        }.get(
            red.get("criterio_caudal") or "cargas",
            "con el aire exterior del espacio (cargas)."
            if red["tipo"] == "extraccion"
            else f"de las cargas, con ΔT de impulsión {red['salto_impulsion']:g} K.",
        ),
        "Presión necesaria: la del camino crítico de la red (sin el equipo: filtros, baterías "
        "y atenuadores los da su fabricante).",
        *(f"Aviso: {a}" for a in r.avisos),
    ]


def exportar_excel(destino: Path, proyecto: str, r: Any) -> Path:
    destino = _con_extension(destino)
    red, c = r.red, r.calculo
    wb = Workbook()
    wb.remove(wb.active)
    resumen = [
        ["Proyecto", proyecto, ""],
        ["Red", red["nombre"], ""],
        ["Tipo", TIPOS[red["tipo"]], ""],
        ["Caudal total", r.caudal_total_m3h, "m³/h"],
        ["Terminales conectados", r.terminales_conectados, ""],
        ["Terminales sin conectar a la red", len(r.terminales) - r.terminales_conectados, ""],
    ]
    if c is not None:
        resumen += [
            ["Presión necesaria en la red (camino crítico)", c.presion_necesaria_pa, "Pa"],
            ["Terminal del camino crítico", c.terminal_critico, ""],
            ["Potencia específica exigida (RITE IT 1.2.4.2.5)", f"SFP {r.sfp_exigida}", ""],
            [
                "Potencia eléctrica máxima del ventilador (SFP × caudal)",
                r.potencia_maxima_w,
                "W",
            ],
            [
                "Rendimiento mínimo del motoventilador solo con la red (cota inferior)",
                r.rendimiento_minimo,
                "",
            ],
            ["Metros de conducto", sum(m.longitud_m for m in r.medicion), "m"],
            ["Superficie de conducto", sum(m.superficie_m2 for m in r.medicion), "m²"],
        ]
    _hoja(wb, "Resumen", [("Concepto", 60), ("Valor", 30), ("Unidad", 8)], resumen, numericas=(2,))
    if c is not None:
        tramos = [
            [
                t.tramo.id,
                t.tramo.padre or "equipo",
                CLASES[t.tramo.clase],
                "paso" if t.tramo.es_paso else "derivación",
                t.tramo.terminal or "",
                t.tramo.longitud_m,
                t.tramo.caudal_m3s * 3600,
                t.seccion.texto(),
                t.velocidad_m_s,
                t.friccion_pa_m,
                t.perdida_friccion_pa,
                t.perdida_accesorios_pa,
                t.perdida_terminal_pa,
                t.perdida_pa,
            ]
            for t in c.tramos
        ]
        _hoja(
            wb,
            "Tramos",
            [
                ("Tramo", 8),
                ("Viene de", 9),
                ("Clase", 11),
                ("En la derivación", 13),
                ("Terminal", 9),
                ("Longitud (m)", 11),
                ("Caudal (m³/h)", 12),
                ("Sección (mm)", 12),
                ("Velocidad (m/s)", 12),
                ("Rozamiento (Pa/m)", 13),
                ("Rozamiento (Pa)", 12),
                ("Accesorios (Pa)", 12),
                ("Terminal (Pa)", 11),
                ("Total (Pa)", 11),
            ],
            tramos,
            numericas=range(6, 15),
        )
        accesorios = [
            [t.tramo.id, nombre, coef, pa] for t in c.tramos for nombre, coef, pa in t.accesorios
        ]
        _hoja(
            wb,
            "Accesorios",
            [("Tramo", 8), ("Accesorio", 26), ("Coeficiente C", 13), ("Pérdida (Pa)", 12)],
            accesorios,
            numericas=(3, 4),
        )
    terminales = [
        [
            t.codigo,
            t.bloque,
            t.espacio or "fuera de los espacios",
            t.caudal_m3h,
            c.caminos.get(t.codigo) if c else None,
            c.exceso_pa.get(t.codigo) if c else None,
            t.origen_caudal,
        ]
        for t in r.terminales
    ]
    _hoja(
        wb,
        "Terminales",
        [
            ("Terminal", 9),
            ("Bloque", 16),
            ("Espacio", 26),
            ("Caudal (m³/h)", 12),
            ("Pérdida del camino (Pa)", 14),
            ("A disipar con compuerta (Pa)", 16),
            ("Caudal de", 60),
        ],
        terminales,
        numericas=(4, 5, 6),
    )
    _hoja(
        wb,
        "Medición",
        [("Sección (mm)", 14), ("Longitud (m)", 12), ("Superficie (m²)", 14)],
        [[m.seccion, m.longitud_m, m.superficie_m2] for m in r.medicion],
        numericas=(2, 3),
    )
    _hoja(wb, "Hipótesis", [("Hipótesis, método y avisos", 140)], [[h] for h in hipotesis(r)])
    for ws in wb.worksheets:
        for celda in ws[1]:
            celda.font = Font(bold=True)
    for fila in wb["Resumen"].iter_rows(min_row=2, min_col=2, max_col=2):
        if isinstance(fila[0].value, float):
            fila[0].number_format = FORMATO_NUMERO
    wb.save(destino)
    return destino
