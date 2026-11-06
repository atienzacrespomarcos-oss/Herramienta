"""BC3 del presupuesto completo actualizado (FIEBDC-3/2024).

Lo esencial: lo que no se toca queda IDÉNTICO (descompuestos, textos, pliegos…), lo que se
toca es lo justo, y el fichero se relee igual que lo esperado.
"""

from __future__ import annotations

import pytest

from traza.app.ordenes import (
    AnadirPartidaNueva,
    CrearModificado,
    OrdenRechazada,
    VariarPartida,
)
from traza.io import bc3

# Original con: subcapítulo, partida con descompuesto (mano de obra y material), texto ~T,
# medición ~M con líneas, un código sinónimo, ~K y un registro de pliego (~L) que TRAZA no
# interpreta. Juego de caracteres 850 (DOS) para comprobar que se respeta.
ORIGINAL = (
    "~V|AUTOR|FIEBDC-3/2016|PROGRAMA||850|Contrato|2|\r\n"
    "~K|\\2\\2\\3\\2\\2\\2\\2\\EUR\\|0\\0\\0\\0\\21|\r\n"
    "~C|OBRA##||Nave climatizada|37244||0|\r\n"
    "~C|01#||Climatización|37244||0|\r\n"
    "~C|01.1#||Conductos y difusión|24364||0|\r\n"
    "~C|UTA01|ud|Unidad de tratamiento de aire|12880||0|\r\n"
    "~C|MO1|h|Oficial instalador|20||1|\r\n"
    "~C|MAT1|ud|UTA según pliego|12800||3|\r\n"
    "~C|CND01\\CND-ALT|m2|Conducto de chapa galvanizada|10||0|\r\n"
    "~C|REJ01|ud|Rejilla de impulsión con regulación|45.5||0|\r\n"
    "~T|UTA01|Unidad de tratamiento de aire de 2400 m3/h. Ventilación cañón.|\r\n"
    "~L|UTA01|Pliego de la UTA: no lo interpreta TRAZA.|\r\n"
    "~D|OBRA##|01#\\1\\1\\|\r\n"
    "~D|01#|UTA01\\1\\1\\01.1#\\1\\1\\|\r\n"
    "~D|UTA01|MO1\\1\\4\\MAT1\\1\\1\\|\r\n"
    "~D|01.1#|CND-ALT\\1\\2400\\REJ01\\1\\8\\|\r\n"
    "~M|01.1#\\CND01|1\\2\\1\\|2400|\\Tramo A\\1\\1500\\\\\\\\Tramo B\\1\\900\\\\\\|1.2.1|\r\n"
    "~M|01.1#\\REJ01|1\\2\\2\\|8||1.2.2|\r\n"
    "~M|01#\\UTA01|1\\1\\|1||1.1|\r\n"
)
OFERTA = (
    "~V|PROVEEDOR|FIEBDC-3/2016|PRUEBA||ANSI|Oferta|2|\n"
    "~C|OF##||Oferta|0||0|\n~C|EXT01|ud|Extractor helicoidal de cubierta|850||0|\n"
    "~C|UTA01|ud|Código que choca con la base|10||0|\n"
    "~D|OF##|EXT01\\1\\1\\UTA01\\1\\1\\|\n"
)


@pytest.fixture
def mod(proyecto, tmp_path):
    f = tmp_path / "Contrato.bc3"
    f.write_bytes(ORIGINAL.encode("cp850"))
    base = proyecto.leer_medicion(proyecto.incorporar_documento(f), "presupuesto")[0]
    g = tmp_path / "Oferta.bc3"
    g.write_bytes(OFERTA.encode("cp1252"))
    oferta = proyecto.leer_medicion(proyecto.incorporar_documento(g), "oferta")[0]
    o = CrearModificado(base, "Ampliación")
    proyecto.ejecutar(o)
    ids = {p["codigo"]: p["id"] for p in proyecto.partidas(base)}
    of = {p["codigo"]: p["id"] for p in proyecto.partidas(oferta)}
    return proyecto, o.id, ids, of, f


