"""Condiciones exteriores de proyecto para el cálculo de cargas (motor puro).

Fuente: IDAE, «Guía técnica. Condiciones climáticas exteriores de proyecto» (2010):
- Apartado 5.2, percentiles:
  - cobertura «alta» (hospitales, clínicas, residencias de ancianos, centros de cálculo):
    invierno TS 99,6 %, verano TS 0,4 % con su húmeda coincidente THC 0,4 %;
  - cobertura «normal» (el resto): invierno TS 99 %, verano TS 1 % con THC 1 %.
- Apartado 5.1: presión atmosférica según la altitud.
- Anexo 7.3, obra a otra cota que su estación de referencia:
  - temperatura seca −1 °C por cada 100 m que la obra esté POR ENCIMA de la estación; si
    está por debajo, la misma que la estación;
  - se mantiene la humedad absoluta (cambian la humedad relativa y la temperatura húmeda).
- Humedad de invierno: HUMcoin (humedad relativa coincidente con TS 99 %).

Los datos de la estación entran como números (los lee `io/clima_idae.py` de la guía que
tiene el usuario): aquí no hay ninguna cifra de la guía.
"""

from __future__ import annotations

from dataclasses import dataclass

from traza.core import psicrometria as ps

COBERTURAS = {
    "normal": "TS 99 % en invierno, TS 1 % en verano (IDAE 5.2)",
    "alta": "TS 99,6 % en invierno, TS 0,4 % en verano: hospitales, clínicas, residencias de "
    "ancianos, centros de cálculo (IDAE 5.2)",
}


@dataclass(frozen=True)
class DatosEstacion:
    altitud_m: float
    ts_996: float
    ts_99: float
    hum_coin: float  # %
    ts_04: float
    thc_04: float
    ts_1: float
    thc_1: float


@dataclass(frozen=True)
class CondicionesProyecto:
    cobertura: str
    altitud_obra_m: float
    presion_pa: float
    correccion_cota_c: float  # lo que se ha restado a las temperaturas secas
    invierno_ts: float
    invierno_hr: float  # 0–1
    verano_ts: float
    verano_th: float
    verano_w: float  # kg/kg
    notas: tuple[str, ...]


def condiciones(
    e: DatosEstacion, cobertura: str = "normal", altitud_obra_m: float | None = None
) -> CondicionesProyecto:
    if cobertura not in COBERTURAS:
        raise ValueError(f"Cobertura no prevista: «{cobertura}».")
    z = e.altitud_m if altitud_obra_m is None else float(altitud_obra_m)
    p_est = ps.presion_atmosferica(e.altitud_m)
    p = ps.presion_atmosferica(z)
    dz = z - e.altitud_m
    correccion = dz / 100.0 if dz > 0 else 0.0
    notas = []
    if dz > 0:
        notas.append(
            f"Obra {dz:.0f} m por encima de la estación: temperaturas secas −{correccion:.1f} °C "
            "y misma humedad absoluta (IDAE, anexo 7.3)."
        )
    elif dz < 0:
        notas.append(
            f"Obra {-dz:.0f} m por debajo de la estación: mismas temperaturas secas (IDAE, "
            "anexo 7.3)."
        )
    if cobertura == "alta":
        ts_inv, ts_ver, th_ver = e.ts_996, e.ts_04, e.thc_04
    else:
        ts_inv, ts_ver, th_ver = e.ts_99, e.ts_1, e.thc_1

    # Verano: humedad absoluta de la estación, temperatura seca corregida.
    w = ps.humedad_especifica_bulbo_humedo(ts_ver, th_ver, p_est)
    ts_v = ts_ver - correccion
    w = min(w, ps.humedad_especifica_saturacion(ts_v, p))
    th_v = ps.temperatura_humeda(ts_v, w, p)

    # Invierno: humedad relativa coincidente de la estación → humedad absoluta → nueva HR.
    w_inv = ps.humedad_especifica_relativa(ts_inv, e.hum_coin / 100.0, p_est)
    ts_i = ts_inv - correccion
    hr_i = min(ps.humedad_relativa(ts_i, w_inv, p), 1.0)

    return CondicionesProyecto(cobertura, z, p, correccion, ts_i, hr_i, ts_v, th_v, w, tuple(notas))
