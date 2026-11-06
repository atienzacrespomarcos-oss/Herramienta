"""Ampliaciones y modificaciones: reglas, cálculo y Excel (decisiones del usuario, 06-11-2026)."""

from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from traza.app.ordenes import (
    AnadirPartidaNueva,
    BorrarModificado,
    CrearModificado,
    OrdenRechazada,
    QuitarCambio,
    QuitarMedicion,
    VariarPartida,
)

BASE = (
    "~V|AUTOR|FIEBDC-3/2016|PRUEBA||ANSI|Contrato|2|\n"
    "~C|OBRA##||Nave|0||0|\n~C|01#||Climatización||0|\n"
    "~C|UTA01|ud|Unidad de tratamiento de aire|12500||0|\n"
    "~C|CND01|m2|Conducto de chapa galvanizada|10||0|\n"
    "~C|REJ01|ud|Rejilla de impulsión|45.5||0|\n"
    "~D|OBRA##|01#\\1\\1\\|\n~D|01#|UTA01\\1\\1\\CND01\\1\\2400\\REJ01\\1\\8\\|\n"
)
OFERTA = (
    "~V|PROVEEDOR|FIEBDC-3/2016|PRUEBA||ANSI|Oferta|2|\n"
    "~C|OF##||Oferta|0||0|\n~C|EXT01|ud|Extractor helicoidal de cubierta|850||0|\n"
    "~C|SINP|ud|Línea sin precio||0|\n"
    "~D|OF##|EXT01\\1\\1\\SINP\\1\\1\\|\n"
)


def _leer(proyecto, tmp_path: Path, nombre: str, contenido: str, clase: str) -> str:
    f = tmp_path / nombre
    f.write_bytes(contenido.encode("cp1252"))
    doc = proyecto.incorporar_documento(f)
    med_id, _ = proyecto.leer_medicion(doc, clase)
    return med_id


@pytest.fixture
def escenario(proyecto, tmp_path):
    base = _leer(proyecto, tmp_path, "Contrato.bc3", BASE, "presupuesto")
    oferta = _leer(proyecto, tmp_path, "Oferta.bc3", OFERTA, "oferta")
    o = CrearModificado(base, "Ampliación zona de carga")
    proyecto.ejecutar(o)
    partidas = {p["codigo"]: p["id"] for p in proyecto.partidas(base)}
    ofertas = {p["codigo"]: p["id"] for p in proyecto.partidas(oferta)}
    return proyecto, o.id, partidas, ofertas, base


def test_modificado_completo_y_sus_cifras(escenario):
    p, mod, partidas, ofertas, _ = escenario
    p.ejecutar(VariarPartida(mod, partidas["CND01"], 2600, "medicion", "Faltaba el tramo B"))
    p.ejecutar(VariarPartida(mod, partidas["REJ01"], 0, "economica", "Se sustituyen por extractor"))
    p.ejecutar(AnadirPartidaNueva(mod, ofertas["EXT01"], 2, "economica", "Más barato en total"))
    r = p.resumen_modificado(mod)
    cambios = {x.codigo: x for x in r.cambios}
    assert [x.tipo for x in r.cambios] == ["aumento", "anulacion", "nueva"]
    assert (
        cambios["CND01"].diferencia_cantidad == 200 and cambios["CND01"].diferencia_importe == 2000
    )
    assert cambios["REJ01"].importe_modificado == 0 and cambios["REJ01"].diferencia_importe == -364
    ext = cambios["EXT01"]
    assert (ext.cantidad_contrato, ext.cantidad_modificada, ext.precio) == (0, 2, 850)
    assert ext.origen_precio.startswith("Oferta.bc3 · ~D OF##, línea 1")
    assert r.total_contrato == 12500 + 24000 + 364
    assert r.total_modificado == 12500 + 26000 + 0 + 1700
    assert r.diferencia == 2000 - 364 + 1700
    assert not r.parcial
    assert p.modificado(mod)["numero"] == 1 and p.modificado(mod)["n_cambios"] == 3


def test_motivo_y_justificacion_obligatorios(escenario):
    p, mod, partidas, _, _ = escenario
    with pytest.raises(OrdenRechazada, match="justificación"):
        p.ejecutar(VariarPartida(mod, partidas["CND01"], 2600, "medicion", "  "))
    with pytest.raises(OrdenRechazada, match="Motivo desconocido"):
        p.ejecutar(VariarPartida(mod, partidas["CND01"], 2600, "capricho", "x"))


def test_reglas_de_las_variaciones(escenario):
    p, mod, partidas, ofertas, _ = escenario
    with pytest.raises(OrdenRechazada, match="igual a la de contrato"):
        p.ejecutar(VariarPartida(mod, partidas["CND01"], 2400, "medicion", "x"))
    with pytest.raises(OrdenRechazada, match="no negativo"):
        p.ejecutar(VariarPartida(mod, partidas["CND01"], -1, "medicion", "x"))
    with pytest.raises(OrdenRechazada, match="medición de base"):
        p.ejecutar(VariarPartida(mod, ofertas["EXT01"], 3, "medicion", "x"))
    p.ejecutar(VariarPartida(mod, partidas["CND01"], 2600, "medicion", "x"))
    with pytest.raises(OrdenRechazada, match="ya tiene una variación"):
        p.ejecutar(VariarPartida(mod, partidas["CND01"], 2700, "medicion", "x"))