def test_bc3_actualizado_conserva_lo_que_no_toca_y_relee_igual(mod, tmp_path):
    p, m, ids, of, original = mod
    p.ejecutar(VariarPartida(m, ids["CND01"], 2600, "medicion", "Faltaba el tramo C"))
    p.ejecutar(VariarPartida(m, ids["REJ01"], 0, "economica", "Se sustituyen"))
    p.ejecutar(AnadirPartidaNueva(m, of["EXT01"], 2, "economica", "Extractor"))
    p.ejecutar(AnadirPartidaNueva(m, of["UTA01"], 1, "diseno", "Choque de código"))
    ruta, avisos = p.exportar_modificado_bc3(m, tmp_path / "Modificado 1")
    assert ruta.name == "Modificado 1.bc3"

    texto = ruta.read_bytes().decode("cp850")
    original_txt = original.read_bytes().decode("cp850")
    # Registros que no se tocan: idénticos (descompuesto, texto, pliego, ~K…).
    for intacto in (
        "~K|\\2\\2\\3\\2\\2\\2\\2\\EUR\\|0\\0\\0\\0\\21|",
        "~D|UTA01|MO1\\1\\4\\MAT1\\1\\1\\|",
        "~T|UTA01|Unidad de tratamiento de aire de 2400 m3/h. Ventilación cañón.|",
        "~L|UTA01|Pliego de la UTA: no lo interpreta TRAZA.|",
        "~C|MAT1|ud|UTA según pliego|12800||3|",
        "~M|01#\\UTA01|1\\1\\|1||1.1|",
    ):
        assert intacto in original_txt and intacto in texto

    b = bc3.leer_bc3(ruta)
    r = bc3.leer_partidas(b)
    cant = {x.codigo: x.cantidad for x in r.partidas}
    assert cant["CND01"] == 2600 and cant["REJ01"] is None  # 0 = anulada (pág. 2)
    assert cant["UTA01"] == 1
    nuevas = [x for x in r.partidas if x.capitulos and x.capitulos[0][0] == "MOD1"]
    assert [(x.codigo, x.cantidad, x.precio) for x in nuevas] == [
        ("EXT01", 2.0, 850.0),
        ("MOD1.2", 1.0, 10.0),
    ]
    assert any("se renombra «MOD1.2»" in a for a in avisos)
    # Medición con líneas: se añade una línea con la diferencia y el motivo.
    assert "Modificado nº 1: Error de medición. Faltaba el tramo C\\200\\" in texto
    assert not any("la medición (~M) suma" in a for a in r.avisos)
    # Precios de capítulos corregidos con la diferencia de importe.
    assert b.conceptos["01.1"].precios[0] == pytest.approx(24364 + 2000 - 364)
    assert b.conceptos["OBRA"].precios[0] == pytest.approx(37244 + 2000 - 364 + 1700 + 10)
    # El sinónimo sigue resolviendo y los descompuestos siguen valiendo para el precio.
    uta = next(x for x in r.partidas if x.codigo == "UTA01" and x.capitulos[0][0] != "MOD1")
    assert uta.precio == 12880


def test_bc3_de_una_base_leida_de_pdf_se_genera(proyecto, tmp_path):
    import pymupdf

    ruta = tmp_path / "base.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text(
        (40, 60), "Rejilla de impulsión   ud   8   45,50   364,00", fontsize=9
    )
    doc.save(ruta)
    doc.close()

    def ia(texto, imagenes):
        n = {"texto": None, "valor": None, "donde": None}
        return {
            "proveedor": None,
            "total": n,
            "partidas": [
                {
                    "capitulo": "Difusión",
                    "codigo": None,
                    "descripcion": "Rejilla de impulsión",
                    "unidad": "ud",
                    "donde": "p. 1",
                    "cantidad": {"texto": "8", "valor": 8, "donde": "p. 1"},
                    "precio": {"texto": "45,50", "valor": 45.5, "donde": "p. 1"},
                    "importe": {"texto": "364,00", "valor": 364.0, "donde": "p. 1"},
                }
            ],
        }

    proyecto.extractor_ia = ia
    base = proyecto.leer_medicion(proyecto.incorporar_documento(ruta), "presupuesto")[0]
    o = CrearModificado(base, "M")
    proyecto.ejecutar(o)
    pid = proyecto.partidas(base)[0]["id"]
    proyecto.ejecutar(VariarPartida(o.id, pid, 10, "medicion", "Dos más"))
    salida, avisos = proyecto.exportar_modificado_bc3(o.id, tmp_path / "m.bc3")
    r = bc3.leer_partidas(bc3.leer_bc3(salida))
    assert [(x.codigo, x.cantidad, x.precio) for x in r.partidas] == [("P0001", 10.0, 45.5)]
    assert r.partidas[0].capitulos == [("C01", "Difusión")]
    assert "generado con lo leído" in avisos[0]


