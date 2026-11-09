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


def _es_nombre(v: Any) -> bool:
    """El nombre de un grupo es un texto: no un número ni una fórmula (un total escrito
    encima de una columna no puede pasar por el nombre del paquete)."""
    if not isinstance(v, str) or not v.strip() or _es_formula(v):
        return False
    try:
        float(v.replace(",", "."))
    except ValueError:
        return True
    return False


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
                            (ws.cell(fila, k).value.strip() for k in (c, c + 1, c + 2)
                             if _es_nombre(ws.cell(fila, k).value)),
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
    repetidos = sorted({n for n in nombres if nombres.count(n) > 1})
    if repetidos:
        raise CosteNoReconocido(
            f"El paquete «{repetidos[0]}» está dos veces en la fila de títulos: cambia el "
            "nombre de uno."
        )
    r = CosteObjetivo(wv.title, nombres)
    sin_nombre = [n for n, g in zip(nombres, paquetes, strict=True) if not g[0]]
    if sin_nombre:
        r.avisos.append(f"Grupos de columnas sin nombre encima: se llaman {', '.join(sin_nombre)}.")
    c_cod, c_nat = fijas["Código"], fijas["Nat"]
    c_ud, c_res = fijas.get("Ud"), fijas["Resumen"]
    capitulo = ""
    sin_valor: list[int] = []
    con_error: list[int] = []
    vistos: dict[str, int] = {}  # código de partida o capítulo → primera fila
    total_excel: tuple[int, float] | None = None
    for fila in range(fila0 + 1, wv.max_row + 1):
        codigo = _texto(wv.cell(fila, c_cod).value)
        nat = _texto(wv.cell(fila, c_nat).value)
        resumen = _texto(wv.cell(fila, c_res).value)
        imp_v = wv.cell(fila, objetivo[3]).value
        es_total = not nat and not codigo and resumen.upper().startswith("TOTAL")
        if es_total and _numero(imp_v) is not None:
            total_excel = (fila, _numero(imp_v))  # la última fila de TOTAL, para contrastar
            continue
        if nat == "Capítulo":
            capitulo = f"{codigo} {resumen}".strip()
            vistos.setdefault(codigo.casefold(), fila)
            continue
        manual = nat == "" and _es_manual(wf, fila, objetivo, codigo, resumen, vistos)
        if nat != "Partida" and not manual:
            continue
        if nat == "Partida" and codigo.casefold() in vistos:
            r.avisos.append(
                f"{codigo} (fila {fila}) ya estaba en la fila {vistos[codigo.casefold()]}: se "
                "cuentan las dos."
            )
        vistos.setdefault(codigo.casefold(), fila)
        importe = _numero(imp_v)
        if importe is None:
            texto_precio = isinstance(wv.cell(fila, objetivo[2]).value, str)
            if isinstance(imp_v, str) and imp_v.startswith("#") and not texto_precio:
                # Con un texto en el precio («NO INCLUIDO…») el #¡VALOR! es esperable: la
                # nota ya explica el 0 (revisión 09-11-2026).
                con_error.append(fila)  # #¡VALOR!, #REF!…: un error de la hoja
            elif imp_v is None and _es_formula(wf.cell(fila, objetivo[3]).value):
                sin_valor.append(fila)
            importe = 0.0
        precio_bruto = wv.cell(fila, objetivo[2]).value
        nota = precio_bruto.strip() if isinstance(precio_bruto, str) else ""
        reparto: dict[str, float] = {}
        for nombre, (_n, _c, _p, c_imp) in zip(nombres, paquetes, strict=True):
            v = _numero(wv.cell(fila, c_imp).value)
            if v:
                reparto[nombre] = v
        partida = PartidaCoste(
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
        r.partidas.append(partida)
        if manual:
            # Toda inferencia se declara (CLAUDE.md, línea roja 9).
            r.avisos.append(
                f"Línea añadida a mano (fila {fila}): «{resumen}», {_eur(importe)}. Cuenta en "
                "el coste objetivo."
            )
        if importe < 0 or any(v < 0 for v in reparto.values()):
            r.avisos.append(f"{codigo or resumen} (fila {fila}): importe negativo.")
    if not r.partidas:
        raise CosteNoReconocido("La hoja no tiene ninguna partida («Nat» = Partida).")
    if sin_valor:
        r.avisos.append(
            f"Fórmula sin resultado guardado en la(s) fila(s) {_filas(sin_valor)}: abre el "
            "Excel en Excel y guárdalo para que se lean sus importes (cuentan 0)."
        )
    if con_error:
        r.avisos.append(
            f"Error de la hoja (#…) en el importe de la(s) fila(s) {_filas(con_error)}: "
            "corrígelo en el Excel (cuentan 0)."
        )
    for p in r.partidas:
        if round(abs(p.sin_repartir), 2) > CENTIMO:
            r.avisos.append(
                f"{p.codigo or p.resumen} (fila {p.fila}): {_eur(p.sin_repartir)} del "
                "objetivo sin repartir en paquetes."
            )
    # Contraste con el TOTAL del propio Excel: si no cuadra, algo se ha contado dos veces o
    # se ha perdido (revisión 09-11-2026).
    if total_excel is None:
        r.avisos.append(
            "El Excel no tiene una fila de TOTAL con importe: la suma no se ha podido contrastar."
        )
    elif round(abs(total_excel[1] - r.total), 2) > CENTIMO:
        r.avisos.append(
            f"La suma leída ({_eur(r.total)}) no coincide con el TOTAL del Excel "
            f"({_eur(total_excel[1])}, fila {total_excel[0]}): revisa las líneas leídas."
        )
    return r


def _es_manual(wf, fila: int, objetivo, codigo: str, resumen: str, vistos) -> bool:
    """Línea añadida a mano fuera de Presto: sin naturaleza, con resumen, y con el precio
    escrito (o, sin precio, el importe escrito). No lo son las filas de cierre (su resumen
    es el código de la partida o del capítulo que cierran) ni las de total."""
    if not resumen or resumen.casefold() in vistos or (codigo and codigo.casefold() in vistos):
        return False
    precio = wf.cell(fila, objetivo[2]).value
    importe = wf.cell(fila, objetivo[3]).value
    return _numero(precio) is not None or (precio is None and _numero(importe) is not None)


def _eur(v: float) -> str:
    return f"{v:.2f} €".replace(".", ",")


def _filas(filas: list[int]) -> str:
    return ", ".join(map(str, filas[:10])) + (" …" if len(filas) > 10 else "")
