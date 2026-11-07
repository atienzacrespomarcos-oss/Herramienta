"""Cargas térmicas de un espacio (motor puro): invierno y verano por componentes en hora punta.

Decisión del usuario (07-11-2026): verano «por componentes en hora punta», sin fricción;
la carga se dimensiona con margen. Fuentes (docs/modules/cargas.md):

- Transmisión: Q = U·A·ΔT. En verano los opacos usan la temperatura sol-aire (ASHRAE
  Handbook – Fundamentals, cap. 18): T_sa = T_e + (α/h_o)·I − ε·ΔR/h_o.
  - α/h_o: 0,026 m²K/W en superficie clara y 0,052 en oscura (el máximo).
  - ε·ΔR/h_o: 3,9 K en horizontal y 0 en vertical.
- Huecos: conducción U·A·(T_e − T_i) más radiación A·F_H·F_S·I (factor solar modificado
  del CEC).
- Temperatura exterior a lo largo del día: T(h) = T_max − f(h)·OMDR, con las fracciones de
  la oscilación de ASHRAE (Handbook – Fundamentals 2009, cap. 14, tabla 6, tal como las
  incorpora EnergyPlus) y la oscilación media diaria OMDR de la guía del IDAE.
- Aire: densidad y calor específico del aire húmedo (ASHRAE Fundamentals, cap. 1);
  latente con h_fg = 2501 kJ/kg.
- Infiltración: UNE-EN 12831 (V_inf = 2·V·n50·e·ε) con n50 según el CTE DB HE, Anejo H.

Todas las magnitudes llevan la unidad en el nombre (_w, _m2, _c, _m3h…).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from traza.core import psicrometria as ps
from traza.engines import solar

#: Fracción de la oscilación diaria por hora (hora 1 a 24): ASHRAE 2009, cap. 14, tabla 6.
FRACCION_OSCILACION = (
    0.88, 0.92, 0.95, 0.98, 1.00, 0.98, 0.91, 0.74, 0.55, 0.38, 0.23, 0.13,
    0.05, 0.00, 0.00, 0.06, 0.14, 0.24, 0.39, 0.50, 0.59, 0.68, 0.75, 0.82,
)  # fmt: skip

#: ASHRAE: α/h_o en m²K/W.
ALFA_HO = {"claro": 0.026, "oscuro": 0.052}
DELTA_R_HORIZONTAL_K = 3.9
CALOR_LATENTE_J_KG = 2_501_000.0

CLASES = ("opaco", "hueco", "terreno", "interior")

NOTAS_INVIERNO = (
    "Sin descontar ganancias internas ni solares (del lado de la seguridad).",
    "Solera y terreno con la temperatura exterior de proyecto (del lado de la seguridad).",
)
NOTAS_VERANO = (
    "Régimen permanente, sin inercia: radiación por huecos, personas e iluminación "
    "instantáneas y opacos con la temperatura sol-aire de la misma hora (del lado de la "
    "seguridad, sobre todo en cerramientos pesados).",
    "Horas solares; humedad absoluta exterior constante durante el día.",
    "Sin carga por el terreno en verano.",
    "Si el aire exterior es más seco que el interior, no se descuenta su efecto "
    "deshumectante (del lado de la seguridad).",
)


@dataclass(frozen=True)
class Cerramiento:
    nombre: str
    clase: str  # opaco | hueco | terreno | interior
    area_m2: float
    u_w_m2k: float
    azimut: float = 180.0  # normal exterior desde el norte, sentido horario
    inclinacion: float = 90.0  # 0 cubierta, 90 fachada
    factor_solar: float = 0.0  # huecos: F_H
    factor_sombra: float = 1.0  # huecos: F_S (retranqueos, voladizos, lamas…)
    alfa_ho: float = ALFA_HO["oscuro"]  # opacos
    t_contigua_invierno_c: float | None = None  # interior: local no acondicionado
    t_contigua_verano_c: float | None = None

    def __post_init__(self):
        if self.clase not in CLASES:
            raise ValueError(f"Clase de cerramiento no prevista: «{self.clase}».")
        if self.area_m2 < 0 or self.u_w_m2k < 0:
            raise ValueError(f"«{self.nombre}»: superficie y U no pueden ser negativas.")
        if self.clase == "interior" and (
            self.t_contigua_invierno_c is None or self.t_contigua_verano_c is None
        ):
            raise ValueError(f"«{self.nombre}»: falta la temperatura del local contiguo.")


@dataclass(frozen=True)
class Espacio:
    nombre: str
    area_m2: float
    volumen_m3: float
    t_invierno_c: float | None  # None: sin calefacción (cámaras frigoríficas)
    t_verano_c: float
    hr_invierno: float = 0.40  # RITE, tabla 1.4.1.1
    hr_verano: float = 0.50
    personas: float = 0.0
    sensible_persona_w: float = 0.0
    latente_persona_w: float = 0.0
    iluminacion_w: float = 0.0
    equipos_w: float = 0.0
    proceso_sensible_w: float = 0.0
    proceso_latente_w: float = 0.0
    aire_exterior_m3h: float = 0.0
    infiltracion_m3h: float = 0.0
    recuperacion: float = 0.0  # eficiencia sensible del recuperador (0–1)
    cerramientos: tuple[Cerramiento, ...] = ()

    def __post_init__(self):
        if not 0 <= self.recuperacion < 1:
            raise ValueError("La eficiencia del recuperador va de 0 a 1.")


@dataclass(frozen=True)
class Clima:
    latitud: float
    presion_pa: float
    invierno_ts_c: float
    verano_ts_c: float  # máxima del día de proyecto
    verano_w: float  # kg/kg
    oscilacion_c: float  # OMDR
    mes: int = 7


@dataclass(frozen=True)
class Partida:
    concepto: str
    sensible_w: float
    latente_w: float = 0.0


@dataclass(frozen=True)
class Resultado:
    partidas: tuple[Partida, ...]
    notas: tuple[str, ...]
    hora_solar: int | None = None
    t_exterior_c: float | None = None
    perfil_w: tuple[float, ...] = field(default=())  # verano: total de cada hora 1–24

    @property
    def sensible_w(self) -> float:
        return sum(p.sensible_w for p in self.partidas)

    @property
    def latente_w(self) -> float:
        return sum(p.latente_w for p in self.partidas)

    @property
    def total_w(self) -> float:
        return self.sensible_w + self.latente_w


def temperatura_exterior(clima: Clima, hora: int) -> float:
    return clima.verano_ts_c - FRACCION_OSCILACION[hora - 1] * clima.oscilacion_c


def _aire(caudal_m3h: float, t_int: float, w_int: float, p: float) -> tuple[float, float]:
    """Gasto de aire seco (kg/s) y calor específico del aire húmedo (J/kg·K)."""
    densidad = p / (287.042 * (t_int + 273.15) * (1 + 1.607858 * w_int))
    return densidad * caudal_m3h / 3600.0, 1006.0 + 1860.0 * w_int


def _suma(partidas: dict[str, list[float]]) -> tuple[Partida, ...]:
    return tuple(Partida(k, v[0], v[1]) for k, v in partidas.items() if v[0] or v[1])


def invierno(espacio: Espacio, clima: Clima) -> Resultado:
    """Pérdidas de calor de proyecto (W): transmisión, ventilación e infiltración."""
    ti = espacio.t_invierno_c
    if ti is None:
        return Resultado((), ("Espacio sin calefacción.",))
    te = clima.invierno_ts_c
    acc: dict[str, list[float]] = {}

    def sumar(concepto, sensible, latente=0.0):
        a = acc.setdefault(concepto, [0.0, 0.0])
        a[0] += sensible
        a[1] += latente

    for c in espacio.cerramientos:
        ua = c.u_w_m2k * c.area_m2
        if c.clase == "opaco":
            sumar("Transmisión por cerramientos opacos", ua * (ti - te))
        elif c.clase == "hueco":
            sumar("Transmisión por huecos", ua * (ti - te))
        elif c.clase == "terreno":
            sumar("Solera y terreno", ua * (ti - te))
        else:
            sumar("Particiones con locales no acondicionados", ua * (ti - c.t_contigua_invierno_c))
    w_i = ps.humedad_especifica_relativa(ti, espacio.hr_invierno, clima.presion_pa)
    m, cp = _aire(espacio.aire_exterior_m3h, ti, w_i, clima.presion_pa)
    sumar("Ventilación", m * cp * (ti - te) * (1 - espacio.recuperacion))
    m, cp = _aire(espacio.infiltracion_m3h, ti, w_i, clima.presion_pa)
    sumar("Infiltración", m * cp * (ti - te))
    return Resultado(_suma(acc), NOTAS_INVIERNO)


def _verano_hora(espacio: Espacio, clima: Clima, hora: int) -> tuple[Partida, ...]:
    ti = espacio.t_verano_c
    te = temperatura_exterior(clima, hora)
    p = clima.presion_pa
    acc: dict[str, list[float]] = {}

    def sumar(concepto, sensible, latente=0.0):
        a = acc.setdefault(concepto, [0.0, 0.0])
        a[0] += sensible
        a[1] += latente

    for c in espacio.cerramientos:
        ua = c.u_w_m2k * c.area_m2
        if c.clase in ("opaco", "hueco"):
            i = solar.irradiancia(clima.latitud, clima.mes, hora, c.azimut, c.inclinacion).total
        if c.clase == "opaco":
            dr = DELTA_R_HORIZONTAL_K if c.inclinacion < 45 else 0.0
            t_sa = te + c.alfa_ho * i - dr
            sumar("Transmisión por cerramientos opacos", ua * (t_sa - ti))
        elif c.clase == "hueco":
            sumar("Transmisión por huecos", ua * (te - ti))
            sumar("Radiación solar por huecos", c.area_m2 * c.factor_solar * c.factor_sombra * i)
        elif c.clase == "interior":
            sumar("Particiones con locales no acondicionados", ua * (c.t_contigua_verano_c - ti))
    sumar(
        "Personas",
        espacio.personas * espacio.sensible_persona_w,
        espacio.personas * espacio.latente_persona_w,
    )
    sumar("Iluminación", espacio.iluminacion_w)
    sumar("Equipos", espacio.equipos_w)
    sumar("Proceso", espacio.proceso_sensible_w, espacio.proceso_latente_w)
    w_i = ps.humedad_especifica_relativa(ti, espacio.hr_verano, p)
    # Aire exterior más seco que el interior: no se descuenta su efecto deshumectante (del
    # lado de la seguridad; restaba el latente de las personas, revisión 07-11-2026).
    dw = max(clima.verano_w - w_i, 0.0)
    for concepto, caudal, eta in (
        ("Ventilación", espacio.aire_exterior_m3h, espacio.recuperacion),
        ("Infiltración", espacio.infiltracion_m3h, 0.0),
    ):
        m, cp = _aire(caudal, ti, w_i, p)
        sumar(concepto, m * cp * (te - ti) * (1 - eta), m * CALOR_LATENTE_J_KG * dw)
    return _suma(acc)


def verano(espacio: Espacio, clima: Clima) -> Resultado:
    """Carga de refrigeración en la hora punta del espacio (la de mayor carga total)."""
    horas = [_verano_hora(espacio, clima, h) for h in range(1, 25)]
    totales = tuple(sum(p.sensible_w + p.latente_w for p in partidas) for partidas in horas)
    punta = max(range(24), key=lambda k: totales[k])
    return Resultado(
        horas[punta], NOTAS_VERANO, punta + 1, temperatura_exterior(clima, punta + 1), totales
    )


def verano_simultaneo(espacios: list[Espacio], clima: Clima) -> tuple[int, float]:
    """Hora punta del conjunto (suma simultánea de los espacios) y su carga total (W)."""
    if not espacios:
        return 0, 0.0
    perfiles = [verano(e, clima).perfil_w for e in espacios]
    suma = [sum(p[k] for p in perfiles) for k in range(24)]
    k = max(range(24), key=lambda i: suma[i])
    return k + 1, suma[k]


# --- Infiltración: UNE-EN 12831 con n50 del CTE DB HE, Anejo H ---------------------------

#: CTE DB HE, tabla a-Anejo H: coeficiente de caudal de la parte opaca a 100 Pa (m³/h·m²).
CO_OPACO = {"nuevo": 16.0, "existente": 29.0}
#: Permeabilidad de huecos a 100 Pa (m³/h·m²), clases de la UNE-EN 12207: 1 → 50, 2 → 27,
#: 3 → 9, 4 → 3. El CTE (tabla 3.1.3.a-HE1) exige clase 2 en zonas α, A y B y clase 3 en C,
#: D y E.
CH_CLASE = {1: 50.0, 2: 27.0, 3: 9.0, 4: 3.0}


def n50(volumen_m3: float, area_opaca_m2: float, area_huecos_m2: float, co: float, ch: float):
    """Renovaciones a 50 Pa: n50 = 0,629·(Co·Ao + Ch·Ah)/V (CTE DB HE, Anejo H)."""
    if volumen_m3 <= 0:
        raise ValueError("El volumen tiene que ser positivo.")
    return 0.629 * (co * area_opaca_m2 + ch * area_huecos_m2) / volumen_m3


def infiltracion_m3h(volumen_m3: float, n50_h: float, fachadas_expuestas: int, altura_m: float):
    """Caudal de infiltración, UNE-EN 12831 (anexo D): V_inf = 2·V·n50·e·ε.

    e (protección moderada): 0 sin fachadas expuestas, 0,02 con una, 0,03 con más de una.
    ε (altura del local sobre el terreno): 1,0 hasta 10 m, 1,2 hasta 30 m, 1,5 por encima.
    """
    e = 0.0 if fachadas_expuestas <= 0 else (0.02 if fachadas_expuestas == 1 else 0.03)
    eps = 1.0 if altura_m <= 10 else (1.2 if altura_m <= 30 else 1.5)
    return 2 * volumen_m3 * n50_h * e * eps