def test_bc3_sin_cambios_se_rechaza(mod, tmp_path):
    p, m, _, _, _ = mod
    with pytest.raises(OrdenRechazada, match="no tiene cambios"):
        p.exportar_modificado_bc3(m, tmp_path / "x.bc3")


def test_original_alterado_no_se_parchea_a_ciegas(mod, tmp_path):
    p, m, ids, _, original = mod
    p.ejecutar(VariarPartida(m, ids["CND01"], 2600, "medicion", "x"))
    # Alguien sustituye el documento guardado por otro distinto (no debería pasar: el
    # almacén es de solo lectura; aquí se fuerza para probar la defensa).
    guardado = p.ruta_documento(p.mediciones()[0]["documento_id"])
    guardado.chmod(0o644)
    guardado.write_bytes(ORIGINAL.replace("CND-ALT\\1\\2400", "REJ01\\1\\2400").encode("cp850"))
    with pytest.raises(OrdenRechazada):
        p.exportar_modificado_bc3(m, tmp_path / "x.bc3")
    assert not (tmp_path / "x.bc3").exists()


# --- Revisión 06-11-2026: casos que antes salían mal o con un error engañoso -----------------

CABECERA = "~V|A|FIEBDC-3/2016|P||ANSI||2|\r\n~C|O##||Obra|0||0|\r\n~C|C1#||Cap|0||0|\r\n"


def _base(proyecto, tmp_path, cuerpo: str, nombre="b.bc3"):
    f = tmp_path / nombre
    f.write_bytes((CABECERA + cuerpo).encode("cp1252"))
    base = proyecto.leer_medicion(proyecto.incorporar_documento(f), "presupuesto")[0]
    o = CrearModificado(base, "M")
    proyecto.ejecutar(o)
    return o.id, proyecto.partidas(base)


def test_medicion_con_expresiones_no_se_modifica_a_ciegas(proyecto, tmp_path):
    m, ps = _base(
        proyecto,
        tmp_path,
        "~C|P1|m|Tubo|10||0|\r\n~D|O##|C1#\\1\\1\\|\r\n~D|C1#|P1\\1\\6\\|\r\n"
        "~M|C1#\\P1|1\\1\\|6|3\\a*b\\2\\3\\\\\\|\r\n",
    )
    proyecto.ejecutar(VariarPartida(m, ps[0]["id"], 8, "medicion", "x"))
    with pytest.raises(OrdenRechazada, match="tipo «3»"):
        proyecto.exportar_modificado_bc3(m, tmp_path / "x.bc3")
    assert not list(tmp_path.glob("x.bc3*"))


def test_lineas_que_no_suman_el_total_se_rechazan(proyecto, tmp_path):
    m, ps = _base(
        proyecto,
        tmp_path,
        "~C|P1|m|Tubo|10||0|\r\n~D|O##|C1#\\1\\1\\|\r\n~D|C1#|P1\\1\\6\\|\r\n"
        "~M|C1#\\P1|1\\1\\|6|\\Tramo\\1\\5\\\\\\|\r\n",
    )
    proyecto.ejecutar(VariarPartida(m, ps[0]["id"], 8, "medicion", "x"))
    with pytest.raises(OrdenRechazada, match="suman 5 y su total es 6"):
        proyecto.exportar_modificado_bc3(m, tmp_path / "x.bc3")


def test_lineas_con_subtotales_suman_bien(proyecto, tmp_path):
    # Subtotales (tipo 1 y 2, pág. 22) no suman; la línea añadida va con TIPO vacío.
    m, ps = _base(
        proyecto,
        tmp_path,
        "~C|P1|m|Tubo|10||0|\r\n~D|O##|C1#\\1\\1\\|\r\n~D|C1#|P1\\1\\6\\|\r\n"
        "~M|C1#\\P1|1\\1\\|6|\\A\\2\\3\\\\\\1\\Subtotal\\\\\\\\\\|\r\n",
    )
    proyecto.ejecutar(VariarPartida(m, ps[0]["id"], 8, "medicion", "Uno # dos"))
    ruta, _ = proyecto.exportar_modificado_bc3(m, tmp_path / "x.bc3")
    texto = ruta.read_bytes().decode("cp1252")
    # «#» separa los ID_BIM en el comentario (pág. 21): se sustituye.
    assert "\\Modificado nº 1: Error de medición. Uno / dos\\2\\\\\\\\|" in texto


