"""Mediciones dentro del proyecto: leer un BC3 incorporado, guardar partidas con su origen,
deshacer, quitar y exportar el «Excel con todo»."""

from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from traza.app.ordenes import CambiarEncargo, OrdenRechazada, QuitarMedicion
from traza.app.proyecto import Proyecto

BC3 = (
    "~V|AUTOR|FIEBDC-3/2016|PRUEBA||ANSI|Prueba|2|\n"
    "~C|OBRA##||Nave|1500||0|\n"
    "~C|01#||Climatización|1500||0|\n"
    "~C|UTA01|ud|Unidad de tratamiento de aire|1200||0|\n"
    "~C|CND01|m2|Conducto de chapa galvanizada|30||0|\n"
    "~C|REJ01|ud|Rejilla de impulsión||0|\n"
    "~D|OBRA##|01#\\1\\1\\|\n"
    "~D|01#|UTA01\\1\\1\\CND01\\1\\10\\REJ01\\1\\4\\|\n"
)


@pytest.fixture
def bc3(tmp_path: Path) -> Path:
    f = tmp_path / "Oferta climatización.bc3"
    f.write_bytes(BC3.encode("cp1252"))
    return f


def test_leer_bc3_guarda_partidas_con_origen(proyecto, bc3):
    doc = proyecto.incorporar_documento(bc3, "oferta")
    med_id, avisos = proyecto.leer_medicion(doc, "oferta", "Proveedor A")
    med = proyecto.mediciones()[0]
    assert (med["id"], med["clase"], med["proveedor"], med["n_partidas"]) == (
        med_id,
        "oferta",
        "Proveedor A",
        3,
    )
    assert med["lector"] == "bc3" and med["documento_nombre"] == "Oferta climatización.bc3"
    ps = proyecto.partidas(med_id)
    assert [(p["codigo"], p["cantidad"], p["precio"], p["importe"]) for p in ps] == [
        ("UTA01", 1.0, 1200.0, 1200.0),
        ("CND01", 10.0, 30.0, 300.0),
        ("REJ01", 4.0, None, None),  # sin precio: no consta, no cero
    ]
    assert ps[0]["capitulo"] == [["01", "Climatización"]]
    assert all(p["localizador"] for p in ps)
    assert avisos == []


def test_leer_medicion_se_deshace_entera(proyecto, bc3):
    doc = proyecto.incorporar_documento(bc3)
    proyecto.leer_medicion(doc, "medicion")
    assert proyecto.deshacer() == "ImportarMedicion"
    assert proyecto.mediciones() == []
    assert proyecto._con.execute("SELECT count(*) FROM partida").fetchone()[0] == 0
    proyecto.rehacer()
    assert proyecto.mediciones()[0]["n_partidas"] == 3


def test_quitar_medicion_y_deshacer(proyecto, bc3):
    doc = proyecto.incorporar_documento(bc3)
    med_id, _ = proyecto.leer_medicion(doc, "medicion")
    proyecto.ejecutar(QuitarMedicion(med_id))
    assert proyecto.mediciones() == []
    proyecto.deshacer()
    assert [p["orden"] for p in proyecto.partidas(med_id)] == [1, 2, 3]


def test_formato_no_disponible_se_dice(proyecto, pdf_3_paginas):
    doc = proyecto.incorporar_documento(pdf_3_paginas)
    with pytest.raises(OrdenRechazada, match="Todavía no se pueden leer"):
        proyecto.leer_medicion(doc, "oferta")


def test_bc3_ilegible_se_rechaza_sin_dejar_rastro(proyecto, tmp_path):
    f = tmp_path / "malo.bc3"
    f.write_bytes(b"~V||FIEBDC-3/2016|||UTF-16|\n")
    doc = proyecto.incorporar_documento(f)
    with pytest.raises(OrdenRechazada, match="malo.bc3"):
        proyecto.leer_medicion(doc, "oferta")
    assert proyecto.mediciones() == []


def test_excel_con_todo(proyecto, bc3, tmp_path):
    doc = proyecto.incorporar_documento(bc3, "oferta")
    proyecto.leer_medicion(doc, "oferta", "Proveedor A")
    ruta = proyecto.exportar_excel(tmp_path / "salida" / "Todo")
    assert ruta.suffix == ".xlsx" and ruta.is_file()
    wb = load_workbook(ruta)
    ws = wb["Partidas"]
    filas = list(ws.iter_rows(values_only=True))
    assert filas[0][:3] == ("Documento", "Tipo", "Proveedor")
    assert filas[1][3:11] == (
        "01 Climatización",
        "UTA01",
        None,
        "ud",
        "Unidad de tratamiento de aire",
        1,
        1200,
        1200,
    )
    # Sin precio: precio e importe vacíos, nunca 0.
    assert filas[3][9] is None and filas[3][10] is None
    assert isinstance(filas[2][8], float | int) and ws["I2"].number_format == "#,##0.00"
    assert "Avisos de lectura" in wb.sheetnames


