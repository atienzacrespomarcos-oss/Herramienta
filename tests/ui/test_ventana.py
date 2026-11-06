"""La interfaz, recorrida como la usa el ingeniero, con respuestas preparadas a los diálogos."""

from __future__ import annotations

from collections import deque
from pathlib import Path

import pytest
from PySide6.QtCore import QMetaMethod, Qt
from PySide6.QtGui import QAction

from traza.core.procedencia import Origen, Procedencia
from traza.ui.dialogos import DatosValor, DialogoValor
from traza.ui.ventana import NO_CONSTA, VentanaPrincipal

pytestmark = pytest.mark.ui


class PreguntasPreparadas:
    """Sustituye los diálogos: cada método devuelve la siguiente respuesta preparada."""

    def __init__(self) -> None:
        self.respuestas: dict[str, deque] = {}
        self.avisos: list[str] = []
        self.informaciones: list[str] = []

    def preparar(self, metodo: str, *valores) -> None:
        self.respuestas.setdefault(metodo, deque()).extend(valores)

    def _siguiente(self, metodo: str):
        cola = self.respuestas.get(metodo)
        assert cola, f"La interfaz preguntó «{metodo}» sin respuesta preparada"
        return cola.popleft()

    def nuevo_proyecto(self):
        return self._siguiente("nuevo_proyecto")

    def proyecto_existente(self):
        return self._siguiente("proyecto_existente")

    def documento(self):
        return self._siguiente("documento")

    def nuevo_elemento(self, tipos, elementos):
        return self._siguiente("nuevo_elemento")

    def valor(self, tipo, documentos, clave_inicial=None):
        return self._siguiente("valor")

    def texto(self, titulo, etiqueta):
        return self._siguiente("texto")

    def elegir(self, titulo, etiqueta, opciones):
        r = self._siguiente("elegir")
        return r(opciones) if callable(r) else r

    def confirmar(self, titulo, texto):
        return self._siguiente("confirmar")

    def aviso(self, titulo, texto):
        self.avisos.append(texto)

    def informacion(self, titulo, texto):
        self.informaciones.append(texto)

    def encargo(self, actual):
        return self._siguiente("encargo")

    def leer_medicion(self, documentos):
        return self._siguiente("leer_medicion")

    def destino_excel(self, sugerido):
        return self._siguiente("destino_excel")


@pytest.fixture
def ventana(qtbot):
    preguntas = PreguntasPreparadas()
    v = VentanaPrincipal(preguntas)
    qtbot.addWidget(v)
    yield v, preguntas
    if v.proyecto is not None:
        v.proyecto.cerrar()


def _acciones(v: VentanaPrincipal) -> list[QAction]:
    return [a for m in v.menuBar().actions() for a in m.menu().actions() if not a.isSeparator()]


class PreguntasQueCancelan(PreguntasPreparadas):
    """El usuario cancela todos los diálogos."""

    def _siguiente(self, metodo):
        return False if metodo == "confirmar" else None


def test_todas_las_acciones_se_ejecutan_sin_error(qtbot, tmp_path, pdf_3_paginas):
    """Cada acción del menú se dispara de verdad (con un proyecto, un elemento, un
    documento y un pendiente) y ninguna termina en «Error en …»: no hay acción decorativa
    ni acción que reviente. Antes este test solo miraba que la señal estuviera conectada,
    lo que siempre es cierto (revisión 06-11-2026)."""
    q = PreguntasQueCancelan()
    v = VentanaPrincipal(q)
    qtbot.addWidget(v)
    try:
        v._usar_proyecto(
            __import__("traza.app.proyecto", fromlist=["Proyecto"]).Proyecto.crear(
                tmp_path / "N", "N"
            )
        )
        v.proyecto.incorporar_documento(pdf_3_paginas)
        from traza.app.ordenes import CrearElemento, CrearPendiente

        o = CrearElemento("equipo", "EQ-1")
        v.proyecto.ejecutar(o)
        v.proyecto.ejecutar(CrearPendiente("dato"))
        v.refrescar()
        v.seleccionar(o.id)
        v.tabla_documentos.setCurrentCell(0, 0)
        v.tabla_pendientes.setCurrentCell(0, 0)
        v.tabla_propiedades.setCurrentCell(0, 0)
        acciones = [a for a in _acciones(v) if a is not v.a_salir]
        assert len(acciones) >= 18
        ejecutadas = 0
        for a in acciones:
            assert a.isSignalConnected(QMetaMethod.fromSignal(a.triggered)), a.text()
            if a is v.a_abrir_doc:
                continue  # abriría el visor de PDF del sistema; se prueba aparte
            a.trigger()
            ejecutadas += 1
            if v.proyecto is None:  # «Cerrar proyecto»: se vuelve a abrir para seguir
                v.abrir(tmp_path / "N.traza")
                v.seleccionar(o.id)
        assert ejecutadas == len(acciones) - 1
        assert not [x for x in q.avisos if x.startswith("Error")], q.avisos
    finally:
        if v.proyecto is not None:
            v.proyecto.cerrar()


