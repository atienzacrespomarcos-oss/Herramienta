"""Paso «Planos» en el proyecto: leer un DXF con capas elegidas, confirmar espacios y
obstáculos, alturas por nivel con excepciones, bloques por espacio y longitudes por capa.

Nave de prueba (en mm, como suelen venir los planos de arquitectura):
- ALMACÉN 40 x 25 m; OFICINAS 10 x 8 m con un lado en semicírculo hacia fuera (radio 4 m).
- Pilares: dos circulares de radio 0,25 m y uno cuadrado de 0,4 m.
- Difusores (bloque DIFUSOR): 3 en el almacén, 2 en oficinas, 1 fuera.
- Conductos: 12 m de LINE en la capa M-CONDUCTOS.
"""

from __future__ import annotations

import json
import math

import ezdxf
import pytest
from openpyxl import load_workbook

from traza.app.ordenes import (
    Aprobar,
    BorrarPropiedad,
    CrearElemento,
    CrearNivel,
    CrearPendiente,
    FijarAlturaEspacio,
    FijarPropiedad,
    OrdenRechazada,
    QuitarDePlano,
    RecuperarPropuesta,
)
from traza.core.procedencia import Origen, Procedencia

SUP_OFICINAS = 80 + math.pi * 16 / 2


def _nave(tmp_path):
    doc = ezdxf.new("R2013")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    for capa in ("A-ESPACIOS", "A-TEXTOS", "E-PILARES", "M-DIFUSORES", "M-CONDUCTOS", "COTAS"):
        doc.layers.add(capa)
    esp = {"layer": "A-ESPACIOS"}
    msp.add_lwpolyline([(0, 0), (40000, 0), (40000, 25000), (0, 25000)], close=True, dxfattribs=esp)
    msp.add_lwpolyline(
        [
            (40000, 0, 0, 0, 0),
            (50000, 0, 0, 0, 1.0),
            (50000, 8000, 0, 0, 0),
            (40000, 8000, 0, 0, 0),
        ],
        format="xyseb",
        close=True,
        dxfattribs=esp,
    )
    msp.add_lwpolyline(
        [(0, 30000), (2000, 32000), (2000, 30000), (0, 32000)], close=True, dxfattribs=esp
    )
    msp.add_text("ALMACÉN", dxfattribs={"layer": "A-TEXTOS", "height": 500}).set_placement(
        (20000, 12000)
    )
    msp.add_text("OFICINAS", dxfattribs={"layer": "A-TEXTOS", "height": 300}).set_placement(
        (45000, 4000)
    )
    msp.add_text("12,5 m", dxfattribs={"layer": "COTAS", "height": 200}).set_placement(
        (20000, 13000)
    )
    pil = {"layer": "E-PILARES"}
    msp.add_circle((10000, 10000), 250, dxfattribs=pil)
    msp.add_circle((30000, 10000), 250, dxfattribs=pil)
    msp.add_lwpolyline(
        [(20000, 20000), (20400, 20000), (20400, 20400), (20000, 20400)], close=True, dxfattribs=pil
    )
    doc.blocks.new("DIFUSOR").add_circle((0, 0), 300)
    for x, y in (
        (5000, 5000),
        (15000, 5000),
        (25000, 5000),
        (44000, 2000),
        (52000, 4000),
        (60000, 60000),
    ):
        msp.add_blockref("DIFUSOR", (x, y), dxfattribs={"layer": "M-DIFUSORES"})
    msp.add_line((0, -1000), (12000, -1000), dxfattribs={"layer": "M-CONDUCTOS"})
    ruta = tmp_path / "Nave.dxf"
    doc.saveas(ruta)
    return ruta
    # (52000, 4000) cae dentro del semicírculo de oficinas: centro (50000, 4000), radio 4 m.


