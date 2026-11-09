"""Reglas de los subcuadros eléctricos de clima (docs/modules/electricidad.md, «Fuentes»).

REBT (RD 842/2002) y las guías técnicas de aplicación del Ministerio (GUÍA-BT-19, -22,
-24 y Anexo 2). Cable de cobre.
"""

from __future__ import annotations

REBT = "REBT (RD 842/2002)"
TENSION_TRIFASICA_V = 400.0
TENSION_MONOFASICA_V = 230.0

#: Secciones normalizadas (mm²) de la tabla A de la GUÍA-BT-19 (hasta 300; ver la ficha).
SECCIONES = (1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300)

#: GUÍA-BT-19, tabla A (= UNE 20460-5-523:2004 tabla A.52-1 bis): intensidades admisibles
#: (A) de cables de cobre no enterrados a 40 °C; una fila por sección, columnas 2 a 13.
#: None = sin valor en la tabla.
_TABLA_A = {
    1.5: (11, 11.5, 13, 13.5, 15, 16, 16.5, 19, 20, 21, 24, None),
    2.5: (15, 16, 17.5, 18.5, 21, 22, 23, 26, 26.5, 29, 33, None),
    4: (20, 21, 23, 24, 27, 30, 31, 34, 36, 38, 45, None),
    6: (25, 27, 30, 32, 36, 37, 40, 44, 46, 49, 57, None),
    10: (34, 37, 40, 44, 50, 52, 54, 60, 65, 68, 76, None),
    16: (45, 49, 54, 59, 66, 70, 73, 81, 87, 91, 105, None),
    25: (59, 64, 70, 77, 84, 88, 95, 103, 110, 116, 123, 140),
    35: (None, 77, 86, 96, 104, 110, 119, 127, 137, 144, 154, 174),
    50: (None, 94, 103, 117, 125, 133, 145, 155, 167, 175, 188, 210),
    70: (None, None, None, 149, 160, 171, 185, 199, 214, 224, 244, 269),
    95: (None, None, None, 180, 194, 207, 224, 241, 259, 271, 296, 327),
    120: (None, None, None, 208, 225, 240, 260, 280, 301, 314, 348, 380),
    150: (None, None, None, 236, 260, 278, 299, 322, 343, 363, 404, 438),
    185: (None, None, None, 268, 297, 317, 341, 368, 391, 415, 464, 500),
    240: (None, None, None, 315, 350, 374, 401, 435, 468, 490, 552, 590),
    300: (None, None, None, 361, 401, 430, 461, 500, 538, 563, 638, 678),
}
#: Columna de la tabla A por (método, conductores cargados, aislamiento), leída con la
#: posición de cada celda en la página 10 del PDF de la guía (tabla en la ficha).
COLUMNA = {
    ("A1", 3, "PVC"): 3, ("A1", 2, "PVC"): 4, ("A1", 3, "XLPE"): 6, ("A1", 2, "XLPE"): 7,
    ("A2", 3, "PVC"): 2, ("A2", 2, "PVC"): 3, ("A2", 3, "XLPE"): 5, ("A2", 2, "XLPE"): 6,
    ("B1", 3, "PVC"): 5, ("B1", 2, "PVC"): 6, ("B1", 3, "XLPE"): 8, ("B1", 2, "XLPE"): 10,
    ("B2", 3, "PVC"): 4, ("B2", 2, "PVC"): 5, ("B2", 3, "XLPE"): 7, ("B2", 2, "XLPE"): 8,
    ("C", 3, "PVC"): 6, ("C", 2, "PVC"): 8, ("C", 3, "XLPE"): 9, ("C", 2, "XLPE"): 11,
    ("E", 3, "PVC"): 7, ("E", 2, "PVC"): 9, ("E", 3, "XLPE"): 10, ("E", 2, "XLPE"): 12,
    ("F", 3, "PVC"): 8, ("F", 2, "PVC"): 10, ("F", 3, "XLPE"): 11, ("F", 2, "XLPE"): 13,
}  # fmt: skip
#: Métodos que ofrece la herramienta (subcuadros de clima).
METODOS = {
    "E": "Bandeja perforada, cable multipolar (E)",
    "B2": "Tubo en superficie, cable multipolar (B2)",
    "C": "Sobre pared, cable multipolar (C)",
}