def test_un_error_de_disco_se_avisa_y_no_revienta(ventana, tmp_path, monkeypatch):
    v, q = ventana
    q.preparar("nuevo_proyecto", (tmp_path / "N", "N", "instalacion"))
    v.a_nuevo.trigger()

    def disco_lleno():
        raise OSError("No queda espacio en el disco")

    monkeypatch.setattr(v.proyecto, "copia_de_seguridad", disco_lleno)
    v.a_copia.trigger()
    assert "No queda espacio en el disco" in q.avisos[-1]


def test_no_se_ejecutan_ficheros_incorporados(ventana, tmp_path, monkeypatch):
    v, q = ventana
    q.preparar("nuevo_proyecto", (tmp_path / "N", "N", "instalacion"))
    v.a_nuevo.trigger()
    bat = tmp_path / "peligroso.bat"
    bat.write_text("echo hola", encoding="utf-8")
    q.preparar("documento", (bat, "otro"))
    v.a_incorporar.trigger()
    abiertos = []
    monkeypatch.setattr("traza.ui.ventana.QDesktopServices.openUrl", abiertos.append)
    v.tabla_documentos.setCurrentCell(0, 0)
    v.a_abrir_doc.trigger()
    assert abiertos == [] and "Por seguridad" in q.avisos[-1]


def test_restaurar_sin_copias_avisa(ventana, tmp_path):
    v, q = ventana
    q.preparar("nuevo_proyecto", (tmp_path / "N", "N", "instalacion"))
    v.a_nuevo.trigger()
    v.a_restaurar.trigger()
    assert "no tiene copias" in q.avisos[-1]


def test_sin_proyecto_solo_se_puede_crear_abrir_salir_y_ayuda(ventana):
    v, _ = ventana
    activas = {a.text() for a in _acciones(v) if a.isEnabled()}
    assert activas == {"Nuevo proyecto…", "Abrir proyecto…", "Salir", "Acerca de TRAZA"}


def _fila(v: VentanaPrincipal, etiqueta: str) -> list[str]:
    t = v.tabla_propiedades
    for i in range(t.rowCount()):
        if t.item(i, 0).text().rstrip(" *") == etiqueta:
            return [t.item(i, j).text() for j in range(t.columnCount())]
    raise AssertionError(f"No hay fila «{etiqueta}»")


def _elegir_propiedad(v: VentanaPrincipal, etiqueta: str) -> None:
    t = v.tabla_propiedades
    for i in range(t.rowCount()):
        if t.item(i, 0).text().rstrip(" *") == etiqueta:
            t.setCurrentCell(i, 0)
            return
    raise AssertionError(etiqueta)


