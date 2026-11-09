"""Estado de los pasos del proyecto (docs/modules/flujo.md).

Decisión del usuario (09-11-2026): «pasos con estado» — hecho, pendiente (con lo que
falta) o desactualizado (algo de un paso del que depende ha cambiado después; se marca
hasta que se revise).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

HECHO, PENDIENTE, DESACTUALIZADO = "hecho", "pendiente", "desactualizado"

#: Dependencias directas entre pasos de cálculo.
DEPENDE: dict[str, tuple[str, ...]] = {
    "planos": (),
    "cargas": ("planos",),
    "redes": ("planos", "cargas"),
    "hidronica": ("planos", "cargas"),
    "subcuadros": ("redes", "hidronica"),
}
#: Tablas cuyos cambios son «del paso» (registro de cambios).
TABLAS: dict[str, tuple[str, ...]] = {
    "planos": ("plano", "geometria"),
    "cargas": ("cargas_proyecto", "cargas_espacio"),
    "redes": ("red_aire",),
    "hidronica": ("sistema_hidraulico",),
    "subcuadros": ("subcuadro",),
}


@dataclass(frozen=True)
class EstadoPaso:
    estado: str  # hecho | pendiente | desactualizado | "" (sin estado)
    texto: str = ""  # qué falta o qué ha cambiado


def _ancestros(paso: str) -> set[str]:
    vistos: set[str] = set()
    pendientes = list(DEPENDE.get(paso, ()))
    while pendientes:
        p = pendientes.pop()
        if p not in vistos:
            vistos.add(p)
            pendientes.extend(DEPENDE.get(p, ()))
    return vistos


def _ultimo(con, tablas, sin_ordenes_de=()) -> int:
    """Último cambio en `tablas`. Con `sin_ordenes_de`, sin contar las órdenes que también
    cambiaron esas otras tablas: cuando un plano revisado mueve la red al plano nuevo, o
    quitar un espacio borra sus cargas, eso no es que el usuario haya revisado la red o las
    cargas (revisión 09-11-2026: la red salía «hecha» tras revisar el plano)."""
    if not tablas:
        return 0
    marcas = ",".join("?" * len(tablas))
    sql = f"SELECT MAX(n) FROM cambio c WHERE entidad IN ({marcas})"
    if sin_ordenes_de:
        otras = ",".join("?" * len(sin_ordenes_de))
        sql += (
            " AND NOT EXISTS (SELECT 1 FROM cambio a WHERE a.orden_id = c.orden_id"
            f" AND a.entidad IN ({otras}))"
        )
    fila = con.execute(sql, (*tablas, *sin_ordenes_de)).fetchone()
    return fila[0] or 0


def _revisado(con, paso: str) -> int:
    fila = con.execute("SELECT marca FROM paso_revisado WHERE paso = ?", (paso,)).fetchone()
    return int(fila[0]) if fila else 0


def _contenido(p: Any, paso: str) -> EstadoPaso | None:
    """Pendiente (con lo que falta) o None si el paso tiene lo que necesita."""
    from traza.app.ordenes import OrdenRechazada

    if paso == "documentacion":
        return None if p.documentos() else EstadoPaso(PENDIENTE, "Falta: incorporar documentos")
    if paso == "planos":
        if not p.planos():
            return EstadoPaso(PENDIENTE, "Falta: leer el plano DXF")
        if not p.espacios():
            if p.encargo == "ampliacion":
                # Se diseña la parte nueva: solo se confirman sus espacios (usuario,
                # 09-11-2026); lo existente queda sin confirmar o se descarta.
                return EstadoPaso(PENDIENTE, "Falta: confirmar los espacios de la ampliación")
            return EstadoPaso(PENDIENTE, "Falta: confirmar los espacios")
        return None
    # Cargas, redes e hidráulica necesitan la guía del IDAE, que se lee una vez por sesión
    # y tarda unos segundos: el estado no la lee (la lista de pasos se refresca a cada
    # cambio). Hasta que el usuario pulsa «Calcular» en Cargas, se mira si están los datos
    # y no si calculan (revisión 09-11-2026: el refresco leía la guía sin pedirlo).
    config = p.cargas_config()
    calcula = config is not None and p.guia_leida(config["guia_documento_id"])
    if paso == "cargas":
        if not p.espacios():
            return EstadoPaso(PENDIENTE, "Falta: espacios confirmados en Planos")
        if config is None:
            return EstadoPaso(PENDIENTE, "Falta: el clima y la obra")
        if calcula:
            try:
                p.calcular_cargas()
            except OrdenRechazada as exc:
                return EstadoPaso(PENDIENTE, f"Falta: {exc}")
            except Exception as exc:  # noqa: BLE001 — un dato roto no tumba la lista de pasos
                return EstadoPaso(PENDIENTE, f"No se calcula: {exc}")
        return None
    if paso in ("redes", "hidronica", "subcuadros"):
        listar, calcular, vacio = {
            "redes": (p.redes, p.calcular_red, "definir una red de aire"),
            "hidronica": (
                p.sistemas_hidraulicos,
                p.calcular_sistema_hidraulico,
                "definir un sistema hidráulico",
            ),
            "subcuadros": (p.subcuadros, p.calcular_subcuadro, "definir un subcuadro"),
        }[paso]
        filas = listar()
        if not filas:
            return EstadoPaso(PENDIENTE, f"Falta: {vacio}")
        if paso != "subcuadros" and not calcula:
            return None
        for f in filas:
            try:
                calcular(f["id"])
            except Exception as exc:  # noqa: BLE001 — se muestra, no rompe la lista
                return EstadoPaso(PENDIENTE, f"«{f['nombre']}» no se calcula: {exc}")
        return None
    if paso == "mediciones":
        return None if p.mediciones() else EstadoPaso(PENDIENTE, "Falta: leer una medición")
    if paso == "modificados":
        return None if p.modificados() else EstadoPaso(PENDIENTE, "Sin modificados")
    return EstadoPaso("")  # sin estado (p. ej. Equipos)


def estado(p: Any, paso: str) -> EstadoPaso:
    falta = _contenido(p, paso)
    if falta is not None:
        return falta
    if paso in DEPENDE:
        con = p._con
        ancestros = _ancestros(paso)
        de_ancestros = tuple(t for a in ancestros for t in TABLAS[a])
        propio = max(_ultimo(con, TABLAS[paso], de_ancestros), _revisado(con, paso))
        cambiados = [a for a in ancestros if _ultimo(con, TABLAS[a]) > propio]
        if cambiados:
            nombres = {"planos": "Planos", "cargas": "Cargas", "redes": "Redes de aire",
                       "hidronica": "Sistema hidráulico"}  # fmt: skip
            orden = [k for k in DEPENDE if k in cambiados]
            return EstadoPaso(
                DESACTUALIZADO,
                "Ha cambiado "
                + ", ".join(nombres[k] for k in orden)
                + ": revisa y da por revisado",
            )
    return EstadoPaso(HECHO)
