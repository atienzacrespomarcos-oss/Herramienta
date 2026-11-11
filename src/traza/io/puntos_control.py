"""Listado de puntos de control del usuario (docs/modules/control.md, parte 2).

Usuario (11-11-2026): «en caso de que sí [exista el control], sacar esquemas si no hay (hay
el qué pero no el cómo)». El listado llega como lo tenga (Excel, .xls o CSV, sin plantilla):

- **Columnas por sus títulos**: señal (obligatoria), tipo (obligatoria), equipo, sistema y
  cantidad. Se busca la fila de títulos en las primeras filas de cada hoja; vale la
  primera hoja que tenga señal y tipo.
- **Tipo**: se aceptan las siglas españolas (ED, SD, EA, SA) y las inglesas habituales (DI,
  DO, AI, AO, y BI/BO de BACnet). Lo que no se entiende **no se adivina**: la fila no entra
  y se dice cuál es.
- Sin equipo, la señal va a «Sin equipo»; sin sistema, a «Listado»; sin cantidad, 1.
"""

from __future__ import annotations

from pathlib import Path

from traza.core.numeros import escribir_numero
from traza.engines.control import Punto
from traza.io import hoja_calculo
from traza.io.certificacion_excel import _tiene, normalizar

#: Títulos de columna por dato. Se recorren en orden y gana el primero que casa: lo
#: específico antes que lo general («tipo de señal» es el tipo, no la señal).
TITULOS = (
    ("tipo", ("tipo de senal", "tipo de punto", "tipo e/s", "tipo", "e/s", "i/o", "io")),
    ("cantidad", ("cantidad", "cant", "uds", "unidades", "n puntos", "numero")),
    ("sistema", ("sistema", "instalacion", "subsistema", "circuito")),
    ("equipo", ("equipo", "elemento", "aparato", "maquina")),
    ("senal", ("senal", "descripcion", "punto", "variable", "denominacion", "concepto")),
)
TIPOS = {
    "ED": "ED",
    "DI": "ED",
    "BI": "ED",
    "SD": "SD",
    "DO": "SD",
    "BO": "SD",
    "EA": "EA",
    "AI": "EA",
    "SA": "SA",
    "AO": "SA",
}
FILAS_TITULO = 15  # dónde se busca la fila de títulos


class ListadoNoLegible(ValueError):
    pass


def tipo_de(texto) -> str | None:
    t = normalizar(texto).upper().replace(" ", "").replace("-", "").replace("/", "")
    return TIPOS.get(t)


def _rol(titulo: str) -> str | None:
    t = normalizar(titulo)
    if not t:
        return None
    for rol, terminos in TITULOS:
        if _tiene(t, terminos):
            return rol
    return None


def _mapa(ws) -> tuple[int, dict[str, int]] | None:
    for fila in range(1, min(ws.max_row, FILAS_TITULO) + 1):
        roles: dict[str, int] = {}
        for col in range(1, ws.max_column + 1):
            rol = _rol(ws.cell(fila, col).value)
            if rol is not None and rol not in roles:
                roles[rol] = col
        if "senal" in roles and "tipo" in roles:
            return fila, roles
    return None


def leer(ruta: Path) -> tuple[list[Punto], list[str]]:
    """Puntos del listado y avisos (filas que no entran, con el motivo)."""
    ruta = Path(ruta)
    valores, formulas = hoja_calculo.abrir(ruta)
    try:
        for ws in valores.worksheets:
            m = _mapa(ws)
            if m is None:
                continue
            fila_titulos, roles = m
            return _filas(ws, fila_titulos, roles)
    finally:
        valores.close()
        if formulas is not valores:
            formulas.close()
    raise ListadoNoLegible(
        f"«{ruta.name}»: no se encuentra una fila de títulos con la señal (o descripción) y "
        "su tipo (ED, SD, EA, SA o DI, DO, AI, AO)."
    )


def _filas(ws, fila_titulos: int, roles: dict[str, int]) -> tuple[list[Punto], list[str]]:
    puntos: list[Punto] = []
    avisos: list[str] = []

    def celda(fila, rol):
        col = roles.get(rol)
        v = ws.cell(fila, col).value if col else None
        return "" if v is None else str(v).strip()

    for fila in range(fila_titulos + 1, ws.max_row + 1):
        senal = celda(fila, "senal")
        texto_tipo = celda(fila, "tipo")
        if not senal and not texto_tipo:
            continue  # fila vacía o de separación
        tipo = tipo_de(texto_tipo)
        if not senal or tipo is None:
            avisos.append(
                f"Fila {fila}: "
                + ("sin señal" if not senal else f"tipo «{texto_tipo}» no reconocido")
                + "; no entra en el esquema."
            )
            continue
        cantidad = 1
        if "cantidad" in roles:
            v = ws.cell(fila, roles["cantidad"]).value
            if v not in (None, ""):
                if isinstance(v, bool) or not isinstance(v, int | float) or v < 1 or v != int(v):
                    texto = escribir_numero(v) if isinstance(v, int | float) else v
                    avisos.append(f"Fila {fila}: cantidad «{texto}» no es un entero ≥ 1; no entra.")
                    continue
                cantidad = int(v)
        puntos.append(
            Punto(
                celda(fila, "sistema") or "Listado",
                celda(fila, "equipo") or "Sin equipo",
                senal,
                tipo,
                cantidad,
                f"Listado del usuario, fila {fila}",
            )
        )
    if not puntos:
        raise ListadoNoLegible(
            "El listado no tiene ningún punto con señal y tipo reconocido."
            + (" " + " ".join(avisos[:5]) if avisos else "")
        )
    return puntos, avisos