def test_escenario_aceptacion_etapa_1_desde_la_interfaz(ventana, tmp_path, pdf_3_paginas):
    v, q = ventana
    # Crear proyecto
    q.preparar("nuevo_proyecto", (tmp_path / "Nave A", "Nave A", "instalacion"))
    v.a_nuevo.trigger()
    assert v.windowTitle() == "TRAZA — Nave A · Solo instalación"

    # Incorporar PDF
    q.preparar("documento", (pdf_3_paginas, "oferta"))
    v.a_incorporar.trigger()
    assert v.tabla_documentos.rowCount() == 1
    assert v.tabla_documentos.item(0, 2).text() == "3"
    doc_id = v.tabla_documentos.item(0, 0).data(Qt.UserRole)

    # Crear elemento: queda seleccionado y muestra «no consta» en lo que falta
    q.preparar("nuevo_elemento", ("equipo", "UTA-01", None))
    v.a_nuevo_elemento.trigger()
    assert v.elemento_seleccionado()["codigo"] == "UTA-01"
    assert _fila(v, "Caudal de aire")[1] == NO_CONSTA

    # Fijar valores; el caudal citando página del PDF
    usuario = Procedencia(Origen.USUARIO)
    cita = Procedencia(Origen.DOCUMENTO, documento_id=doc_id, localizador="p. 2, tabla 1")
    q.preparar(
        "valor",
        DatosValor("fabricante", "Fabricante X", None, usuario),
        DatosValor("modelo", "Modelo Y", None, usuario),
        DatosValor("caudal_aire", 2400, "m³/h", cita),
    )
    for _ in range(3):
        v.a_fijar.trigger()
    assert _fila(v, "Caudal de aire") == [
        "Caudal de aire",
        "2400",
        "m³/h",
        "Documento",
        "oferta.pdf · p. 2, tabla 1",
    ]
    assert v.tabla_documentos.item(0, 4).text() == "1", "el documento sabe quién lo cita"

    # Cita a una página que no existe: aviso y nada cambia
    q.preparar(
        "valor",
        DatosValor(
            "tension",
            400,
            "V",
            Procedencia(Origen.DOCUMENTO, documento_id=doc_id, localizador="p. 9"),
        ),
    )
    v.a_fijar.trigger()
    assert "no existe la página 9" in q.avisos[-1]
    assert _fila(v, "Tensión de alimentación")[1] == NO_CONSTA

    # Aprobar: las acciones de edición se desactivan y reabrir se activa
    q.preparar("texto", "Equipo seleccionado según oferta")
    v.a_aprobar.trigger()
    assert v.elemento_seleccionado()["estado"] == "aprobado"
    assert not v.a_fijar.isEnabled() and v.a_reabrir.isEnabled()

    # Deshacer / rehacer desde el menú
    v.a_deshacer.trigger()
    assert v.elemento_seleccionado()["estado"] == "borrador"
    v.a_rehacer.trigger()
    assert v.elemento_seleccionado()["estado"] == "aprobado"

    # Reabrir con motivo y modificar
    q.preparar("texto", "Revisión B del cliente")
    v.a_reabrir.trigger()
    q.preparar("valor", DatosValor("caudal_aire", 2600, "m³/h", usuario))
    v.a_fijar.trigger()
    assert _fila(v, "Caudal de aire")[1:4] == ["2600", "m³/h", "Usuario"]
    assert v.tabla_historial.rowCount() > 0

    # Cerrar y reabrir sin pérdidas
    raiz = v.proyecto.carpeta.raiz
    v.a_cerrar.trigger()
    assert v.proyecto is None and v.arbol.topLevelItemCount() == 0
    q.preparar("proyecto_existente", raiz)
    v.a_abrir.trigger()
    v.seleccionar(v.proyecto.elementos()[0]["id"])
    assert _fila(v, "Caudal de aire")[1] == "2600"
    assert q.avisos == ["«oferta.pdf» tiene 3 páginas; no existe la página 9."]


def test_pendientes_desde_la_interfaz(ventana, tmp_path):
    v, q = ventana
    q.preparar("nuevo_proyecto", (tmp_path / "N", "N", "instalacion"))
    v.a_nuevo.trigger()
    q.preparar("texto", "Confirmar tensión de la UTA")
    v.a_nuevo_pendiente.trigger()
    assert v.tabla_pendientes.rowCount() == 1
    v.tabla_pendientes.setCurrentCell(0, 0)
    assert v.a_resolver.isEnabled()
    q.preparar("texto", "400 V según ficha técnica")
    v.a_resolver.trigger()
    assert v.tabla_pendientes.rowCount() == 0


