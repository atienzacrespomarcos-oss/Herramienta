"""Paso «Control» desde la ventana y en el proyecto (docs/modules/control.md).

Proyecto de tests/ui/test_paso_redes.py (ALMACÉN y OFICINAS con cargas): se añade un
sistema hidráulico de 2 tubos y se comprueba la propuesta, el Excel y el estado del paso.
"""

from __future__ import annotations

import ezdxf
import pytest
from openpyxl import load_workbook
from tests.ui.test_paso_redes import ventana  # noqa: F401 (fixture)

pytestmark = pytest.mark.ui


def _sistema(p, unidades=(4, 2), perdidas_kpa=(15.0, 20.0)):
    e = {x["nombre"]: x["id"] for x in p.espacios()}
    return p.definir_sistema_hidraulico(
        titulo="Clima",
        tipo="2_tubos",
        circuitos=[
            {
                "nombre": "Oficinas",
                "espacios": [e["OFICINAS"]],
                "unidades": unidades[0],
                "longitud_m": 30.0,
                "perdida_terminal_kpa": perdidas_kpa[0],
            },
            {
                "nombre": "Nave",
                "espacios": [e["ALMACÉN"]],
                "unidades": unidades[1],
                "longitud_m": 60.0,
                "perdida_terminal_kpa": perdidas_kpa[1],
            },
        ],
    )


def test_recorrido_completo(ventana, tmp_path):  # noqa: F811
    v, q = ventana
    p = v.proyecto
    pc = v.pagina_control
    assert p.estado_paso("control").estado == "pendiente"
    v.ir_a_paso("control")
    # Solo espacios con cargas: sus sondas de zona, y el aviso de que sin sistema
    # hidráulico se supone frío y calor. El paso sigue pendiente (faltan los equipos).
    assert "Sin sistema hidráulico" in pc.resumen.text()
    assert {x.sistema for x in p.propuesta_control().resultado.puntos} == {"Zonas", "General"}

    _sistema(p)
    v.refrescar()
    assert p.estado_paso("control").estado == "hecho"
    propuesta = p.propuesta_control()
    r = propuesta.resultado
    cargas = {c.nombre: c for c in p.calcular_cargas().espacios}
    # Una categoría por espacio calculado, con el uso de las cargas.
    assert {c.espacio for c in r.categorias} == set(cargas)
    for c in r.categorias:
        assert c.uso == cargas[c.espacio].uso.nombre
    # Una válvula de control por unidad (4 + 2), en las unidades de cada circuito.
    valvulas = {x.equipo: x.cantidad for x in r.puntos if x.senal.startswith("Válvula")}
    assert valvulas == {"Unidades de Oficinas": 4, "Unidades de Nave": 2}
    # 2 tubos: frío y calor en el mismo generador → se citan las dos exigencias.
    consigna = next(x for x in r.puntos if x.senal.startswith("Consigna"))
    assert "1.2.4.3.1.7" in consigna.motivo and "1.2.4.3.1.6" in consigna.motivo
    # Válvulas: el Kv del sistema hidráulico se dimensiona con la pérdida de la unidad
    # (relación 1): es una exigencia incluida, no una verificación.
    valv = next(c for c in r.comprobaciones if c.requisito.startswith("Válvulas"))
    assert valv.resultado == "Incluida en la propuesta"
    assert "relación 1 en 2 circuitos" in valv.detalle
    # En pantalla: puntos por tipo, resultado del RITE y las tres pestañas llenas.
    texto = pc.resumen.text()
    assert "total" in texto and "exigencias del RITE incluidas en la propuesta" in texto
    assert "CUMPLE" not in texto
    assert pc.tabla_categorias.rowCount() == len(r.categorias)
    assert pc.tabla_puntos.rowCount() == len(r.puntos)
    assert pc.tabla_comprobaciones.rowCount() == len(r.comprobaciones)

    # Excel con todo.
    assert pc.a_excel.isEnabled()
    q.preparar("destino_excel", tmp_path / "Control")
    pc.a_excel.trigger()
    assert any("Guardado" in t for t in q.informaciones)
    wb = load_workbook(tmp_path / "Control.xlsx")
    assert wb.sheetnames == ["Resumen", "Categorías", "Puntos", "Comprobaciones", "Hipótesis"]
    filas = list(wb["Puntos"].iter_rows(min_row=2, values_only=True))
    assert len(filas) == len(r.puntos) and all(f[5] for f in filas)  # cada uno con su motivo
    resumen = {f[0]: f[1] for f in wb["Resumen"].iter_rows(min_row=2, values_only=True)}
    assert resumen["Total de puntos"] == sum(r.resumen.values())

    # Esquema de control (DXF) de la propuesta, con la secuencia de cada sistema.
    q.preparar("destino_dxf", tmp_path / "Esquema")
    pc.a_esquema.trigger()
    doc = ezdxf.readfile(tmp_path / "Esquema.dxf")
    textos = [e.dxf.text for e in doc.modelspace().query("TEXT")]
    assert textos.count("Secuencia de funcionamiento") == len(r.secuencias)
    assert any("1.2.4.3.1.7" in x for x in textos)


