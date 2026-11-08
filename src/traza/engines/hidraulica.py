"""Sistema hidráulico de climatización primario-secundario (docs/modules/hidronica.md).

Motor puro: recibe circuitos (potencia, unidades, longitud) y devuelve diámetros, pérdidas,
bombas, colectores, depósito de inercia, vaso de expansión, presiones y la lista completa
de elementos del esquema de principio. Criterios y fuentes en rules/hidraulica.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from traza.engines.conductos import factor_friccion
from traza.rules import agua as tabla_agua
from traza.rules import hidraulica as rh

SERVICIOS = {"frio": "Frío", "calor": "Calor", "frio_calor": "Frío / calor (2 tubos)"}


@dataclass(frozen=True)
class Agua:
    t_c: float
    densidad: float  # kg/m³
    viscosidad: float  # Pa·s
    cp: float  # J/(kg·K)


def agua(t_c: float) -> Agua:
    """Propiedades por interpolación lineal de la tabla de rules/agua.py."""
    filas = tabla_agua.TABLA
    if not filas[0][0] <= t_c <= filas[-1][0]:
        raise ValueError(f"Agua a {t_c:g} °C: fuera de la tabla (0–90 °C).")
    for (t0, *a), (t1, *b) in zip(filas, filas[1:], strict=False):
        if t0 <= t_c <= t1:
            f = (t_c - t0) / (t1 - t0)
            rho, mu, cp = (x + (y - x) * f for x, y in zip(a, b, strict=True))
            return Agua(t_c, rho, mu * 1e-6, cp)
    raise AssertionError("inalcanzable")


def caudal_m3s(potencia_w: float, salto_k: float, a: Agua) -> float:
    """Q = P/(ρ·cp·ΔT) (IDAE nº 18, Ap. B)."""
    if salto_k <= 0:
        raise ValueError("El salto térmico tiene que ser positivo.")
    return potencia_w / (a.densidad * a.cp * salto_k)


@dataclass(frozen=True)
class TuboElegido:
    tubo: rh.Tubo
    velocidad_m_s: float
    friccion_pa_m: float
    aviso: str = ""


def flujo(caudal: float, tubo: rh.Tubo, a: Agua) -> tuple[float, float]:
    """(velocidad m/s, pérdida Pa/m) con Darcy-Weisbach y Colebrook."""
    d = tubo.interior_m
    v = caudal / (math.pi * d * d / 4)
    if v == 0:
        return 0.0, 0.0
    re = a.densidad * v * d / a.viscosidad
    f = factor_friccion(re, rh.RUGOSIDAD_M[tubo.material] / d)
    return v, f / d * a.densidad * v * v / 2


def elegir_tubo(caudal: float, material: str, a: Agua, minimo: rh.Tubo | None = None):
    """El menor tubo con ≤ 40 mm c.a./m y, hasta DN50, ≤ 1,2 m/s (ficha, «Criterios»)."""
    serie = rh.TUBOS[material]
    for t in serie:
        if minimo is not None and t.interior_m < minimo.interior_m - 1e-9:
            continue
        v, r = flujo(caudal, t, a)
        lento = v <= rh.VELOCIDAD_MAXIMA_M_S or t.dn > rh.VELOCIDAD_HASTA_DN
        if r <= rh.PERDIDA_MAXIMA_PA_M and lento:
            return TuboElegido(t, v, r)
    t = serie[-1]
    v, r = flujo(caudal, t, a)
    return TuboElegido(
        t,
        v,
        r,
        f"Caudal de {caudal * 3600:.1f} m³/h: no cabe en {rh.MATERIALES[material]} "
        f"({t.nombre}, {r:.0f} Pa/m); hace falta un diámetro mayor (a definir).",
    )


def elegir_colector(caudal: float, a: Agua, general: rh.Tubo) -> TuboElegido:
    """Acero, ≤ 0,9 m/s con el caudal total y nunca menor que la tubería general."""
    for t in rh.ACERO:
        if t.interior_m < general.interior_m - 1e-9:
            continue
        v, r = flujo(caudal, t, a)
        if v <= rh.VELOCIDAD_COLECTOR_M_S:
            return TuboElegido(t, v, r)
    t = rh.ACERO[-1]
    v, r = flujo(caudal, t, a)
    return TuboElegido(t, v, r, "Colector mayor que DN150: a definir.")


# --- Datos y resultados -----------------------------------------------------------------
@dataclass(frozen=True)
class Circuito:
    nombre: str
    potencia_frio_w: float
    potencia_calor_w: float
    unidades: int
    longitud_m: float  # ida, del colector a la unidad más lejana
    perdida_terminal_pa: float = rh.PERDIDA_TERMINAL_PA
    exterior: bool = False


@dataclass(frozen=True)
class Temperaturas:
    frio_impulsion: float = rh.FRIO_IMPULSION_C
    frio_retorno: float = rh.FRIO_RETORNO_C
    calor_impulsion: float = rh.CALOR_IMPULSION_C
    calor_retorno: float = rh.CALOR_RETORNO_C


TEMPERATURAS_IDAE = Temperaturas()  # 7/12 y 45/40 °C (IDAE nº 18)


@dataclass(frozen=True)
class CircuitoCalculado:
    datos: Circuito
    caudal_m3s: float
    tubo: TuboElegido
    conexion: TuboElegido  # picaje a cada unidad
    perdida_tuberia_pa: float
    perdida_valvula_pa: float  # válvula de control, autoridad 1
    altura_bomba_pa: float
    kv_valvula: float  # m³/h a 1 bar, de la válvula de cada unidad
    aislamiento_mm: int
    dilatacion_mm: float | None
    volumen_l: float


@dataclass(frozen=True)
class Servicio:
    """Una red hidráulica: un generador, su primario, colectores y secundarios."""

    clave: str  # frio | calor | frio_calor
    potencia_w: float
    caudal_m3s: float
    primario: TuboElegido
    altura_primario_pa: float
    colector: TuboElegido
    circuitos: tuple[CircuitoCalculado, ...]
    volumen_minimo_l: float  # del fabricante (l/kW × potencia)
    volumen_instalacion_l: float  # tuberías (primario y secundarios), sin depósito ni equipos
    volumen_primario_l: float  # el que cuenta para el volumen mínimo del generador
    inercia_l: float
    bocas_inercia: TuboElegido
    cuerpo_inercia_mm: float  # D = 3·d (Caleffi)
    vaso_l: float
    presiones: rh.Presiones
    t_max_c: float
    t_min_c: float
    avisos: tuple[str, ...] = field(default=())

    @property
    def potencia_kw(self) -> float:
        return self.potencia_w / 1000

    @property
    def frio(self) -> bool:
        return self.clave in ("frio", "frio_calor")

    @property
    def calor(self) -> bool:
        return self.clave in ("calor", "frio_calor")


def _modo(clave: str, t: Temperaturas):
    """(salto, temperatura media de cálculo) de cada modo que lleva el servicio."""
    modos = []
    if clave in ("frio", "frio_calor"):
        modos.append(("frio", t.frio_retorno - t.frio_impulsion, t.frio_impulsion))
    if clave in ("calor", "frio_calor"):
        modos.append(("calor", t.calor_impulsion - t.calor_retorno, t.calor_retorno))
    return modos


def _caudal(c: Circuito | None, potencias: dict[str, float], modos) -> float:
    """El mayor de los modos (en 2 tubos la red se dimensiona para el peor)."""
    return max(caudal_m3s(potencias[m], salto, agua(tm)) for m, salto, tm in modos)


def calcular_servicio(
    clave: str,
    circuitos: list[Circuito],
    material: str = "acero",
    temperaturas: Temperaturas = TEMPERATURAS_IDAE,
    potencia_generador_w: float | None = None,
    longitud_primario_m: float = 10.0,
    perdida_generador_pa: float = rh.PERDIDA_GENERADOR_PA,
    altura_instalacion_m: float = 0.0,
    volumen_minimo_l_kw: float = rh.VOLUMEN_MINIMO_L_KW,
) -> Servicio:
    if clave not in SERVICIOS:
        raise ValueError(f"Servicio no previsto: «{clave}».")
    if not circuitos:
        raise ValueError("El sistema necesita al menos un circuito.")
    modos = _modo(clave, temperaturas)
    for _m, salto, _t in modos:
        if salto <= 0:
            raise ValueError("Impulsión y retorno al revés: el salto tiene que ser positivo.")
    # Temperatura de cálculo de pérdidas: la más fría de los modos (más viscosa, peor;
    # IDAE nº 18, Ap. B: «se aplicará la tabla de 10 °C por tener mayor pérdida»).
    a = agua(min(tm for _m, _s, tm in modos))
    t_frio = temperaturas.frio_impulsion if clave != "calor" else None
    t_calor = temperaturas.calor_impulsion if clave != "frio" else None
    t_max = max(rh.TEMPERATURA_MAXIMA_C, t_calor or 0.0)
    t_min = min(rh.TEMPERATURA_MINIMA_C, t_frio if t_frio is not None else 99.0)
    avisos: list[str] = []
    calculados = []
    for c in circuitos:
        if c.unidades < 1 or c.longitud_m < 0:
            raise ValueError(f"{c.nombre}: al menos una unidad y longitud no negativa.")
        q = _caudal(c, {"frio": c.potencia_frio_w, "calor": c.potencia_calor_w}, modos)
        tubo = elegir_tubo(q, material, a)
        conexion = elegir_tubo(q / c.unidades, material, a)
        if tubo.aviso:
            avisos.append(f"{c.nombre}: {tubo.aviso}")
        tuberia = 2 * rh.FACTOR_ACCESORIOS * tubo.friccion_pa_m * c.longitud_m
        valvula = c.perdida_terminal_pa  # autoridad 1 (RITE IT 1.2.4.3.1.5: 0,6–1,3)
        q_unidad_m3h = q / c.unidades * 3600
        kv = q_unidad_m3h / math.sqrt(valvula / 1e5) if valvula > 0 else 0.0
        dil = rh.DILATACION_MM_M_K.get(material)
        calculados.append(
            CircuitoCalculado(
                c,
                q,
                tubo,
                conexion,
                tuberia,
                valvula,
                tuberia + c.perdida_terminal_pa + valvula,
                kv,
                rh.espesor_aislamiento_mm(
                    tubo.tubo.exterior_mm, "exterior" if c.exterior else "interior", t_calor, t_frio
                ),
                None if dil is None else dil * c.longitud_m * (t_max - t_min),
                2 * c.longitud_m * math.pi * tubo.tubo.interior_m**2 / 4 * 1000,
            )
        )
    suma = {
        "frio": sum(c.potencia_frio_w for c in circuitos),
        "calor": sum(c.potencia_calor_w for c in circuitos),
    }
    if potencia_generador_w is not None:
        suma = dict.fromkeys(suma, potencia_generador_w)
    potencia = max(suma[m] for m, _s, _t in modos)
    q_primario = _caudal(None, suma, modos)
    primario = elegir_tubo(q_primario, "acero", a)
    q_secundario = sum(c.caudal_m3s for c in calculados)
    colector = elegir_colector(max(q_primario, q_secundario), a, primario.tubo)
    altura_primario = (
        perdida_generador_pa
        + 2 * rh.FACTOR_ACCESORIOS * primario.friccion_pa_m * longitud_primario_m
    )
    vol_primario = 2 * longitud_primario_m * math.pi * primario.tubo.interior_m**2 / 4 * 1000
    vol_tubos = sum(c.volumen_l for c in calculados) + vol_primario
    minimo = volumen_minimo_l_kw * potencia / 1000
    # Solo cuenta el agua del primario: con las válvulas de 2 vías cerradas, la de los
    # secundarios no está disponible para el generador, y el volumen mínimo tiene que
    # estarlo «cualquiera que sea el estado de los elementos terminales» (IDAE, «La bomba
    # de calor…», 2023).
    inercia = max(minimo - vol_primario, 0.0)
    bocas = elegir_colector(max(q_primario, q_secundario), a, rh.ACERO[0])
    p = rh.presiones(altura_instalacion_m)
    vaso = rh.volumen_vaso_l(vol_tubos + inercia, t_max, p)
    return Servicio(
        clave,
        potencia,
        q_primario,
        primario,
        altura_primario,
        colector,
        tuple(calculados),
        minimo,
        vol_tubos,
        vol_primario,
        inercia,
        bocas,
        3 * bocas.tubo.exterior_mm,
        vaso,
        p,
        t_max,
        t_min,
        tuple(avisos),
    )
