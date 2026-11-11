"""Parte 2 del control: listado de puntos del usuario y esquema DXF (docs/modules/control.md).

Los listados son inventados para la prueba (estructura habitual de un listado de puntos:
título, fila de títulos, una fila por señal).
"""

from __future__ import annotations

import ezdxf
import pytest
from openpyxl import Workbook

from traza.engines import control as mc
from traza.io import esquema_control_dxf, puntos_control


def _xlsx(ruta, filas):
    wb = Workbook()
    ws = wb.active
    for f in filas:
        ws.append(f)
    wb.save(ruta)
    return ruta


def test_listado_con_titulos_debajo_de_un_encabezado(tmp_path):
    ruta = _xlsx(
        tmp_path / "puntos.xlsx",
        [
            ["LISTADO DE PUNTOS - CLIMATIZACIÓN"],
            [],
            ["Sistema", "Equipo", "Descripción", "Tipo de señal", "Cantidad"],
            ["UTA-1", "Ventilador impulsión", "Orden de marcha", "DO", 1],
            ["UTA-1", "Ventilador impulsión", "Estado", "di", None],
            ["UTA-1", "Batería", "Válvula de 3 vías", "AO", 1],
            [None, None, None, None, None],
            ["Zonas", "Fancoils", "Temperatura ambiente", "AI", 12],
            ["Zonas", "Fancoils", "Ventilador", "XX", 1],
            ["Zonas", "Fancoils", "Presencia", "ED", 2.5],
        ],
    )
    puntos, avisos = puntos_control.leer(ruta)
    assert [(p.equipo, p.senal, p.tipo, p.cantidad) for p in puntos] == [
        ("Ventilador impulsión", "Orden de marcha", "SD", 1),
        ("Ventilador impulsión", "Estado", "ED", 1),  # sin cantidad: 1
        ("Batería", "Válvula de 3 vías", "SA", 1),
        ("Fancoils", "Temperatura ambiente", "EA", 12),
    ]
    assert puntos[0].sistema == "UTA-1" and puntos[0].motivo == "Listado del usuario, fila 4"
    # Lo que no se entiende no se adivina: se dice, con su fila.
    assert avisos == [
        "Fila 9: tipo «XX» no reconocido; no entra en el esquema.",
        "Fila 10: cantidad «2,5» no es un entero ≥ 1; no entra.",
    ]


def test_listado_csv_sin_sistema_ni_equipo(tmp_path):
    ruta = tmp_path / "puntos.csv"
    ruta.write_text("Señal;E/S\nAlarma enfriadora;ED\nConsigna impulsión;SA\n", encoding="utf-8")
    puntos, avisos = puntos_control.leer(ruta)
    assert avisos == []
    assert {(p.sistema, p.equipo) for p in puntos} == {("Listado", "Sin equipo")}
    assert [p.tipo for p in puntos] == ["ED", "SA"]


def test_listado_sin_columnas_de_senal_y_tipo(tmp_path):
    ruta = _xlsx(tmp_path / "otro.xlsx", [["Partida", "Importe"], ["Fancoil", 1200]])
    with pytest.raises(puntos_control.ListadoNoLegible, match="fila de títulos"):
        puntos_control.leer(ruta)


def test_esquema_dxf_r2013_con_simbolos_controlador_y_secuencia(tmp_path):
    puntos = [
        mc.Punto("Red IMP", "Ventilador de impulsión", "Orden de marcha", "SD", 1, ""),
        mc.Punto("Red IMP", "Ventilador de impulsión", "Estado (en marcha)", "ED", 1, ""),
        mc.Punto("Red IMP", "Filtros", "Colmatación (presostato diferencial)", "ED", 1, ""),
        mc.Punto("Clima", "Unidades de A", "Válvula de control", "SA", 4, ""),
    ]
    sec = {"Red IMP": ["Marcha y paro por horario (RITE IT 1.2.4.3.1.4)."]}
    ruta = esquema_control_dxf.escribir(
        tmp_path / "esquema", "Nave", puntos, sec, "control:esquema", "prueba"
    )
    assert ruta.suffix == ".dxf"
    doc = ezdxf.readfile(ruta)
    assert doc.dxfversion == "AC1027"  # AutoCAD 2013 (entorno del usuario)
    msp = doc.modelspace()
    textos = [e.dxf.text for e in msp.query("TEXT")]
    # Dos bandas, cada una con su controlador y su recuento.
    assert "Nave · Red IMP" in textos and "Nave · Clima" in textos
    assert textos.count("Controlador") == 2
    assert "ED: 2" in textos and "SA: 4" in textos
    # Entradas en círculo (2 de la red), salidas en cuadrado; cantidad en la línea.
    assert len([c for c in msp.query("CIRCLE") if c.dxf.layer == "TRAZA-C-SIMBOLOS"]) == 2
    assert "SA ×4" in textos and "ΔP" in textos
    # Línea de trazos de cada señal al controlador.
    trazos = [e for e in msp.query("LWPOLYLINE") if e.dxf.get("linetype") == "DASHED"]
    assert len(trazos) == len(puntos)
    # Secuencia solo en la banda que la tiene.
    assert textos.count("Secuencia de funcionamiento") == 1
    assert any("1.2.4.3.1.4" in t for t in textos)


def test_sin_puntos_no_hay_esquema(tmp_path):
    with pytest.raises(ValueError, match="No hay puntos"):
        esquema_control_dxf.escribir(tmp_path / "x", "Nave", [], None, "id", "prueba")
