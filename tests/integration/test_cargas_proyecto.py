"""Cargas y ventilación en el proyecto: clima de la guía del IDAE, uso por espacio,
fachadas automáticas con correcciones, cálculo y protección de lo aprobado.

La guía del IDAE no se reproduce (repositorio público): el lector se sustituye por una
estación INVENTADA. Nave de prueba en mm: ALMACÉN 40 × 25 m y OFICINAS 9,8 × 8 m
adosadas a su lado este con un muro de 0,2 m.
"""

from __future__ import annotations

import ezdxf
import pytest

from traza.app.cargas import PROPUESTA, USUARIO, uso_por_nombre
from traza.app.ordenes import Aprobar, CrearNivel, OrdenRechazada, QuitarDePlano
from traza.app.proyecto import ElementoBloqueado
from traza.io.clima_idae import EstacionIdae

ESTACION = EstacionIdae(
    provincia="Madrid", nombre="Ficticia", indicativo="0000", pagina=2, altitud_m=600,
    latitud=40.4, longitud=-3.7, ts_min=-8, ts_996=-4.5, ts_99=-3, omdc=11, hum_coin=80,
    oma=45, ts_max=41, ts_04=37, thc_04=20.5, ts_1=35.5, thc_1=20, ts_2=34, thc_2=19.5,
    omdr=15, th_04=22, tsc_04=33, th_1=21, tsc_1=32, th_2=20.5, tsc_2=31,
)  # fmt: skip


def _nave(tmp_path):
    doc = ezdxf.new("R2013")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    for capa in ("A-ESPACIOS", "A-TEXTOS"):
        doc.layers.add(capa)
    esp = {"layer": "A-ESPACIOS"}
    msp.add_lwpolyline([(0, 0), (40000, 0), (40000, 25000), (0, 25000)], close=True, dxfattribs=esp)
    msp.add_lwpolyline(
        [(40200, 0), (50000, 0), (50000, 8000), (40200, 8000)], close=True, dxfattribs=esp
    )
    for texto, xy in (("ALMACÉN", (20000, 12000)), ("OFICINAS", (45000, 4000))):
        msp.add_text(texto, dxfattribs={"layer": "A-TEXTOS", "height": 300}).set_placement(xy)
    ruta = tmp_path / "Nave.dxf"
    doc.saveas(ruta)
    return ruta


@pytest.fixture
def nave(proyecto, tmp_path, pdf_3_paginas):
    p = proyecto
    plano_id = p.leer_plano(p.incorporar_documento(_nave(tmp_path)), "mm", ["A-ESPACIOS"], [],
                            ["A-TEXTOS"])  # fmt: skip
    nivel = CrearNivel("Planta baja", 0.0, 8.0)
    p.ejecutar(nivel)
    ids = {}
    for prop in p.propuestas(plano_id):
        texto = prop.nombre_sugerido.texto
        ids[texto] = p.confirmar_contorno(plano_id, prop.handle, nivel.id, nombre=texto)
    guia = p.incorporar_documento(pdf_3_paginas)
    p.lector_guia = lambda ruta: [ESTACION]
    p.fijar_cargas(
        guia_documento_id=guia, estacion_pagina=2, provincia="Madrid", altitud_obra=650,
        tipo_construccion="nave_panel",
    )  # fmt: skip
    return p, ids, guia


def _por_codigo(r):
    return {e.nombre: e for e in r.espacios}


def test_calculo_completo_con_usos_propuestos_por_el_nombre(nave):
    p, ids, _ = nave
    r = p.calcular_cargas()
    assert r.zona == "D3" and r.estacion.pagina == 2
    # Obra 50 m por encima de la estación: −0,5 °C (IDAE, anexo 7.3).
    assert r.condiciones["normal"].verano_ts == pytest.approx(35.0)
    e = _por_codigo(r)
    alm, ofi = e["ALMACÉN"], e["OFICINAS"]
    assert (alm.uso.clave, alm.uso_origen) == ("almacen", PROPUESTA)
    assert ofi.uso.clave == "oficina_abierta"
    # Fachadas: el lado este del almacén lo tapan 8 m de oficinas (muro de 0,2 m).
    assert alm.fachadas_m == pytest.approx({"S": 40, "E": 17, "N": 40, "O": 25})
    assert "O" not in ofi.fachadas_m and ofi.fachadas_m["E"] == pytest.approx(8)
    # Una sola planta: cubierta y solera en los dos.
    nombres = {c.nombre for c in alm.cerramientos}
    assert {"Cubierta", "Solera", "Fachada S", "Huecos S"} <= nombres
    # Almacén: 50 m³/h por trabajador (RD 486), 3 personas/100 m² → 30 personas.
    assert alm.aire_exterior_m3h == pytest.approx(30 * 50)
    assert alm.invierno.total_w > 0 and alm.verano.total_w > 0 and alm.infiltracion_m3h > 0
    assert 1 <= r.hora_simultanea <= 24
    assert r.verano_simultaneo_w <= alm.verano.total_w + ofi.verano.total_w + 1e-6
    fuentes = {d.concepto: d for d in alm.datos}
    assert fuentes["Ocupación"].origen == PROPUESTA and "ASHRAE" in fuentes["Ocupación"].fuente
    assert "RD 486" in fuentes["Aire exterior"].fuente


