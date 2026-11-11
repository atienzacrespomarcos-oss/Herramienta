"""Caso de referencia publicado: permeabilidad al aire del edificio, n50 (CTE DB HE, Anejo H).

Fuente: Ministerio de Transportes, Movilidad y Agenda Urbana, «Guía de aplicación del DB HE
2019. Ejemplos prácticos I», ejemplo «Vivienda unifamiliar mínima», opción 3, apartado
«Cumplimiento F0 ET-n50 HE1», págs. 98 a 100.
https://www.codigotecnico.org/pdf/GuiasyOtros/Guia_aplicacion_DBHE2019_Ejemplos_I.pdf
(consultado el 11-11-2026).

Entradas exactas de la guía (pág. 100, totales del edificio): parte opaca en contacto con el
aire exterior 195,80 m² con Co 16 m³/h·m² (obra nueva); ventanas y lucernarios 36,40 m² de
clase 3 (Ch 9 m³/h·m²); puertas 2,20 m² con Ch 60 m³/h·m²; volumen de «aire interior»
341,30 m³. Resultado publicado:
    n50 = 0,629 · (16 · 195,80 + 9 · 36,40 + 60 · 2,20) / 341,30 = 6,6206 h⁻¹

Tolerancia: 0,00005 h⁻¹, media unidad de la última cifra que publica la guía (el motor usa la
misma expresión: la diferencia solo puede ser de redondeo).
"""

from __future__ import annotations

import pytest

from traza.engines import cargas as cg


def test_n50_vivienda_unifamiliar_minima_opcion_3():
    n50 = cg.n50(
        volumen_m3=341.30,
        area_opaca_m2=195.80,
        area_huecos_m2=36.40,
        co=cg.CO_OPACO["nuevo"],
        ch=cg.CH_CLASE[3],
        area_puertas_m2=2.20,
    )
    assert n50 == pytest.approx(6.6206, abs=0.00005)


def test_valores_de_tabla_de_la_guia():
    """Los coeficientes que usa la guía (pág. 100) son los del motor: Co 16 (nuevo) y 29
    (existente), clase 3 de carpintería = 9, puertas = 60."""
    assert cg.CO_OPACO == {"nuevo": 16.0, "existente": 29.0}
    assert cg.CH_CLASE[3] == 9.0
    assert cg.CH_PUERTAS == 60.0
