"""Propiedad: cualquier secuencia de órdenes, deshecha entera, deja el proyecto exactamente
como estaba; rehecha entera, exactamente como quedó; y cada orden rechazada no deja rastro.

Cubre todas las órdenes del núcleo, incluidas las de la IA (proponer) y el motor (estados).
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from traza.app.ordenes import (
    Aprobar,
    BorrarPropiedad,
    CambiarEstado,
    ConfirmarPropuesta,
    CrearElemento,
    CrearPendiente,
    FijarPropiedad,
    OrdenRechazada,
    Reabrir,
    ResolverPendiente,
)
from traza.app.proyecto import Proyecto
from traza.core.estados import Estado
from traza.core.procedencia import Origen, Procedencia

USUARIO = Procedencia(Origen.USUARIO)
IA = Procedencia(Origen.IA_PROPUESTA)
TABLAS = ("elemento", "propiedad", "decision", "pendiente", "documento", "cambio")
TABLAS_MODELO = TABLAS[:-1]

ACCIONES = [
    "crear",
    "crear_hijo",
    "fijar",
    "proponer_ia",
    "confirmar",
    "borrar",
    "aprobar",
    "reabrir",
    "estado_propuesto",
    "estado_calculado_motor",
    "pendiente",
    "resolver",
    "documento",
]


def _foto(p: Proyecto, tablas=TABLAS_MODELO) -> dict[str, list[tuple]]:
    return {t: sorted(tuple(r) for r in p._con.execute(f"SELECT * FROM {t}")) for t in tablas}


def _orden(accion, el, pend, x, n):
    """Devuelve (orden, autor) o None si la acción no aplica todavía."""
    if accion == "crear":
        return CrearElemento("equipo", f"EQ-{n}"), "usuario"
    if accion == "pendiente":
        return CrearPendiente("dato por confirmar", el), "usuario"
    if accion == "resolver":
        return (ResolverPendiente(pend, "resuelto"), "usuario") if pend else None
    if el is None:
        return None
    return {
        "crear_hijo": (CrearElemento("equipo", f"EQ-{n}", padre_id=el), "usuario"),
        "fijar": (FijarPropiedad(el, "potencia_frigorifica", x, "kW", USUARIO), "usuario"),
        "proponer_ia": (FijarPropiedad(el, "modelo", f"M{n}", None, IA), "ia"),
        "confirmar": (ConfirmarPropuesta(el, "modelo"), "usuario"),
        "borrar": (BorrarPropiedad(el, "potencia_frigorifica"), "usuario"),
        "aprobar": (Aprobar(el, "ok"), "usuario"),
        "reabrir": (Reabrir(el, "cambio"), "usuario"),
        "estado_propuesto": (CambiarEstado(el, Estado.PROPUESTO), "usuario"),
        "estado_calculado_motor": (CambiarEstado(el, Estado.CALCULADO), "motor"),
    }[accion]


secuencias = st.lists(
    st.tuples(st.sampled_from(ACCIONES), st.integers(0, 5), st.floats(1, 1e5)),
    min_size=1,
    max_size=30,
)


@settings(
    max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(secuencias)
def test_deshacer_y_rehacer_todo(tmp_path_factory, secuencia):
    carpeta_docs = tmp_path_factory.mktemp("docs")
    p = Proyecto.crear(tmp_path_factory.mktemp("h") / "N", "N")
    try:
        inicial = _foto(p)
        ids: list[str] = []
        pendientes: list[str] = []
        ejecutadas = rechazadas = 0
        for n, (accion, i, x) in enumerate(secuencia):
            el = ids[i % len(ids)] if ids else None
            pend = pendientes[i % len(pendientes)] if pendientes else None
            antes = _foto(p, TABLAS)
            try:
                if accion == "documento":
                    # Contenido distinto en cada paso: cada uno es un documento nuevo.
                    f = carpeta_docs / f"doc{n}.txt"
                    f.write_text(f"documento {n}", encoding="utf-8")
                    p.incorporar_documento(f)
                else:
                    par = _orden(accion, el, pend, x, n)
                    if par is None:
                        continue
                    orden, autor = par
                    p.ejecutar(orden, autor=autor)
                    if isinstance(orden, CrearElemento):
                        ids.append(orden.id)
                    if isinstance(orden, CrearPendiente):
                        pendientes.append(orden.id)
                ejecutadas += 1
            except OrdenRechazada:
                rechazadas += 1
                assert _foto(p, TABLAS) == antes, f"«{accion}» rechazada dejó rastro"
        assert len(p._deshacer) == ejecutadas
        final = _foto(p)
        while p.deshacer():
            pass
        assert _foto(p) == inicial
        while p.rehacer():
            pass
        assert _foto(p) == final
    finally:
        p.cerrar()
