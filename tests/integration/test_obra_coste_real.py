"""Obra, bloque 2a: coste real por paquete, foto de lo real y previsión del usuario
(docs/modules/obra.md). Con el comparativo inventado de tests/integration/test_obra.py:
paquetes EQUIPOS 18600, CHAPA 3000, MANO DE OBRA 1600 (objetivo 23200)."""

from __future__ import annotations

import pytest
from tests.integration.test_obra import comparativo, obra  # noqa: F401 (fixture)

from traza.app.ordenes import OrdenRechazada


@pytest.fixture
def con_coste(obra, tmp_path):  # noqa: F811
    p, med_id = obra
    p.fijar_venta_contratada(med_id)
    p.importar_coste_objetivo(p.incorporar_documento(comparativo(tmp_path / "C.xlsx")))
    return p


def factura(p, paquete="EQUIPOS", proveedor="Fabricante", numero="F-1", importe=10000.0, **k):
    return p.registrar_factura(
        paquete=paquete,
        proveedor=proveedor,
        numero=numero,
        fecha="2026-11-03",
        importe=importe,
        **k,
    )


def test_facturas_por_paquete_y_descuadres(con_coste):
    p = con_coste
    assert p.estado_paso("coste_real").estado == ""  # sin facturas, sin marca
    factura(p, numero="F-1", importe=12000)
    factura(p, numero="F-2", importe=7000)  # EQUIPOS: 19000 > 18600
    factura(p, paquete="CHAPA", proveedor="Chapista", numero="7", importe=1000)
    factura(p, paquete="CHAPA", proveedor="Chapista", numero="8", importe=-100)  # abono
    f = p.foto_obra()
    por = {x.nombre: x for x in f.paquetes}
    assert por["EQUIPOS"].facturado == 19000 and por["EQUIPOS"].diferencia == -400
    assert por["CHAPA"].facturado == 900 and por["CHAPA"].facturas == 2
    assert por["MANO DE OBRA"].facturado == 0
    assert [x.nombre for x in f.descuadrados] == ["EQUIPOS"]
    assert f.facturado == 19900
    assert p.estado_paso("coste_real").estado == "hecho"


def test_corregir_quitar_y_rechazos(con_coste):
    p = con_coste
    fid = factura(p)
    with pytest.raises(OrdenRechazada, match="Ya está apuntada la factura F-1"):
        factura(p)
    with pytest.raises(OrdenRechazada, match="no es un paquete"):
        factura(p, paquete="INVENTADO", numero="X")
    with pytest.raises(OrdenRechazada, match="no puede ser 0"):
        factura(p, numero="Z", importe=0)
    with pytest.raises(OrdenRechazada, match="Fecha no válida"):
        p.registrar_factura(
            paquete="CHAPA", proveedor="A", numero="1", fecha="31/11/2026", importe=5.0
        )
    # Corregir (mismo id) no choca consigo misma.
    factura(p, importe=11000, id=fid)
    assert p.facturas()[0]["importe"] == 11000
    with pytest.raises(OrdenRechazada, match="No hay cambios"):
        factura(p, importe=11000, id=fid)
    p.quitar_factura(fid)
    assert p.facturas() == []
    p.deshacer()
    assert p.facturas()[0]["importe"] == 11000


def test_paquete_cerrado_no_admite_facturas_y_se_reabre(con_coste):
    p = con_coste
    fid = factura(p)
    p.cerrar_paquete("EQUIPOS")
    assert p.foto_obra().paquetes[0].cerrado
    with pytest.raises(OrdenRechazada, match="está cerrado"):
        factura(p, numero="F-9")
    with pytest.raises(OrdenRechazada, match="está cerrado"):
        p.quitar_factura(fid)
    with pytest.raises(OrdenRechazada, match="ya está cerrado"):
        p.cerrar_paquete("EQUIPOS")
    p.cerrar_paquete("EQUIPOS", cerrar=False)  # reabrir queda en el registro
    factura(p, numero="F-9", importe=50)
    assert len(p.facturas()) == 2


def test_sin_coste_objetivo_no_hay_paquetes(obra):  # noqa: F811
    p, _ = obra
    assert p.estado_paso("coste_real").texto.startswith("Falta: importar el coste objetivo")
    with pytest.raises(OrdenRechazada, match="Importa antes el coste objetivo"):
        factura(p)


