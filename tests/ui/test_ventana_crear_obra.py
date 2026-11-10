"""«Nueva obra desde documentos» y «Añadir documentos a la obra» desde la ventana
(docs/modules/obra.md, bloque 4c): de los documentos recibidos a la obra montada."""

from __future__ import annotations

import pytest
from tests.integration.test_crear_obra import documentos
from tests.integration.test_obra_certificaciones import sin_ia
from tests.ui.test_ventana import PreguntasPreparadas

from traza.ui.ventana import VentanaPrincipal

pytestmark = pytest.mark.ui


@pytest.fixture
def ventana(qtbot):
    q = PreguntasPreparadas()
    v = VentanaPrincipal(q)
    qtbot.addWidget(v)
    yield v, q
    if v.proyecto is not None:
        v.proyecto.cerrar()


def test_nueva_obra_desde_todos_los_documentos(ventana, tmp_path, pdf_3_paginas, monkeypatch):
    v, q = ventana
    # Las pruebas nunca llaman a la IA real.
    from traza.app import proyecto as modulo

    original = modulo.Proyecto.crear

    def crear(*a, **k):
        p = original(*a, **k)
        p.mapeador_ia = p.mapeador_facturas_ia = sin_ia
        return p

    monkeypatch.setattr(modulo.Proyecto, "crear", staticmethod(crear))
    recibidos = tmp_path / "recibidos"
    recibidos.mkdir()
    rutas = documentos(recibidos, pdf_3_paginas)
    q.preparar("nueva_obra", (tmp_path / "Nave 3", "Nave 3"))
    q.preparar("ficheros", rutas)

    def confirmar_plan(propuestas):
        # El usuario acepta lo propuesto (el PDF queda como documentación: no va a la IA).
        return [(x, x.tipo) for x in propuestas]

    q.preparar("plan_obra", confirmar_plan)
    q.preparar("certificacion", {"numero": 3, "fecha": "2026-10-31"})
    q.preparar("elegir", 0)  # las facturas del listado: de la obra OB-25 Nave

    def facturas(propuestas, paquetes):
        return [
            {"paquete": "EQUIPOS", "proveedor": x.leida.proveedor, "numero": x.leida.numero,
             "fecha": x.leida.fecha, "importe": x.leida.importe}
            for x in propuestas
        ]  # fmt: skip

    q.preparar("facturas_erp", facturas)
    v.a_nueva_obra.trigger()
    assert not q.avisos, (q.titulos, q.avisos)
    p = v.proyecto
    assert p.encargo == "obra" and p.nombre == "Nave 3"
    assert len(p.documentos()) == len(rutas)
    # El núcleo de la obra, montado.
    venta = p.venta_contratada()
    assert venta["documento_nombre"] == "Presupuesto cliente.bc3"
    r = p.resumen_obra()
    assert r.venta == pytest.approx(26500) and r.objetivo == pytest.approx(23200)
    assert [c["numero"] for c in p.certificaciones()] == [3]
    assert len(p.facturas()) == 3
    resumen = q.informaciones[-1]
    assert "✓ Presupuesto cliente.bc3: presupuesto contratado (venta)" in resumen
    assert "Planta.dxf: plano (dxf)" in resumen and "✗" not in resumen
    assert v.lista_pasos.currentItem().text().endswith("Venta")
    # Deshacer funciona paso a paso (nada se ha escrito fuera de órdenes).
    assert v.a_deshacer.isEnabled()


def test_anadir_documentos_y_lo_que_falla_se_dice(ventana, tmp_path):
    from tests.integration.test_obra import BC3_VENTA

    from traza.app.proyecto import Proyecto

    v, q = ventana
    p = Proyecto.crear(tmp_path / "Obra", "Obra", "obra")
    p.mapeador_ia = p.mapeador_facturas_ia = sin_ia
    v._usar_proyecto(p)
    assert v.a_anadir_documentos.isEnabled()
    venta = tmp_path / "Venta.bc3"
    venta.write_bytes(BC3_VENTA.encode("cp1252"))
    roto = tmp_path / "Roto.xlsx"
    roto.write_bytes(b"no es un excel")
    q.preparar("ficheros", [venta, roto])
    # El usuario dice que el Excel roto es el coste objetivo: falla, y se dice; el resto sigue.
    q.preparar(
        "plan_obra",
        lambda ps: [(x, "coste_objetivo" if x.nombre == "Roto.xlsx" else x.tipo) for x in ps],
    )
    v.a_anadir_documentos.trigger()
    assert p.venta_contratada() is not None
    resumen = q.informaciones[-1]
    assert "✓ Venta.bc3" in resumen and "✗ Roto.xlsx: coste objetivo" in resumen
    # Echar otra vez el mismo documento: no se duplica.
    q.preparar("ficheros", [venta])
    v.a_anadir_documentos.trigger()
    assert "ya está incorporado" in q.avisos[-1]
    # Cancelar la tabla deja los documentos en Documentación, sin leer.
    otro = tmp_path / "Otro.bc3"
    otro.write_bytes(BC3_VENTA.replace("|500|", "|700|").encode("cp1252"))
    q.preparar("ficheros", [otro])
    q.preparar("plan_obra", None)
    v.a_anadir_documentos.trigger()
    assert "sin leer" in q.informaciones[-1] and len(p.mediciones()) == 1