def test_registro_n_se_rechaza(proyecto, tmp_path):
    m, ps = _base(
        proyecto,
        tmp_path,
        "~C|P1|m|Tubo|10||0|\r\n~D|O##|C1#\\1\\1\\|\r\n~D|C1#|P1\\1\\6\\|\r\n"
        "~M|C1#\\P1|1\\1\\|4|\\A\\4\\\\\\\\|\r\n~N|C1#\\P1|1\\1\\|2|\\B\\2\\\\\\\\|\r\n",
    )
    proyecto.ejecutar(VariarPartida(m, ps[0]["id"], 8, "medicion", "x"))
    with pytest.raises(OrdenRechazada, match="~N"):
        proyecto.exportar_modificado_bc3(m, tmp_path / "x.bc3")


def test_partida_repetida_usa_la_medicion_de_su_posicion(proyecto, tmp_path):
    m, ps = _base(
        proyecto,
        tmp_path,
        "~C|P1|m|Tubo|10||0|\r\n~D|O##|C1#\\1\\1\\|\r\n~D|C1#|P1\\1\\6\\P1\\1\\4\\|\r\n"
        "~M|C1#\\P1|1\\1\\|6||\r\n~M|C1#\\P1|1\\2\\|4||\r\n",
    )
    segunda = ps[1]
    assert segunda["cantidad"] == 4
    proyecto.ejecutar(VariarPartida(m, segunda["id"], 5, "medicion", "x"))
    ruta, _ = proyecto.exportar_modificado_bc3(m, tmp_path / "x.bc3")
    texto = ruta.read_bytes().decode("cp1252")
    assert "~M|C1#\\P1|1\\1\\|6||" in texto and "~M|C1#\\P1|1\\2\\|5||" in texto


def test_partida_repetida_sin_posicion_no_se_modifica_a_ciegas(proyecto, tmp_path):
    m, ps = _base(
        proyecto,
        tmp_path,
        "~C|P1|m|Tubo|10||0|\r\n~D|O##|C1#\\1\\1\\|\r\n~D|C1#|P1\\1\\6\\P1\\1\\4\\|\r\n"
        "~M|C1#\\P1||6||\r\n",
    )
    proyecto.ejecutar(VariarPartida(m, ps[1]["id"], 5, "medicion", "x"))
    with pytest.raises(OrdenRechazada, match="POSICION"):
        proyecto.exportar_modificado_bc3(m, tmp_path / "x.bc3")


def test_anular_partida_con_lineas(mod, tmp_path):
    p, m, ids, _, _ = mod
    p.ejecutar(VariarPartida(m, ids["CND01"], 0, "diseno", "Se quita"))
    ruta, _ = p.exportar_modificado_bc3(m, tmp_path / "x.bc3")
    r = bc3.leer_partidas(bc3.leer_bc3(ruta))
    assert next(x for x in r.partidas if x.codigo == "CND01").cantidad is None
    assert "\\Modificado nº 1: Fallo de diseño. Se quita\\-2400\\" in ruta.read_bytes().decode(
        "cp850"
    )


def test_capitulo_con_porcentaje_se_avisa(proyecto, tmp_path):
    m, ps = _base(
        proyecto,
        tmp_path,
        "~C|P1|m|Tubo|10||0|\r\n~C|%MA|%|Medios auxiliares|0||0|\r\n"
        "~D|O##|C1#\\1\\1\\|\r\n~D|C1#|P1\\1\\6\\%MA\\1\\0.02\\|\r\n~M|C1#\\P1|1\\1\\|6||\r\n",
    )
    proyecto.ejecutar(VariarPartida(m, ps[0]["id"], 8, "medicion", "x"))
    _, avisos = proyecto.exportar_modificado_bc3(m, tmp_path / "x.bc3")
    assert any("«C1» aplica porcentajes" in a for a in avisos)


def test_original_ilegible_da_error_claro(mod, tmp_path):
    p, m, ids, _, _ = mod
    p.ejecutar(VariarPartida(m, ids["CND01"], 2600, "medicion", "x"))
    guardado = p.ruta_documento(p.mediciones()[0]["documento_id"])
    guardado.chmod(0o644)
    guardado.write_bytes(ORIGINAL.replace("|2400|", "|dos mil|").encode("cp850"))
    with pytest.raises(OrdenRechazada, match="no se puede leer"):
        p.exportar_modificado_bc3(m, tmp_path / "x.bc3")
    assert not list(tmp_path.glob("x.bc3*"))


