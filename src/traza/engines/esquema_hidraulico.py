"""Elementos del esquema de principio primario-secundario (docs/modules/hidronica.md).

Pedido del usuario (08-11-2026): «esquemas hidráulicos de calidad y completos, sin omitir
ninguna clase de elemento». Cada elemento lleva el artículo que lo exige o la fuente que lo
justifica; los que el RITE exige solo por encima de 70 kW lo dicen.
"""

from __future__ import annotations

from dataclasses import dataclass

from traza.engines.hidraulica import Servicio
from traza.rules import hidraulica as rh


@dataclass(frozen=True)
class Elemento:
    zona: str  # «Generador», «Colectores», «Circuito C1», «Unidades de C1»…
    elemento: str
    especificacion: str
    dn: int | None
    cantidad: int
    norma: str


def _n(v: float, d: int = 1) -> str:
    return f"{v:.{d}f}".replace(".", ",")


def _m3h(q_m3s: float) -> str:
    return f"{_n(q_m3s * 3600, 2)} m³/h"


def _mca(pa: float) -> str:
    return f"{_n(pa / 9806.65, 1)} m c.a."


def elementos(s: Servicio, potencia_instalacion_kw: float | None = None) -> list[Elemento]:
    """Todos los elementos de un servicio. `potencia_instalacion_kw`: la de toda la
    instalación (con 4 tubos, frío + calor), para los umbrales de 70 kW del RITE."""
    total_kw = potencia_instalacion_kw if potencia_instalacion_kw is not None else s.potencia_kw
    grande = total_kw > 70
    medida = "RITE IT 1.3.4.4.5.6" + ("" if grande else " (exigido > 70 kW; recomendado)")
    dn_p = s.primario.tubo.dn
    p = s.presiones
    lista: list[Elemento] = []

    def add(zona, elemento, especificacion, dn, cantidad, norma):
        lista.append(Elemento(zona, elemento, especificacion, dn, cantidad, norma))

    # --- Generador y primario ---
    z = "Generador y primario"
    generador = {
        "frio": "Enfriadora de agua",
        "calor": "Generador de calor (bomba de calor o caldera)",
        "frio_calor": "Bomba de calor reversible aire-agua",
    }[s.clave]
    add(
        z,
        generador,
        f"{_n(s.potencia_kw)} kW; {_m3h(s.caudal_m3s)}; ΔP intercambiador del fabricante",
        dn_p,
        1,
        rh.IDAE_18,
    )
    add(
        z,
        "Manguito antivibratorio",
        "En la conexión del generador",
        dn_p,
        2,
        "RITE IT 1.3.4.2.1.2 (equipos con motor > 3 kW)",
    )
    add(
        z,
        f"Válvula de corte {rh.valvula_corte(dn_p)}",
        "Entrada y salida del generador",
        dn_p,
        2,
        "Mantenimiento; RITE IT 1.3.4.2.7",
    )
    add(
        z,
        "Filtro de malla 1 mm",
        "Retorno al generador; paso ≤ velocidad de la tubería",
        dn_p,
        1,
        "RITE IT 1.3.4.2.8.1",
    )
    add(z, "Termómetro con vaina", "Entrada y salida del generador", None, 2, medida)
    add(z, "Manómetro con amortiguador", "Entrada y salida del generador", None, 2, medida)
    add(
        z,
        "Bomba de primario",
        f"{_m3h(s.caudal_m3s)} a {_mca(s.altura_primario_pa)} (generador + primario)",
        dn_p,
        1,
        "RITE IT 1.2.4.2.5; IDAE nº 18 (pérdidas ×1,3 por accesorios)",
    )
    add(
        z,
        f"Válvula de retención {rh.valvula_retencion(dn_p)}",
        "Impulsión de la bomba de primario",
        dn_p,
        1,
        "RITE IT 1.3.4.2.7",
    )
    add(
        z, "Manómetro diferencial", "Aspiración y descarga de la bomba de primario", None, 1, medida
    )
    add(
        z,
        "Manguito antivibratorio",
        "Aspiración y descarga de la bomba de primario",
        dn_p,
        2,
        "RITE IT 1.3.4.2.1.2 (motor > 3 kW)",
    )
    add(
        z,
        "Tubería del primario",
        f"{rh.MATERIALES['acero']} {s.primario.tubo.nombre}; "
        f"{_n(s.primario.velocidad_m_s, 2)} m/s; {_n(s.primario.friccion_pa_m, 0)} Pa/m",
        dn_p,
        1,
        "Criterio IDAE nº 18 Ap. B / ASHRAE",
    )
    # --- Depósito de inercia (compensador) ---
    z = "Depósito de inercia"
    db = s.bocas_inercia.tubo.dn
    add(
        z,
        "Depósito de inercia de 4 bocas en paralelo (compensador hidráulico)",
        f"≥ {_n(s.inercia_l, 0)} l (mínimo del fabricante {_n(s.volumen_minimo_l, 0)} l menos "
        f"{_n(s.volumen_primario_l, 0)} l del primario); cuerpo ≥ "
        f"{_n(s.cuerpo_inercia_mm, 0)} mm (3·d)",
        db,
        1,
        "IDAE «La bomba de calor…» (2023); Caleffi Idraulica 18 (tres diámetros)",
    )
    add(
        z,
        "Purgador automático",
        "Parte alta del depósito",
        rh.PURGADOR_DN_MIN,
        1,
        "RITE IT 1.3.4.2.3.6",
    )
    add(
        z,
        "Válvula de vaciado",
        "Parte baja del depósito",
        rh.VACIADO_PARCIAL_DN_MIN,
        1,
        "RITE IT 1.3.4.2.3.2",
    )
    # --- Colectores ---
    z = "Colectores"
    dc = s.colector.tubo.dn
    n = len(s.circuitos)
    for lado in ("impulsión", "retorno"):
        add(
            z,
            f"Colector de {lado}",
            f"{s.colector.tubo.nombre}, {_n(s.colector.velocidad_m_s, 2)} m/s; picajes: "
            f"1 de primario DN{db}, {n} de circuitos y 1 de reserva",
            dc,
            1,
            "Criterio de la ficha (separador de baja pérdida, Caleffi)",
        )
        add(z, "Termómetro con vaina", f"Colector de {lado}", None, 1, medida)
    # --- Expansión, seguridad, llenado y vaciado ---
    z = "Expansión, seguridad y llenado"
    frio = s.frio
    add(
        z,
        "Vaso de expansión cerrado de membrana",
        f"≥ {_n(s.vaso_l, 1)} l; precarga {_n(p.inicial_vaso)} bar; llenado {_n(p.llenado)} bar; "
        f"máxima {_n(p.maxima_servicio)} bar; {_n(s.t_min_c, 0)}–{_n(s.t_max_c, 0)} °C",
        None,
        1,
        "RITE IT 1.3.4.2.4; IDAE nº 18 3.1.3 (UNE 100155)",
    )
    add(z, "Manómetro", "En el vaso de expansión", None, 1, medida)
    add(
        z,
        "Válvula de seguridad con accionamiento manual",
        f"Tarada a {_n(p.seguridad)} bar; descarga conducida y visible",
        None,
        1,
        "RITE IT 1.3.4.2.5",
    )
    dn_al = rh.dn_alimentacion(total_kw, frio)
    for elemento in ("Válvula de corte", "Filtro", "Contador", "Desconector"):
        add(
            z,
            elemento,
            "Alimentación, en este orden; llenado manual",
            dn_al,
            1,
            "RITE IT 1.3.4.2.2 (tabla 3.4.2.2)",
        )
    add(
        z,
        "Válvula automática de alivio",
        f"Tarada a {_n(p.alivio)} bar (máxima + 0,3)",
        max(rh.ALIVIO_DN_MIN, dn_al),
        1,
        "RITE IT 1.3.4.2.2",
    )
    add(
        z,
        "Presostato de mínima",
        "Alarma y paro si falta presión",
        None,
        1,
        "RITE IT 1.3.4.2.2 y 1.3.4.2.5",
    )
    add(
        z,
        "Válvula de vaciado total",
        "Punto más bajo; descarga visible",
        rh.dn_vaciado(total_kw, frio),
        1,
        "RITE IT 1.3.4.2.3 (tabla 3.4.2.3)",
    )
    add(
        z,
        "Presión nominal de equipos y accesorios",
        f"PN{p.nominal}; prueba a {_n(p.prueba)} bar",
        None,
        1,
        "IDAE nº 18 3.1.2",
    )
    # --- Circuitos secundarios ---
    pic = "independiente de la presión (PICV)" if grande else "de 2 vías"
    for c in s.circuitos:
        z = f"Circuito {c.datos.nombre}"
        d = c.tubo.tubo.dn
        add(z, "Picaje en colector", "Impulsión y retorno", d, 2, "Ficha")
        add(
            z,
            f"Válvula de corte {rh.valvula_corte(d)}",
            "Salida y retorno del colector",
            d,
            2,
            "RITE IT 1.3.4.2.7",
        )
        add(
            z,
            "Bomba secundaria de velocidad variable",
            f"{_m3h(c.caudal_m3s)} a {_mca(c.altura_bomba_pa)} (tuberías + unidad + válvula)",
            d,
            1,
            "RITE IT 1.2.4.2.5; IDAE nº 18 4.1–4.2",
        )
        add(
            z,
            f"Válvula de retención {rh.valvula_retencion(d)}",
            "Impulsión de la bomba",
            d,
            1,
            "RITE IT 1.3.4.2.7",
        )
        add(z, "Manómetro diferencial", "Aspiración y descarga de la bomba", None, 1, medida)
        add(z, "Filtro de malla 1 mm", "Retorno del circuito", d, 1, "RITE IT 1.3.4.2.8.1")
        add(z, "Válvula de equilibrado", "Retorno del circuito", d, 1, "RITE IT 1.2.4.2.7")
        add(z, "Termómetro con vaina", "Retorno del circuito", None, 1, medida)
        add(z, "Purgador automático", "Puntos altos", rh.PURGADOR_DN_MIN, 1, "RITE IT 1.3.4.2.3.6")
        add(
            z,
            "Vaciado parcial",
            "Puntos bajos",
            rh.VACIADO_PARCIAL_DN_MIN,
            1,
            "RITE IT 1.3.4.2.3.2",
        )
        add(
            z,
            "Tubería",
            f"{rh.MATERIALES[c.tubo.tubo.material]} {c.tubo.tubo.nombre}; "
            f"{_n(c.datos.longitud_m * 2, 0)} m (ida y vuelta); {_n(c.tubo.velocidad_m_s, 2)} m/s; "
            f"{_n(c.tubo.friccion_pa_m, 0)} Pa/m",
            d,
            1,
            "Criterio IDAE nº 18 Ap. B / ASHRAE",
        )
        add(
            z,
            "Aislamiento (λ 0,040 W/(m·K))",
            f"{c.aislamiento_mm} mm, " + ("exterior" if c.datos.exterior else "interior"),
            d,
            1,
            "RITE IT 1.2.4.2.1.2",
        )
        if c.dilatacion_mm is not None:
            add(
                z,
                "Dilatación a compensar",
                f"{_n(c.dilatacion_mm, 0)} mm en el tramo (cambios de dirección o compensador)",
                d,
                1,
                "RITE IT 1.3.4.2.6; IDAE nº 18 3.1.4",
            )
        # --- Unidades terminales ---
        zu = f"Unidades de {c.datos.nombre}"
        u = c.datos.unidades
        du = c.conexion.tubo.dn
        add(zu, "Válvula de corte", "Entrada de cada unidad", du, u, "RITE IT 1.3.4.2.12")
        add(
            zu,
            "Válvula de equilibrado (también de corte)",
            "Salida de cada unidad",
            du,
            u,
            "RITE IT 1.3.4.2.12",
        )
        add(
            zu,
            f"Válvula de control {pic}",
            f"Kv ≥ {_n(c.kv_valvula, 2)} (ΔP = la de la unidad, {_mca(c.perdida_valvula_pa)})",
            du,
            u,
            "RITE IT 1.2.4.3.1.5",
        )
        if du > 15:
            add(
                zu,
                "Filtro de malla 0,25 mm",
                "Antes de la válvula de control",
                du,
                u,
                "RITE IT 1.3.4.2.8.2",
            )
        add(zu, "Termómetro con vaina", "Entrada y salida de la batería", None, 2 * u, medida)
        add(zu, "Purgador", "En la batería", rh.PURGADOR_DN_MIN, u, "RITE IT 1.3.4.2.3.6")
        add(
            zu,
            "Picaje de conexión",
            f"{c.conexion.tubo.nombre}; {_m3h(c.caudal_m3s / u)} por unidad",
            du,
            2 * u,
            "Criterio IDAE nº 18 Ap. B / ASHRAE",
        )
    return lista
