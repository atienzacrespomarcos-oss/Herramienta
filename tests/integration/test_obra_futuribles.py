"""Obra, bloque 3: futuribles (escenarios sí/no) y Excel de control (docs/modules/obra.md).

Venta inventada de tests/integration/test_obra.py: UTA01 20 000 + CND01 100 m² × 60 + EXTRA
500 = 26 500 €; coste objetivo 23 200 € (EQUIPOS 18 600, CHAPA 3 000, MANO DE OBRA 1 600).
"""

from __future__ import annotations

import pytest
from openpyxl import load_workbook
from tests.integration.test_obra import BC3_VENTA, comparativo, obra  # noqa: F401 (fixture)

from traza.app.ordenes import (
    BorrarModificado,
    CrearModificado,
    OrdenRechazada,
    QuitarCambio,
    QuitarMedicion,
    VariarPartida,
)


@pytest.fixture
def con_venta(obra, tmp_path):  # noqa: F811
    p, med_id = obra
    p.fijar_venta_contratada(med_id)
    p.importar_coste_objetivo(p.incorporar_documento(comparativo(tmp_path / "C.xlsx")))
    return p, med_id


def _modificado(p, med_id, titulo="Ampliación zona de carga", cantidad=150):
    o = CrearModificado(med_id, titulo)
    p.ejecutar(o)
    cnd = next(x["id"] for x in p.partidas(med_id) if x["codigo"] == "CND01")
    p.ejecutar(VariarPartida(o.id, cnd, cantidad, "medicion", "Faltaba el tramo B"))
    return o.id


def test_escenario_sin_y_con_los_marcados(con_venta):
    p, _ = con_venta
    assert p.estado_paso("futuribles").estado == ""  # sin futuribles, sin marca
    a = p.guardar_futurible(titulo="Oficinas planta 1", venta=12000.004, coste=9000)
    b = p.guardar_futurible(titulo="Baja de rejillas", venta=-800, coste=-650, nota="Pedida")
    assert p.estado_paso("futuribles").estado == "hecho"
    # Sin tu previsión no hay escenario que sumar.
    e = p.escenario()
    assert [f.titulo for f in e.futuribles] == ["Oficinas planta 1", "Baja de rejillas"]
    assert e.futuribles[0].venta == 12000.0  # al céntimo
    assert e.futuribles[1].margen == pytest.approx(-150)
    assert e.venta is None and e.coste is None
    p.fijar_prevision(coste_total=24000, venta_total=27000)
    e = p.escenario()
    # Nada marcado: el escenario es tu previsión.
    assert (e.venta, e.coste, e.margen) == (27000, 24000, 3000)
    p.marcar_futurible(a, True)
    p.marcar_futurible(b, True)
    e = p.escenario()
    assert e.venta == pytest.approx(27000 + 12000 - 800)
    assert e.coste == pytest.approx(24000 + 9000 - 650)
    assert e.margen_pct == pytest.approx(100 * (38200 - 32350) / 38200)
    # Tu previsión no se toca (los futuribles nunca entran en ella).
    assert p.foto_obra().margen_previsto == 3000
    p.marcar_futurible(b, False)
    assert p.escenario().venta == pytest.approx(39000)
    with pytest.raises(OrdenRechazada, match="Ya está fuera"):
        p.marcar_futurible(b, False)
    p.deshacer()
    assert p.escenario().venta == pytest.approx(38200)


def test_venta_de_un_modificado_al_dia(con_venta):
    p, med_id = con_venta
    mod = _modificado(p, med_id)  # CND01 100 → 150 m² × 60 €
    fid = p.guardar_futurible(titulo="Zona de carga", modificado_id=mod, coste=2500)
    f = p.futuribles()[0]
    assert f.venta == 3000 and f.margen == 500
    assert f.origen == "modificado nº 1 «Ampliación zona de carga»" and f.avisos == ()
    # El modificado cambia: la venta del futurible le sigue (no se copia una cifra).
    cnd = next(x["id"] for x in p.partidas(med_id) if x["codigo"] == "CND01")
    p.ejecutar(QuitarCambio(p.resumen_modificado(mod).cambios[0].cambio_id))
    p.ejecutar(VariarPartida(mod, cnd, 120, "medicion", "Al final, tramo corto"))
    assert p.futuribles()[0].venta == 1200
    # Uno por modificado; no se borra el modificado del que sale una venta.
    with pytest.raises(OrdenRechazada, match="ya es el futurible «Zona de carga»"):
        p.guardar_futurible(titulo="Otra vez", modificado_id=mod, coste=1)
    with pytest.raises(OrdenRechazada, match="Quita antes el futurible"):
        p.ejecutar(BorrarModificado(mod))
    p.quitar_futurible(fid)
    p.ejecutar(BorrarModificado(mod))