def test_borrar_valor_y_jerarquia(ventana, tmp_path):
    v, q = ventana
    q.preparar("nuevo_proyecto", (tmp_path / "N", "N", "instalacion"))
    v.a_nuevo.trigger()
    q.preparar("nuevo_elemento", ("equipo", "UTA-01", None))
    v.a_nuevo_elemento.trigger()
    padre = v.elemento_seleccionado()["id"]
    q.preparar("nuevo_elemento", ("equipo", "VENT-01", padre))
    v.a_nuevo_elemento.trigger()
    raiz = v.arbol.topLevelItem(0)
    assert raiz.text(0) == "UTA-01" and raiz.child(0).text(0) == "VENT-01"

    q.preparar("valor", DatosValor("masa", 120, "kg", Procedencia(Origen.USUARIO)))
    v.a_fijar.trigger()
    _elegir_propiedad(v, "Masa en servicio")
    v.a_borrar_valor.trigger()
    assert _fila(v, "Masa en servicio")[1] == NO_CONSTA


def test_restaurar_copia_desde_la_interfaz(ventana, tmp_path):
    v, q = ventana
    q.preparar("nuevo_proyecto", (tmp_path / "N", "N", "instalacion"))
    v.a_nuevo.trigger()
    v.a_copia.trigger()  # copia 1: sin elementos
    q.preparar("nuevo_elemento", ("equipo", "UTA-01", None))
    v.a_nuevo_elemento.trigger()
    v.a_copia.trigger()  # copia 2 (la más reciente): con UTA-01
    q.preparar("nuevo_elemento", ("equipo", "UTA-02", None))
    v.a_nuevo_elemento.trigger()
    q.preparar("elegir", 1)  # [copia 2, copia 1]: la segunda es la más antigua
    q.preparar("confirmar", True)
    v.a_restaurar.trigger()
    assert v.proyecto is not None and v.proyecto.elementos() == []
    # Lista de la más reciente a la más antigua: [apertura, antes de restaurar, copia 2,
    # copia 1]. La primera «manual» es la copia 2.
    q.preparar("elegir", lambda ops: [i for i, o in enumerate(ops) if "manual" in o][0])
    q.preparar("confirmar", True)
    v.a_restaurar.trigger()
    assert [e["codigo"] for e in v.proyecto.elementos()] == ["UTA-01"]
    assert any("antes-de-restaurar" in c.name for c in v.proyecto.copias())


# --- Diálogo de valor (el real, sin mostrarlo) ------------------------------------------


def test_dialogo_valor_rechaza_numero_ambiguo_y_cita_incompleta(qtbot):
    from traza.core.tipos import EQUIPO

    d = DialogoValor(None, EQUIPO, [{"id": "d1", "nombre_original": "oferta.pdf"}], "caudal_aire")
    qtbot.addWidget(d)
    d.valor.setText("2.400")
    d.unidad.setText("m³/h")
    d._aceptar()
    assert d.resultado is None and "ambiguo" in d.error.text()

    d.valor.setText("2400")
    d.origen.setCurrentIndex(d.origen.findData(Origen.DOCUMENTO))
    d.localizador.setText("")
    d._aceptar()
    assert d.resultado is None and "dónde está" in d.error.text()

    d.localizador.setText("p. 2")
    d._aceptar()
    assert d.resultado == DatosValor(
        "caudal_aire",
        2400,
        "m³/h",
        Procedencia(Origen.DOCUMENTO, documento_id="d1", localizador="p. 2"),
    )


def test_dialogo_valor_no_ofrece_calculo_ni_ia(qtbot):
    from traza.core.tipos import EQUIPO

    d = DialogoValor(None, EQUIPO, [])
    qtbot.addWidget(d)
    origenes = {d.origen.itemData(i) for i in range(d.origen.count())}
    assert Origen.CALCULO not in origenes and Origen.IA_PROPUESTA not in origenes


def test_autoprueba_desde_el_codigo_fuente(tmp_path):
    """La misma autoprueba que ejecuta TRAZA.exe en el CI de Windows (allí sobre el .exe)."""
    from traza.__main__ import main

    informe = tmp_path / "informe.txt"
    assert main(["--autoprueba", "--informe", str(informe)]) == 0
    assert informe.read_text(encoding="utf-8") == "Autoprueba correcta"