def test_excel_sin_mediciones(proyecto, tmp_path):
    with pytest.raises(OrdenRechazada, match="No hay mediciones"):
        proyecto.exportar_excel(tmp_path / "x.xlsx")


def test_tipo_de_encargo(tmp_path):
    p = Proyecto.crear(tmp_path / "N", "N", encargo="instalacion")
    try:
        assert p.encargo == "instalacion"
        p.ejecutar(CambiarEncargo("presupuesto"))
        assert p.encargo == "presupuesto"
        p.deshacer()
        assert p.encargo == "instalacion"
        with pytest.raises(OrdenRechazada):
            p.ejecutar(CambiarEncargo("otro"))
    finally:
        p.cerrar()
    with pytest.raises(OrdenRechazada, match="desconocido"):
        Proyecto.crear(tmp_path / "M", "M", encargo="otro")
    assert not (tmp_path / "M.traza").exists()


# --- Revisión del 06-11-2026 ---------------------------------------------------------------


def test_no_se_lee_dos_veces_el_mismo_documento(proyecto, bc3):
    doc = proyecto.incorporar_documento(bc3)
    proyecto.leer_medicion(doc, "oferta")
    with pytest.raises(OrdenRechazada, match="ya está leído"):
        proyecto.leer_medicion(doc, "medicion")
    assert len(proyecto.mediciones()) == 1


def test_sin_partidas_se_explica_el_motivo(proyecto, tmp_path):
    f = tmp_path / "vacio.bc3"
    f.write_bytes(b"~V||FIEBDC-3/2016|||ANSI|\n~C|R##||O|\n~D|R##|NOEXISTE\\1\\1\\|\n")
    doc = proyecto.incorporar_documento(f)
    with pytest.raises(OrdenRechazada, match="NOEXISTE"):
        proyecto.leer_medicion(doc, "oferta")


def test_importacion_que_falla_en_la_ultima_partida_no_deja_nada(proyecto, bc3):
    """Atomicidad real: la base de datos rechaza la última partida y no queda ninguna."""
    from traza.app.ordenes import ImportarMedicion, PartidaNueva

    doc = proyecto.incorporar_documento(bc3)
    buena = PartidaNueva([], "A", None, "ud", "a", None, 1.0, 2.0, "~C A")
    mala = PartidaNueva([], "B", None, "ud", "b", None, 1.0, 2.0, "   ")  # sin localizador
    with pytest.raises(OrdenRechazada):
        proyecto.ejecutar(
            ImportarMedicion(doc, "x", "oferta", None, "bc3", "1", [buena, buena, mala], [])
        )
    assert proyecto.mediciones() == []
    assert proyecto._con.execute("SELECT count(*) FROM partida").fetchone()[0] == 0


def test_omitidas_se_guardan(proyecto, tmp_path):
    f = tmp_path / "pct.bc3"
    f.write_bytes(
        b"~V||FIEBDC-3/2016|||ANSI|\n~C|R##||O|\n~C|P1|ud|P|10|\n~C|%A|%|Aux|\n"
        b"~D|R##|P1\\1\\2\\%A\\\\0.03\\|\n"
    )
    doc = proyecto.incorporar_documento(f)
    proyecto.leer_medicion(doc, "oferta")
    assert proyecto.mediciones()[0]["omitidas"] == 1


def test_excel_conserva_puntos_del_nombre_y_no_crea_formulas(proyecto, tmp_path):
    f = tmp_path / "f.bc3"
    f.write_bytes(
        b"~V||FIEBDC-3/2016|||ANSI|\n~C|R##||O|\n~C|P1|ud|=1+1 no es formula|10|\n"
        b"~D|R##|P1\\1\\2\\|\n"
    )
    doc = proyecto.incorporar_documento(f)
    proyecto.leer_medicion(doc, "oferta")
    ruta = proyecto.exportar_excel(tmp_path / "Nave 2.1")
    assert ruta.name == "Nave 2.1.xlsx"
    ws = load_workbook(ruta)["Partidas"]
    assert ws["H2"].value == "=1+1 no es formula" and ws["H2"].data_type == "s"
