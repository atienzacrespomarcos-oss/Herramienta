"""Propiedad: cualquier secuencia de órdenes válidas, deshecha entera, deja el proyecto
exactamente como estaba; y rehecha entera, exactamente como quedó."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from traza.app.ordenes import (
    Aprobar,
    BorrarPropiedad,
    CrearElemento,
    CrearPendiente,
    FijarPropiedad,
    OrdenRechazada,
    Reabrir,
)
from traza.app.proyecto import Proyecto
from traza.core.procedencia import Origen, Procedencia

USUARIO = Procedencia(Origen.USUARIO)
TABLAS = ("elemento", "propiedad", "decision", "pendiente", "documento")


def _foto(p: Proyecto) -> dict[str, list[tuple]]:
    return {t: sorted(tuple(r) for r in p._con.execute(f"SELECT * FROM {t}")) for t in TABLAS}


acciones = st.lists(
    st.tuples(
        st.sampled_from(["crear", "fijar", "borrar", "aprobar", "reabrir", "pendiente"]),
        st.integers(0, 3),
        st.floats(1, 1e5, allow_nan=False),
    ),
    min_size=1,
    max_size=25,
)


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(acciones)
def test_deshacer_y_rehacer_todo(tmp_path_factory, secuencia):
    p = Proyecto.crear(tmp_path_factory.mktemp("h") / "N", "N")
    try:
        inicial = _foto(p)
        ids: list[str] = []
        for accion, i, x in secuencia:
            el = ids[i % len(ids)] if ids else None
            try:
                if accion == "crear":
                    o = CrearElemento("equipo", f"EQ-{len(ids)}")
                    p.ejecutar(o)
                    ids.append(o.id)
                elif el is None:
                    continue
                elif accion == "fijar":
                    p.ejecutar(FijarPropiedad(el, "potencia_frigorifica", x, "kW", USUARIO))
                    p.ejecutar(FijarPropiedad(el, "fabricante", "F", None, USUARIO))
                    p.ejecutar(FijarPropiedad(el, "modelo", "M", None, USUARIO))
                elif accion == "borrar":
                    p.ejecutar(BorrarPropiedad(el, "potencia_frigorifica"))
                elif accion == "aprobar":
                    p.ejecutar(Aprobar(el, "ok"))
                elif accion == "reabrir":
                    p.ejecutar(Reabrir(el, "cambio"))
                elif accion == "pendiente":
                    p.ejecutar(CrearPendiente("dato", el))
            except OrdenRechazada:
                pass  # rechazos esperables (bloqueo, sin valor…): no deben dejar rastro
        final = _foto(p)
        while p.deshacer():
            pass
        assert _foto(p) == inicial
        while p.rehacer():
            pass
        assert _foto(p) == final
    finally:
        p.cerrar()
