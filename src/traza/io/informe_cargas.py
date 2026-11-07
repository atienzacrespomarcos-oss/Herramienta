"""Informe de cargas y ventilación: Excel con todo el detalle y PDF presentable.

Decisión del usuario (07-11-2026): «Excel + PDF». El Excel sirve para revisar y dimensionar
aguas abajo (números como números); el PDF, para el cliente o la dirección facultativa, con
el resumen, las hipótesis y las fuentes. Recibe el resultado de `app.cargas.calcular`.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import pymupdf
from openpyxl import Workbook
from openpyxl.styles import Font

from traza.engines.cargas import NOTAS_INVIERNO, NOTAS_VERANO
from traza.io.excel import FORMATO_NUMERO, _hoja
from traza.rules.cerramientos import TIPOS

MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
GUIA = "IDAE, «Guía técnica. Condiciones climáticas exteriores de proyecto» (2010)"


def _con_extension(destino: Path, ext: str) -> Path:
    destino = Path(destino)
    # with_suffix cambiaría «Nave 2.1» por «Nave 2.xlsx»: se añade, no se sustituye.
    return destino if destino.suffix.lower() == ext else destino.with_name(destino.name + ext)


def _w_m2(w: float, area: float) -> float | None:
    return w / area if area else None


def _resumen(proyecto: str, r: Any) -> list[tuple[str, Any, str]]:
    e = r.estacion
    filas: list[tuple[str, Any, str]] = [
        ("Proyecto", proyecto, ""),
        ("Estación climática", f"{e.nombre} ({e.provincia}), {e.altitud_m:g} m", ""),
        ("Fuente del clima", f"{GUIA}, p. {e.pagina}", ""),
        ("Obra", f"{r.provincia}, {r.altitud_obra_m:g} m", ""),
        ("Zona climática (CTE DB HE, Anejo B)", r.zona, ""),
        ("Tipo de construcción", TIPOS.get(r.tipo_construccion, r.tipo_construccion), ""),
        ("Mes de proyecto (verano)", MESES[r.mes - 1], ""),
    ]
    for clave, c in r.condiciones.items():
        cob = "cobertura normal" if clave == "normal" else "cobertura alta (sanitario, CPD)"
        filas += [
            (f"Invierno, {cob}: temperatura seca", c.invierno_ts, "°C"),
            (f"Invierno, {cob}: humedad relativa", c.invierno_hr * 100, "%"),
            (f"Verano, {cob}: temperatura seca", c.verano_ts, "°C"),
            (f"Verano, {cob}: temperatura húmeda", c.verano_th, "°C"),
        ]
    filas += [
        ("Oscilación media diaria de verano (OMDR)", e.omdr, "°C"),
        ("Calefacción, suma de los espacios", r.invierno_total_w / 1000, "kW"),
        (
            "Refrigeración, suma de las puntas de cada espacio",
            sum(x.verano.total_w for x in r.espacios) / 1000,
            "kW",
        ),
        (
            f"Refrigeración simultánea (hora solar {r.hora_simultanea})",
            r.verano_simultaneo_w / 1000,
            "kW",
        ),
        ("Aire exterior total", sum(x.aire_exterior_m3h for x in r.espacios), "m³/h"),
    ]
    return filas


def exportar_excel(destino: Path, proyecto: str, r: Any) -> Path:
    destino = _con_extension(destino, ".xlsx")
    wb = Workbook()
    wb.remove(wb.active)
    _hoja(
        wb,
        "Resumen",
        [("Concepto", 55), ("Valor", 40), ("Unidad", 8)],
        [list(f) for f in _resumen(proyecto, r)],
        numericas=(2,),
    )
    cols = [
        ("Código", 10),
        ("Espacio", 26),
        ("Nivel", 16),
        ("Uso", 30),
        ("Superficie (m²)", 12),
        ("Altura (m)", 10),
        ("Volumen (m³)", 12),
        ("Personas", 10),
        ("Calefacción (W)", 14),
        ("Calefacción (W/m²)", 12),
        ("Refrig. sensible (W)", 14),
        ("Refrig. latente (W)", 14),
        ("Refrig. total (W)", 14),
        ("Refrig. (W/m²)", 12),
        ("Hora punta (solar)", 10),
        ("T. exterior en punta (°C)", 12),
        ("Aire exterior (m³/h)", 14),
        ("Infiltración (m³/h)", 14),
        ("Impulsión sala limpia (m³/h)", 14),
    ]
    filas = []
    for x in r.espacios:
        personas = next(d.valor for d in x.datos if d.concepto == "Ocupación")
        filas.append(
            [
                x.codigo,
                x.nombre,
                x.nivel,
                x.uso.nombre,
                x.superficie_m2,
                x.altura_m,
                x.volumen_m3,
                personas,
                x.invierno.total_w,
                _w_m2(x.invierno.total_w, x.superficie_m2),
                x.verano.sensible_w,
                x.verano.latente_w,
                x.verano.total_w,
                _w_m2(x.verano.total_w, x.superficie_m2),
                x.verano.hora_solar,
                x.verano.t_exterior_c,
                x.aire_exterior_m3h,
                x.infiltracion_m3h,
                x.impulsion_m3h,
            ]
        )
    _hoja(wb, "Espacios", cols, filas, numericas=range(5, 20))
    partidas = []
    for x in r.espacios:
        for estacion, res in (("Invierno", x.invierno), ("Verano", x.verano)):
            for p in res.partidas:
                partidas.append(
                    [x.codigo, x.nombre, estacion, p.concepto, p.sensible_w, p.latente_w]
                )
    _hoja(
        wb,
        "Partidas",
        [
            ("Código", 10),
            ("Espacio", 26),
            ("Estación", 10),
            ("Concepto", 40),
            ("Sensible (W)", 14),
            ("Latente (W)", 14),
        ],
        partidas,
        numericas=(5, 6),
    )
    datos = [
        [x.codigo, x.nombre, d.concepto, d.valor, d.unidad, d.origen, d.fuente]
        for x in r.espacios
        for d in x.datos
    ]
    _hoja(
        wb,
        "Datos y fuentes",
        [
            ("Código", 10),
            ("Espacio", 26),
            ("Dato", 30),
            ("Valor", 14),
            ("Unidad", 10),
            ("Origen", 12),
            ("Fuente", 90),
        ],
        datos,
        numericas=(4,),
    )
    cerr = [
        [
            x.codigo,
            x.nombre,
            c.nombre,
            c.clase,
            c.area_m2,
            c.u_w_m2k,
            c.factor_solar or None,
            # Orientación solo en fachadas y huecos: lo que el usuario revisa (revisión
            # 07-11-2026); cubierta y solera no la tienen.
            c.azimut if c.clase in ("opaco", "hueco") and c.inclinacion == 90 else None,
            c.inclinacion if c.clase != "terreno" else None,
        ]
        for x in r.espacios
        for c in x.cerramientos
    ]
    _hoja(
        wb,
        "Cerramientos",
        [
            ("Código", 10),
            ("Espacio", 26),
            ("Cerramiento", 16),
            ("Clase", 10),
            ("Superficie (m²)", 14),
            ("U (W/m²K)", 12),
            ("Factor solar", 12),
            ("Azimut (° desde el norte)", 14),
            ("Inclinación (°)", 12),
        ],
        cerr,
        numericas=(5, 6, 7, 8, 9),
    )
    _hoja(wb, "Hipótesis", [("Hipótesis, método y avisos", 140)], [[t] for t in hipotesis(r)])
    for ws in wb.worksheets:
        for celda in ws[1]:
            celda.font = Font(bold=True)
    wb["Resumen"].column_dimensions["B"].width = 45
    for fila in wb["Resumen"].iter_rows(min_row=2, min_col=2, max_col=2):
        if isinstance(fila[0].value, float):
            fila[0].number_format = FORMATO_NUMERO
    wb.save(destino)
    return destino


def hipotesis(r: Any) -> list[str]:
    env = r.envolvente
    lineas = [
        f"Clima: {GUIA}, ficha de la estación (p. {r.estacion.pagina}); percentiles según el "
        "apartado 5.2 (cobertura normal TS 99 % / TS 1 %; alta TS 99,6 % / TS 0,4 %); obra a "
        "otra cota según el anexo 7.3.",
        f"Cerramientos ({TIPOS.get(r.tipo_construccion, r.tipo_construccion)}): {env.fuente}. "
        f"U muro {env.u_muro:.2f}, cubierta {env.u_cubierta:.2f} W/m²K.",
        f"Huecos: U {env.hueco.u:.2f} W/m²K, factor solar {env.hueco.factor_solar:.2f} "
        f"({env.hueco.fuente}).",
        "Ocupación, calor de las personas, iluminación y equipos: valores de diseño de ASHRAE "
        "por tipo de espacio, salvo lo cambiado por el usuario (hoja «Datos y fuentes»).",
        "Ventilación: RITE IT 1.1.4.2 (IDA), RD 486/1997 (lugares de trabajo), UNE 100713 "
        "(quirófanos); infiltración UNE-EN 12831 con n50 del CTE DB HE, Anejo H.",
        "Verano: por componentes, hora a hora del día 21 del mes de proyecto (horas solares), "
        "cielo despejado de ASHRAE y temperatura sol-aire en opacos; hora punta = la de mayor "
        "carga total de cada espacio.",
    ]
    # Las notas del motor, no las del primer espacio: si era una cámara sin calefacción,
    # el informe decía «Invierno: espacio sin calefacción» (revisión 07-11-2026).
    lineas += [f"Invierno: {n}" for n in NOTAS_INVIERNO]
    lineas += [f"Verano: {n}" for n in NOTAS_VERANO]
    lineas += [
        "Cubierta: la parte de la planta sin otro espacio encima (rejilla de 30 × 30 puntos), "
        "con su superficie en planta (en cubierta inclinada la real es algo mayor); solera: "
        "los espacios de la cota más baja, con la U límite del CTE en edificio nuevo y, en el "
        "resto, la de la losa entera (ISO 13370).",
        "Refrigeración simultánea: sin las cámaras frigoríficas (instalación de frío aparte).",
    ]
    lineas += [f"Aviso: {a}" for a in r.avisos]
    return lineas


# --- PDF ----------------------------------------------------------------------------------

CSS = """
body { font-family: sans-serif; font-size: 9pt; color: #222; }
h1 { font-size: 16pt; margin-bottom: 2pt; }
h2 { font-size: 12pt; margin-top: 12pt; border-bottom: 1px solid #888; }
table { border-collapse: collapse; width: 100%; }
th { background-color: #e8eef4; text-align: left; font-size: 8pt; }
th, td { border: 1px solid #bbb; padding: 2pt 3pt; }
td.n { text-align: right; }
p.nota { font-size: 8pt; color: #555; }
"""


def _n(v: Any, dec: int = 1) -> str:
    if v is None:
        return "—"
    if isinstance(v, float | int):
        return f"{v:,.{dec}f}".replace(",", " ").replace(".", ",")
    return html.escape(str(v))


def _tabla(cabecera: list[str], filas: list[list[str]], numericas: set[int]) -> str:
    th = "".join(f"<th>{html.escape(c)}</th>" for c in cabecera)
    cuerpo = "".join(
        "<tr>"
        + "".join(
            f'<td class="n">{v}</td>' if i in numericas else f"<td>{v}</td>"
            for i, v in enumerate(f)
        )
        + "</tr>"
        for f in filas
    )
    return f"<table><tr>{th}</tr>{cuerpo}</table>"


def exportar_pdf(destino: Path, proyecto: str, r: Any) -> Path:
    destino = _con_extension(destino, ".pdf")
    partes = [f"<h1>Cargas térmicas y ventilación</h1><p>{html.escape(proyecto)}</p>"]
    partes.append("<h2>Datos de partida y resultados globales</h2>")
    partes.append(
        _tabla(
            ["Concepto", "Valor", "Unidad"],
            [[html.escape(c), _n(v), html.escape(u)] for c, v, u in _resumen(proyecto, r)[1:]],
            {1},
        )
    )
    partes.append("<h2>Cargas por espacio</h2>")
    filas = [
        [
            html.escape(x.codigo),
            html.escape(x.nombre),
            html.escape(x.uso.nombre),
            _n(x.superficie_m2),
            _n(x.invierno.total_w / 1000, 2),
            _n(x.verano.total_w / 1000, 2),
            _n(x.verano.total_w / x.superficie_m2, 0),
            _n(x.verano.hora_solar, 0),
            _n(x.aire_exterior_m3h, 0),
        ]
        for x in r.espacios
    ]
    partes.append(
        _tabla(
            [
                "Código",
                "Espacio",
                "Uso",
                "m²",
                "Calef. kW",
                "Refrig. kW",
                "W/m²",
                "Hora",
                "Aire ext. m³/h",
            ],
            filas,
            {3, 4, 5, 6, 7, 8},
        )
    )
    partes.append(
        '<p class="nota">Refrigeración: carga total (sensible + latente) en la hora punta '
        "de cada espacio, en hora solar.</p>"
    )
    partes.append("<h2>Desglose de verano en la hora punta</h2>")
    for x in r.espacios:
        partes.append(f"<p><b>{html.escape(x.codigo)} {html.escape(x.nombre)}</b></p>")
        partes.append(
            _tabla(
                ["Concepto", "Sensible W", "Latente W"],
                [
                    [html.escape(p.concepto), _n(p.sensible_w, 0), _n(p.latente_w, 0)]
                    for p in x.verano.partidas
                ],
                {1, 2},
            )
        )
    partes.append("<h2>Hipótesis, método y fuentes</h2><ul>")
    partes += [f"<li>{html.escape(t)}</li>" for t in hipotesis(r)]
    partes.append("</ul>")
    story = pymupdf.Story("".join(partes), user_css=CSS)
    pagina = pymupdf.paper_rect("a4")
    zona = pagina + (40, 40, -40, -40)
    writer = pymupdf.DocumentWriter(str(destino))
    try:
        mas = 1
        while mas:
            dispositivo = writer.begin_page(pagina)
            mas, _ = story.place(zona)
            story.draw(dispositivo)
            writer.end_page()
    finally:
        writer.close()
    return destino
