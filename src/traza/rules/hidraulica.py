"""Reglas del sistema hidráulico de climatización (docs/modules/hidronica.md, «Fuentes»).

Cada tabla lleva su fuente; las elecciones entre fuentes están escritas en la ficha.
"""

from __future__ import annotations

from dataclasses import dataclass

RITE = "RITE (RD 1027/2007, texto consolidado BOE-A-2007-15820)"
IDAE_18 = "IDAE, Guía técnica nº 18 «Instalaciones de climatización por agua» (2012)"


# --- Tubos ------------------------------------------------------------------------------
@dataclass(frozen=True)
class Tubo:
    material: str
    nombre: str  # «DN50» o «22×1»
    dn: int  # diámetro nominal (mm) para el listado; en cobre y plástico, el exterior
    exterior_mm: float
    espesor_mm: float

    @property
    def interior_m(self) -> float:
        return (self.exterior_mm - 2 * self.espesor_mm) / 1000


def _serie(material: str, filas, dn_es_exterior: bool) -> tuple[Tubo, ...]:
    tubos = []
    for nombre, de, e in filas:
        dn = round(de) if dn_es_exterior else int(nombre.removeprefix("DN"))
        tubos.append(Tubo(material, nombre, dn, de, e))
    return tuple(tubos)


#: Acero negro UNE-EN 10255 serie media M (tabla de compatibilidad Megapress de Viega).
ACERO = _serie(
    "acero",
    [
        ("DN15", 21.3, 2.6),
        ("DN20", 26.9, 2.6),
        ("DN25", 33.7, 3.2),
        ("DN32", 42.4, 3.2),
        ("DN40", 48.3, 3.2),
        ("DN50", 60.3, 3.6),
        ("DN65", 76.1, 3.6),
        ("DN80", 88.9, 4.0),
        ("DN100", 114.3, 4.5),
        ("DN125", 139.7, 5.0),
        ("DN150", 165.1, 5.0),
    ],
    dn_es_exterior=False,
)
#: Cobre UNE-EN 1057, los de las tablas del Ap. B de la guía IDAE nº 18.
COBRE = _serie(
    "cobre",
    [
        ("12×1", 12, 1.0),
        ("15×1", 15, 1.0),
        ("18×1", 18, 1.0),
        ("22×1", 22, 1.0),
        ("25×1,5", 25, 1.5),
        ("28×1,5", 28, 1.5),
        ("35×1,5", 35, 1.5),
        ("42×1,5", 42, 1.5),
        ("54×2", 54, 2.0),
    ],
    dn_es_exterior=True,
)
#: Termoplástico, los de las tablas del Ap. B de la guía IDAE nº 18.
PLASTICO = _serie(
    "plastico",
    [
        ("12×0,7", 12, 0.7),
        ("16×0,9", 16, 0.9),
        ("20×1,2", 20, 1.2),
        ("25×1,5", 25, 1.5),
        ("32×1,9", 32, 1.9),
        ("40×2,4", 40, 2.4),
        ("50×2,9", 50, 2.9),
        ("63×3,7", 63, 3.7),
    ],
    dn_es_exterior=True,
)
TUBOS = {"acero": ACERO, "cobre": COBRE, "plastico": PLASTICO}
MATERIALES = {
    "acero": "Acero negro UNE-EN 10255 serie M",
    "cobre": "Cobre UNE-EN 1057",
    "plastico": "Termoplástico",
}
#: Rugosidad absoluta (m): cobre y plástico, guía IDAE nº 18 (al pie de sus tablas); acero
#: comercial, diagrama de Moody.
RUGOSIDAD_M = {"acero": 0.045e-3, "cobre": 0.002e-3, "plastico": 0.006e-3}
#: Dilatación (mm/(m·K)), guía IDAE nº 18, 3.1.4; el plástico no la da y no se calcula.
DILATACION_MM_M_K = {"acero": 0.012, "cobre": 0.017}

