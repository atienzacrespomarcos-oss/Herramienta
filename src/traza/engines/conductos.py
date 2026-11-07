"""Redes de conductos de aire (motor puro): rozamiento, dimensionado por pérdida de carga
constante con límites de velocidad, pérdidas en accesorios, camino crítico y equilibrado.

Fuentes (docs/modules/redes_aire.md):
- Rozamiento: Darcy-Weisbach con Colebrook (ASHRAE Fundamentals, cap. 21; manual Climaver
  de Isover, 6.2.1), rugosidad de chapa galvanizada 0,09 mm.
- Diámetro equivalente de Huebscher: De = 1,30·(a·b)^0,625/(a+b)^0,25.
- Accesorios: `rules/accesorios_conductos.py` (manual Climaver, coeficientes de ASHRAE).
- Velocidades máximas por ruido: 10 m/s en principales, 7,5 en ramales y 4 cerca de los
  terminales (manual Climaver, 4.3.4).

Magnitudes con la unidad en el nombre (_m, _m3s, _pa…).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from traza.rules import accesorios_conductos as acc

RUGOSIDAD_GALVANIZADA_M = 0.09e-3
VISCOSIDAD_AIRE_PA_S = 1.81e-5  # aire normal de ASHRAE a 20 °C
R_AIRE = 287.055

#: UNE-EN 1506 (gama de tubo helicoidal de 80 a 1250 mm), en metros.
DIAMETROS_M = tuple(
    d / 1000
    for d in (
        80,
        100,
        125,
        160,
        200,
        250,
        315,
        355,
        400,
        450,
        500,
        560,
        630,
        710,
        800,
        900,
        1000,
        1120,
        1250,
    )
)
PASO_RECTANGULAR_M = 0.05
LADO_MINIMO_M = 0.10
RELACION_MAXIMA = 4.0
#: Alto con «sin límite»: el mayor lado que se fabrica en panel o chapa de forma habitual.
ALTO_SIN_LIMITE_M = 3.0

#: Velocidad máxima por clase de tramo (manual Climaver, 4.3.4).
VELOCIDAD_MAXIMA = {"principal": 10.0, "ramal": 7.5, "terminal": 4.0}
FUENTE_VELOCIDAD = "Manual de Conductos CLIMAVER, 4.3.4: 10 / 7,5 / 4 m/s"

#: Codo por defecto: radio igual al lado del giro (r/b = 1).
R_B_CODO = 1.0


@dataclass(frozen=True)
class Aire:
    densidad: float = 1.204  # kg/m³ (20 °C, 101 325 Pa)
    viscosidad: float = VISCOSIDAD_AIRE_PA_S


AIRE_NORMAL = Aire()


def aire(temperatura_c: float = 20.0, presion_pa: float = 101_325.0) -> Aire:
    return Aire(presion_pa / (R_AIRE * (temperatura_c + 273.15)))


@dataclass(frozen=True)
class Seccion:
    forma: str  # rectangular | circular
    a_m: float  # ancho, o diámetro
    b_m: float | None = None  # alto (rectangular)

    def __post_init__(self):
        if self.forma not in ("rectangular", "circular"):
            raise ValueError(f"Forma de conducto no prevista: «{self.forma}».")
        if self.a_m <= 0 or (self.forma == "rectangular" and (self.b_m or 0) <= 0):
            raise ValueError("Las medidas del conducto tienen que ser positivas.")

    @property
    def area_m2(self) -> float:
        if self.forma == "circular":
            return math.pi * self.a_m**2 / 4
        return self.a_m * self.b_m

    @property
    def diametro_equivalente_m(self) -> float:
        if self.forma == "circular":
            return self.a_m
        a, b = self.a_m, self.b_m
        return 1.30 * (a * b) ** 0.625 / (a + b) ** 0.25

    @property
    def perimetro_m(self) -> float:
        if self.forma == "circular":
            return math.pi * self.a_m
        return 2 * (self.a_m + self.b_m)

    def texto(self) -> str:
        if self.forma == "circular":
            return f"Ø{self.a_m * 1000:.0f}"
        return f"{self.a_m * 1000:.0f}×{self.b_m * 1000:.0f}"


def factor_friccion(re: float, rugosidad_relativa: float) -> float:
    """Colebrook: 1/√f = −2·log10(ε/(3,7·D) + 2,51/(Re·√f)), por iteración."""
    if re < 2300:
        return 64.0 / re  # laminar (no se da en conductos de climatización)
    f = 0.02
    for _ in range(50):
        nuevo = (-2.0 * math.log10(rugosidad_relativa / 3.7 + 2.51 / (re * math.sqrt(f)))) ** -2
        if abs(nuevo - f) < 1e-12:
            return nuevo
        f = nuevo
    return f


def friccion_pa_m(
    caudal_m3s: float,
    s: Seccion,
    a: Aire = AIRE_NORMAL,
    rugosidad_m: float = RUGOSIDAD_GALVANIZADA_M,
) -> float:
    """Pérdida por rozamiento (Pa/m). En rectangulares, con el círculo de igual pérdida
    (diámetro equivalente de Huebscher) y su velocidad."""
    if caudal_m3s <= 0:
        return 0.0
    d = s.diametro_equivalente_m
    v = caudal_m3s / (math.pi * d * d / 4)
    re = a.densidad * v * d / a.viscosidad
    f = factor_friccion(re, rugosidad_m / d)
    return f / d * a.densidad * v * v / 2


def reynolds(caudal_m3s: float, s: Seccion, a: Aire = AIRE_NORMAL) -> float:
    d = s.diametro_equivalente_m
    return a.densidad * (caudal_m3s / s.area_m2) * d / a.viscosidad


@dataclass(frozen=True)
class Dimensionado:
    seccion: Seccion
    velocidad_m_s: float
    friccion_pa_m: float
    avisos: tuple[str, ...] = ()


def dimensionar(
    caudal_m3s: float,
    forma: str,
    friccion_objetivo_pa_m: float,
    velocidad_max_m_s: float,
    alto_max_m: float | None = None,
    a: Aire = AIRE_NORMAL,
) -> Dimensionado:
    """La sección comercial más pequeña que cumple a la vez la pérdida de carga objetivo y la
    velocidad máxima. Rectangular: lados múltiplos de 50 mm, relación ≤ 4, alto ≤ alto
    máximo; entre las que cumplen, la de menor perímetro (menos chapa)."""
    if caudal_m3s <= 0:
        raise ValueError("El caudal del tramo tiene que ser positivo.")

    def cumple(s: Seccion) -> bool:
        return (
            caudal_m3s / s.area_m2 <= velocidad_max_m_s + 1e-9
            and friccion_pa_m(caudal_m3s, s, a) <= friccion_objetivo_pa_m + 1e-9
        )

    def resultado(s: Seccion, avisos=()) -> Dimensionado:
        return Dimensionado(s, caudal_m3s / s.area_m2, friccion_pa_m(caudal_m3s, s, a), avisos)

    if forma == "circular":
        for d in DIAMETROS_M:
            s = Seccion("circular", d)
            if cumple(s):
                return resultado(s)
        s = Seccion("circular", DIAMETROS_M[-1])
        return resultado(s, ("Caudal mayor que el del mayor diámetro comercial (Ø1250).",))

    # Sin alto máximo: hasta ALTO_SIN_LIMITE_M (antes se ponía 1 m sin decirlo).
    alto = alto_max_m if alto_max_m is not None else ALTO_SIN_LIMITE_M
    pasos_b = [LADO_MINIMO_M + PASO_RECTANGULAR_M * i for i in range(200)]
    pasos_b = [b for b in pasos_b if b <= alto + 1e-9] or [LADO_MINIMO_M]
    for relacion, aviso in (
        (RELACION_MAXIMA, ()),
        (10.0, ("Relación de lados mayor que 4 por el alto máximo.",)),
    ):
        mejor = None
        for b in pasos_b:
            a_lado = b
            while a_lado <= relacion * b + 1e-9 and a_lado <= 6.0:
                s = Seccion("rectangular", round(a_lado, 3), round(b, 3))
                if cumple(s):
                    clave = (s.perimetro_m, s.area_m2)
                    if mejor is None or clave < mejor[0]:
                        mejor = (clave, s)
                    break  # el siguiente ancho con este alto es mayor: no mejora
                a_lado += PASO_RECTANGULAR_M
        if mejor is not None:
            return resultado(mejor[1], aviso)
    s = Seccion("rectangular", 6.0, pasos_b[-1])
    return resultado(s, ("Caudal demasiado grande para el alto máximo.",))


# --- Red en árbol ---------------------------------------------------------------------


@dataclass(frozen=True)
class Tramo:
    id: str
    padre: str | None  # tramo aguas arriba; None = sale (o llega) del equipo
    longitud_m: float
    caudal_m3s: float
    clase: str  # principal | ramal | terminal
    es_paso: bool = True  # en la derivación de su padre: sigue recto (True) o deriva
    codos: tuple[float, ...] = ()  # ángulos de los cambios de dirección del tramo (°)
    terminal: str | None = None  # código del terminal al final del tramo
    seccion_fija: Seccion | None = None


@dataclass(frozen=True)
class TramoCalculado:
    tramo: Tramo
    seccion: Seccion
    velocidad_m_s: float
    friccion_pa_m: float
    perdida_friccion_pa: float
    perdida_accesorios_pa: float
    perdida_terminal_pa: float
    accesorios: tuple[tuple[str, float, float], ...]  # (accesorio, C, Pa)
    avisos: tuple[str, ...] = ()

    @property
    def perdida_pa(self) -> float:
        return self.perdida_friccion_pa + self.perdida_accesorios_pa + self.perdida_terminal_pa


@dataclass(frozen=True)
class ResultadoRed:
    tramos: tuple[TramoCalculado, ...]
    caminos: dict[str, float]  # terminal → pérdida total desde el equipo (Pa)
    terminal_critico: str | None
    presion_necesaria_pa: float  # la del camino crítico
    exceso_pa: dict[str, float] = field(default_factory=dict)  # a disipar por terminal


def calcular_red(
    tramos: list[Tramo],
    tipo: str,
    friccion_objetivo_pa_m: float,
    alto_max_m: float | None,
    forma: str = "rectangular",
    a: Aire = AIRE_NORMAL,
) -> ResultadoRed:
    """Dimensiona cada tramo y suma las pérdidas por caminos. `tipo`: impulsion | retorno |
    extraccion (la pérdida del terminal sale del RITE). En retorno y extracción el aire
    converge: se usan los coeficientes de derivación divergente como aproximación
    (declarada en la ficha)."""
    if tipo not in acc.TERMINAL_PA:
        raise ValueError(f"Tipo de red no previsto: «{tipo}».")
    por_id = {t.id: t for t in tramos}
    if len(por_id) != len(tramos):
        raise ValueError("Hay tramos con el mismo identificador.")
    for t in tramos:
        if t.padre is not None and t.padre not in por_id:
            raise ValueError(f"El tramo {t.id} cuelga de un tramo que no existe ({t.padre}).")

    dim: dict[str, Dimensionado] = {}
    for t in tramos:
        if t.seccion_fija is not None:
            s = t.seccion_fija
            dim[t.id] = Dimensionado(s, t.caudal_m3s / s.area_m2, friccion_pa_m(t.caudal_m3s, s, a))
        else:
            dim[t.id] = dimensionar(
                t.caudal_m3s,
                forma,
                friccion_objetivo_pa_m,
                VELOCIDAD_MAXIMA[t.clase],
                alto_max_m,
                a,
            )

    calculados: dict[str, TramoCalculado] = {}
    for t in tramos:
        d = dim[t.id]
        pv = a.densidad * d.velocidad_m_s**2 / 2
        accesorios: list[tuple[str, float, float]] = []
        s = d.seccion
        # Los giros del plano son horizontales: el lado en el plano del giro («b» del manual)
        # es el ancho, y «a» el alto (revisión 07-11-2026: estaban al revés).
        ancho, alto = (s.a_m, s.b_m) if s.forma == "rectangular" else (s.a_m, s.a_m)
        re = reynolds(t.caudal_m3s, s, a)
        for angulo in t.codos:
            c = acc.codo_radio(alto, ancho, R_B_CODO, angulo, re)
            accesorios.append((f"Codo {angulo:.0f}°", c, c * pv))
        if t.padre is not None:
            ve = dim[t.padre].velocidad_m_s
            if t.es_paso:
                c = acc.derivacion_paso(
                    d.velocidad_m_s, ve, s.area_m2 / dim[t.padre].seccion.area_m2
                )
                accesorios.append(("Derivación, paso recto", c, c * pv))
            else:
                c = acc.derivacion_ramal(d.velocidad_m_s, ve)
                accesorios.append(("Derivación, ramal", c, c * pv))
        terminal = acc.TERMINAL_PA[tipo] if t.terminal else 0.0
        calculados[t.id] = TramoCalculado(
            t,
            s,
            d.velocidad_m_s,
            d.friccion_pa_m,
            d.friccion_pa_m * t.longitud_m,
            sum(x[2] for x in accesorios),
            terminal,
            tuple(accesorios),
            d.avisos,
        )

    caminos: dict[str, float] = {}
    for t in tramos:
        if t.terminal is None:
            continue
        total, actual, vistos = 0.0, t, set()
        while actual is not None:
            if actual.id in vistos:
                raise ValueError("La red tiene un ciclo: no es un árbol.")
            vistos.add(actual.id)
            total += calculados[actual.id].perdida_pa
            actual = por_id.get(actual.padre) if actual.padre else None
        caminos[t.terminal] = total
    critico = max(caminos, key=caminos.get) if caminos else None
    presion = caminos[critico] if critico else 0.0
    return ResultadoRed(
        tuple(calculados[t.id] for t in tramos),
        caminos,
        critico,
        presion,
        {k: presion - v for k, v in caminos.items()},
    )


# --- Ventilador: potencia específica (RITE IT 1.2.4.2.5) -----------------------------

#: Tabla 2.4.2.7: límite superior de W/(m³/s) de cada categoría.
SFP = ((0, 300), (1, 500), (2, 750), (3, 1250), (4, 2000), (5, 3000), (6, 4500))
#: Categoría exigida (apartado 5): (tipo de red, climatización) → SFP máxima.
SFP_EXIGIDA = {
    ("impulsion", True): 4,
    ("impulsion", False): 3,
    ("retorno", True): 3,
    ("extraccion", True): 3,
    ("extraccion", False): 2,
    ("retorno", False): 2,
}


def categoria_sfp(w_m3s: float) -> int:
    for categoria, limite in SFP:
        if w_m3s <= limite:
            return categoria
    return 7


def rendimiento_minimo(presion_total_pa: float, categoria: int) -> float | None:
    """Rendimiento global mínimo del grupo motoventilador para no pasar de la categoría
    SFP: SFP = Δp/η ⇒ η ≥ Δp/límite."""
    limite = dict(SFP).get(categoria)
    return presion_total_pa / limite if limite else None