def test_autoprueba_informa_del_fallo(tmp_path, monkeypatch):
    import traza.__main__ as m

    def rota():
        raise AssertionError("se modificó un elemento aprobado")

    monkeypatch.setattr(m, "_autoprueba", rota)
    informe = tmp_path / "informe.txt"
    assert m.main(["--autoprueba", "--informe", str(informe)]) == 1
    assert "se modificó un elemento aprobado" in informe.read_text(encoding="utf-8")


def test_conftest_pdf_existe(pdf_3_paginas: Path):
    assert pdf_3_paginas.is_file()


# --- Pasos del proyecto y mediciones (Etapa 2) -------------------------------------------

BC3_PRUEBA = (
    "~V|AUTOR|FIEBDC-3/2016|PRUEBA||ANSI|Prueba|2|\n"
    "~C|OBRA##||Nave|1500||0|\n~C|01#||Climatización|1500||0|\n"
    "~C|UTA01|ud|Unidad de tratamiento de aire|1200||0|\n"
    "~C|CND01|m2|Conducto de chapa galvanizada|30||0|\n"
    "~C|REJ01|ud|Rejilla de impulsión||0|\n"
    "~D|OBRA##|01#\\1\\1\\|\n~D|01#|UTA01\\1\\1\\CND01\\1\\10\\REJ01\\1\\4\\|\n"
)


def test_sin_proyecto_se_ve_la_bienvenida_y_ningun_paso(ventana):
    v, _ = ventana
    assert v.paginas.currentIndex() == 0 and v.lista_pasos.count() == 0


def test_pasos_visibles_y_navegacion(ventana, tmp_path):
    v, q = ventana
    q.preparar("nuevo_proyecto", (tmp_path / "N", "N", "instalacion"))
    v.a_nuevo.trigger()
    textos = [v.lista_pasos.item(i).text() for i in range(v.lista_pasos.count())]
    assert textos == ["1. Documentación", "2. Mediciones y ofertas", "3. Equipos"]
    assert v.paso_actual() == "documentacion"
    v.ir_a_paso("equipos")
    assert v.paginas.currentWidget() is v._pagina["equipos"]
    v.refrescar()
    assert v.paso_actual() == "equipos", "refrescar no debe devolverte al primer paso"


def test_leer_medicion_exportar_y_quitar_desde_la_interfaz(ventana, tmp_path):
    v, q = ventana
    q.preparar("nuevo_proyecto", (tmp_path / "N", "N", "presupuesto"))
    v.a_nuevo.trigger()
    assert not v.a_leer_medicion.isEnabled(), "sin documentos legibles no se ofrece leer"
    bc3 = tmp_path / "Oferta.bc3"
    bc3.write_bytes(BC3_PRUEBA.encode("cp1252"))
    q.preparar("documento", (bc3, "oferta"))
    v.a_incorporar.trigger()
    assert v.a_leer_medicion.isEnabled()

    doc_id = v.tabla_documentos.item(0, 0).data(Qt.UserRole)
    q.preparar("leer_medicion", (doc_id, "oferta", "Proveedor A"))
    v.a_leer_medicion.trigger()
    assert v.paso_actual() == "mediciones"
    assert v.tabla_mediciones.rowCount() == 1
    assert [v.tabla_mediciones.item(0, j).text() for j in range(5)] == [
        "Oferta.bc3",
        "Oferta",
        "Proveedor A",
        "3",
        "1.500,00 (parcial)",
    ]
    capitulo = v.arbol_partidas.topLevelItem(0)
    assert capitulo.text(0) == "01" and capitulo.childCount() == 3
    rejilla = capitulo.child(2)
    assert rejilla.text(4) == NO_CONSTA and rejilla.text(5) == ""
    assert "1 partida(s) sin precio" in v.total_medicion.text()

    destino = tmp_path / "salida.xlsx"
    q.preparar("destino_excel", destino)
    v.a_exportar_excel.trigger()
    assert destino.is_file()

    q.preparar("confirmar", True)
    v.a_quitar_medicion.trigger()
    assert v.tabla_mediciones.rowCount() == 0
    v.a_deshacer.trigger()
    assert v.tabla_mediciones.rowCount() == 1
    assert q.avisos == []


