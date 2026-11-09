"""Estado de los pasos (docs/modules/flujo.md): pendiente con lo que falta, hecho y
desactualizado cuando cambia un paso del que depende; «dar por revisado»."""

from __future__ import annotations

from tests.integration.test_hidronica_proyecto import _circuitos, red  # noqa: F401

from traza.app.flujo import DESACTUALIZADO, HECHO, PENDIENTE, EstadoPaso


def test_pendiente_dice_lo_que_falta(proyecto):
    p = proyecto
    assert p.estado_paso("planos") == EstadoPaso(PENDIENTE, "Falta: leer el plano DXF")
    assert p.estado_paso("cargas").texto == "Falta: espacios confirmados en Planos"
    assert p.estado_paso("hidronica").texto == "Falta: definir un sistema hidráulico"
    assert p.estado_paso("subcuadros").texto == "Falta: definir un subcuadro"
    assert p.estado_paso("equipos").estado == ""


def test_hecho_desactualizado_y_revisado(red):  # noqa: F811
    p, red_id, _, _ = red
    assert p.estado_paso("planos").estado == HECHO
    assert p.estado_paso("cargas").estado == HECHO
    assert p.estado_paso("redes").estado == HECHO
    p.definir_sistema_hidraulico(titulo="Clima", tipo="2_tubos", circuitos=_circuitos(p))
    assert p.estado_paso("hidronica").estado == HECHO
    # Cambian las cargas: redes e hidráulica quedan desactualizadas (y lo dicen).
    cargas = p.estado_paso("cargas")
    assert cargas.estado == HECHO
    p.fijar_cargas_espacio(p.espacios()[0]["id"], uso="almacen")
    for paso in ("redes", "hidronica"):
        e = p.estado_paso(paso)
        assert e.estado == DESACTUALIZADO and "Cargas" in e.texto, paso
    # Dar por revisado lo quita; se puede deshacer.
    p.dar_por_revisado("redes")
    assert p.estado_paso("redes").estado == HECHO
    assert p.estado_paso("hidronica").estado == DESACTUALIZADO
    p.deshacer()
    assert p.estado_paso("redes").estado == DESACTUALIZADO
    # Cambiar el propio paso también lo da por revisado.
    p.definir_sistema_hidraulico(
        titulo="Clima", tipo="4_tubos", circuitos=_circuitos(p),
        id=p.sistemas_hidraulicos()[0]["id"],
    )  # fmt: skip
    assert p.estado_paso("hidronica").estado == HECHO


def test_el_estado_no_lee_la_guia_del_idae(red):  # noqa: F811
    """La lista de pasos se refresca a cada cambio: no puede leer el PDF de la guía
    (tarda segundos). Sin leer, se mira que estén los datos."""
    p, _, _, _ = red
    p._guias.clear()  # como al abrir el proyecto otra vez

    def no_leer(_ruta):
        raise AssertionError("el estado ha leído la guía")

    p.lector_guia = no_leer
    for paso in ("cargas", "redes"):
        assert p.estado_paso(paso).estado == HECHO
