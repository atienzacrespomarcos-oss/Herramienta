"""Lector BC3 contra las reglas de la especificación FIEBDC-3/2024 (página citada en cada test).

Los ficheros de prueba los construye el propio test siguiendo la sintaxis del documento; no
son ficheros reales de ningún programa. La validación con un BC3 real exportado de Presto o
Arquímedes queda pendiente del usuario (docs/modules/mediciones.md, criterio 1).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from traza.io.bc3 import Bc3Error, leer_bc3, leer_bc3_texto, leer_partidas, partidas

# Obra mínima: raíz → capítulo 01 (con subcapítulo 01.1) → partidas.
OBRA = r"""
Texto anterior al primer registro: se ignora (pág. 2).
~V|AUTOR|FIEBDC-3/2016\06112026|PROGRAMA PRUEBA|\EUR\|ANSI|Prueba|2|
~K|\2\2\3\2\2\2\2\EUR\|0\0\0\0\21|
~C|OBRA##||Nave de prueba|1500||0|
~C|01#||Climatización|1500||0|
~C|01.1#||Conductos|300||0|
~C|UTA01|ud|Unidad de tratamiento de aire|1200||0|
~C|CND01|m2|Conducto de chapa galvanizada|30||0|
~T|UTA01|Unidad de tratamiento de aire de 2400 m3/h, según pliego.|
~D|OBRA##|01#\1\1\|
~D|01#|UTA01\1\1\01.1#\1\1\|
~D|01.1#|CND01\1\10\|
~M|01.1#\CND01|1\1\1\|10|\Tramo principal\2\5\\\|1.1.1|
"""


def _partidas(texto: str):
    b = leer_bc3_texto(texto, "ANSI")
    ps, avisos = partidas(b)
    return b, ps, avisos


def test_estructura_capitulos_y_partidas():
    b, ps, avisos = _partidas(OBRA)
    assert b.raiz == "OBRA" and b.version_formato == "FIEBDC-3/2016"
    assert b.programa == "PROGRAMA PRUEBA" and b.tipo_informacion == "2"
    assert [(p.codigo, p.cantidad, p.precio) for p in ps] == [
        ("UTA01", 1.0, 1200.0),
        ("CND01", 10.0, 30.0),
    ]
    assert ps[0].capitulos == [("01", "Climatización")]
    assert ps[1].capitulos == [("01", "Climatización"), ("01.1", "Conductos")]
    assert ps[0].texto == "Unidad de tratamiento de aire de 2400 m3/h, según pliego."
    assert ps[1].etiqueta == "1.1.1"
    assert "~D 01.1#, línea 1" in ps[1].localizador
    # ~K se conserva sin interpretar y se avisa (no se oculta).
    assert any("~K (1)" in a for a in b.avisos)
    assert avisos == []


def test_espacios_y_saltos_delante_de_separadores_se_ignoran():
    # Pág. 2: blancos, tabuladores y fines de línea delante de ~, | y \ se ignoran.
    texto = "~V||FIEBDC-3/2016  |\n~C|R##   |  |Obra\t|\n~C|P1|ud |Partida |10 \\ |\n~D|R##|P1\\1\\3  \\|\n"
    _, ps, _ = _partidas(texto)
    assert [(p.codigo, p.unidad, p.resumen, p.cantidad, p.precio) for p in ps] == [
        ("P1", "ud", "Partida", 3.0, 10.0)
    ]


def test_sin_rendimiento_ni_medicion_la_cantidad_no_consta():
    # Pág. 9 da 1.0 por defecto al rendimiento, pero eso no es una medición: sin rendimiento
    # explícito ni ~M, la cantidad «no consta» (antes se daba 1 y se sumaba).
    _, ps, avisos = _partidas("~C|R##||O|\n~C|P1|ud|P|5|\n~D|R##|P1\\\\\\|\n")
    assert ps[0].cantidad is None
    assert any("sin cantidad" in a for a in avisos)


def test_sin_rendimiento_se_usa_la_medicion():
    _, ps, _ = _partidas("~C|R##||O|\n~C|P1|ud|P|5|\n~D|R##|P1\\\\\\|\n~M|R##\\P1|1\\|7|\n")
    assert ps[0].cantidad == 7.0


def test_campo_3_de_descomposicion_tiene_preferencia():
    # Pág. 9: los programas deben leer el campo 3 y, en su defecto, el 2.
    texto = "~C|R##||O|\n~C|P1|ud|P|5|\n~D|R##|P1\\1\\2\\|P1\\1\\7\\\\|\n"
    _, ps, _ = _partidas(texto)
    assert ps[0].cantidad == 7.0


def test_campo_vacio_no_borra_informacion_previa():
    # Pág. 2: campo vacío = SIN INFORMACIÓN (permite ficheros de actualización).
    texto = "~C|R##||O|\n~C|P1|ud|Partida|5|\n~C|P1|||8|\n~D|R##|P1\\1\\1\\|\n"
    _, ps, _ = _partidas(texto)
    assert (ps[0].unidad, ps[0].resumen, ps[0].precio) == ("ud", "Partida", 8.0)


def test_medicion_que_no_coincide_con_el_rendimiento_se_avisa():
    # Pág. 22: MEDICION_TOTAL debe coincidir con el rendimiento del ~D.
    texto = OBRA.replace("~M|01.1#\\CND01|1\\1\\1\\|10|", "~M|01.1#\\CND01|1\\1\\1\\|12|")
    _, ps, avisos = _partidas(texto)
    assert ps[1].cantidad == 10.0
    assert any("la medición (~M) suma 12.0" in a for a in avisos)


def test_precio_de_la_descomposicion_prima_sobre_el_del_concepto():
    # Págs. 8 y 10: si el precio sale de ~C y de ~D, prima la descomposición.
    texto = (
        "~C|R##||O|\n~C|P1|ud|Partida|100|\n~C|MO1|h|Oficial|20||1|\n~C|MAT1|ud|Material|50||3|\n"
        "~D|R##|P1\\1\\1\\|\n~D|P1|MO1\\1\\2\\MAT1\\1\\1\\|\n"
    )
    _, ps, avisos = _partidas(texto)
    assert ps[0].precio == 90.0
    assert any(
        "descomposición suma 90.0" in a and "Se usa el de la descomposición" in a for a in avisos
    )


def test_descomposicion_con_porcentajes_no_se_recalcula_y_se_dice():
    texto = (
        "~C|R##||O|\n~C|P1|ud|Partida|103|\n~C|MAT1|ud|Material|100||3|\n"
        "~C|%AUX|%|Medios auxiliares|\n~D|R##|P1\\1\\1\\|\n~D|P1|MAT1\\1\\1\\%AUX\\\\0.03\\|\n"
    )
    _, _, avisos = _partidas(texto)
    assert any(
        "porcentajes" in a and "no recalcula" in a and "Se usa el precio del ~C" in a
        for a in avisos
    )


def test_mediciones_no_estructuradas_sin_raiz():
    # Pág. 21: sin código raíz ni ~D en mediciones no estructuradas.
    _, ps, avisos = _partidas("~C|P1|m|Tubo cobre|4.5|\n~M|P1||25.5|\n")
    assert [(p.codigo, p.cantidad, p.precio) for p in ps] == [("P1", 25.5, 4.5)]
    assert any("no estructuradas" in a for a in avisos)


def test_dos_raices_es_un_error():
    # Pág. 8: únicamente puede haber un concepto raíz.
    with pytest.raises(Bc3Error, match="raíz"):
        leer_bc3_texto("~C|A##||A|\n~C|B##||B|\n")


def test_numero_con_coma_es_un_error():
    # Pág. 3: punto decimal y sin separador de miles.
    with pytest.raises(Bc3Error, match="Número no válido"):
        leer_bc3_texto("~C|R##||O|\n~C|P1|ud|P|12,5|\n")


def test_hijo_sin_concepto_se_avisa():
    _, ps, avisos = _partidas("~C|R##||O|\n~D|R##|NOEXISTE\\1\\1\\|\n")
    assert ps == [] and any("no tiene ~C" in a for a in avisos)


@pytest.mark.parametrize(
    "juego,codificacion,texto",
    # Cada texto tiene un carácter que solo existe (o cambia) en ese juego, para que el test
    # falle si se decodifica con otro: «Á» no está en 437; «╨» es 0xD0, que en 850 es «ð»;
    # «€» solo está en ANSI (cp1252).
    [
        ("850", "cp850", "ÁREA cañón"),
        ("437", "cp437", "cañón ╨"),
        ("ANSI", "cp1252", "cañón 25 €"),
        ("", "cp850", "ÁREA cañón"),
    ],
)
def test_juego_de_caracteres(tmp_path: Path, juego, codificacion, texto):
    # Pág. 4: 850 o 437 (DOS), ANSI (Windows); vacío = 850.
    resumen = texto
    texto = (
        f"~V||FIEBDC-3/2016|||{juego}|\n~C|R##||Obra|\n~C|P1|ud|{resumen}|1|\n~D|R##|P1\\1\\1\\|\n"
    )
    f = tmp_path / "obra.bc3"
    f.write_bytes(texto.encode(codificacion))
    b = leer_bc3(f)
    ps, _ = partidas(b)
    assert ps[0].resumen == resumen


def test_juego_de_caracteres_no_previsto_se_rechaza(tmp_path: Path):
    f = tmp_path / "obra.bc3"
    f.write_bytes(b"~V||FIEBDC-3/2016|||UTF-16|\n~C|R##||Obra|\n")
    with pytest.raises(Bc3Error, match="no previsto"):
        leer_bc3(f)


def test_fichero_sin_registros():
    with pytest.raises(Bc3Error, match="no es un fichero BC3"):
        leer_bc3_texto("esto no es un bc3")


# --- Fallos de la revisión del 06-11-2026 (uno por prueba) ------------------------------


def test_linea_de_porcentaje_en_un_capitulo_no_es_una_partida():
    # Págs. 9-10: «%»/«&» es un porcentaje sobre las líneas anteriores, no una partida.
    texto = "~C|R##||O|\n~C|P1|ud|P|10|\n~C|%AUX|%|Medios auxiliares|5|\n~D|R##|P1\\1\\2\\%AUX\\\\0.03\\|\n"
    b = leer_bc3_texto(texto)
    r = leer_partidas(b)
    assert [p.codigo for p in r.partidas] == ["P1"]
    assert r.omitidas == 1 and any("porcentaje" in a for a in r.avisos)


def test_concepto_citado_por_sinonimo():
    # Pág. 7: varios códigos del mismo concepto actúan como sinónimos.
    texto = "~D|R##|B\\1\\5\\|\n~C|R##||O|\n~C|A\\B|ud|Partida con dos códigos|3|\n~T|B|Texto por sinónimo|\n"
    _, ps, avisos = _partidas(texto)
    assert [(p.codigo, p.cantidad, p.texto) for p in ps] == [("A", 5.0, "Texto por sinónimo")]
    assert avisos == []


def test_partida_repetida_en_un_capitulo_usa_la_posicion():
    # Pág. 22: POSICION identifica la medición cuando un hijo se repite.
    texto = (
        "~C|R##||O|\n~C|C1#||Cap|\n~C|P1|ud|P|1|\n~D|R##|C1#\\1\\1\\|\n~D|C1#|P1\\1\\2\\P1\\1\\5\\|\n"
        "~M|C1#\\P1|1\\1\\|2||A|\n~M|C1#\\P1|1\\2\\|5||B|\n"
    )
    _, ps, avisos = _partidas(texto)
    assert [(p.cantidad, p.etiqueta) for p in ps] == [(2.0, "A"), (5.0, "B")]
    assert avisos == []


def test_cantidad_es_el_rendimiento_no_factor_por_rendimiento():
    # Pág. 22: MEDICION_TOTAL coincide con el rendimiento del ~D.
    texto = "~C|R##||O|\n~C|P1|ud|P|1|\n~D|R##|P1\\2\\10\\|\n~M|R##\\P1|1\\|10|\n"
    _, ps, avisos = _partidas(texto)
    assert ps[0].cantidad == 10.0
    assert any("factor 2.0" in a for a in avisos)
    assert not any("la medición (~M) suma" in a for a in avisos)


def test_base_de_datos_tipo_1_se_avisa():
    b = leer_bc3_texto("~V||FIEBDC-3/2016|||ANSI||1|\n~C|R##||O|\n")
    assert any("base de datos" in a for a in b.avisos)


def test_capitulo_sin_almohadilla_se_avisa():
    texto = (
        "~C|R##||O|\n~C|CAP||Capítulo mal marcado|\n~C|P1|ud|P|1|\n"
        "~D|R##|CAP\\1\\1\\|\n~D|CAP|P1\\1\\3\\|\n~M|CAP\\P1|1\\|3|\n"
    )
    _, _, avisos = _partidas(texto)
    assert any("parece un capítulo sin «#»" in a for a in avisos)


def test_precio_vacio_no_desplaza_a_los_siguientes():
    # Pág. 8: cada precio corresponde a su rótulo; un vacío no corre los demás.
    _, ps, _ = _partidas("~C|R##||O|\n~C|P1|ud|P|\\95|\n~D|R##|P1\\1\\1\\|\n")
    assert ps[0].precio is None


def test_cero_explicito_anula_el_campo():
    # Pág. 2: para anular un campo numérico aparece explícitamente 0.
    _, ps, avisos = _partidas("~C|R##||O|\n~C|P1|ud|P|0|\n~D|R##|P1\\1\\0\\|\n")
    assert ps[0].precio is None and ps[0].cantidad is None
    assert sum("anulado" in a for a in avisos) == 2


def test_bytes_ajenos_al_juego_declarado(tmp_path: Path):
    f = tmp_path / "obra.bc3"
    f.write_bytes(b"~V||FIEBDC-3/2016|||ANSI|\n~C|R##||Obra \x81|\n")
    with pytest.raises(Bc3Error, match="bytes que no"):
        leer_bc3(f)


def test_descomposicion_vacia_no_aborta_el_fichero():
    b = leer_bc3_texto("~C|R##||O|\n~D|R##|\n")
    assert any("sin descomposición" in a for a in b.avisos)


def test_sin_raiz_las_mediciones_de_capitulos_no_son_partidas():
    texto = "~C|C1#||Cap|\n~C|P1|m|Tubo|2|\n~M|C1#||1||1|\n~M|C1#\\P1|1\\|4|\n"
    _, ps, _ = _partidas(texto)
    assert [p.codigo for p in ps] == ["P1"]


def test_raiz_con_descomposicion_pero_sin_almohadillas_se_explica():
    _, ps, avisos = _partidas("~C|R||O|\n~C|P1|ud|P|1|\n~D|R|P1\\1\\1\\|\n")
    assert ps == [] and any("ningún concepto raíz" in a for a in avisos)