# --- Criterios de dimensionado ----------------------------------------------------------
#: 40 mm c.a./m (guía IDAE nº 18, Ap. B), en Pa/m.
PERDIDA_MAXIMA_PA_M = 40 * 9.80665
#: < 1,2 m/s por ruido (IDAE nº 18, Ap. B); ASHRAE Fundamentals 1997 (SI) cap. 33 lo limita
#: a DN50 y menores y admite más velocidad en diámetros mayores.
VELOCIDAD_MAXIMA_M_S = 1.2
VELOCIDAD_HASTA_DN = 50
#: Colectores y bocas del depósito de inercia: separador de baja pérdida, ≤ 0,9 m/s (Caleffi,
#: Idraulica 18, método de los tres diámetros). Cuerpo del separador D = 3·d.
VELOCIDAD_COLECTOR_M_S = 0.9
#: Pérdidas en accesorios: 30 % de las de los tubos; ida y vuelta (IDAE nº 18, ej. 4.1 y 4.2).
FACTOR_ACCESORIOS = 1.3
#: Intercambiador de la máquina, «suele ser de 1 a 2 m c.a.» (IDAE nº 18, 4.1): 2 m c.a.
PERDIDA_GENERADOR_PA = 2 * 9806.65
#: Fancoil de conductos, 1.500 mm c.a. (IDAE nº 18, 4.1). Se cambia por circuito.
PERDIDA_TERMINAL_PA = 1.5 * 9806.65
#: Temperaturas de los ejemplos de la guía IDAE nº 18 (fancoils): 7/12 °C y 45/40 °C.
FRIO_IMPULSION_C, FRIO_RETORNO_C = 7.0, 12.0
CALOR_IMPULSION_C, CALOR_RETORNO_C = 45.0, 40.0
#: «En el caso de instalaciones de agua con bomba de calor, la temperatura mínima es de 5 °C
#: y la máxima puede ser de 45 °C» (IDAE nº 18, 3.1.4): dilatación y vaso de expansión.
TEMPERATURA_MINIMA_C, TEMPERATURA_MAXIMA_C = 5.0, 45.0
#: Volumen mínimo de agua del fabricante; por defecto 3,5 l/kW (Carrier 30RA, aire
#: acondicionado).
VOLUMEN_MINIMO_L_KW = 3.5


# --- RITE IT 1.3.4.2 --------------------------------------------------------------------
def _por_potencia(tabla, potencia_kw: float, frio: bool) -> int:
    for limite, calor_dn, frio_dn in tabla:
        if potencia_kw <= limite:
            return frio_dn if frio else calor_dn
    raise AssertionError("inalcanzable")


#: Tabla 3.4.2.2: (potencia hasta kW, DN calor, DN frío).
ALIMENTACION = ((70, 15, 20), (150, 20, 25), (400, 25, 32), (float("inf"), 32, 40))
#: Tabla 3.4.2.3.
VACIADO = ((70, 20, 25), (150, 25, 32), (400, 32, 40), (float("inf"), 40, 50))
ALIVIO_DN_MIN = 20  # IT 1.3.4.2.2.1
VACIADO_PARCIAL_DN_MIN = 20  # IT 1.3.4.2.3.2
PURGADOR_DN_MIN = 15  # IT 1.3.4.2.3.6


def dn_alimentacion(potencia_kw: float, frio: bool) -> int:
    return _por_potencia(ALIMENTACION, potencia_kw, frio)


def dn_vaciado(potencia_kw: float, frio: bool) -> int:
    return _por_potencia(VACIADO, potencia_kw, frio)


def valvula_retencion(dn: int) -> str:
    """IT 1.3.4.2.7: clapeta solo hasta DN32; disco con muelle hasta DN150."""
    if dn <= 32:
        return "de clapeta"
    if dn <= 150:
        return "de disco con muelle de retorno"
    return "de disco o motorizada con tiempo de actuación ajustable"


def valvula_corte(dn: int) -> str:
    """De bola hasta DN50 y de mariposa por encima (criterio de la ficha); IT 1.3.4.2.7:
    las de mariposa desde DN100, con desmultiplicador."""
    if dn <= 50:
        return "de bola"
    return "de mariposa con desmultiplicador" if dn >= 100 else "de mariposa"


