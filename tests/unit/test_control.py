"""Propuesta de control (engines/control.py, docs/modules/control.md).

Las categorías se comprueban contra el texto del RITE (IT 1.2.4.3.2 y 1.2.4.3.3, BOE, texto
consolidado) y los recuentos de puntos se cuentan a mano señal por señal.
"""

from __future__ import annotations

import math

import pytest

from traza.engines import control as mc
from traza.rules import control as rc
from traza.rules import usos


def _e(clave: str, nombre: str = "") -> mc.EspacioControl:
    u = usos.POR_CLAVE[clave]
    return mc.EspacioControl(
        nombre or clave, u.clave, u.nombre, u.t_invierno is not None, u.ventilacion.metodo
    )


def test_categorias_segun_el_rite():
    # Ocupación variable (salón de actos y similares): IDA-C6 obligatorio (IT 1.2.4.3.3.4).
    c = mc.categoria(_e("reuniones"), refrigeracion=True)
    assert (c.thm, c.ida, c.ocupacion) == ("THM-C3", "IDA-C6", "variable")
    assert "1.2.4.3.3.4" in c.ida_motivo
    # Sin ocupación permanente (pasillo): C2, C3 o C4 (IT 1.2.4.3.3.3); se propone C3.
    c = mc.categoria(_e("pasillo"), refrigeracion=True)
    assert (c.ida, c.ocupacion) == ("IDA-C3", "no_permanente")
    # Ocupación permanente: C2, C3 y C4 NO valen; oficina → C6 (CO₂), producción → C1.
    c = mc.categoria(_e("oficina_abierta"), refrigeracion=True)
    assert (c.ida, c.ocupacion) == ("IDA-C6", "permanente")
    c = mc.categoria(_e("almacen"), refrigeracion=True)
    assert (c.ida, c.ocupacion) == ("IDA-C1", "permanente")
    # Solo calefacción: THM-C1 (tabla 2.4.3.1).
    assert mc.categoria(_e("despacho"), refrigeracion=False).thm == "THM-C1"
    # Quirófano: humedad en el local por UNE 100713 → THM-C5.
    assert mc.categoria(_e("quirofano"), refrigeracion=True).thm == "THM-C5"
    # Cámara frigorífica: sin categoría de climatización.
    camara = next(u for u in usos.USOS if u.t_invierno is None)
    c = mc.categoria(_e(camara.clave), refrigeracion=True)
    assert (c.thm, c.ida, c.ocupacion) == (None, None, "ninguna")


def test_ninguna_propuesta_usa_c2_c3_c4_con_ocupacion_permanente():
    """IT 1.2.4.3.3.3, para todos los usos del catálogo."""
    for u in usos.USOS:
        c = mc.categoria(_e(u.clave), refrigeracion=True)
        if c.ocupacion == "permanente":
            assert c.ida not in rc.SIN_OCUPACION_PERMANENTE, u.clave
        if u.clave in rc.OCUPACION_VARIABLE:
            assert c.ida == "IDA-C6", u.clave


def test_los_usos_del_control_existen_en_el_catalogo():
    """Vocabulario atado: un uso renombrado en el catálogo dejaría el IDA-C6 obligatorio
    sin aplicar, en silencio."""
    for clave in (*rc.OCUPACION_VARIABLE, *rc.HUMEDAD_POR_NORMA):
        assert clave in usos.POR_CLAVE, clave


def _circuito(nombre: str, unidades: int, relacion: float = 1.0, perdida_pa: float = 15_000.0):
    """Circuito con una válvula cuyo Kv da `relacion` × la pérdida de la unidad a 1 m³/h."""
    kv = 1.0 / math.sqrt(relacion * perdida_pa / 1e5) if relacion > 0 else 0.0
    return mc.CircuitoControl(nombre, unidades, 1.0, kv, perdida_pa)


def test_recuento_de_puntos_contado_a_mano():
    """Un despacho, una red de impulsión climatizada de 10 000 m³/h y frío de 50 kW con un
    circuito de 3 unidades.

    SD: ventilador 1 + generador 1 + primario 1 + bomba del circuito 1 = 4
    ED: ventilador 2 + filtros 1 + generador 2 + primario 2 + bomba 2 = 9
    EA: zona (temperatura + CO₂) 2 + impulsión de aire 1 + generador (impulsión y retorno)
        2 + presión diferencial 1 + temperatura del circuito 1 + exterior 1 = 8
    SA: ventilador 1 + consigna del generador 1 + variador de la bomba 1 + válvulas 3 = 6
    """
    r = mc.proponer(
        [_e("despacho", "Despacho 1")],
        [mc.RedControl("IMP-1", "impulsion", 10_000.0, True)],
        [mc.ServicioControl("Clima", "Frío", True, False, 50.0, (_circuito("Oficinas", 3),))],
        refrigeracion=True,
    )
    assert r.resumen == {"ED": 9, "SD": 4, "EA": 8, "SA": 6}
    valvulas = next(p for p in r.puntos if p.equipo == "Unidades de Oficinas")
    assert valvulas.cantidad == 3 and "de 2 vías" in valvulas.senal
    # Frío: consigna de impulsión constante (IT 1.2.4.3.1.7).
    consigna = next(p for p in r.puntos if p.senal.startswith("Consigna"))
    assert "1.2.4.3.1.7" in consigna.motivo and "1.2.4.3.1.6" not in consigna.motivo