def intensidad_admisible(seccion: float, metodo: str, conductores: int, aislamiento="XLPE"):
    """Iz (A) de la tabla A, sin factores; None si la tabla no da valor."""
    columna = COLUMNA[(metodo, conductores, aislamiento)]
    return _TABLA_A[seccion][columna - 2]


#: GUÍA-BT-19, tabla E (A.52-3), capa única: (número de circuitos, factor). Para un número
#: que no está en la tabla se toma el del siguiente mayor (del lado de la seguridad); sin
#: más reducción por encima de 9.
AGRUPAMIENTO = {
    "bandeja": ((1, 1.00), (2, 0.90), (3, 0.80), (4, 0.75), (6, 0.75), (9, 0.70)),
    "pared": ((1, 1.00), (2, 0.85), (3, 0.80), (4, 0.75), (6, 0.70), (9, 0.70)),
}
REFERENCIA_AGRUPAMIENTO = {"E": "bandeja", "B2": "pared", "C": "pared"}


def factor_agrupamiento(metodo: str, circuitos: int) -> float:
    tabla = AGRUPAMIENTO[REFERENCIA_AGRUPAMIENTO[metodo]]
    for n, f in tabla:
        if circuitos <= n:
            return f
    return tabla[-1][1]


#: GUÍA-BT Anexo 2, tabla 3: conductividad del cobre (m/(Ω·mm²)) por temperatura.
CONDUCTIVIDAD_CU = {20: 56.0, 70: 48.0, 90: 44.0}
TEMPERATURA_SERVICIO = {"XLPE": 90, "PVC": 70}
#: GUÍA-BT Anexo 2, tabla 1: reactancia aproximada en fracción de R (0 hasta 120 mm²).
REACTANCIA = {150: 0.15, 185: 0.20, 240: 0.25, 300: 0.25}


def caida_tension_v(potencia_w, longitud_m, seccion, fases, cos_phi, aislamiento="XLPE"):
    """Caída de tensión (V): trifásica (R + X·tg φ)·P/U; monofásica, el doble (Anexo 2,
    fórmulas [4] a [7] y [15]–[16]). R = L/(γ·S)."""
    gamma = CONDUCTIVIDAD_CU[TEMPERATURA_SERVICIO[aislamiento]]
    r = longitud_m / (gamma * seccion)
    sen = (1 - cos_phi**2) ** 0.5
    x = REACTANCIA.get(seccion, 0.0) * r
    termino = (r + x * sen / cos_phi) * potencia_w
    if fases == 3:
        return termino / TENSION_TRIFASICA_V
    return 2 * termino / TENSION_MONOFASICA_V


#: ITC-BT-19 2.2.2: caída máxima en «demás usos» (el clima no es alumbrado).
CAIDA_MAXIMA = {"compania": 5.0, "ct": 6.5}
SUMINISTROS = {
    "compania": "BT de compañía (5 % en fuerza)",
    "ct": "Centro de transformación propio (6,5 % en fuerza)",
}
#: GUÍA-BT Anexo 2: factor de potencia a falta de datos.
COS_PHI_DEFECTO = 0.85
#: Calibres de interruptores automáticos (catálogo GE ElfaPlus; 160 A en caja moldeada).
CALIBRES = (6, 10, 13, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160)


def calibre(intensidad: float) -> int | None:
    """El menor calibre ≥ la intensidad (Ib ≤ In, GUÍA-BT-22)."""
    return next((c for c in CALIBRES if c >= intensidad - 1e-9), None)


def seccion_proteccion(seccion: float) -> float:
    """ITC-BT-19 tabla 2: S ≤ 16 → S; 16 < S ≤ 35 → 16; S > 35 → S/2 (normalizada)."""
    if seccion <= 16:
        return seccion
    if seccion <= 35:
        return 16
    return next(s for s in SECCIONES if s >= seccion / 2)


def diferencial(fases: int, calibre_a: int, variador: bool) -> tuple[int, str]:
    """(sensibilidad mA, tipo) según la ficha (GUÍA-BT-24)."""
    sensibilidad = 30 if fases == 1 and calibre_a <= 32 else 300
    tipo = ("B" if fases == 3 else "F") if variador else "A"
    return sensibilidad, tipo


#: Tensión límite convencional (GUÍA-BT-24): 50 V; 24 V en locales húmedos.
TENSION_LIMITE_V = 50.0
