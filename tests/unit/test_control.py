"""Propuesta de control (engines/control.py, docs/modules/control.md).

Las categorías se comprueban contra el texto del RITE (IT 1.2.4.3.2 y 1.2.4.3.3, BOE, texto
consolidado) y los recuentos de puntos se cuentan a mano señal por señal.
"""

from __future__ import annotations

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
        [
            mc.ServicioControl(
                "Clima", "Frío", True, False, 50.0, (mc.CircuitoControl("Oficinas", 3),)
            )
        ],
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
        circuito = (mc.CircuitoControl("Nave", 2),)
        return [
            mc.ServicioControl("4T", "Frío", True, False, total, circuito),
            mc.ServicioControl("4T", "Calor", False, True, total, circuito),
        ]

    r = mc.proponer([], [], servicios(80.0), True)
    valvulas = [p for p in r.puntos if p.equipo == "Unidades de Nave"]
    assert len(valvulas) == 2 and all("PICV" in p.senal for p in valvulas)
    c = next(c for c in r.comprobaciones if c.requisito.startswith("Presión diferencial"))
    assert c.cumple is True
    r = mc.proponer([], [], servicios(70.0), True)
    assert all("de 2 vías" in p.senal for p in r.puntos if p.equipo == "Unidades de Nave")
    c = next(c for c in r.comprobaciones if c.requisito.startswith("Presión diferencial"))
    assert c.cumple is None  # no aplica: 70 kW no es «más de 70»


def test_comprobaciones_detectan_una_categoria_que_no_vale():
    """Las comprobaciones miran las categorías, no se dan por buenas: una oficina con
    IDA-C3 (horario) y un salón de actos sin IDA-C6 salen NO CUMPLE."""
    r = mc.ResultadoControl(
        categorias=[
            mc.Categoria("Oficina", "Oficina", "THM-C3", "", "IDA-C3", "", "permanente"),
            mc.Categoria("Salón", "Reuniones", "THM-C3", "", "IDA-C1", "", "variable"),
        ]
    )
    mc._comprobar(r, [], [], [])
    por = {c.norma: c for c in r.comprobaciones}
    assert por["RITE IT 1.2.4.3.3.3"].cumple is False
    assert "Oficina" in por["RITE IT 1.2.4.3.3.3"].detalle
    assert por["RITE IT 1.2.4.3.3.4"].cumple is False
    # Sin sondas de temperatura de zona: tampoco cumple la regulación por espacio.
    assert por["RITE IT 1.2.4.3.1.1"].cumple is False


def test_sin_nada_disenado_no_hay_puntos():
    r = mc.proponer([], [], [], True)
    assert r.puntos == [] and all(c.cumple is None for c in r.comprobaciones)