@pytest.fixture
def plano(proyecto, tmp_path):
    doc_id = proyecto.incorporar_documento(_nave(tmp_path))
    plano_id = proyecto.leer_plano(doc_id, "mm", ["A-ESPACIOS"], ["E-PILARES"], ["A-TEXTOS"])
    nivel = CrearNivel("Planta baja", 0.0, 9.5)
    proyecto.ejecutar(nivel)
    return proyecto, plano_id, nivel.id, doc_id


def _por_nombre(propuestas):
    return {(p.nombre_sugerido.texto if p.nombre_sugerido else p.handle): p for p in propuestas}


def test_propuestas_con_superficie_y_nombre_del_plano(plano):
    p, plano_id, _, _ = plano
    props = p.propuestas(plano_id)
    espacios = [x for x in props if x.rol == "espacio"]
    obstaculos = [x for x in props if x.rol == "obstaculo"]
    assert len(espacios) == 3 and len(obstaculos) == 3
    por = _por_nombre(espacios)
    assert por["ALMACÉN"].superficie == pytest.approx(1000)
    assert por["OFICINAS"].superficie == pytest.approx(SUP_OFICINAS)
    # El texto de cota no es de la capa de nombres: no se propone como nombre.
    assert [t.texto for t in por["ALMACÉN"].textos] == ["ALMACÉN"]
    corbata = next(x for x in espacios if x.autointersecante)
    assert corbata.nombre_sugerido is None
    assert sorted(round(x.superficie, 4) for x in obstaculos) == sorted(
        [round(math.pi * 0.0625, 4)] * 2 + [0.16]
    )


def test_confirmar_espacio_con_procedencia(plano):
    p, plano_id, nivel_id, doc_id = plano
    almacen = _por_nombre(p.propuestas(plano_id))["ALMACÉN"]
    texto = almacen.nombre_sugerido
    eid = p.confirmar_contorno(plano_id, almacen.handle, nivel_id, texto_handle=texto.handle)
    props = {x["clave"]: x for x in p.propiedades(eid)}
    # Nombre: del texto del plano, citado.
    assert props["nombre"]["valor"] == "ALMACÉN" and props["nombre"]["origen"] == "documento"
    assert props["nombre"]["documento_id"] == doc_id
    assert texto.handle in props["nombre"]["localizador"]
    # Superficie y perímetro: cálculo exacto, con su registro.
    assert props["superficie"]["origen"] == "calculo" and props["superficie"][
        "valor"
    ] == pytest.approx(1000)
    assert props["perimetro"]["valor"] == pytest.approx(130)
    reg = p._filas(
        "SELECT * FROM registro_calculo WHERE id = ?", (props["superficie"]["registro_calculo_id"],)
    )[0]
    contenido = json.loads(reg["contenido"])
    assert (
        reg["motor"] == "geometria.contorno" and contenido["entradas"]["handle"] == almacen.handle
    )
    assert contenido["entradas"]["unidad_dibujo"] == "mm" and contenido["aproximaciones"] == []
    [e] = p.espacios()
    assert e["codigo"] == "ESP-001" and e["nivel_nombre"] == "Planta baja"
    # Ya no se propone.
    assert almacen.handle not in {x.handle for x in p.propuestas(plano_id)}


def test_altura_heredada_del_nivel_y_excepcion(plano):
    p, plano_id, nivel_id, _ = plano
    por = _por_nombre(p.propuestas(plano_id))
    a = p.confirmar_contorno(plano_id, por["ALMACÉN"].handle, nivel_id, nombre="Almacén")
    o = p.confirmar_contorno(plano_id, por["OFICINAS"].handle, nivel_id, nombre="Oficinas")
    p.ejecutar(FijarPropiedad(o, "altura_libre", 3.0, "m", Procedencia(Origen.USUARIO)))
    alturas = {e["nombre"]: (e["altura"], e["altura_origen"]) for e in p.espacios()}
    assert alturas == {"Almacén": (9.5, "del nivel"), "Oficinas": (3.0, "propia")}
    nombre = {x["clave"]: x for x in p.propiedades(a)}["nombre"]
    assert nombre["origen"] == "usuario"  # escrito por el usuario, no del plano


