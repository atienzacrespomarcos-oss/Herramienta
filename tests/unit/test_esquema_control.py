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


# --- Revisión del 11-11-2026 ------------------------------------------------------------


def test_numero_de_fila_no_es_la_cantidad_y_prioridad_de_columnas(tmp_path):
    """«Nº» numera las filas: no es la cantidad. «Tipo de equipo» no es el tipo de la señal.
    Con «Descripción» y «Señal», gana «Señal» aunque esté a la derecha. Los saltos de línea
    de una celda (Alt+Intro) se quedan en una línea."""
    ruta = _xlsx(
        tmp_path / "puntos.xlsx",
        [
            ["Nº", "Tipo de equipo", "Descripción", "Señal", "E/S"],
            [1, "UTA", "Climatizadora planta 1", "Orden de\nmarcha", "SD"],
            [2, "UTA", "Climatizadora planta 1", "Temperatura impulsión", "EA"],
            [3, "UTA", "Climatizadora planta 1", "Válvula batería", "SA"],
        ],
    )
    puntos, avisos = puntos_control.leer(ruta)
    assert avisos == []
    assert [(p.senal, p.tipo, p.cantidad) for p in puntos] == [
        ("Orden de marcha", "SD", 1),
        ("Temperatura impulsión", "EA", 1),
        ("Válvula batería", "SA", 1),
    ]


def test_listado_en_la_segunda_hoja_y_csv_con_cantidad(tmp_path):
    wb = Workbook()
    wb.active.title = "Portada"
    wb.active.append(["Proyecto de climatización"])
    ws = wb.create_sheet("Puntos")
    ws.append(["Equipo", "Señal", "Tipo", "Cantidad"])
    ws.append(["Fancoils", "Temperatura ambiente", "EA", 12])
    wb.save(tmp_path / "libro.xlsx")
    puntos, _ = puntos_control.leer(tmp_path / "libro.xlsx")
    assert [(p.equipo, p.cantidad) for p in puntos] == [("Fancoils", 12)]
    csv = tmp_path / "p.csv"
    csv.write_text("Señal;Tipo;Uds\nVálvula fancoil;AO;8\n", encoding="utf-8")
    (p,) = puntos_control.leer(csv)[0]
    assert (p.tipo, p.cantidad) == ("SA", 8)


def test_simbolos_alarma_y_marcha_antes_que_la_magnitud_o_el_equipo():
    assert mc.simbolo("Alarma temperatura alta", "ED") == "F"
    assert mc.simbolo("Fallo sonda temperatura", "ED") == "F"
    assert mc.simbolo("Orden de marcha del variador", "SD") == "M"
    assert mc.simbolo("Heat recovery status", "EA") == "EA"  # «cov» no casa en «recovery»


def test_controlador_con_pocas_senales_y_textos_largos(tmp_path):
    """Con una sola señal el recuento cabe en la caja del controlador; una señal larga va en
    dos líneas que no llegan a la línea de trazos; el nombre largo del equipo entero."""
    largo = "Temperatura de retorno del agua del circuito secundario de climatización " * 2
    equipo = "Climatizadora de tratamiento de aire primario de la nave de producción norte"
    puntos = [mc.Punto("S", equipo, largo.strip(), "EA", 1, "")]
    ruta = esquema_control_dxf.escribir(tmp_path / "e", "N", puntos, None, "id", "prueba")
    doc = ezdxf.readfile(ruta)
    assert "DASHED" in doc.linetypes
    msp = doc.modelspace()
    caja = next(e for e in msp.query("LWPOLYLINE") if e.dxf.layer == "TRAZA-C-CONTROLADOR")
    ys = [p[1] for p in caja.get_points()]
    recuento = [e for e in msp.query("TEXT") if e.dxf.text.startswith(("ED:", "SD:", "EA:", "SA:"))]
    assert len(recuento) == 4
    for e in recuento:
        assert min(ys) < e.dxf.align_point[1] < max(ys), e.dxf.text
    # Señal en dos líneas, ninguna más larga que LARGO_SENAL, sin llegar a los trazos.
    senal = [
        e.dxf.text
        for e in msp.query("TEXT")
        if e.dxf.layer == "TRAZA-C-TEXTOS" and e.dxf.text != "N · S"
    ]
    assert len(senal) == 2 and all(len(s) <= esquema_control_dxf.LARGO_SENAL for s in senal)
    # El nombre del equipo, entero (en varias líneas).
    nombre = " ".join(e.dxf.text for e in msp.query("TEXT") if e.dxf.layer == "TRAZA-C-EQUIPOS")
    assert nombre == equipo