def test_umbral_de_5_m3s_en_ventiladores():
    """IT 1.2.4.3.1.10: «más de 5 m³/s» = más de 18 000 m³/h (estricto)."""

    def medicion(caudal):
        r = mc.proponer([], [mc.RedControl("R", "extraccion", caudal, False)], [], True)
        return [p for p in r.puntos if p.senal == "Medición del caudal de aire"]

    assert medicion(18_000.0) == []
    (p,) = medicion(18_001.0)
    assert "1.2.4.3.1.10" in p.motivo


def test_umbral_de_70_kw_con_la_potencia_de_la_instalacion():
    """IT 1.2.4.3.1.5: con caudal variable y más de 70 kW de generación total, presión
    diferencial estabilizada → PICV. Con 4 tubos cuenta frío + calor (40 + 40 = 80 kW)."""

    def servicios(total):
        circuito = (_circuito("Nave", 2),)
        return [
            mc.ServicioControl("4T", "Frío", True, False, total, circuito),
            mc.ServicioControl("4T", "Calor", False, True, total, circuito),
        ]

    r = mc.proponer([], [], servicios(80.0), True)
    valvulas = [p for p in r.puntos if p.equipo == "Unidades de Nave"]
    assert len(valvulas) == 2 and all("PICV" in p.senal for p in valvulas)
    c = next(c for c in r.comprobaciones if c.requisito.startswith("Presión diferencial"))
    assert c.resultado == mc.INCLUIDA
    r = mc.proponer([], [], servicios(70.0), True)
    assert all("de 2 vías" in p.senal for p in r.puntos if p.equipo == "Unidades de Nave")
    c = next(c for c in r.comprobaciones if c.requisito.startswith("Presión diferencial"))
    assert c.resultado == mc.NO_APLICA  # 70 kW no es «más de 70»


def test_valvulas_de_control_se_calculan_con_su_kv():
    """IT 1.2.4.3.1.5: Δp de la válvula abierta = 10⁵·(q/Kv)², entre la de la unidad.
    q = 1 m³/h, unidad 15 kPa: Kv = 1/√0,15 = 2,582 → relación 1,00 (CUMPLE). Con Kv para
    0,5 (Kv = 1/√0,075 = 3,651) → NO CUMPLE. Sin pérdida de la unidad (Kv 0) → NO CUMPLE.
    En el proyecto el Kv sale de la pérdida de la unidad (relación 1): lo que puede fallar de
    verdad es la unidad sin pérdida (tests/ui/test_paso_control.py)."""

    def resultado(*circuitos):
        s = mc.ServicioControl("S", "Frío", True, False, 50.0, circuitos)
        r = mc.proponer([], [], [s], True)
        return next(c for c in r.comprobaciones if c.requisito.startswith("Válvulas"))

    c = mc.CircuitoControl("A", 1, 1.0, 1 / math.sqrt(0.15), 15_000.0)
    assert mc.relacion_valvula(c) == pytest.approx(1.0)
    # Dentro del rango: el Kv recoge la exigencia («Incluida»), no se verifica nada más.
    assert resultado(c).resultado == mc.INCLUIDA
    assert resultado(_circuito("A", 1, 1.3)).resultado == mc.INCLUIDA  # límite incluido
    malo = resultado(_circuito("A", 1), _circuito("B", 1, 0.5))
    assert malo.resultado == mc.NO_CUMPLE and "B (0,5)" in malo.detalle
    sin = resultado(mc.CircuitoControl("C", 1, 1.0, 0.0, 0.0))
    assert sin.resultado == mc.NO_CUMPLE and "sin pérdida" in sin.detalle


def test_lo_que_recoge_la_propuesta_no_se_cuenta_como_cumple():
    """Revisión 11-11-2026: sondas, categorías, PICV y medición de caudal no se pueden
    «comprobar» contra la propia propuesta; salen «Incluida en la propuesta»."""
    r = mc.proponer(
        [_e("reuniones", "Sala"), _e("oficina_abierta", "Oficina")],
        [mc.RedControl("R", "impulsion", 20_000.0, True)],
        [mc.ServicioControl("S", "Frío", True, False, 100.0, (_circuito("A", 2),))],
        True,
    )
    por = {c.requisito: c.resultado for c in r.comprobaciones}
    assert [k for k, v in por.items() if v == mc.CUMPLE] == []
    assert sum(v == mc.INCLUIDA for v in por.values()) == 6


def test_consigna_de_calor_es_propuesta():
    """El .6 obliga con calderas (estándar, baja temperatura, condensación); TRAZA no sabe
    el tipo de generador: en calor la consigna es propuesta, en frío exigencia (.7)."""
    s = mc.ServicioControl("S", "Calor", False, True, 50.0, (_circuito("A", 1),))
    r = mc.proponer([], [], [s], False)
    consigna = next(p for p in r.puntos if p.senal.startswith("Consigna"))
    assert consigna.motivo.startswith(rc.PROPUESTA) and "1.2.4.3.1.7" not in consigna.motivo


def test_sin_nada_disenado_no_hay_puntos():
    r = mc.proponer([], [], [], True)
    assert r.puntos == [] and all(c.resultado == mc.NO_APLICA for c in r.comprobaciones)