def test_obstaculos_con_y_sin_altura(plano):
    p, plano_id, nivel_id, _ = plano
    pilares = [x for x in p.propuestas(plano_id) if x.rol == "obstaculo"]
    p.confirmar_contorno(plano_id, pilares[0].handle, nivel_id, nombre="Pilar")
    p.confirmar_contorno(plano_id, pilares[1].handle, nivel_id, altura=2.5, cota_inferior=0)
    obs = p.obstaculos()
    assert [(x["altura"], x["altura_origen"]) for x in obs] == [(9.5, "del nivel"), (2.5, "propia")]
    assert obs[1]["cota_inferior"] == 0


def test_contorno_que_se_corta_no_se_confirma(plano):
    p, plano_id, nivel_id, _ = plano
    corbata = next(x for x in p.propuestas(plano_id) if x.autointersecante)
    with pytest.raises(OrdenRechazada, match="se corta a sí mismo"):
        p.confirmar_contorno(plano_id, corbata.handle, nivel_id, nombre="X")


def test_espacio_sin_nombre_y_texto_que_no_esta_dentro(plano):
    p, plano_id, nivel_id, _ = plano
    por = _por_nombre(p.propuestas(plano_id))
    with pytest.raises(OrdenRechazada, match="necesita un nombre"):
        p.confirmar_contorno(plano_id, por["ALMACÉN"].handle, nivel_id)
    with pytest.raises(OrdenRechazada, match="no está dentro"):
        p.confirmar_contorno(
            plano_id, por["ALMACÉN"].handle, nivel_id, texto_handle=por["OFICINAS"].textos[0].handle
        )


def test_descartar_y_recuperar(plano):
    p, plano_id, nivel_id, _ = plano
    corbata = next(x for x in p.propuestas(plano_id) if x.autointersecante)
    p.descartar_propuesta(plano_id, corbata.handle)
    assert corbata.handle not in {x.handle for x in p.propuestas(plano_id)}
    with pytest.raises(OrdenRechazada, match="no está entre las propuestas"):
        p.confirmar_contorno(plano_id, corbata.handle, nivel_id, nombre="X")
    p.ejecutar(RecuperarPropuesta(plano_id, corbata.handle))
    assert corbata.handle in {x.handle for x in p.propuestas(plano_id)}


def test_bloques_por_espacio_y_longitudes(plano):
    p, plano_id, nivel_id, _ = plano
    por = _por_nombre(p.propuestas(plano_id))
    p.confirmar_contorno(
        plano_id, por["ALMACÉN"].handle, nivel_id, texto_handle=por["ALMACÉN"].textos[0].handle
    )
    p.confirmar_contorno(
        plano_id, por["OFICINAS"].handle, nivel_id, texto_handle=por["OFICINAS"].textos[0].handle
    )
    b = p.bloques_por_espacio(plano_id)
    cuenta = {f.espacio: f.cantidad for f in b.filas}
    # El de (52000, 4000) está en el semicírculo de oficinas: cuenta en oficinas.
    assert cuenta == {
        "ESP-001 ALMACÉN": 3,
        "ESP-002 OFICINAS": 2,
        "Fuera de los espacios confirmados": 1,
    }
    longitudes = {f.capa: f.longitud_m for f in p.longitudes_por_capa(plano_id)}
    assert longitudes["M-CONDUCTOS"] == pytest.approx(12)


