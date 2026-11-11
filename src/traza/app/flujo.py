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
#: Cómo se nombran los pasos de cálculo en los avisos.
#: Los mismos que la lista de pasos de la ventana (ui/ventana.PASOS; un test lo vigila).
NOMBRES = {
    "planos": "Planos y espacios",
    "cargas": "Cargas y ventilación",
    "redes": "Redes de aire",
    "hidronica": "Sistema hidráulico",
    "subcuadros": "Subcuadros de clima",
}
#: Qué cambios del registro son «del paso»: solo los que cambian datos de cálculo.
#: `{t}` es el alias de la tabla `cambio`. Planos: la geometría confirmada y los niveles,
#: espacios y obstáculos con sus propiedades (alturas, cotas); NO la tabla `plano` (capas,
#: descartes, otro DXF leído), que no cambia ningún cálculo (revisión 09-11-2026: descartar
#: una propuesta marcaba todo como desactualizado y cambiar una altura no marcaba nada).
_ELEMENTO_DEL_CAMBIO = (
    "CASE WHEN {t}.entidad = 'elemento' THEN {t}.entidad_id"
    " ELSE substr({t}.entidad_id, 1, instr({t}.entidad_id, '/') - 1) END"
)
FILTROS: dict[str, str] = {
    "planos": (
        "({t}.entidad = 'geometria' OR ({t}.entidad IN ('elemento', 'propiedad')"
        # Aprobar o reabrir solo cambia el estado: no es un dato de cálculo (segunda
        # revisión 09-11-2026: aprobar un espacio marcaba Cargas y Redes).
        " AND coalesce({t}.campo, '') NOT IN ('estado', 'modificado', 'estado,modificado')"
        " AND "
        + _ELEMENTO_DEL_CAMBIO
        # Mira los elementos que existen hoy: quitar un espacio u obstáculo cuenta por su
        # geometría; quitar un nivel (vacío, si no, no se puede) no cambia ningún cálculo.
        + " IN (SELECT id FROM elemento WHERE tipo IN ('nivel', 'espacio', 'obstaculo'))))"
    ),
    "cargas": "{t}.entidad IN ('cargas_proyecto', 'cargas_espacio')",
    "redes": "{t}.entidad = 'red_aire'",
    "hidronica": "{t}.entidad = 'sistema_hidraulico'",
    "subcuadros": "{t}.entidad = 'subcuadro'",
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


def _ultimo(con, paso: str, sin_ordenes_de: tuple[str, ...] = ()) -> int:
    """Último cambio del paso. Con `sin_ordenes_de` (otros pasos), sin contar las órdenes
    que también los cambiaron: cuando un plano revisado mueve la red al plano nuevo, o
    quitar un espacio borra sus cargas, eso no es que el usuario haya revisado la red o las
    cargas (revisión 09-11-2026: la red salía «hecha» tras revisar el plano)."""
    sql = "SELECT MAX(n) FROM cambio c WHERE " + FILTROS[paso].format(t="c")
    if sin_ordenes_de:
        otros = " OR ".join(FILTROS[a].format(t="a") for a in sin_ordenes_de)
        sql += (
            f" AND NOT EXISTS (SELECT 1 FROM cambio a WHERE a.orden_id = c.orden_id AND ({otros}))"
        )
    fila = con.execute(sql).fetchone()
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
    if paso == "control":
        # Se recalcula con lo diseñado, nunca se queda atrás: sin «desactualizado». No
        # calcula aquí (necesita las cargas y la guía del IDAE, como arriba).
        if not (p.redes() or p.sistemas_hidraulicos()):
            return EstadoPaso(PENDIENTE, "Falta: diseñar una red de aire o un sistema hidráulico")
        return None
    if paso == "mediciones":
        return None if p.mediciones() else EstadoPaso(PENDIENTE, "Falta: leer una medición")
    if paso == "modificados":
        # Un modificado no siempre hace falta: sin ninguno, el paso no tiene marca; con
        # alguno, ✓ hecho.
        return None if p.modificados() else EstadoPaso("")
    if paso == "venta":
        if p.venta_contratada() is None:
            if not p.mediciones():
                return EstadoPaso(PENDIENTE, "Falta: leer el presupuesto en «Mediciones»")
            return EstadoPaso(PENDIENTE, "Falta: elegir el presupuesto contratado")
        return None
    if paso == "coste_objetivo":
        if p.coste_objetivo() is None:
            return EstadoPaso(PENDIENTE, "Falta: importar el Excel de coste objetivo")
        return None
    if paso == "certificaciones":
        if p.venta_contratada() is None:
            return EstadoPaso(PENDIENTE, "Falta: el presupuesto contratado (Venta)")
        # Al empezar la obra no hay certificaciones: sin marca, no «pendiente».
        return None if p.certificaciones() else EstadoPaso("")
    if paso == "coste_real":
        if p.coste_objetivo() is None:
            return EstadoPaso(PENDIENTE, "Falta: importar el coste objetivo (sus paquetes)")
        # Al empezar la obra no hay facturas: sin marca, no «pendiente».
        return None if p.facturas() else EstadoPaso("")
    if paso == "prevision":
        if p.prevision() is None:
            return EstadoPaso(PENDIENTE, "Falta: tu previsión (venta y coste finales)")
        return None
    if paso == "futuribles":
        # No siempre hay ofertas pendientes: sin ninguno, sin marca; con alguno, ✓ hecho.
        return None if p.futuribles() else EstadoPaso("")
    return EstadoPaso("")  # sin estado (p. ej. Equipos)


def estado(p: Any, paso: str) -> EstadoPaso:
    falta = _contenido(p, paso)
    if falta is not None:
        return falta
    if paso in DEPENDE:
        con = p._con
        ancestros = tuple(sorted(_ancestros(paso)))
        propio = max(_ultimo(con, paso, ancestros), _revisado(con, paso))
        cambiados = [a for a in ancestros if _ultimo(con, a) > propio]
        if cambiados:
            orden = [k for k in DEPENDE if k in cambiados]
            return EstadoPaso(
                DESACTUALIZADO,
                "Ha cambiado "
                + ", ".join(NOMBRES[k] for k in orden)
                + ": revisa y da por revisado",
            )
    return EstadoPaso(HECHO)
