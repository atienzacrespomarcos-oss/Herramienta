"""Zonas climáticas del CTE por provincia y altitud (GENERADO, no editar a mano).

Fuente: CTE DB HE (versión vigente en www.codigotecnico.org, consultada el
07-11-2026), Anejo B, tabla a-Anejo B «Zonas climáticas». Texto legal (Real Decreto):
se puede reproducir. Generado con scripts/extraer_zonas_cte.py.

Cada provincia: lista de (altitud mínima en m, zona); la zona vale desde esa altitud
hasta la siguiente.
"""

ZONAS: dict[str, tuple[tuple[int, str], ...]] = {
    "A Coruña": (
        (0, "C1"),
        (201, "D1"),
    ),
    "Albacete": (
        (0, "C3"),
        (451, "D3"),
        (951, "E1"),
    ),
    "Alicante/Alacant": (
        (0, "B4"),
        (251, "C3"),
        (701, "D3"),
    ),
    "Almería": (
        (0, "A4"),
        (101, "B4"),
        (251, "B3"),
        (401, "C3"),
        (801, "D3"),
    ),
    "Araba/Álava": (
        (0, "D1"),
        (601, "E1"),
    ),
    "Asturias": (
        (0, "C1"),
        (51, "D1"),
        (551, "E1"),
    ),
    "Badajoz": (
        (0, "C4"),
        (401, "C3"),
        (451, "D3"),
    ),
    "Barcelona": (
        (0, "C2"),
        (251, "D2"),
        (451, "D1"),
        (751, "E1"),
    ),
    "Bizkaia": (
        (0, "C1"),
        (251, "D1"),
    ),
    "Burgos": (
        (0, "D1"),
        (601, "E1"),
    ),
    "Cantabria": (
        (0, "C1"),
        (151, "D1"),
        (651, "E1"),
    ),
    "Castellón/Castelló": (
        (0, "B3"),
        (101, "C3"),
        (501, "D3"),
        (601, "D2"),
        (1001, "E1"),
    ),
    "Ceuta": ((0, "B3"),),
    "Ciudad Real": (
        (0, "C4"),
        (451, "C3"),
        (501, "D3"),
    ),
    "Cuenca": (
        (0, "D3"),
        (801, "D2"),
        (1051, "E1"),
    ),
    "Cáceres": (
        (0, "C4"),
        (601, "D3"),
        (1051, "E1"),
    ),
    "Cádiz": (
        (0, "A3"),
        (151, "B3"),
        (451, "C3"),
        (601, "C2"),
        (851, "D2"),
    ),
    "Córdoba": (
        (0, "B4"),
        (151, "C4"),
        (551, "D3"),
    ),
    "Gipuzkoa": (
        (0, "D1"),
        (401, "E1"),
    ),
    "Girona": (
        (0, "C2"),
        (101, "D2"),
        (601, "E1"),
    ),
    "Granada": (
        (0, "A4"),
        (51, "B4"),
        (351, "C4"),
        (601, "C3"),
        (801, "D3"),
        (1301, "E1"),
    ),
    "Guadalajara": (
        (0, "D3"),
        (951, "D2"),
        (1001, "E1"),
    ),
    "Huelva": (
        (0, "A4"),
        (51, "B4"),
        (151, "B3"),
        (351, "C3"),
        (801, "D3"),
    ),
    "Huesca": (
        (0, "C3"),
        (201, "D3"),
        (401, "D2"),
        (701, "E1"),
    ),
    "Illes Balears": (
        (0, "B3"),
        (251, "C3"),
    ),
    "Jaén": (
        (0, "B4"),
        (351, "C4"),
        (751, "D3"),
        (1251, "E1"),
    ),
    "La Rioja": (
        (0, "C2"),
        (201, "D2"),
        (701, "E1"),
    ),
    "Las Palmas": (
        (0, "α3"),
        (351, "A2"),
        (751, "B2"),
        (1001, "C2"),
    ),
    "León": ((0, "E1"),),
    "Lleida": (
        (0, "C3"),
        (101, "D3"),
        (601, "E1"),
    ),
    "Lugo": (
        (0, "D1"),
        (501, "E1"),
    ),
    "Madrid": (
        (0, "C3"),
        (501, "D3"),
        (951, "D2"),
        (1001, "E1"),
    ),
    "Melilla": ((0, "A3"),),
    "Murcia": (
        (0, "B3"),
        (101, "C3"),
        (551, "D3"),
    ),
    "Málaga": (
        (0, "A3"),
        (101, "B3"),
        (301, "C3"),
        (701, "D3"),
    ),
    "Navarra": (
        (0, "C2"),
        (101, "D2"),
        (351, "D1"),
        (601, "E1"),
    ),
    "Ourense": (
        (0, "C3"),
        (151, "C2"),
        (301, "D2"),
        (801, "E1"),
    ),
    "Palencia": (
        (0, "D1"),
        (801, "E1"),
    ),
    "Pontevedra": (
        (0, "C1"),
        (351, "D1"),
    ),
    "Salamanca": (
        (0, "D2"),
        (851, "E1"),
    ),
    "Santa Cruz de Tenerife": (
        (0, "α3"),
        (351, "A2"),
        (751, "B2"),
        (1001, "C2"),
    ),
    "Segovia": (
        (0, "D2"),
        (1051, "E1"),
    ),
    "Sevilla": (
        (0, "B4"),
        (201, "C4"),
    ),
    "Soria": (
        (0, "D2"),
        (751, "D1"),
        (801, "E1"),
    ),
    "Tarragona": (
        (0, "B3"),
        (101, "C3"),
        (501, "D3"),
    ),
    "Teruel": (
        (0, "C3"),
        (451, "C2"),
        (501, "D2"),
        (1001, "E1"),
    ),
    "Toledo": (
        (0, "C4"),
        (501, "D3"),
    ),
    "Valencia/València": (
        (0, "B3"),
        (51, "C3"),
        (501, "D2"),
        (951, "E1"),
    ),
    "Valladolid": (
        (0, "D2"),
        (801, "E1"),
    ),
    "Zamora": (
        (0, "D2"),
        (801, "E1"),
    ),
    "Zaragoza": (
        (0, "C3"),
        (201, "D3"),
        (651, "E1"),
    ),
    "Ávila": (
        (0, "D2"),
        (551, "D1"),
        (851, "E1"),
    ),
}