def test_excel_del_plano(plano, tmp_path):
    p, plano_id, nivel_id, _ = plano
    por = _por_nombre(p.propuestas(plano_id))
    p.confirmar_contorno(
        plano_id, por["OFICINAS"].handle, nivel_id, texto_handle=por["OFICINAS"].textos[0].handle
    )
    ruta = p.exportar_plano_excel(plano_id, tmp_path / "plano")
    wb = load_workbook(ruta)
    assert wb.sheetnames == [
        "Espacios",
        "Obstáculos",
        "Bloques",
        "Longitudes por capa",
        "Información",
    ]
    fila = [c.value for c in wb["Espacios"][2]]
    assert fila[:4] == ["ESP-001", "OFICINAS", "Planta baja", pytest.approx(SUP_OFICINAS)]
    assert fila[5:7] == [9.5, "del nivel"] and fila[7] is None  # vacío = no consta
    info = {r[0].value: r[1].value for r in wb["Información"].iter_rows(min_row=2)}
    assert info["Unidad del dibujo (confirmada)"] == "mm"


def test_leer_plano_rechaza_capas_que_no_existen_o_repetidas(proyecto, tmp_path):
    doc_id = proyecto.incorporar_documento(_nave(tmp_path))
    with pytest.raises(OrdenRechazada, match="no tiene la capa «NO-EXISTE»"):
        proyecto.leer_plano(doc_id, "mm", ["NO-EXISTE"], [])
    with pytest.raises(OrdenRechazada, match="a la vez de espacios y de obstáculos"):
        proyecto.leer_plano(doc_id, "mm", ["A-ESPACIOS"], ["A-ESPACIOS"])
    with pytest.raises(OrdenRechazada, match="Unidad"):
        proyecto.leer_plano(doc_id, "pulgadas", ["A-ESPACIOS"], [])
    proyecto.leer_plano(doc_id, "mm", ["A-ESPACIOS"], [])
    with pytest.raises(OrdenRechazada, match="ya está leído"):
        proyecto.leer_plano(doc_id, "mm", ["A-ESPACIOS"], [])


def test_no_dxf_se_rechaza(proyecto, pdf_3_paginas):
    doc_id = proyecto.incorporar_documento(pdf_3_paginas)
    with pytest.raises(OrdenRechazada, match="no es un DXF"):
        proyecto.leer_plano(doc_id, "mm", ["A"], [])


def test_unidad_no_cambia_con_geometria_confirmada(plano):
    p, plano_id, nivel_id, _ = plano
    por = _por_nombre(p.propuestas(plano_id))
    eid = p.confirmar_contorno(plano_id, por["ALMACÉN"].handle, nivel_id, nombre="A")
    with pytest.raises(OrdenRechazada, match="confirmados con la unidad «mm»"):
        p.cambiar_plano(plano_id, "m", ["A-ESPACIOS"], ["E-PILARES"], ["A-TEXTOS"])
    p.ejecutar(QuitarDePlano(eid))
    p.cambiar_plano(plano_id, "m", ["A-ESPACIOS"], ["E-PILARES"], ["A-TEXTOS"])
    assert p.plano(plano_id)["unidad"] == "m"


def test_quitar_deshacer_y_rehacer(plano):
    p, plano_id, nivel_id, _ = plano
    por = _por_nombre(p.propuestas(plano_id))
    handle = por["ALMACÉN"].handle
    eid = p.confirmar_contorno(plano_id, handle, nivel_id, nombre="A")
    with pytest.raises(OrdenRechazada, match="tiene 1 espacio"):
        p.ejecutar(QuitarDePlano(nivel_id))
    p.ejecutar(QuitarDePlano(eid))
    assert p.espacios() == [] and handle in {x.handle for x in p.propuestas(plano_id)}
    assert p.deshacer() == "QuitarDePlano"
    assert [e["id"] for e in p.espacios()] == [eid]
    # Deshacer la confirmación quita la geometría y el registro de cálculo; rehacerla los
    # repone igual (orden compuesta, con claves foráneas).
    assert p.deshacer() == "ConfirmarContorno"
    assert p.espacios() == [] and handle in {x.handle for x in p.propuestas(plano_id)}
    assert p._filas("SELECT count(*) AS n FROM registro_calculo")[0]["n"] == 0
    assert p._filas("SELECT count(*) AS n FROM geometria")[0]["n"] == 0
    assert p.rehacer() == "ConfirmarContorno"
    [e] = p.espacios()
    assert e["id"] == eid and e["handle"] == handle and e["superficie"] == pytest.approx(1000)