def test_reglas_de_las_partidas_nuevas(escenario):
    p, mod, partidas, ofertas, _ = escenario
    with pytest.raises(OrdenRechazada, match="de una oferta"):
        p.ejecutar(AnadirPartidaNueva(mod, partidas["UTA01"], 1, "diseno", "x"))
    with pytest.raises(OrdenRechazada, match="no tiene precio"):
        p.ejecutar(AnadirPartidaNueva(mod, ofertas["SINP"], 1, "diseno", "x"))
    with pytest.raises(OrdenRechazada, match="mayor que cero"):
        p.ejecutar(AnadirPartidaNueva(mod, ofertas["EXT01"], 0, "diseno", "x"))
    p.ejecutar(AnadirPartidaNueva(mod, ofertas["EXT01"], 1, "diseno", "x"))
    with pytest.raises(OrdenRechazada, match="ya está añadida"):
        p.ejecutar(AnadirPartidaNueva(mod, ofertas["EXT01"], 2, "diseno", "x"))
    assert {x["codigo"] for x in p.ofertas_utilizables()} == {"EXT01"}


def test_no_se_quita_una_medicion_que_usa_un_modificado(escenario):
    p, mod, _, ofertas, base = escenario
    p.ejecutar(AnadirPartidaNueva(mod, ofertas["EXT01"], 1, "diseno", "x"))
    with pytest.raises(OrdenRechazada, match="la usa el modificado"):
        p.ejecutar(QuitarMedicion(base))
    oferta = next(m["id"] for m in p.mediciones() if m["clase"] == "oferta")
    with pytest.raises(OrdenRechazada, match="la usa el modificado"):
        p.ejecutar(QuitarMedicion(oferta))


def test_numeracion_quitar_borrar_y_deshacer(escenario):
    p, mod, partidas, _, base = escenario
    o2 = CrearModificado(base, "Segundo")
    p.ejecutar(o2)
    assert p.modificado(o2.id)["numero"] == 2
    v = VariarPartida(mod, partidas["CND01"], 2600, "medicion", "x")
    p.ejecutar(v)
    p.ejecutar(QuitarCambio(v.id))
    assert p.resumen_modificado(mod).cambios == []
    p.deshacer()
    assert len(p.resumen_modificado(mod).cambios) == 1
    p.ejecutar(BorrarModificado(mod))
    assert p.modificado(mod) is None
    p.deshacer()
    assert p.modificado(mod)["n_cambios"] == 1


def test_partida_a_revisar_no_se_puede_usar(escenario, tmp_path):
    p, mod, _, _, _ = escenario
    p._con.execute("UPDATE partida SET estado='a_revisar', motivos='[\"x\"]' WHERE codigo='EXT01'")
    ext = next(
        x["id"]
        for x in p.partidas(next(m["id"] for m in p.mediciones() if m["clase"] == "oferta"))
        if x["codigo"] == "EXT01"
    )
    with pytest.raises(OrdenRechazada, match="a revisar"):
        p.ejecutar(AnadirPartidaNueva(mod, ext, 1, "diseno", "x"))


def test_totales_parciales_si_falta_un_precio(proyecto, tmp_path):
    base = _leer(proyecto, tmp_path, "B.bc3", BASE.replace("|45.5||0|", "|||0|"), "presupuesto")
    o = CrearModificado(base, "M")
    proyecto.ejecutar(o)
    r = proyecto.resumen_modificado(o.id)
    assert r.parcial and r.sin_importe_contrato == 1
    assert r.total_contrato == 12500 + 24000


def test_excel_del_modificado(escenario, tmp_path):
    p, mod, partidas, ofertas, _ = escenario
    with pytest.raises(OrdenRechazada, match="no tiene cambios"):
        p.exportar_modificado_excel(mod, tmp_path / "m.xlsx")
    p.ejecutar(VariarPartida(mod, partidas["CND01"], 2600, "medicion", "Faltaba el tramo B"))
    p.ejecutar(AnadirPartidaNueva(mod, ofertas["EXT01"], 2, "economica", "Más barato"))
    ruta = p.exportar_modificado_excel(mod, tmp_path / "Modificado 1")
    wb = load_workbook(ruta)
    ws = wb["Modificado nº 1"]
    filas = list(ws.iter_rows(values_only=True))
    assert filas[1][:12] == (
        "Aumento",
        "01 Climatización",
        "CND01",
        "Conducto de chapa galvanizada",
        "m2",
        2400,
        2600,
        200,
        10,
        24000,
        26000,
        2000,
    )
    assert filas[1][12:14] == ("Error de medición", "Faltaba el tramo B")
    assert filas[2][0] == "Partida nueva" and filas[2][14].startswith("Oferta.bc3")
    # Cada total bajo su columna (J contrato, K modificado, L diferencia). Revisión
    # 06-11-2026: los tres iban en la L.
    assert ws.cell(row=1, column=10).value == "Importe contrato"
    assert ws.cell(row=1, column=11).value == "Importe modificado"
    assert ws.cell(row=1, column=12).value == "Dif. importe"
    totales = {
        f[0]: f[9:12] for f in filas if f and f[0] and str(f[0]).startswith(("Suma", "Pres"))
    }
    assert totales == {
        "Suma de estas líneas": (24000, 26000 + 1700, 3700),
        "Presupuesto completo": (36864, 36864 + 2000 + 1700, 3700),
    }
    actualizado = list(wb["Presupuesto actualizado"].iter_rows(values_only=True))
    assert [f[0] for f in actualizado if f and str(f[0] or "").startswith("Suma")] == []
    assert any(f and f[0] == "Presupuesto completo" for f in actualizado)


