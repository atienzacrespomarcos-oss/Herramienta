"""Cerramientos típicos por tipo de construcción (decisión del usuario, 07-11-2026: «Nunca
me dan esos datos. Presupón los típicos dependiendo del tipo de construcción»).

Todo lo de aquí entra en el modelo como HIPÓTESIS con su fuente; el usuario lo cambia por
espacio o por cerramiento. Fuentes (detalle y elección en docs/modules/cargas.md):

- CTE DB HE (2019), tabla 3.1.1.a-HE1: transmitancias límite por zona de invierno.
- CTE, Catálogo de Elementos Constructivos (CEC, v06.3, marzo 2010), codigotecnico.org:
  - 3.15.2 acristalamientos incoloros (U del vidrio vertical/horizontal y g⊥);
  - 3.16 marcos (U del marco vertical/horizontal);
  - 4.2.11 fachada de panel sándwich: U = 1/(0,17 + R del panel);
  - 4.3.1.1 huecos: U y factor solar modificado según la fracción de marco (20–40 %,
    se interpola linealmente).
- UNE-EN ISO 6946: Rsi 0,13 (horizontal), 0,10 (hacia arriba), 0,17 (hacia abajo); Rse
  0,04 m²K/W.
- UNE-EN ISO 13370: solera sobre el terreno (método de la dimensión característica B').
- Espesores habituales del panel sándwich: catálogos de Novacero (cubierta 25–50 mm,
  fachada 40–50 mm) y Obramat (cubierta de 30 mm).
- Edificio existente anterior a la NBE-CT-79: TFM Universidad de Zaragoza (2021), tabla de
  transmitancias típicas sin aislamiento.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from traza.rules.zonas_cte import ZONAS

URL_CEC = "https://www.codigotecnico.org/pdf/Programas/CEC/CAT-EC-v06.3_marzo_10.pdf"
URL_DBHE = "https://www.codigotecnico.org/pdf/Documentos/HE/DBHE.pdf"
URL_TFM_UNIZAR = "https://zaguan.unizar.es/record/112232/files/TAZ-TFM-2021-1559_ANE.pdf"
URL_NOVACERO = "https://www.novacero.com/wp-content/uploads/2025/09/Catalogo_Paneles_Inyectados.pdf"

# UNE-EN ISO 6946, resistencias superficiales (m²K/W).
RSI_HORIZONTAL = 0.13
RSI_ARRIBA = 0.10
RSI_ABAJO = 0.17
RSE = 0.04

#: λ del alma de poliuretano del panel sándwich (W/mK): ficha de Deformac (EN 14509). El
#: CEC da 0,022–0,037; se toma el valor del fabricante español.
LAMBDA_PUR = 0.024

#: CTE DB HE, tabla 3.1.1.a-HE1, por zona de invierno (W/m²K).
LETRAS_INVIERNO = ("α", "A", "B", "C", "D", "E")
ULIM = {
    "muro": dict(zip(LETRAS_INVIERNO, (0.80, 0.70, 0.56, 0.49, 0.41, 0.37), strict=True)),
    "cubierta": dict(zip(LETRAS_INVIERNO, (0.55, 0.50, 0.44, 0.40, 0.35, 0.33), strict=True)),
    "terreno": dict(zip(LETRAS_INVIERNO, (0.90, 0.80, 0.75, 0.70, 0.65, 0.59), strict=True)),
    "hueco": dict(zip(LETRAS_INVIERNO, (3.2, 2.7, 2.3, 2.1, 1.8, 1.8), strict=True)),
}

#: Nombres de provincia de la guía del IDAE → nombres del CTE (Anejo B).
ALIAS_PROVINCIA = {
    "Alicante": "Alicante/Alacant",
    "Baleares": "Illes Balears",
    "Castellón": "Castellón/Castelló",
    "Guipúzcoa": "Gipuzkoa",
    "S.C. Tenerife": "Santa Cruz de Tenerife",
    "Valencia": "Valencia/València",
    "Vizcaya": "Bizkaia",
    "Álava": "Araba/Álava",
}


def zona_climatica(provincia: str, altitud_m: float) -> str:
    """Zona climática del CTE (p. ej. «D3») por provincia y altitud (DB HE, Anejo B)."""
    nombre = ALIAS_PROVINCIA.get(provincia, provincia)
    if nombre not in ZONAS:
        raise KeyError(f"Provincia no reconocida en el CTE: «{provincia}».")
    zona = ZONAS[nombre][0][1]
    for desde, z in ZONAS[nombre]:
        # Las columnas de la tabla son de metros enteros («≤ 200», «201–250»…).
        if altitud_m > desde - 1:
            zona = z
    return zona


def letra_invierno(zona: str) -> str:
    return zona[:-1]


@dataclass(frozen=True)
class Vidrio:
    clave: str
    nombre: str
    u_vertical: float
    u_horizontal: float
    g: float


@dataclass(frozen=True)
class Marco:
    clave: str
    nombre: str
    u_vertical: float
    u_horizontal: float


_CEC_V = "CTE, Catálogo de Elementos Constructivos, 3.15.2"
_CEC_M = "CTE, Catálogo de Elementos Constructivos, 3.16"

#: CEC 3.15.2: vidrio sencillo de 4 mm y dobles 4-12-4 (normal y de baja emisividad
#: 0,1 ≥ ε > 0,03).
VIDRIOS = {
    v.clave: v
    for v in (
        Vidrio("sencillo", "Vidrio sencillo 4 mm", 5.7, 6.9, 0.85),
        Vidrio("doble", "Doble acristalamiento 4-12-4", 2.8, 3.4, 0.76),
        Vidrio("doble_be", "Doble bajo emisivo 4-12-4", 1.8, 2.4, 0.63),
    )
}
MARCOS = {
    m.clave: m
    for m in (
        Marco("metalico", "Metálico sin rotura de puente térmico", 5.7, 7.2),
        Marco("rpt_4_12", "Metálico con rotura de puente térmico 4–12 mm", 4.0, 4.5),
        Marco("rpt_12", "Metálico con rotura de puente térmico > 12 mm", 3.2, 3.5),
        Marco("madera", "Madera (700 kg/m³)", 2.2, 2.4),
        Marco("pvc2", "PVC de dos cámaras", 2.2, 2.4),
        Marco("pvc3", "PVC de tres cámaras", 1.8, 1.9),
    )
}

#: Fracción de marco por defecto: el CEC tabula 20 % y 40 % e interpola entre ellos; se
#: toma el punto medio.
FRACCION_MARCO = 0.30
#: Absortividad del marco: la de los valores tabulados del CEC (marco oscuro).
ABSORTIVIDAD_MARCO = 0.8


@dataclass(frozen=True)
class Hueco:
    u: float  # W/m²K del conjunto
    factor_solar: float  # factor solar modificado sin sombras (F_H)
    fuente: str


def hueco(
    vidrio: str,
    marco: str,
    fraccion_marco: float = FRACCION_MARCO,
    horizontal: bool = False,
    absortividad: float = ABSORTIVIDAD_MARCO,
) -> Hueco:
    """U y factor solar de un hueco por ponderación de vidrio y marco.

    U_H = (1 − FM)·U_v + FM·U_m
    F_H = (1 − FM)·g⊥ + FM·0,04·U_m·α
    Es como están calculadas las tablas 4.3.1.1 del CEC (comprobado contra sus valores en
    tests/unit/test_cerramientos.py).
    """
    if not 0 <= fraccion_marco <= 1:
        raise ValueError("La fracción de marco va de 0 a 1.")
    v, m = VIDRIOS[vidrio], MARCOS[marco]
    uv = v.u_horizontal if horizontal else v.u_vertical
    um = m.u_horizontal if horizontal else m.u_vertical
    fm = fraccion_marco
    return Hueco(
        (1 - fm) * uv + fm * um,
        (1 - fm) * v.g + fm * 0.04 * um * absortividad,
        f"{_CEC_V} ({v.nombre}) y {_CEC_M} ({m.nombre}), marco {fm:.0%}",
    )


def u_panel_sandwich(espesor_mm: float, cubierta: bool = False) -> float:
    """Panel sándwich de poliuretano: U = 1/(Rsi + e/λ + Rse) (CEC 4.2.11, ISO 6946).

    En cubierta se toma Rsi hacia arriba (invierno, la condición de más pérdidas)."""
    if espesor_mm <= 0:
        raise ValueError("El espesor del panel tiene que ser positivo.")
    rsi = RSI_ARRIBA if cubierta else RSI_HORIZONTAL
    return 1.0 / (rsi + espesor_mm / 1000.0 / LAMBDA_PUR + RSE)


#: UNE-EN ISO 13370: conductividad del terreno cuando no se conoce (arcilla o limo).
LAMBDA_TERRENO = 2.0


def u_solera(area_m2: float, perimetro_m: float, muro_m: float = 0.3, r_suelo: float = 0.0):
    """Solera sobre el terreno, UNE-EN ISO 13370 (dimensión característica B').

    B' = A/(0,5·P); dt = w + λ·(Rsi + Rf + Rse)
    dt < B' (solera sin aislar o poco aislada): U = 2λ/(πB' + dt)·ln(πB'/dt + 1)
    dt ≥ B' (bien aislada): U = λ/(0,457·B' + dt)
    """
    if area_m2 <= 0 or perimetro_m <= 0:
        raise ValueError("La solera necesita superficie y perímetro expuesto.")
    b = area_m2 / (0.5 * perimetro_m)
    dt = muro_m + LAMBDA_TERRENO * (RSI_ABAJO + r_suelo + RSE)
    if dt < b:
        return 2 * LAMBDA_TERRENO / (math.pi * b + dt) * math.log(math.pi * b / dt + 1)
    return LAMBDA_TERRENO / (0.457 * b + dt)


@dataclass(frozen=True)
class Envolvente:
    """Transmitancias típicas de un tipo de construcción (W/m²K) y su procedencia."""

    tipo: str
    u_muro: float
    u_cubierta: float
    u_terreno: float | None  # None: solera por ISO 13370 con la geometría del espacio
    hueco: Hueco
    fuente: str


TIPOS = {
    "cte": "Edificio nuevo según CTE (2019)",
    "nave_panel": "Nave de panel sándwich",
    "nave_chapa": "Nave de chapa sin aislar",
    "existente_sin_aislar": "Edificio anterior a 1980, sin aislamiento",
}

#: Espesores típicos del panel (mm): catálogos de Novacero y Obramat.
ESPESOR_PANEL_FACHADA = 40.0
ESPESOR_PANEL_CUBIERTA = 30.0


def envolvente(tipo: str, zona: str) -> Envolvente:
    """Cerramientos típicos de un tipo de construcción en una zona climática del CTE."""
    letra = letra_invierno(zona)
    if letra not in LETRAS_INVIERNO:
        raise ValueError(f"Zona climática no prevista: «{zona}».")
    if tipo == "cte":
        h = hueco("doble_be", "rpt_12")
        u_h = ULIM["hueco"][letra]
        return Envolvente(
            tipo,
            ULIM["muro"][letra],
            ULIM["cubierta"][letra],
            ULIM["terreno"][letra],
            Hueco(u_h, h.factor_solar, f"CTE DB HE tabla 3.1.1.a-HE1 (U); {h.fuente} (F)"),
            f"CTE DB HE, tabla 3.1.1.a-HE1, zona {zona}: el máximo permitido",
        )
    if tipo == "nave_panel":
        return Envolvente(
            tipo,
            u_panel_sandwich(ESPESOR_PANEL_FACHADA),
            u_panel_sandwich(ESPESOR_PANEL_CUBIERTA, cubierta=True),
            None,
            hueco("doble", "rpt_4_12"),
            f"Panel sándwich de poliuretano (λ {LAMBDA_PUR}), fachada "
            f"{ESPESOR_PANEL_FACHADA:.0f} mm y cubierta {ESPESOR_PANEL_CUBIERTA:.0f} mm "
            "(espesores habituales de catálogo); CEC 4.2.11 e ISO 6946",
        )
    if tipo == "nave_chapa":
        return Envolvente(
            tipo,
            1.0 / (RSI_HORIZONTAL + RSE),
            1.0 / (RSI_ARRIBA + RSE),
            None,
            hueco("sencillo", "metalico"),
            "Chapa sin aislar: solo resistencias superficiales (UNE-EN ISO 6946)",
        )
    if tipo == "existente_sin_aislar":
        return Envolvente(
            tipo,
            2.5,
            2.5,
            None,
            hueco("sencillo", "metalico"),
            "Edificio anterior a la NBE-CT-79 sin aislamiento: TFM Universidad de Zaragoza "
            "(2021), tabla de transmitancias típicas",
        )
    raise ValueError(f"Tipo de construcción no previsto: «{tipo}».")