def test_codigos_de_nivel_y_cota_negativa(proyecto):
    s = CrearNivel("Sótano", -3.5, 3.0)
    proyecto.ejecutar(s)
    proyecto.ejecutar(CrearNivel("Planta baja", 0, 9))
    assert [(n["codigo"], n["nombre"], n["cota"]) for n in proyecto.niveles()] == [
        ("NIV-01", "Sótano", -3.5),
        ("NIV-02", "Planta baja", 0),
    ]
    with pytest.raises(OrdenRechazada):
        proyecto.ejecutar(CrearNivel("X", 0, 0))
    with pytest.raises(OrdenRechazada):
        proyecto.ejecutar(CrearNivel("  ", 0, 3))


# --- Revisión independiente del bloque B (07-11-2026) --------------------------------------


def test_excel_no_convierte_en_formula_ninguna_fila(plano, tmp_path):
    p, plano_id, nivel_id, _ = plano
    por = _por_nombre(p.propuestas(plano_id))
    p.confirmar_contorno(plano_id, por["ALMACÉN"].handle, nivel_id, nombre="=HIPERVINCULO(1)")
    p.confirmar_contorno(plano_id, por["OFICINAS"].handle, nivel_id, nombre="Oficinas")
    ws = load_workbook(p.exportar_plano_excel(plano_id, tmp_path / "x.xlsx"))["Espacios"]
    celda = ws.cell(row=2, column=2)  # no es la última fila
    assert celda.value == "=HIPERVINCULO(1)" and celda.data_type == "s"


def test_lo_aprobado_no_cambia_por_su_nivel_ni_se_quita(plano):
    from traza.app.proyecto import ElementoBloqueado

    p, plano_id, nivel_id, _ = plano
    por = _por_nombre(p.propuestas(plano_id))
    eid = p.confirmar_contorno(plano_id, por["ALMACÉN"].handle, nivel_id, nombre="A")
    p.ejecutar(Aprobar(eid, "Medido y revisado"))
    # Cambiar la altura del nivel cambiaría la del espacio aprobado, que la hereda.
    with pytest.raises(ElementoBloqueado, match="ESP-001"):
        p.ejecutar(FijarPropiedad(nivel_id, "altura_libre", 8.0, "m", Procedencia(Origen.USUARIO)))
    with pytest.raises(OrdenRechazada, match="ESP-001» está aprobado"):
        p.ejecutar(QuitarDePlano(eid))
    # Nivel aprobado: no se le quitan ni se le añaden espacios.
    otro = p.confirmar_contorno(plano_id, por["OFICINAS"].handle, nivel_id, nombre="O")
    p.ejecutar(Aprobar(nivel_id, "Cotas del proyecto"))
    with pytest.raises(ElementoBloqueado, match="NIV-01"):
        p.ejecutar(QuitarDePlano(otro))
    pilar = next(x for x in p.propuestas(plano_id) if x.rol == "obstaculo")
    with pytest.raises(ElementoBloqueado, match="NIV-01"):
        p.confirmar_contorno(plano_id, pilar.handle, nivel_id)


def test_superficie_calculada_no_se_pisa_ni_se_borra(plano):
    p, plano_id, nivel_id, _ = plano
    eid = p.confirmar_contorno(
        plano_id, _por_nombre(p.propuestas(plano_id))["ALMACÉN"].handle, nivel_id, nombre="A"
    )
    with pytest.raises(OrdenRechazada, match="resultado de cálculo"):
        p.ejecutar(FijarPropiedad(eid, "superficie", 500, "m**2", Procedencia(Origen.USUARIO)))
    with pytest.raises(OrdenRechazada, match="resultado de cálculo"):
        p.ejecutar(BorrarPropiedad(eid, "perimetro"))