def test_modificado_sin_cambios_o_de_otro_presupuesto(con_venta, tmp_path):
    p, med_id = con_venta
    vacio = CrearModificado(med_id, "Pendiente de medir")
    p.ejecutar(vacio)
    p.guardar_futurible(titulo="Por medir", modificado_id=vacio.id, coste=0)
    f = p.futuribles()[0]
    assert f.venta is None and "aún no tiene cambios" in f.avisos[0]  # no consta, no 0
    # Un modificado de otra medición no es una ampliación de esta obra.
    otra = tmp_path / "Otra.bc3"
    otra.write_bytes(BC3_VENTA.replace("Nave", "Nave B").encode("cp1252"))
    otra_id, _ = p.leer_medicion(p.incorporar_documento(otra), "presupuesto")
    ajeno = _modificado(p, otra_id, "Ajeno")
    with pytest.raises(OrdenRechazada, match="no es del presupuesto contratado"):
        p.guardar_futurible(titulo="Ajeno", modificado_id=ajeno, coste=1)
    # Si después se elige otro presupuesto contratado, se avisa (no se calla).
    con_cambios = _modificado(p, med_id, "Con cambios")
    fid = p.guardar_futurible(titulo="Con cambios", modificado_id=con_cambios, coste=100)
    p.marcar_futurible(fid, True)
    p.fijar_prevision(coste_total=24000, venta_total=27000)
    assert p.escenario().venta == 30000
    p.fijar_venta_contratada(otra_id)
    f = p.futuribles()[1]
    assert f.venta is None and "ya no es del presupuesto contratado" in f.avisos[0]
    # Ni suma en el escenario: sin venta, no hay cifra que dar.
    assert p.escenario().venta is None


def test_corregir_y_rechazos(con_venta):
    p, _ = con_venta
    fid = p.guardar_futurible(titulo="Oficinas", venta=1000, coste=800)
    p.marcar_futurible(fid, True)
    p.guardar_futurible(id=fid, titulo="Oficinas  planta 1 ", venta=1100, coste=800)
    f = p.futuribles()[0]
    assert f.titulo == "Oficinas planta 1" and f.venta == 1100
    assert f.marcado  # corregir no lo saca del escenario
    with pytest.raises(OrdenRechazada, match="No hay cambios"):
        p.guardar_futurible(id=fid, titulo="Oficinas planta 1", venta=1100, coste=800)
    with pytest.raises(OrdenRechazada, match="necesita un título"):
        p.guardar_futurible(titulo="  ", venta=1, coste=1)
    with pytest.raises(OrdenRechazada, match="una de las dos"):
        p.guardar_futurible(titulo="Sin venta", coste=1)
    with pytest.raises(OrdenRechazada, match="tiene que ser un número"):
        p.guardar_futurible(titulo="X", venta=float("nan"), coste=1)
    with pytest.raises(OrdenRechazada, match="tiene que ser un número"):
        p.guardar_futurible(titulo="X", venta=1, coste=True)
    with pytest.raises(OrdenRechazada, match="no existe"):
        p.guardar_futurible(titulo="X", modificado_id="nada", coste=1)