def test_base_de_pdf_anulada_y_codigos_que_chocan(proyecto, tmp_path):
    import pymupdf

    ruta = tmp_path / "base.pdf"
    doc = pymupdf.open()
    pagina = doc.new_page()
    pagina.insert_text((40, 60), "C01 Rejilla de impulsión   ud   8   45,50   364,00", fontsize=9)
    pagina.insert_text((40, 80), "C01 Rejilla de retorno   ud   4   30,00   120,00", fontsize=9)
    doc.save(ruta)
    doc.close()

    def linea(desc, cant, precio, importe):
        return {
            "capitulo": "Difusión",
            "codigo": "C01",
            "descripcion": desc,
            "unidad": "ud",
            "donde": "p. 1",
            "cantidad": {"texto": cant, "valor": float(cant), "donde": "p. 1"},
            "precio": {"texto": precio, "valor": float(precio.replace(",", ".")), "donde": "p. 1"},
            "importe": {
                "texto": importe,
                "valor": float(importe.replace(",", ".")),
                "donde": "p. 1",
            },
        }

    def ia(texto, imagenes):
        n = {"texto": None, "valor": None, "donde": None}
        return {
            "proveedor": None,
            "total": n,
            "partidas": [
                linea("Rejilla de impulsión", "8", "45,50", "364,00"),
                linea("Rejilla de retorno", "4", "30,00", "120,00"),
            ],
        }

    proyecto.extractor_ia = ia
    base = proyecto.leer_medicion(proyecto.incorporar_documento(ruta), "presupuesto")[0]
    o = CrearModificado(base, "M")
    proyecto.ejecutar(o)
    ps = proyecto.partidas(base)
    proyecto.ejecutar(VariarPartida(o.id, ps[0]["id"], 0, "economica", "Se anula"))
    salida, avisos = proyecto.exportar_modificado_bc3(o.id, tmp_path / "m.bc3")
    r = bc3.leer_partidas(bc3.leer_bc3(salida))
    # El código «C01» de la base ya no choca con el del capítulo, y el repetido se avisa.
    assert [(x.codigo, x.cantidad, x.precio) for x in r.partidas] == [
        ("C01", None, 45.5),
        ("P0002", 4.0, 30.0),
    ]
    assert r.partidas[0].capitulos == [("C01.1", "Difusión")]
    assert any("«C01» → «P0002»" in a for a in avisos)


def test_partida_repetida_con_una_sola_medicion_no_toca_la_de_otra_linea(proyecto, tmp_path):
    # La única ~M es de la línea 1 (POSICION 1): variar la línea 2 no debe ponerle el total.
    m, ps = _base(
        proyecto,
        tmp_path,
        "~C|P1|m|Tubo|10||0|\r\n~D|O##|C1#\\1\\1\\|\r\n~D|C1#|P1\\1\\6\\P1\\1\\4\\|\r\n"
        "~M|C1#\\P1|1\\1\\|6||\r\n",
    )
    proyecto.ejecutar(VariarPartida(m, ps[1]["id"], 5, "medicion", "x"))
    ruta, avisos = proyecto.exportar_modificado_bc3(m, tmp_path / "x.bc3")
    assert "~M|C1#\\P1|1\\1\\|6||" in ruta.read_bytes().decode("cp1252")
    assert any("no tiene medición" in a for a in avisos)


def test_verificacion_caza_una_medicion_que_no_cuadra(tmp_path):
    from traza.io import bc3_modificar

    original = CABECERA + (
        "~C|P1|m|Tubo|10||0|\r\n~D|O##|C1#\\1\\1\\|\r\n~D|C1#|P1\\1\\6\\|\r\n~M|C1#\\P1|1\\1\\|6||\r\n"
    )
    leido = bc3.leer_partidas(bc3.leer_bc3_texto(original, "ANSI"))
    # Fichero «mal actualizado»: el ~D dice 8 pero la ~M sigue en 6. Las cifras de las
    # partidas cuadran (el lector prima el ~D), pero el lector avisa del descuadre.
    malo = tmp_path / "malo.bc3"
    malo.write_bytes(original.replace("P1\\1\\6\\", "P1\\1\\8\\").encode("cp1252"))
    v = bc3_modificar.Variacion(leido.partidas[0].localizador, "P1", 6, 8, 10, ["C1"], "x")
    with pytest.raises(bc3_modificar.Bc3ModificarError, match="avisos"):
        bc3_modificar._verificar(malo, leido, [v], [], {})
