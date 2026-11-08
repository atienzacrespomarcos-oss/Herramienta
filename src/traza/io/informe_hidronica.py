"""Excel del sistema hidráulico (docs/modules/hidronica.md): resumen por servicio,
circuitos, la lista completa de elementos para pedidos e hipótesis con sus fuentes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import Workbook

from traza.engines.hidraulica import SERVICIOS
from traza.io.excel import _hoja
from traza.io.informe_redes import _con_extension
from traza.rules import agua
from traza.rules import hidraulica as rh

MCA = 9806.65


def hipotesis(r: Any) -> list[str]:
    s = r.sistema
    return [
        "Esquema primario-secundario con depósito de inercia en paralelo (compensador): "
        "IDAE, «La bomba de calor en la rehabilitación energética de edificios» (2023).",
        f"Temperaturas: frío {s['frio_impulsion']:g}/{s['frio_retorno']:g} °C, calor "
        f"{s['calor_impulsion']:g}/{s['calor_retorno']:g} °C. Potencias: las cargas de los "
        "espacios de cada circuito (sin simultaneidad).",
        "Diámetros: ≤ 40 mm c.a./m y ≤ 1,2 m/s hasta DN50 (IDAE nº 18, Ap. B; ASHRAE "
        f"Fundamentals 1997 cap. 33). Tubería: {rh.MATERIALES[s['material']]}.",
        "Bombas: tuberías 2 × 1,3 × R·L (30 % por accesorios, IDAE nº 18 4.1–4.2) + unidad "
        "terminal + válvula de control con autoridad 1 (RITE IT 1.2.4.3.1.5). Generador: "
        "2 m c.a. de intercambiador si no hay dato (IDAE nº 18 4.1).",
        "Colectores: ≤ 0,9 m/s con el caudal total (criterio del separador de baja pérdida, "
        "Caleffi, Idraulica 18).",
        f"Volumen mínimo del generador: {s['volumen_minimo_l_kw']:g} l/kW; solo cuenta el agua "
        "del primario (IDAE 2023). Vaso de expansión: IDAE nº 18 3.1.3 (UNE 100155).",
        f"Agua: {agua.FUENTE}. Rugosidades: cobre 0,002 mm y termoplástico 0,006 mm (IDAE "
        "nº 18), acero 0,045 mm (Moody).",
        "Los volúmenes de agua de generador y unidades no se conocen: el vaso y el depósito "
        "se revisan con los datos del fabricante.",
        *(f"Aviso: {a}" for a in r.avisos),
    ]


def exportar_excel(destino: Path, proyecto: str, r: Any) -> Path:
    destino = _con_extension(destino)
    wb = Workbook()
    wb.remove(wb.active)
    resumen = [["Proyecto", proyecto, ""], ["Sistema", r.sistema["nombre"], ""]]
    for s in r.servicios:
        p = s.presiones
        n = SERVICIOS[s.clave]
        resumen += [
            [f"{n} · potencia del generador", s.potencia_kw, "kW"],
            [f"{n} · caudal", s.caudal_m3s * 3600, "m³/h"],
            [f"{n} · tubería del primario", s.primario.tubo.nombre, ""],
            [f"{n} · bomba de primario (altura)", s.altura_primario_pa / MCA, "m c.a."],
            [f"{n} · colectores", s.colector.tubo.nombre, ""],
            [f"{n} · depósito de inercia (mínimo)", s.inercia_l, "l"],
            [f"{n} · bocas del depósito", s.bocas_inercia.tubo.nombre, ""],
            [f"{n} · vaso de expansión (mínimo)", s.vaso_l, "l"],
            [f"{n} · presión de llenado / máxima", f"{p.llenado:g} / {p.maxima_servicio:g}", "bar"],
            [f"{n} · válvula de seguridad / alivio", f"{p.seguridad:g} / {p.alivio:g}", "bar"],
            [f"{n} · presión de prueba / PN", f"{p.prueba:g} / PN{p.nominal}", "bar"],
        ]
    _hoja(wb, "Resumen", [("Concepto", 50), ("Valor", 22), ("Unidad", 10)], resumen, numericas=(2,))
    filas = []
    for s in r.servicios:
        for c in s.circuitos:
            filas.append(
                [
                    SERVICIOS[s.clave],
                    c.datos.nombre,
                    c.datos.potencia_frio_w / 1000,
                    c.datos.potencia_calor_w / 1000,
                    c.caudal_m3s * 3600,
                    c.tubo.tubo.nombre,
                    c.tubo.velocidad_m_s,
                    c.tubo.friccion_pa_m,
                    c.datos.unidades,
                    c.conexion.tubo.nombre,
                    c.altura_bomba_pa / MCA,
                    c.kv_valvula,
                    c.aislamiento_mm,
                ]
            )
    _hoja(
        wb,
        "Circuitos",
        [
            ("Servicio", 18),
            ("Circuito", 16),
            ("Frío (kW)", 10),
            ("Calor (kW)", 10),
            ("Caudal (m³/h)", 12),
            ("Tubería", 10),
            ("v (m/s)", 9),
            ("R (Pa/m)", 9),
            ("Unidades", 9),
            ("Conexión", 10),
            ("Bomba (m c.a.)", 12),
            ("Kv válvula", 10),
            ("Aislamiento (mm)", 14),
        ],
        filas,
        numericas=(2, 3, 4, 6, 7, 10, 11),
    )
    _hoja(
        wb,
        "Elementos",
        [
            ("Zona", 34),
            ("Elemento", 46),
            ("Especificación", 70),
            ("DN", 6),
            ("Cantidad", 9),
            ("Norma o fuente", 48),
        ],
        [
            [e.zona, e.elemento, e.especificacion, e.dn or "", e.cantidad, e.norma]
            for e in r.elementos
        ],
    )
    _hoja(wb, "Hipótesis", [("Hipótesis, método y avisos", 140)], [[x] for x in hipotesis(r)])
    wb.save(destino)
    return destino
