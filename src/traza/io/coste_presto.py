"""Coste objetivo de una obra: el Excel que el usuario exporta de Presto y reparte en
paquetes (docs/modules/obra.md, «Coste objetivo»).

Usuario (09-11-2026): «Viene del Presto. Exporto a Excel mi coste objetivo, y luego agrupo
por partidas (esto lo seguiré haciendo yo…)». TRAZA lo lee tal cual, sin reagrupar.

Estructura (vista en su comparativo, una hoja):
- Fila de títulos con `Código`, `Nat`, `Ud`, `Resumen` y grupos de tres columnas
  `CanObj · PrObj · ImpObj`. Encima, el nombre de cada grupo: el primero es el OBJETIVO;
  los demás, los **paquetes** de coste (proveedor o subcontrata).
- Filas `Capítulo`, `Partida` (con su objetivo y su reparto por paquetes) y, debajo, sus
  recursos (Material, Mano de obra, Otros) y una fila de cierre.
- Líneas añadidas a mano fuera de Presto (sin código ni naturaleza, con un precio escrito,
  no calculado): cuentan como coste objetivo.
- En una celda de precio puede haber un texto («NO INCLUIDO …»): se guarda como nota.

Se leen los valores que Excel guardó (las fórmulas, por su resultado) y, aparte, las
fórmulas, para distinguir una línea escrita a mano de un total calculado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

LECTOR = "coste_presto"
VERSION = "1.0.0"

#: Un céntimo: tolerancia para comparar el reparto en paquetes con el objetivo.
CENTIMO = 0.01


class CosteNoReconocido(ValueError):
    pass


@dataclass(frozen=True)
class PartidaCoste:
    codigo: str  # «» en una línea añadida a mano fuera de Presto
    resumen: str
    unidad: str
    capitulo: str  # «código resumen» del capítulo en que está
    cantidad: float | None
    precio: float | None
    importe: float  # objetivo
    paquetes: dict[str, float]  # paquete → importe de su reparto
    nota: str = ""  # texto en lugar de precio («NO INCLUIDO …»)
    fila: int = 0  # en el Excel, para citarla

    @property
    def sin_repartir(self) -> float:
        """Objetivo que no está en ningún paquete (recursos sin asignar)."""
        return self.importe - sum(self.paquetes.values())


@dataclass
class CosteObjetivo:
    hoja: str
    paquetes: list[str]
    partidas: list[PartidaCoste] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return sum(p.importe for p in self.partidas)

    def por_paquete(self) -> dict[str, float]:
        totales = dict.fromkeys(self.paquetes, 0.0)
        for p in self.partidas:
            for nombre, importe in p.paquetes.items():
                totales[nombre] += importe
        return totales


def _texto(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _numero(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int | float):
        return float(v)
    return None


def _es_formula(v: Any) -> bool:
    return isinstance(v, str) and v.startswith("=")


def _cabecera(ws) -> tuple[int, dict[str, int], list[tuple[str, int, int, int]]]:
    """Fila de títulos, columnas fijas y grupos (nombre, col Can, col Pr, col Imp)."""
    for r in range(1, min(ws.max_row, 30) + 1):
        valores = {c: _texto(ws.cell(r, c).value) for c in range(1, ws.max_column + 1)}
        if {"Código", "Nat", "Resumen"} <= set(valores.values()):
            fijas = {v: c for c, v in valores.items() if v in ("Código", "Nat", "Ud", "Resumen")}
            grupos = []
            c = 1
            while c <= ws.max_column - 2:
                trio = (valores[c], valores.get(c + 1), valores.get(c + 2))
                if trio == ("CanObj", "PrObj", "ImpObj"):
                    nombre = ""
                    for fila in range(r - 1, 0, -1):  # el nombre, encima de cualquiera de las 3
                        nombre = next(
                            (_texto(ws.cell(fila, k).value) for k in (c, c + 1, c + 2)
                             if _texto(ws.cell(fila, k).value)),
                            "",
                        )  # fmt: skip
                        if nombre:
                            break
                    grupos.append((nombre, c, c + 1, c + 2))
                    c += 3
                else:
                    c += 1
            return r, fijas, grupos
    raise CosteNoReconocido(
        "No es el comparativo de costes de Presto: no hay una fila con «Código», «Nat» y «Resumen»."
    )


def leer(ruta: Path) -> CosteObjetivo:
    ruta = Path(ruta)
    try:
        wb_v = load_workbook(ruta, data_only=True, read_only=False)
        wb_f = load_workbook(ruta, data_only=False, read_only=False)
    except Exception as exc:  # noqa: BLE001 — cualquier fallo de apertura se explica igual
        raise CosteNoReconocido(f"No se puede abrir «{ruta.name}» como Excel: {exc}") from exc
    errores = []
    for nombre in wb_v.sheetnames:
        try:
            return _leer_hoja(wb_v[nombre], wb_f[nombre])
        except CosteNoReconocido as exc:
            errores.append(str(exc))
    raise CosteNoReconocido(errores[0] if errores else "El Excel no tiene hojas.")


def _leer_hoja(wv, wf) -> CosteObjetivo:
    fila0, fijas, grupos = _cabecera(wf)
    if len(grupos) < 1:
        raise CosteNoReconocido("No hay columnas «CanObj · PrObj · ImpObj» de objetivo.")
    objetivo, *paquetes = grupos
    nombres = [g[0] or f"Paquete {i}" for i, g in enumerate(paquetes, start=1)]
    if len(set(nombres)) != len(nombres):
        raise CosteNoReconocido("Hay dos paquetes con el mismo nombre en la fila de títulos.")
    r = CosteObjetivo(wv.title, nombres)
    c_cod, c_nat = fijas["Código"], fijas["Nat"]
    c_ud, c_res = fijas.get("Ud"), fijas["Resumen"]
    capitulo = ""
    sin_valor = 0
    for fila in range(fila0 + 1, wv.max_row + 1):
        codigo = _texto(wv.cell(fila, c_cod).value)
        nat = _texto(wv.cell(fila, c_nat).value)
        resumen = _texto(wv.cell(fila, c_res).value)
        if nat == "Capítulo":
            capitulo = f"{codigo} {resumen}".strip()
            continue
        # Línea añadida a mano: sin código ni naturaleza y con el PRECIO escrito (el
        # importe puede ser una fórmula Can × Pr). Las filas de cierre y de total tienen
        # el precio calculado (suma de recursos o de partidas).
        manual = (
            not codigo
            and not nat
            and resumen
            and _numero(wf.cell(fila, objetivo[2]).value) is not None
        )
        if nat != "Partida" and not manual:
            continue
        importe = _numero(wv.cell(fila, objetivo[3]).value)
        if importe is None:
            if _es_formula(wf.cell(fila, objetivo[3]).value):
                sin_valor += 1
            importe = 0.0
        precio_bruto = wv.cell(fila, objetivo[2]).value
        nota = precio_bruto.strip() if isinstance(precio_bruto, str) else ""
        reparto: dict[str, float] = {}
        for nombre, (_n, _c, _p, c_imp) in zip(nombres, paquetes, strict=True):
            v = _numero(wv.cell(fila, c_imp).value)
            if v:
                reparto[nombre] = v
        r.partidas.append(
            PartidaCoste(
                codigo=codigo,
                resumen=resumen,
                unidad=_texto(wv.cell(fila, c_ud).value) if c_ud else "",
                capitulo=capitulo if not manual else "Añadido fuera de Presto",
                cantidad=_numero(wv.cell(fila, objetivo[1]).value),
                precio=_numero(precio_bruto),
                importe=importe,
                paquetes=reparto,
                nota=nota,
                fila=fila,
            )
        )
    if not r.partidas:
        raise CosteNoReconocido("La hoja no tiene ninguna partida («Nat» = Partida).")
    if sin_valor:
        r.avisos.append(
            f"{sin_valor} partida(s) con fórmula sin resultado guardado: abre el Excel en "
            "Excel y guárdalo para que se lean sus importes."
        )
    for p in r.partidas:
        if abs(p.sin_repartir) > CENTIMO:
            r.avisos.append(
                f"{p.codigo or p.resumen} (fila {p.fila}): {p.sin_repartir:.2f} € del objetivo "
                "sin repartir en paquetes."
            )
    return r