# --- Aislamiento (RITE IT 1.2.4.2.1.2, interior de edificios) ---------------------------
#: Tablas por diámetro exterior hasta (mm): calientes 40–60 °C y > 60–100 °C (1.2.4.2.1);
#: fríos > 0–10 °C y > 10 °C (1.2.4.2.3); exterior, 1.2.4.2.2 y 1.2.4.2.4.
_DIAMETROS = (35, 60, 90, 140, float("inf"))
AISLAMIENTO = {
    ("calor", "interior", 60): (25, 30, 30, 30, 35),
    ("calor", "interior", 100): (25, 30, 30, 40, 40),
    ("calor", "exterior", 60): (35, 40, 40, 40, 45),
    ("calor", "exterior", 100): (35, 40, 40, 50, 50),
    ("frio", "interior", 10): (25, 30, 30, 40, 40),
    ("frio", "interior", 99): (20, 20, 30, 30, 30),
    ("frio", "exterior", 10): (45, 50, 50, 60, 60),
    ("frio", "exterior", 99): (40, 40, 50, 50, 50),
}


def espesor_aislamiento_mm(
    exterior_mm: float, ubicacion: str, t_calor_max: float | None, t_frio_min: float | None
) -> int:
    """Espesor mínimo (mm, λ = 0,040 W/(m·K)); con frío y calor alternos, el más exigente
    (IT 1.2.4.2.1.2.4)."""
    i = next(k for k, d in enumerate(_DIAMETROS) if exterior_mm <= d)
    espesores = []
    if t_calor_max is not None and t_calor_max > 40:
        espesores.append(AISLAMIENTO[("calor", ubicacion, 60 if t_calor_max <= 60 else 100)][i])
    if t_frio_min is not None:
        if t_frio_min <= 0:
            raise ValueError("Agua por debajo de 0 °C: fuera del alcance (glicol).")
        espesores.append(AISLAMIENTO[("frio", ubicacion, 10 if t_frio_min <= 10 else 99)][i])
    return max(espesores, default=0)


# --- Vaso de expansión (IDAE nº 18, 3.1.2 y 3.1.3) --------------------------------------
def coeficiente_expansion(t_c: float) -> float:
    """Ce = (3,24·T² + 102,13·T − 2.708,3)·10⁻⁶ (agua sin aditivos)."""
    return (3.24 * t_c**2 + 102.13 * t_c - 2708.3) * 1e-6


@dataclass(frozen=True)
class Presiones:
    """Presiones relativas (bar) en el punto del vaso."""

    llenado: float  # Pm
    inicial_vaso: float  # Pi
    maxima_servicio: float  # PM
    alivio: float
    seguridad: float
    prueba: float
    nominal: int  # PN de equipos y accesorios


def presiones(altura_m: float) -> Presiones:
    """Con el vaso en la sala (punto bajo) y la instalación `altura_m` por encima: 1 bar en
    el punto alto; Pi 0,3 bar por debajo; PM = Pm + 1; seguridad = PM + 0,5 (las tres
    relaciones de los tres ejemplos de la guía, 3.1.2); alivio PM + 0,3 (RITE
    IT 1.3.4.2.2); prueba 1,5·PM, mínimo 6 bar; PN, el normalizado por encima de la
    seguridad."""
    if altura_m < 0:
        raise ValueError("La altura de la instalación no puede ser negativa.")
    pm = round(1.0 + altura_m * 9.80665 * 1000 / 1e5, 2)
    maxima = round(pm + 1.0, 2)
    seguridad = round(maxima + 0.5, 2)
    nominal = next(pn for pn in (6, 10, 16, 25) if pn > seguridad)
    return Presiones(
        pm,
        round(pm - 0.3, 2),
        maxima,
        round(maxima + 0.3, 2),
        seguridad,
        round(max(6.0, 1.5 * maxima), 2),
        nominal,
    )


def volumen_vaso_l(volumen_instalacion_l: float, t_max_c: float, p: Presiones) -> float:
    """Vt = Ce·V / (Pi/Pm − Pi/PM), presiones absolutas."""
    pi, pm, pmax = p.inicial_vaso + 1, p.llenado + 1, p.maxima_servicio + 1
    return coeficiente_expansion(t_max_c) * volumen_instalacion_l / (pi / pm - pi / pmax)
