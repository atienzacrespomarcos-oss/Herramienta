"""Condiciones climáticas exteriores de proyecto: lectura de la guía técnica del IDAE.

Fuente: IDAE, «Guía técnica. Condiciones climáticas exteriores de proyecto» (serie Ahorro y
Eficiencia Energética en Climatización, junio de 2010, redactada por ATECYR con datos de
AEMET), documento reconocido del RITE. Se descarga gratis de www.idae.es (`URL_GUIA`).

La guía prohíbe reproducir sus datos, y el repositorio de TRAZA es público: por eso aquí no
hay ni una cifra de la guía. TRAZA lee el PDF que el usuario tiene (o descarga) en su equipo,
lo incorpora al proyecto como documento y cita cada valor con su página.

Cada estación ocupa una página con este orden (sección 4 «Datos recogidos» de la guía):
- Provincia, estación, indicativo; altitud, latitud y longitud.
- Calefacción: TSMIN, TS 99,6 %, TS 99 %, OMDC, HUMcoin, OMA.
- Refrigeración por temperatura seca: TSMAX, TS 0,4 %, THC 0,4 %, TS 1 %, THC 1 %, TS 2 %,
  THC 2 %, OMDR.
- Refrigeración por temperatura húmeda: TH 0,4 %, TSC 0,4 %, TH 1 %, TSC 1 %, TH 2 %, TSC 2 %.
Números con coma decimal; el símbolo de grado sale como «O» en el texto del PDF.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from pathlib import Path

URL_GUIA = (
    "https://www.idae.es/uploads/documentos/"
    "documentos_12_Guia_tecnica_condiciones_climaticas_exteriores_de_proyecto_e4e5b769.pdf"
)
TITULO_GUIA = "IDAE, Guía técnica «Condiciones climáticas exteriores de proyecto» (2010)"


class GuiaNoReconocida(RuntimeError):
    pass


@dataclass(frozen=True)
class EstacionIdae:
    provincia: str
    nombre: str
    indicativo: str
    pagina: int  # página del PDF (para citarla)
    altitud_m: float
    latitud: float  # grados, norte positivo
    longitud: float  # grados, este positivo (oeste negativo)
    # Calefacción (°C, salvo HUMcoin en %)
    ts_min: float
    ts_996: float
    ts_99: float
    omdc: float
    hum_coin: float
    oma: float
    # Refrigeración por temperatura seca (°C)
    ts_max: float
    ts_04: float
    thc_04: float
    ts_1: float
    thc_1: float
    ts_2: float
    thc_2: float
    omdr: float
    # Refrigeración por temperatura húmeda (°C)
    th_04: float
    tsc_04: float | None
    th_1: float
    tsc_1: float | None
    th_2: float
    tsc_2: float | None

    @property
    def etiqueta(self) -> str:
        return f"{self.nombre} ({self.provincia})"


_NUMERO = re.compile(r"^[-–−]?\d{1,3}(?:\.\d{3})*(?:,\d+)?$|^[-–−]?\d+(?:,\d+)?$")
_CABECERA = re.compile(
    r"Provincia\s*\nEstación\s*\nIndicativo\s*\n(?P<p>[^\n]+)\n(?P<e>[^\n]+)\n(?P<i>[^\n]+)\n"
)
_GRADOS = re.compile(r"(?P<g>\d{1,3})\s*\n\s*O\s*(?P<m>\d{1,2})’(?P<s>\d{1,2})’’\s*(?P<h>[WE])?")

# Bloques: etiqueta que los precede y número de valores.
_BLOQUES = (
    ("OMA (\nOC)\n", 6),
    ("OMDR (\nOC)\n", 8),
    ("TSC_2 (\nOC)\n", 6),
)


def _numero(t: str) -> float:
    t = t.strip().replace("–", "-").replace("−", "-")
    return float(t.replace(".", "").replace(",", ".")) if "," in t else float(t.replace(".", ""))


def _valores(texto: str, desde: int, n: int) -> list[float]:
    """Los números que siguen a una etiqueta, hasta `n` o hasta el primer texto."""
    salida = []
    for linea in texto[desde:].splitlines():
        linea = linea.strip()
        if not linea:
            continue
        if not _NUMERO.match(linea):
            break
        salida.append(_numero(linea))
        if len(salida) == n:
            break
    return salida


def _coordenadas(texto: str) -> tuple[float, float, float]:
    """(altitud, latitud, longitud) del bloque de ubicación: tras «Rad» van la altitud y
    las dos coordenadas en grados, minutos y segundos."""
    i = texto.find("\nRad\n")
    if i < 0:
        raise GuiaNoReconocida("No se encuentra la ubicación de la estación.")
    resto = texto[i + 5 :]
    altitud = _numero(resto.splitlines()[0])
    coords = list(_GRADOS.finditer(resto))
    if len(coords) < 2:
        raise GuiaNoReconocida("No se encuentran latitud y longitud.")

    def grados(m: re.Match) -> float:
        return int(m["g"]) + int(m["m"]) / 60 + int(m["s"]) / 3600

    latitud = grados(coords[0])
    longitud = grados(coords[1]) * (-1 if (coords[1]["h"] or "W") == "W" else 1)
    return altitud, latitud, longitud


def leer_pagina(texto: str, pagina: int) -> EstacionIdae | None:
    """Una estación de una página de texto de la guía, o None si la página no es de
    estación (índice, introducción, anexos)."""
    cab = _CABECERA.search(texto)
    if cab is None or "Condiciones proyecto calefacción" not in texto:
        return None
    altitud, latitud, longitud = _coordenadas(texto)
    valores: list[float | None] = []
    for etiqueta, n in _BLOQUES:
        i = texto.find(etiqueta)
        if i < 0:
            raise GuiaNoReconocida(f"Página {pagina}: falta el bloque «{etiqueta.split()[0]}».")
        leidos: list[float | None] = list(_valores(texto, i + len(etiqueta), n))
        if etiqueta.startswith("TSC_2") and len(leidos) == 3:
            # Alguna estación da solo TH 0,4/1/2 % (sin la seca coincidente, p. ej. la de la
            # página 25): la seca coincidente no consta en la guía.
            leidos = [leidos[0], None, leidos[1], None, leidos[2], None]
        if len(leidos) != n:
            raise GuiaNoReconocida(
                f"Página {pagina}: el bloque «{etiqueta.split()[0]}» tiene {len(leidos)} "
                f"valores y se esperaban {n}."
            )
        valores += leidos
    return EstacionIdae(
        cab["p"].strip(),
        cab["e"].strip(),
        cab["i"].strip(),
        pagina,
        altitud,
        latitud,
        longitud,
        *valores,
    )


def leer_guia(ruta: Path) -> list[EstacionIdae]:
    """Todas las estaciones de la guía. Si el PDF no es la guía (o es otra edición con otro
    formato), se dice en lugar de devolver datos a medias."""
    import pymupdf

    try:
        doc = pymupdf.open(ruta)
    except Exception as exc:  # noqa: BLE001
        raise GuiaNoReconocida(f"No se puede abrir el PDF: {exc}") from exc
    try:
        estaciones = []
        for n, pagina in enumerate(doc, start=1):
            e = leer_pagina(pagina.get_text(), n)
            if e is not None:
                estaciones.append(e)
    finally:
        doc.close()
    if not estaciones:
        raise GuiaNoReconocida(
            "El PDF no tiene fichas de estación con el formato de la guía del IDAE."
        )
    return estaciones


CAMPOS = tuple(f.name for f in fields(EstacionIdae))