def test_prevision_del_usuario_y_foto(con_coste):
    p = con_coste
    assert p.estado_paso("prevision").estado == "pendiente"
    factura(p, importe=5000)
    p.fijar_prevision(coste_total=24000, venta_total=27000, nota="tras la reunión")
    f = p.foto_obra()
    assert f.prevision["coste_total"] == 24000
    assert f.margen_previsto == 3000 and f.margen_previsto_pct == pytest.approx(100 * 3000 / 27000)
    assert f.certificado is None and f.margen_real is None  # llega con las certificaciones
    assert f.venta == pytest.approx(26500) and f.objetivo == pytest.approx(23200)
    assert p.estado_paso("prevision").estado == "hecho"
    with pytest.raises(OrdenRechazada, match="no cambia"):
        p.fijar_prevision(coste_total=24000, venta_total=27000, nota="tras la reunión")
    with pytest.raises(OrdenRechazada, match="negativa"):
        p.fijar_prevision(coste_total=-1, venta_total=0)
    p.deshacer()
    assert p.prevision() is None


def test_facturas_de_un_paquete_que_desaparece_se_avisan(con_coste, tmp_path):
    p = con_coste
    factura(p, paquete="CHAPA", proveedor="Chapista", numero="1", importe=500)
    # Un comparativo nuevo sin el paquete CHAPA (renombrado).
    from openpyxl import load_workbook

    ruta = comparativo(tmp_path / "C2.xlsx")
    wb = load_workbook(ruta)
    ws = wb.active
    for c in ws[2]:
        if c.value == "CHAPA":
            c.value = "CHAPA Y AISLAMIENTO"
    wb.save(ruta)
    p.importar_coste_objetivo(p.incorporar_documento(ruta))
    assert p.foto_obra().huerfanas == {"CHAPA": 500}


def test_redondeo_al_centimo_y_proveedor_sin_mayusculas(con_coste):
    p = con_coste
    factura(p, proveedor="ACME Clima", numero="F-10", importe=10.006)
    assert p.facturas()[0]["importe"] == 10.01
    with pytest.raises(OrdenRechazada, match="no puede ser 0"):
        factura(p, numero="F-11", importe=0.004)
    with pytest.raises(OrdenRechazada, match="Ya está apuntada"):
        factura(p, proveedor="acme  clima", numero="f-10")


def test_mover_factura_con_origen_o_destino_cerrado(con_coste):
    p = con_coste
    fid = factura(p, paquete="EQUIPOS", numero="A1", importe=100)
    p.cerrar_paquete("CHAPA")
    with pytest.raises(OrdenRechazada, match="«CHAPA» está cerrado"):
        factura(p, paquete="CHAPA", numero="A1", importe=100, id=fid)
    p.cerrar_paquete("CHAPA", cerrar=False)
    p.cerrar_paquete("EQUIPOS")
    with pytest.raises(OrdenRechazada, match="paquete cerrado «EQUIPOS»"):
        factura(p, paquete="CHAPA", numero="A1", importe=100, id=fid)
    # Deshacer y rehacer cerrar.
    p.deshacer()
    assert "EQUIPOS" not in p.paquetes_cerrados()
    p.rehacer()
    assert "EQUIPOS" in p.paquetes_cerrados()


def test_paquete_que_desaparece_sigue_en_la_lista_y_cerrado_avisa(con_coste, tmp_path):
    from openpyxl import load_workbook

    p = con_coste
    fid = factura(p, paquete="CHAPA", proveedor="Chapista", numero="1", importe=500)
    p.cerrar_paquete("CHAPA")
    p.cerrar_paquete("EQUIPOS")
    ruta = comparativo(tmp_path / "C2.xlsx")
    wb = load_workbook(ruta)
    ws = wb.active
    for c in ws[2]:
        if c.value == "CHAPA":
            c.value = "CHAPA Y AISLAMIENTO"
    for fila in ws.iter_rows(min_row=5):  # EQUIPOS de la UTA: 18000 → 17000
        if fila[0].value and str(fila[0].value).strip() == "UTA01":
            fila[8].value = 17000
            fila[9].value = 17000
            fila[5].value = 17400
            fila[6].value = 17400
    wb.save(ruta)
    r = p.importar_coste_objetivo(p.incorporar_documento(ruta))
    assert any("paquete cerrado «EQUIPOS» cambia de objetivo" in a for a in r.avisos)
    chapa = next(x for x in p.foto_obra().paquetes if x.nombre == "CHAPA")
    assert not chapa.en_objetivo and chapa.cerrado and chapa.facturado == 500
    # Se puede reabrir y corregir a un paquete del objetivo.
    p.cerrar_paquete("CHAPA", cerrar=False)
    factura(p, paquete="CHAPA Y AISLAMIENTO", proveedor="Chapista", numero="1", importe=500, id=fid)
    assert p.foto_obra().huerfanas == {}
