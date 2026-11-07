"""Extrae la tabla a-Anejo B (zonas climáticas) del CTE DB HE (versión vigente descargada de
www.codigotecnico.org) a `src/traza/rules/zonas_cte.py`.

Uso: uv run python scripts/extraer_zonas_cte.py ruta/DBHE.pdf

Cada fila es una provincia; cada zona empieza en la columna de su rango de altitud y llega
hasta la siguiente zona. Las columnas se identifican por el límite inferior de su rango.
"""

import sys

import pymupdf

# Límite inferior (m) de cada columna de la tabla, por su índice en la extracción.
COLUMNAS = {
    1: 0,
    3: 51,
    4: 101,
    5: 151,
    7: 201,
    9: 251,
    11: 301,
    12: 351,
    14: 401,
    16: 451,
    18: 501,
    20: 551,
    21: 601,
    22: 651,
    23: 701,
    25: 751,
    27: 801,
    29: 851,
    30: 901,
    32: 951,
    34: 1001,
    35: 1051,
    36: 1251,
    38: 1301,
}


def extraer(ruta: str) -> dict[str, list[tuple[int, str]]]:
    doc = pymupdf.open(ruta)
    pagina = next(p for p in doc if "Tabla a-Anejo B" in p.get_text())
    filas = pagina.find_tables().tables[0].extract()
    zonas: dict[str, list[tuple[int, str]]] = {}
    for fila in filas:
        provincia = (fila[0] or "").strip()
        if not provincia or provincia == "Provincia":
            continue
        tramos = []
        for j, celda in enumerate(fila[1:], start=1):
            celda = (celda or "").strip()
            if celda:
                if j not in COLUMNAS:
                    raise SystemExit(
                        f"{provincia}: zona «{celda}» en una columna no prevista ({j})"
                    )
                tramos.append((COLUMNAS[j], celda))
        if tramos:
            zonas[" ".join(provincia.split())] = tramos
    return zonas


# Nombres tal como salen del PDF (con espacios y comas de las celdas) → nombre normal.
NOMBRES = {
    "Á vila": "Ávila",
    "Balears Illes ,": "Illes Balears",
    "CiudadReal": "Ciudad Real",
    "Coruña A ,": "A Coruña",
    "Palmas Las ,": "Las Palmas",
    "Rioja La ,": "La Rioja",
    "SantaCruzdeTenerife": "Santa Cruz de Tenerife",
}


def generar(ruta_pdf: str, destino: str) -> None:
    z = {NOMBRES.get(k, k): v for k, v in extraer(ruta_pdf).items()}
    lineas = [
        '"""Zonas climáticas del CTE por provincia y altitud (GENERADO, no editar a mano).',
        "",
        "Fuente: CTE DB HE (versión vigente en www.codigotecnico.org, consultada el",
        "07-11-2026), Anejo B, tabla a-Anejo B «Zonas climáticas». Texto legal (Real Decreto):",
        "se puede reproducir. Generado con scripts/extraer_zonas_cte.py.",
        "",
        "Cada provincia: lista de (altitud mínima en m, zona); la zona vale desde esa altitud",
        "hasta la siguiente.",
        '"""',
        "",
        "ZONAS: dict[str, tuple[tuple[int, str], ...]] = {",
    ]
    for k in sorted(z):
        tramos = ", ".join(f"({a}, {zona!r})" for a, zona in z[k])
        lineas.append(f"    {k!r}: ({tramos},),")
    lineas.append("}")
    with open(destino, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")


if __name__ == "__main__":
    generar(sys.argv[1], "src/traza/rules/zonas_cte.py")