def test_esquema_desde_un_listado_del_usuario(ventana, tmp_path):  # noqa: F811
    """«Hay el qué pero no el cómo»: listado propio → esquema; lo que no entra, se dice."""
    v, q = ventana
    listado = tmp_path / "Puntos UTA.csv"
    listado.write_text(
        "Equipo;Señal;Tipo\nUTA-1;Orden de marcha;DO\nUTA-1;Temperatura retorno;AI\n"
        "UTA-1;Compuerta;ZZ\n",
        encoding="utf-8",
    )
    q.preparar("ficheros", [listado])
    q.preparar("destino_dxf", tmp_path / "UTA")
    v.pagina_control.a_listado.trigger()
    assert q.avisos == []
    assert any("Fila 4: tipo «ZZ» no reconocido" in t for t in q.informaciones)
    textos = [e.dxf.text for e in ezdxf.readfile(tmp_path / "UTA.dxf").modelspace().query("TEXT")]
    assert "Temperatura retorno" in textos and "Compuerta" not in textos
    assert any("Puntos UTA.csv" in x for x in textos)  # de dónde salen, en la leyenda
    # Un fichero que no es un listado de puntos: aviso, sin error.
    otro = tmp_path / "otro.csv"
    otro.write_text("Partida;Importe\nFancoil;1200\n", encoding="utf-8")
    q.preparar("ficheros", [otro])
    q.preparar("destino_dxf", tmp_path / "Otro")
    v.pagina_control.a_listado.trigger()
    assert any("fila de títulos" in x for x in q.avisos)
    assert not any(t.startswith("Error en") for t in q.titulos)


def test_unidad_sin_perdida_no_cumple(ventana):  # noqa: F811
    """El sistema hidráulico admite 0 kPa en la unidad, y entonces su válvula no se puede
    dimensionar (Kv 0): NO CUMPLE en el flujo real, en pantalla y con el circuito."""
    v, _ = ventana
    _sistema(v.proyecto, perdidas_kpa=(15.0, 0.0))
    v.ir_a_paso("control")
    r = v.proyecto.propuesta_control().resultado
    valv = next(c for c in r.comprobaciones if c.requisito.startswith("Válvulas"))
    assert valv.resultado == "NO CUMPLE" and "Nave" in valv.detalle
    assert "NO CUMPLE: Válvulas de control" in v.pagina_control.resumen.text()


def test_solo_se_calcula_con_la_pagina_a_la_vista(ventana, monkeypatch):  # noqa: F811
    """La ventana refresca todas las páginas a cada cambio: el control (cargas, redes y
    sistemas) no se recalcula si no se está mirando."""
    v, _ = ventana
    llamadas = []
    original = v.proyecto.propuesta_control
    monkeypatch.setattr(v.proyecto, "propuesta_control", lambda: llamadas.append(1) or original())
    v.ir_a_paso("documentacion")
    v.refrescar()
    assert llamadas == []
    v.ir_a_paso("control")
    assert llamadas == [1]
    # A la vista, cada cambio la recalcula.
    v.refrescar()
    assert llamadas == [1, 1]
