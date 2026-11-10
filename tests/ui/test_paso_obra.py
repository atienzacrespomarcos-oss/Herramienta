"""Pasos de Obra desde la ventana (docs/modules/obra.md)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from tests.integration.test_obra import BC3_VENTA, comparativo
from tests.ui.test_ventana import PreguntasPreparadas

from traza.app.ordenes import CambiarEncargo
from traza.app.proyecto import Proyecto
from traza.ui.ventana import VentanaPrincipal

pytestmark = pytest.mark.ui


@pytest.fixture
def ventana(qtbot, tmp_path):
    q = PreguntasPreparadas()
    v = VentanaPrincipal(q)
    qtbot.addWidget(v)
    p = Proyecto.crear(tmp_path / "Obra", "Obra", "obra")
    bc3 = tmp_path / "Venta.bc3"
    bc3.write_bytes(BC3_VENTA.encode("cp1252"))
    p.leer_medicion(p.incorporar_documento(bc3), "presupuesto")
    p.incorporar_documento(comparativo(tmp_path / "Costes.xlsx"))
    # Las pruebas nunca llaman a la IA real.
    from tests.integration.test_obra_certificaciones import sin_ia

    p.mapeador_ia = sin_ia
    p.mapeador_facturas_ia = sin_ia
    v._usar_proyecto(p)
    yield v, q
    if v.proyecto is not None:
        v.proyecto.cerrar()


def _claves(v):
    return [v.lista_pasos.item(i).data(Qt.UserRole) for i in range(v.lista_pasos.count())]


def test_pasos_y_menu_solo_en_obra(ventana):
    v, _ = ventana
    claves = _claves(v)
    assert claves.index("mediciones") < claves.index("venta") < claves.index("coste_objetivo")
    assert "modificados" in claves and "entregables" not in claves
    assert v.menu_obra.menuAction().isVisible()
    v.proyecto.ejecutar(CambiarEncargo("oferta"))
    v.refrescar()
    assert "venta" not in _claves(v) and not v.menu_obra.menuAction().isVisible()


def test_elegir_venta_e_importar_coste(ventana):
    v, q = ventana
    pv, pc = v.pagina_venta, v.pagina_coste_objetivo
    v.ir_a_paso("venta")
    assert "Elige el presupuesto contratado" in pv.resumen.text()
    q.preparar("elegir", 0)
    pv.a_contratado.trigger()
    assert not q.avisos, q.avisos
    assert "Venta: 26.500,00 €" in pv.resumen.text() and pv.tabla.rowCount() == 1
    assert pv.a_quitar.isEnabled()
    v.ir_a_paso("coste_objetivo")
    q.preparar("elegir", 0)
    pc.a_importar.trigger()
    assert not q.avisos, q.avisos
    texto = pc.resumen.text()
    assert "Coste objetivo (Costes.xlsx, hoja «Hoja1»): 23.200,00 €" in texto
    assert "Margen previsto: 3.300,00 € (12,5 %)" in texto
    filas = {
        pc.tabla.item(i, 0).text(): pc.tabla.item(i, 1).text() for i in range(pc.tabla.rowCount())
    }
    assert filas == {"EQUIPOS": "18.600,00 €", "CHAPA": "3.000,00 €", "MANO DE OBRA": "1.600,00 €"}
    assert "1 solo en la venta, 2 solo en el coste" in pc.avisos.text()
    item = next(
        v.lista_pasos.item(i)
        for i in range(v.lista_pasos.count())
        if v.lista_pasos.item(i).data(Qt.UserRole) == "coste_objetivo"
    )
    assert item.text().startswith("✓ ")


def test_sin_excel_avisa(ventana, tmp_path):
    v, q = ventana
    # Un proyecto de obra sin Excel incorporado.
    p = Proyecto.crear(tmp_path / "Vacia", "Vacía", "obra")
    v._usar_proyecto(p)
    v.pagina_coste_objetivo.a_importar.trigger()
    assert any("Incorpora antes" in a for a in q.avisos)
    v.pagina_venta.a_contratado.trigger()
    assert any("No hay ningún presupuesto leído" in a for a in q.avisos)


def test_objetivo_cero_con_paquetes_no_rompe_la_pantalla(ventana, monkeypatch):
    v, q = ventana
    p = v.proyecto
    q.preparar("elegir", 0)
    v.pagina_coste_objetivo.a_importar.trigger()
    original = p.coste_objetivo

    def a_cero():
        c = original()
        for x in c["partidas"]:
            x["importe"] = 0.0  # fórmulas sin resultado guardado
        return c

    monkeypatch.setattr(p, "coste_objetivo", a_cero)
    v.refrescar()  # no lanza (antes, división por cero)
    assert not q.avisos
    filas = [
        v.pagina_coste_objetivo.tabla.item(i, 0).text()
        for i in range(v.pagina_coste_objetivo.tabla.rowCount())
    ]
    assert "(sin repartir en paquetes)" in filas


def _preparar_obra(v, q):
    q.preparar("elegir", 0)
    v.pagina_venta.a_contratado.trigger()
    q.preparar("elegir", 0)
    v.pagina_coste_objetivo.a_importar.trigger()


def test_coste_real_facturas_y_cerrar(ventana):
    v, q = ventana
    _preparar_obra(v, q)
    pc = v.pagina_coste_real
    v.ir_a_paso("coste_real")
    assert pc.tabla.rowCount() == 3 and pc.a_factura.isEnabled()
    pc.tabla.setCurrentCell(0, 0)  # EQUIPOS
    vistos = []

    def rellenar(paquetes, actual):
        vistos.append(actual)
        return {
            "paquete": "EQUIPOS",
            "proveedor": "Fabricante",
            "numero": "F-1",
            "fecha": "2026-11-03",
            "importe": 19000.0,
        }

    q.preparar("factura", rellenar)
    pc.a_factura.trigger()
    assert not q.avisos, q.avisos
    assert vistos == [{"paquete": "EQUIPOS"}]  # sale con el paquete elegido
    fila = [pc.tabla.item(0, j).text() for j in range(5)]
    assert fila == ["EQUIPOS", "18.600,00 €", "19.000,00 €", "-400,00 €", "Abierto"]
    assert "Se han pasado del objetivo: EQUIPOS (400,00 €)" in pc.avisos.text()
    assert pc.facturas.rowCount() == 1 and pc.facturas.item(0, 0).text() == "03-11-2026"
    # Repetida: el diálogo vuelve con lo escrito y se puede cancelar.
    q.preparar("factura", rellenar, None)
    pc.a_factura.trigger()
    assert any("Ya está apuntada" in a for a in q.avisos)
    pc.tabla.setCurrentCell(0, 0)
    pc.a_cerrar.trigger()
    assert pc.tabla.item(0, 4).text() == "Cerrado"


def test_prevision_en_pantalla(ventana):
    v, q = ventana
    _preparar_obra(v, q)
    pp = v.pagina_prevision
    v.ir_a_paso("prevision")
    assert "Aún no has puesto tu previsión" in pp.resumen.text()
    q.preparar("prevision", {"venta_total": 27000.0, "coste_total": 24000.0, "nota": ""})
    pp.a_prevision.trigger()
    assert not q.avisos, q.avisos
    filas = {
        pp.tabla.item(i, 0).text(): [pp.tabla.item(i, j).text() for j in (1, 2, 3)]
        for i in range(pp.tabla.rowCount())
    }
    assert filas["Venta"] == ["26.500,00 €", "—", "27.000,00 €"]
    assert filas["Coste"] == ["23.200,00 €", "0,00 €", "24.000,00 €"]
    assert filas["Margen"] == ["3.300,00 €", "—", "3.000,00 €"]
    assert "Sin certificaciones: la venta real sale de" in pp.resumen.text()


def test_importar_certificacion_desde_la_ventana(ventana, tmp_path):
    from tests.integration.test_obra_certificaciones import SUYO, excel

    v, q = ventana
    _preparar_obra(v, q)
    p = v.proyecto
    p.incorporar_documento(excel(tmp_path / "Cert3.xlsx", SUYO, titulo_en=3))
    v.refrescar()
    pc = v.pagina_certificaciones
    v.ir_a_paso("certificaciones")
    assert "Sin certificaciones" in pc.resumen.text() and pc.a_importar.isEnabled()
    docs = [d["nombre_original"] for d in p.documentos() if d["extension"] == ".xlsx"]
    q.preparar("elegir", docs.index("Cert3.xlsx"))
    q.preparar("certificacion", {"numero": 3, "fecha": "2026-11-30"})
    pc.a_importar.trigger()
    assert not q.avisos, q.avisos
    explicacion, numero = q.explicaciones[-1]
    assert numero == 1  # la primera: se propone el nº 1
    assert "importe a origen en E («Importe a origen»)" in explicacion
    assert "Certificado a origen: 12.100,00 €" in explicacion
    assert "no coincide con el TOTAL del Excel" in explicacion
    fila = [pc.tabla.item(0, j).text() for j in range(5)]
    assert fila == ["3", "30-11-2026", "12.100,00 €", "12.100,00 €", "45,7 %"]
    assert "Venta real (certificado a origen, nº 3): 12.100,00 €" in pc.resumen.text()
    # La previsión ya enseña la venta real.
    filas = {
        v.pagina_prevision.tabla.item(i, 0).text(): v.pagina_prevision.tabla.item(i, 2).text()
        for i in range(v.pagina_prevision.tabla.rowCount())
    }
    assert filas["Venta"] == "12.100,00 €" and filas["Margen"] == "12.100,00 €"


def test_futuribles_escenario_y_excel_de_control(ventana, tmp_path):
    v, q = ventana
    p = v.proyecto
    med_id = p.mediciones()[0]["id"]
    p.fijar_venta_contratada(med_id)
    p.fijar_prevision(coste_total=24000, venta_total=27000)
    from traza.app.ordenes import CrearModificado, VariarPartida

    o = CrearModificado(med_id, "Zona de carga")
    p.ejecutar(o)
    cnd = next(x["id"] for x in p.partidas(med_id) if x["codigo"] == "CND01")
    p.ejecutar(VariarPartida(o.id, cnd, 150, "medicion", "Tramo B"))
    v.refrescar()
    assert "futuribles" in _claves(v)
    v.ir_a_paso("futuribles")
    pf = v.pagina_futuribles
    assert "Sin futuribles" in pf.resumen.text()
    assert not pf.a_marcar.isEnabled()

    # Lo que ve el diálogo: los modificados del presupuesto contratado.
    def desde_modificado(modificados, actual):
        assert [m["titulo"] for m in modificados] == ["Zona de carga"] and actual is None
        return {"titulo": "Zona de carga", "venta": None, "modificado_id": o.id, "coste": 2500}

    q.preparar("futurible", desde_modificado)
    pf.a_nuevo.trigger()
    q.preparar("futurible", {"titulo": "Oficinas", "venta": 12000, "coste": 9000})
    pf.a_nuevo.trigger()
    assert not q.avisos, q.avisos
    filas = [[pf.tabla.item(i, c).text() for c in range(5)] for i in range(pf.tabla.rowCount())]
    assert filas[0] == ["Zona de carga", "3.000,00 €", "2.500,00 €", "500,00 €", "No"]
    assert "modificado nº 1 «Zona de carga»" in pf.avisos.text()
    pf.tabla.selectRow(0)
    pf.a_marcar.trigger()
    assert pf.tabla.item(0, 4).text() == "Sí"
    assert "Con los 1 marcados: venta 30.000,00 €" in pf.resumen.text()
    # Corregir: el diálogo recibe lo actual; el ya usado sigue ofrecido para sí mismo.
    pf.tabla.selectRow(0)

    def corregir(modificados, actual):
        assert actual["modificado_id"] == o.id and actual["venta"] is None
        assert [m["id"] for m in modificados] == [o.id]
        return {**actual, "coste": 2000}

    q.preparar("futurible", corregir)
    pf.a_corregir.trigger()
    assert not q.avisos, (q.titulos, q.avisos)
    assert pf.tabla.item(0, 2).text() == "2.000,00 €" and pf.tabla.item(0, 4).text() == "Sí"

    v.ir_a_paso("prevision")
    pp = v.pagina_prevision
    assert pp.tabla.item(0, 4).text() == "30.000,00 €"  # 27 000 + 3 000
    assert pp.tabla.item(1, 4).text() == "26.000,00 €"  # 24 000 + 2 000
    assert "Futuribles marcados: 1 de 2" in pp.resumen.text()
    destino = tmp_path / "control.xlsx"
    q.preparar("destino_excel", destino)
    pp.a_excel.trigger()
    assert not q.avisos, q.avisos
    assert destino.exists()

    v.ir_a_paso("futuribles")
    pf.tabla.selectRow(1)
    pf.a_quitar.trigger()
    assert pf.tabla.rowCount() == 1


def test_importar_facturas_del_erp_desde_la_ventana(ventana, tmp_path):
    from tests.integration.test_obra_facturas_erp import CSV

    v, q = ventana
    _preparar_obra(v, q)
    pc = v.pagina_coste_real
    v.ir_a_paso("coste_real")
    ruta = tmp_path / "Facturas.csv"
    ruta.write_bytes(CSV.encode("cp1252"))
    v.proyecto.incorporar_documento(ruta)
    v.refrescar()
    assert pc.a_erp.isEnabled()
    q.preparar("elegir", lambda opciones: opciones.index("Facturas.csv"))  # el listado
    q.preparar("elegir", 0)  # de las dos obras del listado, la primera

    def tabla(propuestas, paquetes):
        assert [x.leida.obra for x in propuestas] == ["OB-25 Nave"] * 3
        assert "MANO DE OBRA" in paquetes
        return [
            {"paquete": "CHAPA" if x.leida.proveedor.startswith("Chapas") else "EQUIPOS",
             "proveedor": x.leida.proveedor, "numero": x.leida.numero,
             "fecha": x.leida.fecha, "importe": x.leida.importe}
            for x in propuestas
        ]  # fmt: skip

    q.preparar("facturas_erp", tabla)
    pc.a_erp.trigger()
    assert not q.avisos, q.avisos
    assert "He entendido (por sus títulos)" in q.explicaciones[-1]
    assert "3 factura(s); 3 nueva(s)" in q.explicaciones[-1]
    filas = {pc.tabla.item(i, 0).text(): pc.tabla.item(i, 2).text() for i in range(3)}
    assert filas["EQUIPOS"] == "12.000,00 €" and filas["CHAPA"] == "900,50 €"
    assert "De la obra: OB-25 Nave" in q.explicaciones[-1]


def test_listado_de_una_sola_obra_se_confirma(ventana, tmp_path):
    from tests.integration.test_obra_facturas_erp import CSV

    v, q = ventana
    _preparar_obra(v, q)
    pc = v.pagina_coste_real
    v.ir_a_paso("coste_real")
    una = "\r\n".join(x for x in CSV.split("\r\n") if "OB-31" not in x)
    ruta = tmp_path / "Otra obra.csv"
    ruta.write_bytes(una.encode("cp1252"))
    v.proyecto.incorporar_documento(ruta)
    v.refrescar()
    q.preparar("elegir", lambda opciones: opciones.index("Otra obra.csv"))
    q.preparar("confirmar", False)  # «no es esta obra»: no se importa nada
    pc.a_erp.trigger()
    assert not q.avisos and v.proyecto.facturas() == []


def test_dialogo_de_facturas_del_erp(qtbot):
    """La tabla de confirmación: las nuevas marcadas con el paquete propuesto; las ya
    apuntadas, sin marcar y sin poder marcarse; sin paquete, no deja aceptar."""
    from PySide6.QtCore import Qt

    from traza.app.obra import FacturaPropuesta
    from traza.io.facturas_erp import FacturaLeida
    from traza.ui.dialogos_obra import SIN_PAQUETE, DialogoFacturasErp

    def leida(n):
        return FacturaLeida(n, "Pérez SL", str(n), "2026-10-05", 100.0 * n, "", "", False)

    propuestas = [
        FacturaPropuesta(leida(1), "nueva", "CHAPA", "sus otras facturas van ahí"),
        FacturaPropuesta(leida(2), "nueva", None, "elige el paquete"),
        FacturaPropuesta(leida(3), "apuntada", "EQUIPOS", "ya está apuntada"),
    ]
    d = DialogoFacturasErp(None, "explicación", propuestas, ["EQUIPOS", "CHAPA"])
    qtbot.addWidget(d)
    assert d.marcada(0) and d.marcada(1) and not d.marcada(2)
    assert not (d.tabla.item(2, 0).flags() & Qt.ItemIsEnabled)  # no se puede marcar
    assert d._combos[0].currentText() == "CHAPA" and d._combos[1].currentText() == SIN_PAQUETE
    assert not d._combos[2].isEnabled()
    d._aceptar()
    assert d.resultado is None and "Elige el paquete de 1" in d.error.text()
    d._combos[1].setCurrentText("EQUIPOS")
    d._aceptar()
    assert [(x["numero"], x["paquete"]) for x in d.resultado] == [("1", "CHAPA"), ("2", "EQUIPOS")]
