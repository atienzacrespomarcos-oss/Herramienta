"""Propiedades del agua líquida a 101 325 Pa.

Generadas una vez con CoolProp 6.6.0 (formulación IAPWS-95, `PropsSI` con «Water»), que es
la biblioteca de propiedades adoptada en la especificación técnica. Se guardan como tabla
para no llevar CoolProp, que es binario, dentro de TRAZA.exe. Se interpolan linealmente
en engines/hidraulica.py.
"""

from __future__ import annotations

FUENTE = "CoolProp 6.6.0 (IAPWS-95), a 101 325 Pa"

#: (temperatura °C, densidad kg/m³, viscosidad dinámica µPa·s, calor específico J/(kg·K)).
TABLA: tuple[tuple[float, float, float, float], ...] = (
    (0, 999.84, 1791.1, 4219),
    (5, 999.97, 1518.2, 4205),
    (10, 999.70, 1305.9, 4195),
    (15, 999.10, 1137.6, 4188),
    (20, 998.21, 1001.6, 4184),
    (25, 997.05, 890.0, 4181),
    (30, 995.65, 797.2, 4180),
    (35, 994.03, 719.1, 4179),
    (40, 992.22, 652.7, 4179),
    (45, 990.21, 595.8, 4180),
    (50, 988.04, 546.5, 4181),
    (55, 985.69, 503.6, 4183),
    (60, 983.20, 466.0, 4185),
    (65, 980.55, 432.9, 4187),
    (70, 977.76, 403.5, 4190),
    (75, 974.84, 377.4, 4193),
    (80, 971.79, 354.1, 4197),
    (85, 968.61, 333.1, 4201),
    (90, 965.31, 314.2, 4205),
)