def test_altura_por_modos(plano):
    p, plano_id, nivel_id, _ = plano
    eid = p.confirmar_contorno(
        plano_id, _por_nombre(p.propuestas(plano_id))["ALMACÉN"].handle, nivel_id, nombre="A"
    )
    p.ejecutar(FijarAlturaEspacio(eid, "inclinada", minima=6.0, maxima=10.5))
    [e] = p.espacios()
    assert (e["altura"], e["altura_origen"], e["altura_minima"], e["altura_maxima"]) == (
        None,
        "inclinada",
        6.0,
        10.5,
    )
    p.ejecutar(FijarAlturaEspacio(eid, "propia", altura=7.0))
    [e] = p.espacios()
    assert (e["altura"], e["altura_origen"], e["altura_minima"]) == (7.0, "propia", None)
    p.ejecutar(FijarAlturaEspacio(eid, "nivel"))
    [e] = p.espacios()
    assert (e["altura"], e["altura_origen"]) == (9.5, "del nivel")
    with pytest.raises(OrdenRechazada, match="menor que la máxima"):
        p.ejecutar(FijarAlturaEspacio(eid, "inclinada", minima=8.0, maxima=8.0))
    with pytest.raises(OrdenRechazada, match="mayor que 0"):
        p.ejecutar(FijarPropiedad(eid, "altura_libre", 0, "m", Procedencia(Origen.USUARIO)))


def test_obstaculo_elevado_sin_altura_no_hereda(plano):
    p, plano_id, nivel_id, _ = plano
    cercha = next(x for x in p.propuestas(plano_id) if x.rol == "obstaculo")
    p.confirmar_contorno(plano_id, cercha.handle, nivel_id, nombre="Cercha", cota_inferior=6.0)
    [o] = p.obstaculos()
    assert (o["altura"], o["altura_origen"], o["cota_inferior"]) == (None, None, 6.0)


def test_tipos_de_plano_no_se_crean_por_otra_via(plano):
    p, plano_id, nivel_id, _ = plano
    with pytest.raises(OrdenRechazada, match="paso «Planos»"):
        p.ejecutar(CrearElemento("espacio", "X"))
    eid = p.confirmar_contorno(
        plano_id, _por_nombre(p.propuestas(plano_id))["ALMACÉN"].handle, nivel_id, nombre="A"
    )
    with pytest.raises(OrdenRechazada, match="no cuelga"):
        p.ejecutar(CrearElemento("equipo", "UTA-01", eid))


def test_descartar_solo_propuestas_y_quitar_con_pendientes(plano):
    p, plano_id, nivel_id, _ = plano
    with pytest.raises(OrdenRechazada, match="no está entre las propuestas"):
        p.descartar_propuesta(plano_id, "NOEXISTE")
    eid = p.confirmar_contorno(
        plano_id, _por_nombre(p.propuestas(plano_id))["ALMACÉN"].handle, nivel_id, nombre="A"
    )
    p.ejecutar(CrearPendiente("Falta la altura real del falso techo", eid))
    with pytest.raises(OrdenRechazada, match="1 pendientes"):
        p.ejecutar(QuitarDePlano(eid))


def test_capas_sin_distinguir_mayusculas(proyecto, tmp_path):
    doc_id = proyecto.incorporar_documento(_nave(tmp_path))
    plano_id = proyecto.leer_plano(doc_id, "mm", ["a-espacios"], [], ["A-Textos"])
    assert len([x for x in proyecto.propuestas(plano_id) if x.rol == "espacio"]) == 3
    assert _por_nombre(proyecto.propuestas(plano_id))["ALMACÉN"]
    with pytest.raises(OrdenRechazada, match="repetida"):
        proyecto.cambiar_plano(plano_id, "mm", ["A-ESPACIOS", "a-espacios"], [])