def test_ajustes_y_correcciones_del_usuario_con_deshacer(nave):
    p, ids, _ = nave
    p.fijar_cargas_espacio(
        ids["OFICINAS"], "despacho", {"personas": 12, "huecos": 0.5}, {"O": True}
    )
    ofi = _por_codigo(p.calcular_cargas())["OFICINAS"]
    datos = {d.concepto: d for d in ofi.datos}
    assert (ofi.uso.clave, ofi.uso_origen) == ("despacho", USUARIO)
    assert datos["Ocupación"].valor == 12 and datos["Ocupación"].origen == USUARIO
    assert ofi.fachadas_m["O"] == pytest.approx(8)  # corregida: el muro da a la calle
    assert ofi.aire_exterior_m3h == pytest.approx(12 * 12.5 * 3.6)  # IDA 2
    p.deshacer()
    ofi = _por_codigo(p.calcular_cargas())["OFICINAS"]
    assert ofi.uso_origen == PROPUESTA and "O" not in ofi.fachadas_m


def test_sin_calefaccion_y_errores(nave):
    p, ids, guia = nave
    p.fijar_cargas_espacio(ids["ALMACÉN"], "almacen", {"sin_calefaccion": True})
    assert _por_codigo(p.calcular_cargas())["ALMACÉN"].invierno.total_w == 0
    with pytest.raises(OrdenRechazada, match="no es la ficha"):
        p.fijar_cargas(guia_documento_id=guia, estacion_pagina=3, provincia="Madrid",
                       altitud_obra=650, tipo_construccion="cte")  # fmt: skip
    with pytest.raises(OrdenRechazada, match="Provincia"):
        p.fijar_cargas(guia_documento_id=guia, estacion_pagina=2, provincia="Narnia",
                       altitud_obra=650, tipo_construccion="cte")  # fmt: skip
    with pytest.raises(OrdenRechazada, match="Uso no previsto"):
        p.fijar_cargas_espacio(ids["ALMACÉN"], "iglú")
    with pytest.raises(OrdenRechazada, match="negativos"):
        p.fijar_cargas_espacio(ids["ALMACÉN"], "almacen", {"personas": -1})
    with pytest.raises(OrdenRechazada, match="fracción"):
        p.fijar_cargas_espacio(ids["ALMACÉN"], "almacen", {"huecos": 1.5})
    with pytest.raises(OrdenRechazada, match="sin calefacción"):
        p.fijar_cargas_espacio(
            ids["ALMACÉN"], "almacen", {"sin_calefaccion": True, "t_invierno_c": 15}
        )


def test_sin_clima_no_se_calcula(proyecto):
    with pytest.raises(OrdenRechazada, match="guía del IDAE"):
        proyecto.calcular_cargas()


def test_aprobado_no_cambia_y_quitar_espacio_con_datos(nave):
    p, ids, _ = nave
    p.fijar_cargas_espacio(ids["OFICINAS"], "despacho")
    p.ejecutar(Aprobar(ids["ALMACÉN"], "Revisado"))
    with pytest.raises(ElementoBloqueado):
        p.fijar_cargas_espacio(ids["ALMACÉN"], "almacen")
    p.ejecutar(QuitarDePlano(ids["OFICINAS"]))
    assert ids["OFICINAS"] not in p.datos_cargas_espacios()
    p.deshacer()
    assert p.datos_cargas_espacios()[ids["OFICINAS"]]["uso"] == "despacho"


def test_uso_por_nombre_especifico_antes_que_general():
    assert uso_por_nombre("Cámara de congelación 2") == "camara_congelacion"
    assert uso_por_nombre("CAMARA FRIO") == "camara_refrigeracion"
    assert uso_por_nombre("Aseo vestuario") == "vestuarios"
    assert uso_por_nombre("Despacho dirección") == "despacho"
    assert uso_por_nombre("Zona X") is None


def test_ninguna_palabra_queda_tapada_por_una_anterior():
    from traza.app.cargas import PALABRAS_USO

    for i, (palabra, _) in enumerate(PALABRAS_USO):
        for anterior, _ in PALABRAS_USO[:i]:
            assert anterior not in palabra, f"«{anterior}» tapa a «{palabra}»"


def test_informe_excel_y_pdf(nave, tmp_path):
    import pymupdf
    from openpyxl import load_workbook

    p, ids, _ = nave
    p.fijar_cargas_espacio(ids["OFICINAS"], "despacho", {"personas": 4})
    x = p.exportar_cargas_excel(tmp_path / "Cargas 2.1")
    assert x.name == "Cargas 2.1.xlsx"
    wb = load_workbook(x)
    assert wb.sheetnames == ["Resumen", "Espacios", "Partidas", "Datos y fuentes",
                             "Cerramientos", "Hipótesis"]  # fmt: skip
    esp = list(wb["Espacios"].iter_rows(min_row=2, values_only=True))
    assert {f[1] for f in esp} == {"ALMACÉN", "OFICINAS"}
    assert all(isinstance(f[8], float) and f[8] > 0 for f in esp)  # números, no texto
    fuentes = list(wb["Datos y fuentes"].iter_rows(min_row=2, values_only=True))
    assert ("OFICINAS", "Ocupación", 4, "usuario") in {(f[1], f[2], f[3], f[5]) for f in fuentes}
    resumen = {f[0]: f[1] for f in wb["Resumen"].iter_rows(min_row=2, values_only=True)}
    assert resumen["Zona climática (CTE DB HE, Anejo B)"] == "D3"
    assert "p. 2" in resumen["Fuente del clima"]
    pdf = p.exportar_cargas_pdf(tmp_path / "Cargas")
    with pymupdf.open(pdf) as doc:
        texto = "".join(pg.get_text() for pg in doc)
    assert "Cargas térmicas y ventilación" in texto and "OFICINAS" in texto
    assert "Hipótesis, método y fuentes" in texto and "ASHRAE" in texto
