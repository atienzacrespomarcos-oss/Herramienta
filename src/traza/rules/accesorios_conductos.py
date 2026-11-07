"""Coeficientes de pérdida de los accesorios de conductos rectangulares.

Fuente: Isover, «Manual de Conductos CLIMAVER», cap. 6.3.1.2, pp. 53–55. Son los valores de
ASHRAE para chapa galvanizada; el manual los da también para Climaver PLUS R y neto.
<https://www.isover.es/documents/catalogos-manuales-y-guias/08-manual-conductos-2.pdf>

ΔP = C · ρ·v²/2, con la velocidad de la sección que indica cada accesorio. Entre los
valores tabulados se interpola linealmente; fuera de la tabla se toma el extremo (no se
extrapola).

Errata corregida: K_Re del codo con r/b ≥ 0,75 y Re = 6·10⁴ figura como 0,46 en el
manual; ASHRAE da 1,46 (la serie es decreciente: 1,56 → 1,46 → 1,38). Ver
docs/modules/redes_aire.md.
"""

from __future__ import annotations

from bisect import bisect_left

FUENTE = "Isover, Manual de Conductos CLIMAVER, cap. 6.3.1.2 (coeficientes de ASHRAE)"


def interpolar(xs: tuple[float, ...], ys: tuple[float, ...], x: float) -> float:
    """Interpolación lineal; fuera del intervalo, el valor del extremo."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect_left(xs, x)
    x0, x1 = xs[i - 1], xs[i]
    return ys[i - 1] + (ys[i] - ys[i - 1]) * (x - x0) / (x1 - x0)


def interpolar_tabla(filas, columnas, valores, fila: float, columna: float) -> float:
    """Bilineal en una tabla valores[fila][columna]."""
    por_fila = [interpolar(columnas, v, columna) for v in valores]
    return interpolar(filas, tuple(por_fila), fila)


# --- Codo de radio uniforme, sección rectangular (p. 53) -------------------------------
CODO_A_B = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0)
CODO_R_B = (0.5, 0.75, 1.0, 1.5, 2.0)
CODO_C = (
    (1.3, 1.3, 1.2, 1.2, 1.1, 1.1, 0.98, 0.92, 0.89, 0.85, 0.83),
    (0.57, 0.52, 0.48, 0.44, 0.40, 0.39, 0.39, 0.40, 0.42, 0.43, 0.44),
    (0.27, 0.25, 0.23, 0.21, 0.19, 0.18, 0.18, 0.19, 0.20, 0.27, 0.21),
    (0.22, 0.20, 0.19, 0.17, 0.15, 0.14, 0.14, 0.15, 0.16, 0.17, 0.17),
    (0.20, 0.18, 0.16, 0.15, 0.14, 0.13, 0.13, 0.14, 0.14, 0.15, 0.15),
)
RE_1E4 = (1, 2, 3, 4, 6, 8, 10, 14, 20)
K_RE_R05 = (1.40, 1.26, 1.19, 1.14, 1.09, 1.06, 1.04, 1.0, 1.0)
K_RE_R075 = (2.0, 1.77, 1.64, 1.56, 1.46, 1.38, 1.30, 1.15, 1.0)  # 1,46: errata del manual
THETA = (20, 30, 45, 60, 75, 90, 110, 130, 150, 180)
K_THETA = (0.31, 0.45, 0.60, 0.78, 0.90, 1.00, 1.13, 1.20, 1.28, 1.40)


def k_reynolds(re: float, r_b: float) -> float:
    tabla = K_RE_R05 if r_b < 0.75 else K_RE_R075
    return interpolar(RE_1E4, tabla, re / 1e4)


def codo_radio(a: float, b: float, r_b: float, angulo: float, re: float) -> float:
    """C = C′·K_Re·K_θ. a = ancho (en el plano del giro, el «b» del manual es el lado del
    giro): se usa a/b con b = lado en el plano del giro."""
    c = interpolar_tabla(CODO_R_B, CODO_A_B, CODO_C, r_b, a / b)
    return c * k_reynolds(re, r_b) * interpolar(THETA, K_THETA, angulo)


# --- Codo a bisel, sin álabes (p. 54) ----------------------------------------------------
BISEL_THETA = (20, 30, 45, 60, 75, 90)
BISEL_C = (
    (0.08, 0.08, 0.08, 0.07, 0.07, 0.07, 0.06, 0.06, 0.05, 0.05, 0.05),
    (0.18, 0.17, 0.17, 0.16, 0.15, 0.15, 0.13, 0.13, 0.12, 0.12, 0.11),
    (0.38, 0.37, 0.36, 0.34, 0.33, 0.31, 0.28, 0.27, 0.26, 0.25, 0.24),
    (0.60, 0.59, 0.57, 0.55, 0.52, 0.49, 0.46, 0.43, 0.41, 0.39, 0.38),
    (0.89, 0.87, 0.84, 0.81, 0.77, 0.73, 0.67, 0.63, 0.61, 0.58, 0.57),
    (1.3, 1.3, 1.2, 1.2, 1.1, 1.1, 0.98, 0.92, 0.89, 0.85, 0.83),
)
K_RE_BISEL = (1.40, 1.26, 1.19, 1.14, 1.09, 1.06, 1.04, 1.0)
RE_BISEL_1E4 = (1, 2, 3, 4, 6, 8, 10, 14)


def codo_bisel(a: float, b: float, angulo: float, re: float) -> float:
    c = interpolar_tabla(BISEL_THETA, CODO_A_B, BISEL_C, angulo, a / b)
    return c * interpolar(RE_BISEL_1E4, K_RE_BISEL, re / 1e4)


# --- Reducción, sección rectangular (p. 53); C con la velocidad de salida -------------
# Los intervalos del manual («15–40», «50–60») valen lo mismo en sus dos extremos.
RED_THETA = (10, 15, 40, 50, 60, 90, 120, 150, 180)
RED_AE_AS = (2, 4, 6, 10)
RED_C = (
    (0.05, 0.05, 0.05, 0.06, 0.06, 0.12, 0.18, 0.24, 0.26),
    (0.05, 0.04, 0.04, 0.07, 0.07, 0.17, 0.27, 0.35, 0.41),
    (0.05, 0.04, 0.04, 0.07, 0.07, 0.18, 0.28, 0.36, 0.42),
    (0.05, 0.05, 0.05, 0.08, 0.08, 0.19, 0.29, 0.37, 0.43),
)


def reduccion(area_entrada: float, area_salida: float, angulo: float = 30.0) -> float:
    """Reducción (estrechamiento) con la velocidad de SALIDA. 30° de ángulo total por
    defecto, dentro del intervalo 15–40° del manual."""
    if area_entrada <= area_salida:
        return 0.0  # ensanchamiento o igual: no es una reducción
    return interpolar_tabla(RED_AE_AS, RED_THETA, RED_C, area_entrada / area_salida, angulo)


# --- Derivación a bisel (p. 55): 15° < θ ≤ 90°, Ae = As + Ad -------------------------
DER_VD_VE = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0)
DER_THETA = (15, 30, 45, 60, 90)
DER_CD = (
    (0.81, 0.65, 0.51, 0.38, 0.28, 0.20, 0.11, 0.06, 0.14, 0.30, 0.51, 0.76, 1.0),
    (0.84, 0.69, 0.56, 0.44, 0.34, 0.26, 0.19, 0.15, 0.15, 0.30, 0.51, 0.76, 1.0),
    (0.87, 0.74, 0.63, 0.54, 0.45, 0.38, 0.29, 0.24, 0.23, 0.30, 0.51, 0.76, 1.0),
    (0.90, 0.82, 0.79, 0.66, 0.59, 0.53, 0.43, 0.36, 0.33, 0.39, 0.51, 0.76, 1.0),
    (1.0,) * 13,
)
DER_VS_VE = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0)
#: C_s en el principal con θ = 90°, por As/Ae (columnas 0–0,4 · 0,5 · 0,6 · 0,7 · ≥ 0,8).
#: Donde el manual no da valor («–», velocidades de salida muy altas), el de la columna
#: 0–0,4 (que es la misma que ≥ 0,8 y la de 15–60°).
DER_AS_AE = (0.4, 0.5, 0.6, 0.7, 0.8)
_CS_04 = (1.0, 0.81, 0.64, 0.50, 0.36, 0.25, 0.16, 0.04, 0.0, 0.07, 0.39, 0.90, 1.8, 3.2)
_CS_05 = (1.0, 0.81, 0.64, 0.52, 0.40, 0.30, 0.23, 0.17, 0.20, 0.36, 0.79, 1.4, 2.4, 4.0)
_CS_06 = (1.0, 0.81, 0.64, 0.52, 0.38, 0.28, 0.20, 0.10, 0.10, 0.21, 0.59, 1.2, 1.8, 3.2)
_CS_07 = (1.0, 0.81, 0.64, 0.50, 0.37, 0.27, 0.18, 0.07, 0.05, 0.14, 0.39, 0.90, 1.8, 3.2)
DER_CS = tuple(zip(_CS_04, _CS_05, _CS_06, _CS_07, _CS_04, strict=True))


def derivacion_ramal(v_ramal: float, v_entrada: float, angulo: float = 90.0) -> float:
    """C_d de la derivación, con la velocidad del RAMAL."""
    return interpolar_tabla(DER_THETA, DER_VD_VE, DER_CD, angulo, v_ramal / v_entrada)


def derivacion_paso(v_salida: float, v_entrada: float, as_ae: float) -> float:
    """C_s del paso recto de una derivación a 90°, con la velocidad de SALIDA."""
    return interpolar_tabla(DER_VS_VE, DER_AS_AE, DER_CS, v_salida / v_entrada, as_ae)


# --- Terminales: caídas máximas del RITE IT 1.2.4.2.4 -------------------------------
TERMINAL_PA = {"impulsion": 40.0, "retorno": 20.0, "extraccion": 20.0}
FUENTE_TERMINAL = "RITE IT 1.2.4.2.4: unidades terminales de aire 40 Pa; rejillas de retorno 20 Pa"
