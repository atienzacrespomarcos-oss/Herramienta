"""Subcuadro eléctrico de clima: línea de alimentación y salidas (docs/modules/electricidad.md).

Motor puro: intensidades (ITC-BT-47 en motores), secciones por intensidad admisible
(GUÍA-BT-19 tablas A y E) y por caída de tensión (Anexo 2, límite de la ITC-BT-19 2.2.2
sumando la de la alimentación), magnetotérmico (GUÍA-BT-22), diferencial (GUÍA-BT-24) y
conductor de protección (ITC-BT-19 tabla 2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from traza.rules import electricidad as re


@dataclass(frozen=True)
class Salida:
    nombre: str
    potencia_kw: float  # eléctrica absorbida (la de la ficha del equipo)
    fases: int  # 3 o 1
    longitud_m: float
    motor: bool = True
    variador: bool = False
    cos_phi: float = re.COS_PHI_DEFECTO
    metodo: str = "E"


@dataclass(frozen=True)
class Linea:
    """Una línea calculada (la alimentación del subcuadro o una salida)."""

    nombre: str
    fases: int
    potencia_kw: float
    intensidad_a: float  # Ib de servicio
    intensidad_diseno_a: float  # la que dimensiona (125 % en motores)
    seccion: float
    seccion_pe: float
    admisible_a: float  # Iz con el factor de agrupamiento
    calibre_a: int | None
    curva: str
    caida_pct: float  # la de esta línea
    caida_total_pct: float  # alimentación + esta línea
    metodo: str
    longitud_m: float
    diferencial_ma: int | None = None
    diferencial_tipo: str = ""
    cumple: bool = True
    avisos: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class ResultadoSubcuadro:
    alimentacion: Linea
    salidas: tuple[Linea, ...]
    limite_pct: float
    avisos: tuple[str, ...] = field(default=())

    @property
    def cumple(self) -> bool:
        return self.alimentacion.cumple and all(s.cumple for s in self.salidas)


def intensidad(potencia_kw: float, fases: int, cos_phi: float) -> float:
    """I = P/(√3·U·cos φ) en trifásico, P/(U·cos φ) en monofásico (Anexo 2)."""
    if fases == 3:
        return potencia_kw * 1000 / (math.sqrt(3) * re.TENSION_TRIFASICA_V * cos_phi)
    return potencia_kw * 1000 / (re.TENSION_MONOFASICA_V * cos_phi)


def _validar(s: Salida) -> None:
    if s.fases not in (1, 3):
        raise ValueError(f"{s.nombre}: 1 o 3 fases.")
    if s.potencia_kw <= 0 or s.longitud_m <= 0:
        raise ValueError(f"{s.nombre}: potencia y longitud positivas.")
    if not 0.5 <= s.cos_phi <= 1:
        raise ValueError(f"{s.nombre}: factor de potencia entre 0,5 y 1.")
    if s.metodo not in re.METODOS:
        raise ValueError(f"{s.nombre}: método de instalación no previsto «{s.metodo}».")


def _elegir(nombre, fases, potencia_kw, cos_phi, i_servicio, i_diseno, longitud, metodo,
            circuitos, limite_linea_pct, caida_previa_pct, motor):  # fmt: skip
    """Menor sección con In ≤ Iz·factor y caída total ≤ límite. None si ninguna cumple."""
    factor = re.factor_agrupamiento(metodo, circuitos)
    conductores = 3 if fases == 3 else 2
    cal = re.calibre(i_diseno)
    for s in re.SECCIONES:
        iz = re.intensidad_admisible(s, metodo, conductores)
        if iz is None:
            continue
        iz *= factor
        if cal is None or cal > iz + 1e-9:
            continue
        u = re.TENSION_TRIFASICA_V if fases == 3 else re.TENSION_MONOFASICA_V
        caida = re.caida_tension_v(potencia_kw * 1000, longitud, s, fases, cos_phi) / u * 100
        if caida_previa_pct + caida <= limite_linea_pct + 1e-9:
            return Linea(
                nombre, fases, potencia_kw, i_servicio, i_diseno, s,
                re.seccion_proteccion(s), iz, cal, "D" if motor else "C", caida,
                caida_previa_pct + caida, metodo, longitud,
            )  # fmt: skip
    return None


def calcular(
    salidas: list[Salida],
    suministro: str = "compania",
    longitud_alimentacion_m: float = 20.0,
    metodo_alimentacion: str = "E",
    nombre: str = "Subcuadro de clima",
) -> ResultadoSubcuadro:
    if not salidas:
        raise ValueError("El subcuadro necesita al menos una salida.")
    if suministro not in re.CAIDA_MAXIMA:
        raise ValueError(f"Suministro no previsto: «{suministro}».")
    if longitud_alimentacion_m <= 0:
        raise ValueError("La longitud de la alimentación tiene que ser positiva.")
    for s in salidas:
        _validar(s)
    limite = re.CAIDA_MAXIMA[suministro]
    # Alimentación (trifásica): 125 % del motor mayor más el resto (ITC-BT-47); la potencia
    # de cálculo de la caída, la suma de todas (todas pueden funcionar a la vez).
    corrientes = [intensidad(s.potencia_kw, s.fases, s.cos_phi) for s in salidas]
    motores = [i for i, s in zip(corrientes, salidas, strict=True) if s.motor]
    i_alim = sum(corrientes) + (0.25 * max(motores) if motores else 0.0)
    p_total = sum(s.potencia_kw for s in salidas)
    cos_alim = p_total * 1000 / (math.sqrt(3) * re.TENSION_TRIFASICA_V * sum(corrientes))
    cos_alim = min(max(cos_alim, 0.5), 1.0)
    por_metodo: dict[str, int] = {}
    for s in salidas:
        por_metodo[s.metodo] = por_metodo.get(s.metodo, 0) + 1
    avisos: list[str] = []
    # Menor sección de la alimentación con la que todas las salidas cumplen (ficha,
    # «Reparto de la caída de tensión»).
    cal_alim = re.calibre(i_alim)
    for s_alim in re.SECCIONES:
        iz = re.intensidad_admisible(s_alim, metodo_alimentacion, 3)
        if iz is None or (cal_alim is not None and cal_alim > iz):
            continue
        if cal_alim is None and i_alim > iz:
            continue
        caida = (
            re.caida_tension_v(p_total * 1000, longitud_alimentacion_m, s_alim, 3, cos_alim)
            / re.TENSION_TRIFASICA_V
            * 100
        )
        if caida > limite:
            continue
        alim = Linea(
            nombre, 3, p_total, sum(corrientes), i_alim, s_alim, re.seccion_proteccion(s_alim),
            iz, cal_alim, "C", caida, caida, metodo_alimentacion, longitud_alimentacion_m,
        )  # fmt: skip
        resultado = []
        for s, i in zip(salidas, corrientes, strict=True):
            linea = _elegir(
                s.nombre, s.fases, s.potencia_kw, s.cos_phi, i, i * (1.25 if s.motor else 1.0),
                s.longitud_m, s.metodo, por_metodo[s.metodo], limite, caida, s.motor,
            )  # fmt: skip
            if linea is None:
                break
            ma, tipo = re.diferencial(s.fases, linea.calibre_a, s.variador)
            resultado.append(
                Linea(**{**vars(linea), "diferencial_ma": ma, "diferencial_tipo": tipo})
            )
        else:
            if cal_alim is None:
                avisos.append(
                    f"Alimentación de {i_alim:.0f} A: por encima de 160 A, interruptor de caja "
                    "moldeada a definir con el fabricante."
                )
            return ResultadoSubcuadro(alim, tuple(resultado), limite, tuple(avisos))
    raise ValueError(
        "Ninguna sección hasta 300 mm² cumple: revisa longitudes o potencias (o divide el "
        "subcuadro)."
    )