def test_cambiar_tipo_de_encargo(ventana, tmp_path):
    v, q = ventana
    q.preparar("nuevo_proyecto", (tmp_path / "N", "N", "instalacion"))
    v.a_nuevo.trigger()
    q.preparar("encargo", "diseno")
    v.a_encargo.trigger()
    assert v.proyecto.encargo == "diseno"
    assert v.windowTitle().endswith("Diseño + presupuesto + instalación")


def test_historial_se_abre_desde_ver(ventana, tmp_path):
    v, q = ventana
    q.preparar("nuevo_proyecto", (tmp_path / "N", "N", "instalacion"))
    v.a_nuevo.trigger()
    v.show()
    assert not v.dock_historial.isVisible()
    v.a_historial.trigger()
    assert v.dock_historial.isVisible()


def test_total_no_consta_si_no_hay_importes(ventana, tmp_path):
    v, q = ventana
    q.preparar("nuevo_proyecto", (tmp_path / "N", "N", "instalacion"))
    v.a_nuevo.trigger()
    f = tmp_path / "sin_precios.bc3"
    f.write_bytes(b"~V||FIEBDC-3/2016|||ANSI|\n~C|R##||O|\n~C|P1|m|Tubo|\n~D|R##|P1\\1\\8\\|\n")
    v.proyecto.incorporar_documento(f)
    v.refrescar()
    q.preparar("leer_medicion", (v.proyecto.documentos()[0]["id"], "medicion", None))
    v.a_leer_medicion.trigger()
    assert v.tabla_mediciones.item(0, 4).text() == NO_CONSTA
    assert "total no consta" in v.total_medicion.text()


def test_leer_pdf_con_ia_pide_permiso_y_permite_confirmar_lo_dudoso(ventana, tmp_path):
    import pymupdf

    v, q = ventana
    q.preparar("nuevo_proyecto", (tmp_path / "N", "N", "instalacion"))
    v.a_nuevo.trigger()
    ruta = tmp_path / "oferta.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text(
        (40, 60), "Rejilla de impulsión   ud   8   45,50   364,00", fontsize=9
    )
    doc.save(ruta)
    doc.close()
    q.preparar("documento", (ruta, "oferta"))
    v.a_incorporar.trigger()
    llamadas = []

    def falsa_ia(texto, imagenes):
        llamadas.append(texto)
        n = {"texto": None, "valor": None, "donde": None}
        return {
            "proveedor": None,
            "total": n,
            "partidas": [
                {
                    "capitulo": None,
                    "codigo": None,
                    "descripcion": "Rejilla de impulsión",
                    "unidad": "ud",
                    "donde": "p. 1",
                    "cantidad": {"texto": "8", "valor": 8, "donde": "p. 1"},
                    "precio": {"texto": "47,00", "valor": 47.0, "donde": "p. 1"},  # inventado
                    "importe": n,
                }
            ],
        }

    v.proyecto.extractor_ia = falsa_ia
    doc_id = v.proyecto.documentos()[0]["id"]

    # Sin permiso, no se envía nada.
    q.preparar("leer_medicion", (doc_id, "oferta", None))
    q.preparar("confirmar", False)
    v.a_leer_medicion.trigger()
    assert llamadas == [] and v.tabla_mediciones.rowCount() == 0

    q.preparar("leer_medicion", (doc_id, "oferta", None))
    q.preparar("confirmar", True)
    v.a_leer_medicion.trigger()
    assert len(llamadas) == 1
    partida = v.arbol_partidas.topLevelItem(0)
    assert partida.text(6) == "⚠ A revisar"
    assert "«47,00» no está, como número completo" in partida.toolTip(6)
    assert any("A revisar" in v.lista_avisos.item(i).text() for i in range(v.lista_avisos.count()))

    v.arbol_partidas.setCurrentItem(partida)
    assert v.a_confirmar_partida.isEnabled()
    q.preparar("confirmar", True)
    v.a_confirmar_partida.trigger()
    assert v.arbol_partidas.topLevelItem(0).text(6) == "Confirmada por ti"