def test_totales_parciales_si_la_base_tiene_omitidas_o_a_revisar(proyecto, tmp_path):
    # Una línea de porcentaje no es partida (se omite): el total del presupuesto no es el
    # completo y tiene que decirse, en pantalla y en el Excel (revisión 06-11-2026).
    base = _leer(
        proyecto,
        tmp_path,
        "B.bc3",
        BASE.replace("REJ01\\1\\8\\", "REJ01\\1\\8\\%MA\\1\\0.02\\"),
        "presupuesto",
    )
    o = CrearModificado(base, "M")
    proyecto.ejecutar(o)
    r = proyecto.resumen_modificado(o.id)
    assert r.omitidas_base == 1 and r.parcial
    assert any("no pudo convertir" in n for n in r.notas())
    pid = proyecto.partidas(base)[0]["id"]
    proyecto.ejecutar(VariarPartida(o.id, pid, 2, "medicion", "x"))
    ruta = proyecto.exportar_modificado_excel(o.id, tmp_path / "m.xlsx")
    filas = list(load_workbook(ruta)["Modificado nº 1"].iter_rows(values_only=True))
    assert any(f[0] == "Presupuesto completo (parcial)" for f in filas)
    assert any(f[0] and "no pudo convertir" in f[0] for f in filas)


def test_partidas_a_revisar_de_la_base_se_dicen_en_los_totales():
    from traza.app.modificados import calcular

    base = [
        {"id": "a", "capitulo": [], "codigo": "A", "resumen": "a", "unidad": "ud",
         "cantidad": 2.0, "precio": 10.0, "estado": "a_revisar"},
    ]  # fmt: skip
    r = calcular(base, [], {}, {})
    assert r.a_revisar_base == 1 and r.total_contrato == 20
    assert any("«a revisar»" in n for n in r.notas())


def test_numero_de_un_modificado_borrado_no_se_reutiliza(escenario):
    # Revisión 06-11-2026: borrar el último y crear otro le daba el mismo número, y un
    # «nº 2» ya exportado podía acabar siendo otro distinto.
    p, _, _, _, base = escenario
    o2 = CrearModificado(base, "Segundo")
    p.ejecutar(o2)
    p.ejecutar(BorrarModificado(o2.id))
    o3 = CrearModificado(base, "Tercero")
    p.ejecutar(o3)
    assert p.modificado(o3.id)["numero"] == 3
    # Deshacer y rehacer conservan su número.
    p.deshacer()
    p.rehacer()
    assert p.modificado(o3.id)["numero"] == 3


def test_cantidad_con_mas_de_seis_decimales_se_rechaza(escenario):
    # El BC3 se escribe con 6 decimales (y un valor diminuto saldría 0 = «anulada»).
    p, mod, partidas, ofertas, _ = escenario
    with pytest.raises(OrdenRechazada, match="6 decimales"):
        p.ejecutar(VariarPartida(mod, partidas["CND01"], 2600.1234567, "medicion", "x"))
    with pytest.raises(OrdenRechazada, match="6 decimales"):
        p.ejecutar(AnadirPartidaNueva(mod, ofertas["EXT01"], 1e-7, "medicion", "x"))
    p.ejecutar(VariarPartida(mod, partidas["CND01"], 2600.123456, "medicion", "x"))


def test_base_oferta_no_se_anade_a_si_misma(proyecto, tmp_path):
    oferta = _leer(proyecto, tmp_path, "Oferta.bc3", OFERTA, "oferta")
    o = CrearModificado(oferta, "Sobre la oferta")
    proyecto.ejecutar(o)
    linea = next(x for x in proyecto.partidas(oferta) if x["codigo"] == "EXT01")
    with pytest.raises(OrdenRechazada, match="propia base"):
        proyecto.ejecutar(AnadirPartidaNueva(o.id, linea["id"], 1, "otro", "x"))
    proyecto.ejecutar(VariarPartida(o.id, linea["id"], 3, "otro", "x"))