def test_excel_de_control(con_venta, tmp_path):
    p, med_id = con_venta
    p.registrar_factura(
        paquete="EQUIPOS", proveedor="Fabricante", numero="F-1", fecha="2026-11-03", importe=9000
    )
    p.fijar_prevision(coste_total=24000, venta_total=27000, nota="Tras la reunión")
    mod = _modificado(p, med_id)
    a = p.guardar_futurible(titulo="Zona de carga", modificado_id=mod, coste=2500)
    p.guardar_futurible(titulo="Oficinas", venta=12000, coste=9000)
    p.marcar_futurible(a, True)
    ruta = p.exportar_control_obra(tmp_path / "salida" / "Nave - control")
    assert ruta.name == "Nave - control.xlsx" and not list(ruta.parent.glob("*.parcial"))
    wb = load_workbook(ruta)
    assert wb.sheetnames == [
        "Resumen",
        "Venta y objetivo",
        "Paquetes",
        "Facturas",
        "Certificaciones",
        "Certificado por partida",
        "Futuribles",
        "Información",
    ]
    r = [[c.value for c in fila] for fila in wb["Resumen"].iter_rows(min_row=1, max_row=5)]
    assert r[1] == ["Venta", 26500, None, 27000, 30000]  # sin certificar: vacío, no 0
    assert r[2] == ["Coste", 23200, 9000, 24000, 26500]
    assert r[3] == ["Margen", 3300, None, 3000, 3500]
    assert r[4][4] == pytest.approx(round(100 * 3500 / 30000, 1))
    notas = [f[0].value for f in wb["Resumen"].iter_rows(min_row=7)]
    assert "Nota de tu previsión: Tras la reunión" in notas
    fut = [[c.value for c in f] for f in wb["Futuribles"].iter_rows(min_row=2)]
    assert fut[0][:6] == [
        "Zona de carga",
        3000,
        2500,
        500,
        "Sí",
        "modificado nº 1 «Ampliación zona de carga»",
    ]
    assert fut[1][:5] == ["Oficinas", 12000, 9000, 3000, "No"]
    paquetes = {f[0].value: f[2].value for f in wb["Paquetes"].iter_rows(min_row=2)}
    assert paquetes["EQUIPOS"] == 9000
    partidas = [[c.value for c in f] for f in wb["Certificado por partida"].iter_rows(min_row=2)]
    assert [x[0] for x in partidas] == ["UTA01", "CND01", "EXTRA"]
    assert partidas[1][2] == 6000 and partidas[1][3] is None  # sin certificaciones


def test_excel_sin_nada_que_controlar(proyecto, tmp_path):
    with pytest.raises(OrdenRechazada, match="nada que controlar"):
        proyecto.exportar_control_obra(tmp_path / "x.xlsx")


def test_deshacer_y_rehacer(con_venta):
    p, med_id = con_venta
    mod = _modificado(p, med_id)
    fid = p.guardar_futurible(titulo="Zona de carga", modificado_id=mod, coste=2500)
    p.guardar_futurible(id=fid, titulo="Zona de carga", modificado_id=mod, coste=2000)
    p.deshacer()
    assert p.futuribles()[0].coste == 2500
    p.rehacer()
    assert p.futuribles()[0].coste == 2000
    p.quitar_futurible(fid)
    assert p.futuribles() == []
    p.deshacer()
    assert p.futuribles()[0].venta == 3000  # vuelve atado a su modificado
    # La base del modificado tampoco se quita mientras haya modificado (y futurible).
    p.quitar_venta_contratada()
    with pytest.raises(OrdenRechazada, match="la usa el modificado"):
        p.ejecutar(QuitarMedicion(med_id))


def test_excel_con_certificaciones_y_textos_ajenos(con_venta, tmp_path):
    from tests.integration.test_obra_certificaciones import CLIENTE, PORCENTAJE, excel, sin_ia

    p, _ = con_venta
    p.mapeador_ia = sin_ia
    for n, filas in ((1, PORCENTAJE), (2, CLIENTE)):
        doc = p.incorporar_documento(excel(tmp_path / f"C{n}.xlsx", filas))
        mapa, r = p.leer_certificacion(doc)
        p.importar_certificacion(doc, n, f"2026-1{n - 1}-30", mapa, r)
    p.guardar_futurible(titulo="=SUMA(A1:A9)", venta=1, coste=1)
    wb = load_workbook(p.exportar_control_obra(tmp_path / "control.xlsx"))
    certs = [[c.value for c in f] for f in wb["Certificaciones"].iter_rows(min_row=2)]
    assert [(c[0], c[3], c[4]) for c in certs] == [(1, 12100, 12100), (2, 12600, 500)]
    ws = wb["Certificado por partida"]
    assert [c.value for c in ws[1]] == [
        "Código",
        "Descripción",
        "Venta",
        "Nº 1 a origen",
        "Nº 2 a origen",
        "% certificado",
    ]
    filas = {f[0].value: [c.value for c in f] for f in ws.iter_rows(min_row=2)}
    assert filas["UTA01"][3:] == [10000, 10000, 50.0]
    assert filas["CND01"][3:] == [2100, 2100, 35.0]
    assert filas["EXTRA"][3:] == [None, 500, 100.0]  # en la nº 1 no consta
    assert wb["Resumen"]["C2"].value == 12600  # venta real = a origen de la última
    celda = wb["Futuribles"]["A2"]
    assert celda.value == "=SUMA(A1:A9)" and celda.data_type == "s"  # texto, no fórmula
