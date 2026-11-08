"""Sistema hidráulico en el proyecto: circuitos de espacios con cargas, cálculo, Excel con
todos los elementos y la orden con sus rechazos (docs/modules/hidronica.md).

Proyecto de tests/integration/test_redes_proyecto.py (ALMACÉN y OFICINAS con cargas).
"""

from __future__ import annotations

import pytest
from openpyxl import load_workbook
from tests.integration.test_redes_proyecto import red  # noqa: F401 (fixture)

from traza.app.ordenes import OrdenRechazada


def _espacios(p):
    return {e["nombre"]: e["id"] for e in p.espacios()}


def _circuitos(p):
    e = _espacios(p)
    return [
        {
            "nombre": "Oficinas",
            "espacios": [e["OFICINAS"]],
            "unidades": 4,
            "longitud_m": 30.0,
            "perdida_terminal_kpa": 15.0,
        },
        {
            "nombre": "Nave",
            "espacios": [e["ALMACÉN"]],
            "unidades": 2,
            "longitud_m": 60.0,
            "perdida_terminal_kpa": 20.0,
        },
    ]


def test_dos_tubos_con_las_cargas_de_los_espacios(red, tmp_path):  # noqa: F811
    p, _, _, _ = red
    sid = p.definir_sistema_hidraulico(titulo="Clima", tipo="2_tubos", circuitos=_circuitos(p))
    r = p.calcular_sistema_hidraulico(sid)
    cargas = {c.nombre: c for c in p.calcular_cargas().espacios}
    assert len(r.servicios) == 1 and r.servicios[0].clave == "frio_calor"
    ofi = r.potencias["Oficinas"]
    assert ofi["frio"] == pytest.approx(cargas["OFICINAS"].verano.total_w)
    assert ofi["calor"] == pytest.approx(cargas["OFICINAS"].invierno.total_w)
    s = r.servicios[0]
    assert {c.datos.nombre for c in s.circuitos} == {"Oficinas", "Nave"}
    assert s.circuitos[0].datos.perdida_terminal_pa == pytest.approx(15_000)
    # Excel: las cuatro hojas y todos los elementos con su norma.
    x = p.exportar_sistema_hidraulico_excel(sid, tmp_path / "Hidráulica")
    wb = load_workbook(x)
    assert wb.sheetnames == ["Resumen", "Circuitos", "Elementos", "Hipótesis"]
    filas = list(wb["Elementos"].iter_rows(min_row=2, values_only=True))
    assert len(filas) == len(r.elementos) > 40
    assert all(f[5] for f in filas)  # cada elemento con su norma o fuente
    assert any(f[1] == "Desconector" for f in filas)


def test_cuatro_tubos_da_dos_servicios(red):  # noqa: F811
    p, _, _, _ = red
    sid = p.definir_sistema_hidraulico(titulo="4T", tipo="4_tubos", circuitos=_circuitos(p))
    r = p.calcular_sistema_hidraulico(sid)
    assert [s.clave for s in r.servicios] == ["frio", "calor"]
    zonas = {e.zona for e in r.elementos}
    assert any(z.startswith("Frío · ") for z in zonas)
    assert any(z.startswith("Calor · ") for z in zonas)
    # Dos generadores, uno por servicio.
    generadores = [
        e
        for e in r.elementos
        if e.zona.endswith("Generador y primario") and e.cantidad == 1 and "kW" in e.especificacion
    ]
    assert len(generadores) == 2


def test_la_orden_rechaza_datos_incoherentes_y_se_deshace(red):  # noqa: F811
    p, _, _, nivel_id = red
    c = _circuitos(p)
    with pytest.raises(OrdenRechazada, match="al menos un circuito"):
        p.definir_sistema_hidraulico(titulo="X", tipo="2_tubos", circuitos=[])
    with pytest.raises(OrdenRechazada, match="nombre propio"):
        p.definir_sistema_hidraulico(titulo="X", tipo="2_tubos", circuitos=[c[0], c[0]])
    with pytest.raises(OrdenRechazada, match="no es un espacio"):
        p.definir_sistema_hidraulico(
            titulo="X", tipo="2_tubos", circuitos=[{**c[0], "espacios": [nivel_id]}]
        )
    with pytest.raises(OrdenRechazada, match="unidades"):
        p.definir_sistema_hidraulico(
            titulo="X", tipo="2_tubos", circuitos=[{**c[0], "unidades": 0}]
        )
    with pytest.raises(OrdenRechazada, match="Frío"):
        p.definir_sistema_hidraulico(
            titulo="X", tipo="2_tubos", circuitos=c, frio_impulsion=12, frio_retorno=7
        )
    # Un espacio en dos circuitos sumaría su carga dos veces.
    with pytest.raises(OrdenRechazada, match="se sumaría dos veces"):
        p.definir_sistema_hidraulico(
            titulo="X", tipo="2_tubos", circuitos=[c[0], {**c[1], "espacios": c[0]["espacios"]}]
        )
    sid = p.definir_sistema_hidraulico(titulo="Clima", tipo="2_tubos", circuitos=c)
    with pytest.raises(OrdenRechazada, match="Ya hay un sistema"):
        p.definir_sistema_hidraulico(titulo="Clima", tipo="4_tubos", circuitos=c)
    assert p.sistema_hidraulico(sid)["circuitos"][0]["exterior"] is False
    p.deshacer()
    assert p.sistemas_hidraulicos() == []
