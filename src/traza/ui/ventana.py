"""Ventana principal de TRAZA.

Distribución clásica de ingeniería (decisión del usuario, 06-11-2026): árbol de elementos
a la izquierda, propiedades con su procedencia en el centro, y abajo pestañas de
Documentos, Historial y Pendientes. Los paneles se pueden mover.

Regla de la interfaz: no hay ninguna acción visible sin función real detrás (lo comprueba
un test) y toda cifra muestra de dónde sale en la misma fila.
"""

from __future__ import annotations

import contextlib
import html
import json
import re
import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEventLoop, Qt, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDockWidget,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QProgressDialog,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from traza import __version__
from traza.app.modificados import TIPOS as TIPOS_MODIFICADO
from traza.app.ordenes import (
    CLASES_MEDICION,
    ENCARGOS,
    ESTADOS_FIABLES,
    AnadirPartidaNueva,
    Aprobar,
    BorrarModificado,
    BorrarPropiedad,
    CambiarEncargo,
    ConfirmarPartida,
    ConfirmarPropuesta,
    CrearElemento,
    CrearModificado,
    CrearPendiente,
    FijarPropiedad,
    Orden,
    OrdenRechazada,
    QuitarCambio,
    QuitarMedicion,
    Reabrir,
    ResolverPendiente,
    VariarPartida,
)
from traza.app.proyecto import Proyecto
from traza.core.estados import Estado
from traza.core.numeros import escribir_numero
from traza.core.tipos import TIPOS_DE_PLANO, tipos
from traza.core.tipos import tipo as tipo_de
from traza.ui.dialogos import Preguntas

ETIQUETA_ORIGEN = {
    "usuario": "Usuario",
    "documento": "Documento",
    "catalogo": "Catálogo",
    "calculo": "Cálculo",
    "hipotesis": "Hipótesis",
    "ia_propuesta": "Propuesta IA — sin confirmar",
}
ESTADO_PARTIDA = {
    "exacta": "Exacta (BC3)",
    "comprobada": "Comprobada",
    "a_revisar": "⚠ A revisar",
    "confirmada": "Confirmada por ti",
}
ETIQUETA_ESTADO = {
    "borrador": "Borrador",
    "propuesto": "Propuesto",
    "calculado": "Calculado",
    "comprobado": "Comprobado",
    "aprobado": "Aprobado",
}
NO_CONSTA = "— no consta —"
EXTENSIONES_ABRIBLES = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".xlsm",
    ".csv",
    ".txt",
    ".dxf",
    ".dwg",
    ".bc3",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".bmp",
}


TODOS = frozenset(ENCARGOS)
#: Pasos del proyecto: (clave, texto, encargos en que se muestra). Solo pasos que funcionan.
#: Tabla de pasos por encargo decidida por el usuario el 09-11-2026 (docs/modules/flujo.md):
#: los de cálculo, en los tres (en Oferta, para recalcular el proyecto ajeno); Mediciones y
#: Modificados, solo en Oferta.
OFERTA = frozenset({"oferta"})
#: Obra (docs/modules/obra.md): venta y coste; lee presupuestos y modificados como Oferta.
OBRA = frozenset({"obra"})
#: Entregables de un diseño (usuario, 09-11-2026): en Diseño y Ampliación.
CON_ENTREGABLES = frozenset({"diseno", "ampliacion"})
#: Marca del estado de cada paso en la lista (el detalle, en el tooltip).
MARCA_ESTADO = {"hecho": "✓ ", "pendiente": "○ ", "desactualizado": "⚠ "}
PASOS = [
    ("documentacion", "Documentación", TODOS),
    ("planos", "Planos y espacios", TODOS),
    ("cargas", "Cargas y ventilación", TODOS),
    ("redes", "Redes de aire", TODOS),
    ("hidronica", "Sistema hidráulico", TODOS),
    ("subcuadros", "Subcuadros de clima", TODOS),
    ("control", "Control", TODOS),
    ("mediciones", "Mediciones y ofertas", OFERTA | OBRA),
    ("venta", "Venta", OBRA),
    ("coste_objetivo", "Coste objetivo", OBRA),
    ("certificaciones", "Certificaciones", OBRA),
    ("coste_real", "Coste real", OBRA),
    ("prevision", "Previsión", OBRA),
    ("futuribles", "Futuribles", OBRA),
    ("modificados", "Modificados", OFERTA | OBRA),
    ("equipos", "Equipos", TODOS),
    ("entregables", "Entregables", CON_ENTREGABLES),
]


def _barra(acciones: list[QAction]) -> QToolBar:
    b = QToolBar()
    b.setToolButtonStyle(Qt.ToolButtonTextOnly)
    for a in acciones:
        b.addAction(a)
    return b


def _dinero(v: float | None) -> str:
    """1234.5 → «1.234,50». Solo para mostrar: los datos se guardan sin formato."""
    if v is None:
        return ""
    return f"{v:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def _tabla(columnas: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(columnas))
    t.setHorizontalHeaderLabels(columnas)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    t.setAlternatingRowColors(True)
    # Densidad de información (requisito de interfaz): filas de una línea de texto.
    t.verticalHeader().setDefaultSectionSize(t.fontMetrics().height() + 8)
    return t


def _llenar(tabla: QTableWidget, filas: list[list[str]], ids: list[str] | None = None) -> None:
    tabla.setRowCount(len(filas))
    for i, fila in enumerate(filas):
        for j, texto in enumerate(fila):
            item = QTableWidgetItem(texto)
            if texto == NO_CONSTA:
                item.setForeground(Qt.gray)
                fuente = item.font()
                fuente.setItalic(True)
                item.setFont(fuente)
            if ids is not None and j == 0:
                item.setData(Qt.UserRole, ids[i])
            tabla.setItem(i, j, item)


def _etiqueta_copia(ruta: Path) -> str:
    """«proyecto-20261106T080336814459Z-manual.db» → «2026-11-06 08:03:36 UTC · manual»."""
    m = re.match(r"proyecto-(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})\d*Z-?(.*)$", ruta.stem)
    if not m:
        return ruta.name
    a, mes, d, h, mi, s, tipo = m.groups()
    return f"{a}-{mes}-{d} {h}:{mi}:{s} UTC · {tipo.replace('-', ' ') or 'sin etiqueta'}"


def _fecha(iso: str) -> str:
    # Se guarda en UTC; se muestra tal cual con la marca para no inventar zona horaria.
    return iso.replace("T", " ").replace("+00:00", " UTC")


class VentanaPrincipal(QMainWindow):
    def __init__(self, preguntas: Preguntas | None = None, ajustes=None) -> None:
        super().__init__()
        self.proyecto: Proyecto | None = None
        self.preguntas = preguntas or Preguntas(self)
        #: Ajustes de este equipo (QSettings): la plantilla de Word. Las pruebas pasan uno
        #: en un fichero temporal para no tocar los del usuario.
        self._ajustes = ajustes
        self.resize(1400, 850)
        self._construir()
        self._actualizar_estado()

    # --- Construcción --------------------------------------------------------------------

    def _construir(self) -> None:
        """Pasos del proyecto a la izquierda; a la derecha, la página del paso elegido.

        Decisión del usuario (06-11-2026): la herramienta se recorre por pasos, adaptados
        al tipo de encargo, y solo se ven los pasos que ya funcionan.
        """
        self._crear_acciones()

        # Página de bienvenida (sin proyecto abierto).
        bienvenida = QWidget()
        lb = QVBoxLayout(bienvenida)
        lb.addStretch()
        titulo = QLabel("<h2>TRAZA</h2><p>Crea un proyecto nuevo o abre uno existente.</p>")
        titulo.setAlignment(Qt.AlignCenter)
        lb.addWidget(titulo)
        fila = QHBoxLayout()
        fila.addStretch()
        for a in (self.a_nuevo, self.a_abrir):
            b = QToolButton()
            b.setDefaultAction(a)
            b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            fila.addWidget(b)
        fila.addStretch()
        lb.addLayout(fila)
        lb.addStretch()

        # Paso Documentación: documentos del proyecto e información pendiente.
        self.tabla_documentos = _tabla(
            ["Documento", "Tipo", "Páginas", "Incorporado", "Valores que lo citan"]
        )
        self.tabla_documentos.doubleClicked.connect(
            lambda _i: self._proteger("Abrir documento", self.accion_abrir_documento)
        )
        self.tabla_pendientes = _tabla(["Pendiente", "Elemento", "Creado"])
        doc = QWidget()
        ld = QVBoxLayout(doc)
        ld.addWidget(_barra([self.a_incorporar, self.a_leer_medicion, self.a_abrir_doc]))
        ld.addWidget(self.tabla_documentos, 3)
        ld.addWidget(QLabel("<b>Información pendiente de confirmar</b>"))
        ld.addWidget(_barra([self.a_nuevo_pendiente, self.a_resolver]))
        ld.addWidget(self.tabla_pendientes, 1)

        # Paso Mediciones y ofertas.
        self.tabla_mediciones = _tabla(
            ["Documento", "Tipo", "Proveedor", "Partidas", "Total", "Avisos"]
        )
        self.tabla_mediciones.itemSelectionChanged.connect(self._al_elegir_medicion)
        self.arbol_partidas = QTreeWidget()
        self.arbol_partidas.setHeaderLabels(
            [
                "Capítulo / código",
                "Descripción",
                "Ud",
                "Cantidad",
                "Precio",
                "Importe",
                "Estado",
                "Origen",
            ]
        )
        self.arbol_partidas.setAlternatingRowColors(True)
        self.arbol_partidas.itemSelectionChanged.connect(self._actualizar_estado)
        self.arbol_partidas.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.total_medicion = QLabel()
        self.lista_avisos = QListWidget()
        med = QWidget()
        lm = QVBoxLayout(med)
        lm.addWidget(
            _barra(
                [
                    self.a_leer_medicion,
                    self.a_exportar_excel,
                    self.a_quitar_medicion,
                    self.a_confirmar_partida,
                ]
            )
        )
        partes = QSplitter(Qt.Vertical)
        partes.addWidget(self.tabla_mediciones)
        partes.addWidget(self.arbol_partidas)
        partes.addWidget(self.lista_avisos)
        partes.setStretchFactor(0, 1)
        partes.setStretchFactor(1, 4)
        partes.setStretchFactor(2, 1)
        lm.addWidget(partes)
        lm.addWidget(self.total_medicion)

        # Paso Equipos: elementos con sus propiedades y procedencia.
        self.arbol = QTreeWidget()
        self.arbol.setHeaderLabels(["Código", "Tipo", "Estado"])
        self.arbol.itemSelectionChanged.connect(self._al_seleccionar)
        self.cabecera = QLabel()
        self.cabecera.setTextFormat(Qt.RichText)
        self.tabla_propiedades = _tabla(
            ["Propiedad", "Valor", "Unidad", "Procedencia", "Fuente / justificación"]
        )
        self.tabla_propiedades.doubleClicked.connect(
            lambda _i: self._proteger("Fijar valor", self.accion_fijar_valor)
        )
        derecha = QWidget()
        lr = QVBoxLayout(derecha)
        lr.setContentsMargins(0, 0, 0, 0)
        lr.addWidget(self.cabecera)
        lr.addWidget(self.tabla_propiedades)
        division = QSplitter(Qt.Horizontal)
        division.addWidget(self.arbol)
        division.addWidget(derecha)
        division.setStretchFactor(1, 3)
        eq = QWidget()
        le = QVBoxLayout(eq)
        le.addWidget(
            _barra(
                [
                    self.a_nuevo_elemento,
                    self.a_fijar,
                    self.a_borrar_valor,
                    self.a_confirmar,
                    self.a_aprobar,
                    self.a_reabrir,
                ]
            )
        )
        le.addWidget(division)

        # Paso Modificados: ampliaciones y modificaciones sobre una medición leída.
        self.tabla_modificados = _tabla(["Nº", "Título", "Base", "Cambios", "Diferencia"])
        self.tabla_modificados.itemSelectionChanged.connect(self._al_elegir_modificado)
        self.tabla_cambios = _tabla(
            [
                "Tipo",
                "Código",
                "Descripción",
                "Ud",
                "Cant. contrato",
                "Cant. nueva",
                "Dif.",
                "Precio",
                "Dif. importe",
                "Motivo",
                "Justificación",
            ]
        )
        self.tabla_cambios.itemSelectionChanged.connect(self._actualizar_estado)
        self.total_modificado = QLabel()
        self.total_modificado.setTextFormat(Qt.RichText)
        mo = QWidget()
        lmo = QVBoxLayout(mo)
        lmo.addWidget(
            _barra(
                [
                    self.a_nuevo_modificado,
                    self.a_variar,
                    self.a_partida_nueva,
                    self.a_quitar_cambio,
                    self.a_exportar_mod_excel,
                    self.a_exportar_mod_bc3,
                    self.a_borrar_modificado,
                ]
            )
        )
        partes_mo = QSplitter(Qt.Vertical)
        partes_mo.addWidget(self.tabla_modificados)
        partes_mo.addWidget(self.tabla_cambios)
        partes_mo.setStretchFactor(0, 1)
        partes_mo.setStretchFactor(1, 4)
        lmo.addWidget(partes_mo)
        lmo.addWidget(self.total_modificado)

        self.paginas = QStackedWidget()
        self.paginas.addWidget(bienvenida)
        # Paso Planos y espacios: módulo propio (ui/paso_planos.py).
        from traza.ui.paso_planos import PaginaPlanos

        self.pagina_planos = PaginaPlanos(self)
        # Paso Cargas y ventilación: módulo propio (ui/paso_cargas.py).
        from traza.ui.paso_cargas import PaginaCargas

        self.pagina_cargas = PaginaCargas(self)
        # Paso Redes de aire: módulo propio (ui/paso_redes.py).
        from traza.ui.paso_redes import PaginaRedes

        self.pagina_redes = PaginaRedes(self)
        # Paso Sistema hidráulico: módulo propio (ui/paso_hidronica.py).
        from traza.ui.paso_hidronica import PaginaHidronica

        self.pagina_hidronica = PaginaHidronica(self)
        # Paso Subcuadros de clima: módulo propio (ui/paso_subcuadros.py).
        from traza.ui.paso_subcuadros import PaginaSubcuadros

        self.pagina_subcuadros = PaginaSubcuadros(self)
        # Paso Control: módulo propio (ui/paso_control.py).
        from traza.ui.paso_control import PaginaControl

        self.pagina_control = PaginaControl(self)
        # Paso Entregables: módulo propio (ui/paso_entregables.py).
        from traza.ui.paso_entregables import PaginaEntregables

        self.pagina_entregables = PaginaEntregables(self, self._ajustes)
        # Pasos de Obra: módulo propio (ui/paso_obra.py).
        from traza.ui.paso_obra import (
            PaginaCertificaciones,
            PaginaCosteObjetivo,
            PaginaCosteReal,
            PaginaFuturibles,
            PaginaPrevision,
            PaginaVenta,
        )

        self.pagina_venta = PaginaVenta(self)
        self.pagina_coste_objetivo = PaginaCosteObjetivo(self)
        self.pagina_certificaciones = PaginaCertificaciones(self)
        self.pagina_coste_real = PaginaCosteReal(self)
        self.pagina_prevision = PaginaPrevision(self)
        self.pagina_futuribles = PaginaFuturibles(self)
        self._pagina = {
            "documentacion": doc,
            "planos": self.pagina_planos,
            "cargas": self.pagina_cargas,
            "redes": self.pagina_redes,
            "hidronica": self.pagina_hidronica,
            "subcuadros": self.pagina_subcuadros,
            "control": self.pagina_control,
            "mediciones": med,
            "modificados": mo,
            "equipos": eq,
            "entregables": self.pagina_entregables,
            "venta": self.pagina_venta,
            "coste_objetivo": self.pagina_coste_objetivo,
            "certificaciones": self.pagina_certificaciones,
            "coste_real": self.pagina_coste_real,
            "prevision": self.pagina_prevision,
            "futuribles": self.pagina_futuribles,
        }
        for p in self._pagina.values():
            self.paginas.addWidget(p)

        self.lista_pasos = QListWidget()
        self.lista_pasos.setMaximumWidth(230)
        self.lista_pasos.currentRowChanged.connect(self._al_elegir_paso)
        self.lista_pasos.setFocusPolicy(Qt.NoFocus)

        centro = QSplitter(Qt.Horizontal)
        centro.addWidget(self.lista_pasos)
        centro.addWidget(self.paginas)
        centro.setStretchFactor(1, 1)
        self.setCentralWidget(centro)

        # Historial: consulta, no un paso del trabajo. Se abre desde «Ver».
        self.tabla_historial = _tabla(["Fecha", "Autor", "Orden", "Afecta a", "Campos"])
        self.dock_historial = QDockWidget("Historial de cambios", self)
        self.dock_historial.setObjectName("dock_historial")
        self.dock_historial.setWidget(self.tabla_historial)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_historial)
        self.dock_historial.hide()

        self.tabla_documentos.itemSelectionChanged.connect(self._actualizar_estado)
        self.tabla_pendientes.itemSelectionChanged.connect(self._actualizar_estado)
        self.statusBar()

    def _refrescar_pasos(self) -> None:
        """Muestra solo los pasos del tipo de encargo (y que ya funcionan)."""
        actual = self.paso_actual()
        self.lista_pasos.blockSignals(True)
        try:
            self.lista_pasos.clear()
            if self.proyecto is None:
                self.paginas.setCurrentIndex(0)
                return
            visibles = [p for p in PASOS if self.proyecto.encargo in p[2]]
            for n, (clave, texto, _) in enumerate(visibles, start=1):
                # Estado del paso (usuario, 09-11-2026: «pasos con estado»).
                e = self.proyecto.estado_paso(clave)
                marca = MARCA_ESTADO.get(e.estado, "")
                item = QListWidgetItem(f"{marca}{n}. {texto}")
                item.setData(Qt.UserRole, clave)
                if e.texto:
                    item.setToolTip(e.texto)
                self.lista_pasos.addItem(item)
            claves = [p[0] for p in visibles]
            fila = claves.index(actual) if actual in claves else 0
            self.lista_pasos.setCurrentRow(fila)
            self.paginas.setCurrentWidget(self._pagina[claves[fila]])
        finally:
            self.lista_pasos.blockSignals(False)

    def paso_actual(self) -> str | None:
        item = self.lista_pasos.currentItem()
        return item.data(Qt.UserRole) if item else None

    def ir_a_paso(self, clave: str) -> None:
        for i in range(self.lista_pasos.count()):
            if self.lista_pasos.item(i).data(Qt.UserRole) == clave:
                self.lista_pasos.setCurrentRow(i)
                return
        raise KeyError(f"El paso «{clave}» no está visible en este encargo.")

    def _al_elegir_paso(self, fila: int) -> None:
        item = self.lista_pasos.item(fila)
        if item is not None:
            self.paginas.setCurrentWidget(self._pagina[item.data(Qt.UserRole)])

    def _accion(self, menu, texto: str, funcion: Callable[[], None], atajo=None) -> QAction:
        a = QAction(texto, self)
        if atajo is not None:
            a.setShortcut(QKeySequence(atajo))
        a.triggered.connect(lambda _marcado=False: self._proteger(texto, funcion))
        menu.addAction(a)
        return a

    def _proteger(self, texto: str, funcion: Callable[[], None]) -> None:
        """Ningún error escapa de una acción en silencio.

        En TRAZA.exe no hay consola: una excepción no capturada no la vería nadie y el
        usuario creería, por ejemplo, que tiene una copia de seguridad que no existe.
        """
        try:
            funcion()
        except OrdenRechazada as exc:
            self.preguntas.aviso("No se ha aplicado", str(exc))
        except Exception as exc:  # noqa: BLE001 — se muestra siempre al usuario
            self.preguntas.aviso(
                f"Error en «{texto.rstrip('…')}»",
                f"{type(exc).__name__}: {exc}\n\nNo se ha completado la operación.",
            )
        finally:
            if self.proyecto is not None:
                with contextlib.suppress(Exception):  # el aviso anterior ya informa
                    self.refrescar()
            else:
                self._actualizar_estado()

    def _crear_acciones(self) -> None:
        mb = self.menuBar()
        m = mb.addMenu("&Archivo")
        self.a_nuevo = self._accion(
            m, "Nuevo proyecto…", self.accion_nuevo_proyecto, QKeySequence.New
        )
        self.a_nueva_obra = self._accion(m, "Nueva obra desde documentos…", self.accion_nueva_obra)
        self.a_abrir = self._accion(
            m, "Abrir proyecto…", self.accion_abrir_proyecto, QKeySequence.Open
        )
        self.a_cerrar = self._accion(m, "Cerrar proyecto", self.accion_cerrar_proyecto)
        m.addSeparator()
        self.a_copia = self._accion(m, "Hacer copia de seguridad", self.accion_copia)
        self.a_restaurar = self._accion(m, "Restaurar copia de seguridad…", self.accion_restaurar)
        m.addSeparator()
        # Revisiones del diseño (RF-009, docs/modules/revisiones.md).
        self.a_emitir_revision = self._accion(m, "Emitir revisión…", self.accion_emitir_revision)
        self.a_comparar = self._accion(m, "Comparar con una revisión…", self.accion_comparar)
        m.addSeparator()
        self.a_salir = self._accion(m, "Salir", self.close, QKeySequence.Quit)

        m = mb.addMenu("&Edición")
        self.a_deshacer = self._accion(m, "Deshacer", self.accion_deshacer, QKeySequence.Undo)
        self.a_rehacer = self._accion(m, "Rehacer", self.accion_rehacer, QKeySequence.Redo)

        m = mb.addMenu("E&lemento")
        self.a_nuevo_elemento = self._accion(
            m, "Nuevo elemento…", self.accion_nuevo_elemento, "Ctrl+E"
        )
        self.a_fijar = self._accion(m, "Fijar valor…", self.accion_fijar_valor, "Ctrl+R")
        self.a_borrar_valor = self._accion(m, "Borrar valor", self.accion_borrar_valor)
        self.a_confirmar = self._accion(
            m, "Confirmar propuesta de IA", self.accion_confirmar_propuesta
        )
        m.addSeparator()
        self.a_aprobar = self._accion(m, "Aprobar…", self.accion_aprobar)
        self.a_reabrir = self._accion(m, "Reabrir…", self.accion_reabrir)

        m = mb.addMenu("&Documentos")
        self.a_incorporar = self._accion(
            m, "Incorporar documento…", self.accion_incorporar_documento, "Ctrl+I"
        )
        self.a_abrir_doc = self._accion(m, "Abrir documento", self.accion_abrir_documento)

        m = mb.addMenu("&Pendientes")
        self.a_nuevo_pendiente = self._accion(
            m, "Anotar información pendiente…", self.accion_nuevo_pendiente
        )
        self.a_resolver = self._accion(m, "Resolver pendiente…", self.accion_resolver_pendiente)

        m = mb.addMenu("&Mediciones")
        self.a_leer_medicion = self._accion(
            m, "Leer medición u oferta…", self.accion_leer_medicion, "Ctrl+L"
        )
        self.a_exportar_excel = self._accion(
            m, "Exportar Excel con todo…", self.accion_exportar_excel
        )
        self.a_quitar_medicion = self._accion(m, "Quitar medición", self.accion_quitar_medicion)
        self.a_confirmar_partida = self._accion(
            m, "Confirmar partida revisada", self.accion_confirmar_partida
        )

        m = mb.addMenu("M&odificados")
        self.a_nuevo_modificado = self._accion(m, "Nuevo modificado…", self.accion_nuevo_modificado)
        self.a_variar = self._accion(m, "Cambiar cantidad de una partida…", self.accion_variar)
        self.a_partida_nueva = self._accion(
            m, "Añadir partida de una oferta…", self.accion_partida_nueva
        )
        self.a_quitar_cambio = self._accion(m, "Quitar cambio", self.accion_quitar_cambio)
        m.addSeparator()
        self.a_exportar_mod_excel = self._accion(
            m, "Exportar modificado a Excel…", self.accion_exportar_mod_excel
        )
        self.a_exportar_mod_bc3 = self._accion(
            m, "Exportar presupuesto actualizado a BC3…", self.accion_exportar_mod_bc3
        )
        m.addSeparator()
        self.a_borrar_modificado = self._accion(
            m, "Borrar modificado", self.accion_borrar_modificado
        )

        # Menú del paso Planos: lo llena ui/paso_planos.PaginaPlanos.
        self.menu_planos = mb.addMenu("&Planos")
        # Menú del paso Cargas: lo llena ui/paso_cargas.PaginaCargas.
        self.menu_cargas = mb.addMenu("&Cargas")
        # Menú del paso Redes de aire: lo llena ui/paso_redes.PaginaRedes.
        self.menu_redes = mb.addMenu("&Redes")
        # Menú del paso Sistema hidráulico: lo llena ui/paso_hidronica.PaginaHidronica.
        self.menu_hidronica = mb.addMenu("&Agua")
        # Menú del paso Subcuadros de clima: lo llena ui/paso_subcuadros.PaginaSubcuadros.
        self.menu_subcuadros = mb.addMenu("E&lectricidad")
        # Menú del paso Control: lo llena ui/paso_control.PaginaControl.
        self.menu_control = mb.addMenu("Con&trol")
        # Menú del paso Entregables: lo llena ui/paso_entregables.PaginaEntregables.
        self.menu_entregables = mb.addMenu("E&ntregables")
        # Menú de Obra: lo llena ui/paso_obra (tras «Añadir documentos», el primero).
        self.menu_obra = mb.addMenu("&Obra")
        self.a_anadir_documentos = self._accion(
            self.menu_obra, "Añadir documentos a la obra…", self.accion_anadir_documentos
        )

        m = mb.addMenu("&Ver")
        self.a_historial = self._accion(m, "Historial de cambios", self.accion_historial)
        self.a_encargo = self._accion(m, "Tipo de encargo…", self.accion_encargo)
        self.a_revisado = self._accion(m, "Dar por revisado este paso", self.accion_revisado)

        m = mb.addMenu("A&yuda")
        self.a_acerca = self._accion(m, "Acerca de TRAZA", self.accion_acerca)

    # --- Estado de la interfaz -------------------------------------------------------------

    def elemento_seleccionado(self) -> dict | None:
        items = self.arbol.selectedItems()
        if not items or self.proyecto is None:
            return None
        return self.proyecto.elemento(items[0].data(0, Qt.UserRole))

    def _clave_seleccionada(self) -> str | None:
        fila = self.tabla_propiedades.currentRow()
        item = self.tabla_propiedades.item(fila, 0) if fila >= 0 else None
        return item.data(Qt.UserRole) if item else None

    def _actualizar_estado(self) -> None:
        hay = self.proyecto is not None
        if hasattr(self, "pagina_planos"):  # durante la construcción aún no existe
            self.pagina_planos.actualizar_estado(hay)
        if hasattr(self, "pagina_cargas"):
            self.pagina_cargas.actualizar_estado(hay)
        if hasattr(self, "pagina_redes"):
            self.pagina_redes.actualizar_estado(hay)
        if hasattr(self, "pagina_hidronica"):
            self.pagina_hidronica.actualizar_estado(hay)
        if hasattr(self, "pagina_subcuadros"):
            self.pagina_subcuadros.actualizar_estado(hay)
        if hasattr(self, "pagina_control"):
            self.pagina_control.actualizar_estado(hay)
        if hasattr(self, "pagina_entregables"):
            self.pagina_entregables.actualizar_estado(hay)
        if hasattr(self, "a_anadir_documentos"):
            self.a_anadir_documentos.setEnabled(hay and self.proyecto.encargo == "obra")
        if hasattr(self, "pagina_coste_objetivo"):
            self.pagina_venta.actualizar_estado(hay)
            self.pagina_coste_objetivo.actualizar_estado(hay)
            self.pagina_certificaciones.actualizar_estado(hay)
            self.pagina_coste_real.actualizar_estado(hay)
            self.pagina_prevision.actualizar_estado(hay)
            self.pagina_futuribles.actualizar_estado(hay)
        el = self.elemento_seleccionado() if hay else None
        aprobado = el is not None and el["estado"] == Estado.APROBADO
        for a in (
            self.a_cerrar,
            self.a_copia,
            self.a_nuevo_elemento,
            self.a_incorporar,
            self.a_nuevo_pendiente,
            self.a_historial,
            self.a_encargo,
            self.a_revisado,
            self.a_emitir_revision,
        ):
            a.setEnabled(hay)
        self.a_comparar.setEnabled(hay and bool(self.proyecto.revisiones()))
        self.a_leer_medicion.setEnabled(hay and bool(self._documentos_legibles()))
        hay_mediciones = hay and self.tabla_mediciones.rowCount() > 0
        self.a_exportar_excel.setEnabled(hay_mediciones)
        self.a_quitar_medicion.setEnabled(hay_mediciones and self._medicion_elegida() is not None)
        elegida = self._partida_elegida() if hay else None
        self.a_confirmar_partida.setEnabled(
            elegida is not None and elegida["estado"] == "a_revisar"
        )
        self.a_nuevo_modificado.setEnabled(hay_mediciones)
        mod = self._modificado_elegido() if hay else None
        for a in (self.a_variar, self.a_borrar_modificado):
            a.setEnabled(mod is not None)
        # Exportar sin cambios lo rechaza la orden; mejor que el botón ni se ofrezca.
        hay_cambios = mod is not None and self.tabla_cambios.rowCount() > 0
        self.a_exportar_mod_excel.setEnabled(hay_cambios)
        self.a_exportar_mod_bc3.setEnabled(hay_cambios)
        self.a_partida_nueva.setEnabled(mod is not None and bool(self._lineas_de_oferta(mod)))
        self.a_quitar_cambio.setEnabled(mod is not None and self._cambio_elegido() is not None)
        self.a_restaurar.setEnabled(hay)
        self.a_abrir_doc.setEnabled(hay and self.tabla_documentos.currentRow() >= 0)
        self.a_resolver.setEnabled(hay and self.tabla_pendientes.currentRow() >= 0)
        self.a_deshacer.setEnabled(hay and self.proyecto.puede_deshacer)
        self.a_rehacer.setEnabled(hay and self.proyecto.puede_rehacer)
        editable = el is not None and not aprobado
        for a in (self.a_fijar, self.a_borrar_valor, self.a_confirmar, self.a_aprobar):
            a.setEnabled(editable)
        self.a_reabrir.setEnabled(aprobado)
        titulo = "TRAZA"
        if hay:
            titulo += f" — {self.proyecto.nombre} · {ENCARGOS[self.proyecto.encargo]}"
        self.setWindowTitle(titulo)

    def refrescar(self) -> None:
        seleccion = self.elemento_seleccionado()
        self._refrescar_pasos()
        self._refrescar_arbol(seleccion["id"] if seleccion else None)
        self._refrescar_propiedades()
        self._refrescar_documentos()
        self._refrescar_mediciones()
        self._refrescar_modificados()
        self.pagina_planos.refrescar()
        self.pagina_cargas.refrescar()
        self.pagina_redes.refrescar()
        self.pagina_hidronica.refrescar()
        self.pagina_subcuadros.refrescar()
        self.pagina_control.refrescar()
        self.pagina_entregables.refrescar()
        self.pagina_venta.refrescar()
        self.pagina_coste_objetivo.refrescar()
        self.pagina_certificaciones.refrescar()
        self.pagina_coste_real.refrescar()
        self.pagina_prevision.refrescar()
        self.pagina_futuribles.refrescar()
        self._refrescar_historial()
        self._refrescar_pendientes()
        self._actualizar_estado()

    # --- Mediciones ------------------------------------------------------------------------

    def _documentos_legibles(self) -> list[dict]:
        if self.proyecto is None:
            return []
        formatos = self.proyecto.FORMATOS_MEDICION
        leidos = {m["documento_id"] for m in self.proyecto.mediciones()}
        # Un documento ya leído no se ofrece: leerlo otra vez duplicaría partidas (y con IA
        # gastaría suscripción en balde).
        return [
            d
            for d in self.proyecto.documentos()
            if d["extension"] in formatos and d["id"] not in leidos
        ]

    def _medicion_elegida(self) -> str | None:
        fila = self.tabla_mediciones.currentRow()
        item = self.tabla_mediciones.item(fila, 0) if fila >= 0 else None
        return item.data(Qt.UserRole) if item else None

    def _refrescar_mediciones(self) -> None:
        elegida = self._medicion_elegida()
        self.tabla_mediciones.blockSignals(True)
        try:
            if self.proyecto is None:
                _llenar(self.tabla_mediciones, [])
            else:
                meds = self.proyecto.mediciones()
                filas = []
                for m in meds:
                    filas.append(
                        [
                            m["documento_nombre"],
                            CLASES_MEDICION[m["clase"]],
                            m["proveedor"] or "",
                            str(m["n_partidas"]),
                            self._texto_total(m)[0],
                            str(len(m["avisos"])) if m["avisos"] else "",
                        ]
                    )
                ids = [m["id"] for m in meds]
                _llenar(self.tabla_mediciones, filas, ids)
                if elegida in ids:
                    self.tabla_mediciones.setCurrentCell(ids.index(elegida), 0)
                elif ids:
                    self.tabla_mediciones.setCurrentCell(len(ids) - 1, 0)
        finally:
            self.tabla_mediciones.blockSignals(False)
        self._refrescar_partidas()

    def _en_segundo_plano(
        self,
        funcion,
        mensaje: str = "Leyendo el documento con IA… puede tardar unos minutos.",
        titulo: str = "Leer con IA",
    ):
        """Ejecuta una tarea larga (la IA, leer un DXF grande) en otro hilo con una ventana
        de progreso.

        Solo la tarea que no toca la base de datos (SQLite no admite usar la conexión desde
        otro hilo); lo que se guarda vuelve a hacerse en el hilo principal.
        """
        resultado: dict = {}

        def trabajo() -> None:
            try:
                resultado["valor"] = funcion()
            except BaseException as exc:  # noqa: BLE001 — se relanza en el hilo principal
                resultado["error"] = exc

        hilo = threading.Thread(target=trabajo, daemon=True)
        hilo.start()
        dialogo = QProgressDialog(mensaje, None, 0, 0, self)
        dialogo.setWindowTitle(titulo)
        dialogo.setWindowModality(Qt.WindowModal)
        dialogo.setMinimumDuration(0)
        dialogo.show()
        try:
            while hilo.is_alive():
                QApplication.processEvents(QEventLoop.AllEvents, 100)
                hilo.join(0.05)
        finally:
            dialogo.close()
        if "error" in resultado:
            raise resultado["error"]
        return resultado["valor"]

    def _texto_total(self, med: dict) -> tuple[str, str]:
        """(texto corto para la tabla, explicación para el pie).

        Nunca se muestra un 0 que no consta: si ninguna partida tiene importe, el total es
        «no consta». Es «parcial» si hay partidas sin importe o líneas que el lector omitió
        (revisión 06-11-2026: antes salía «0,00» y las omitidas no marcaban parcial).
        """
        ps = self.proyecto.partidas(med["id"])
        importes = [p["importe"] for p in ps if p["importe"] is not None]
        sin_importe = len(ps) - len(importes)
        if not importes:
            return NO_CONSTA, "Ninguna partida tiene a la vez cantidad y precio: total no consta."
        motivos = []
        if sin_importe:
            motivos.append(f"{sin_importe} partida(s) sin precio o sin cantidad no sumadas")
        if med["omitidas"]:
            motivos.append(f"{med['omitidas']} línea(s) del documento omitidas (ver avisos)")
        revisar = sum(1 for p in ps if p["estado"] == "a_revisar" and p["importe"] is not None)
        suma = sum(importes)
        corto = _dinero(suma) + (" (parcial)" if motivos else "")
        if revisar:
            corto += f" ⚠ {revisar} a revisar"
            motivos.append(f"incluye {revisar} partida(s) «a revisar»")
        if med["total_documento"] is not None:
            diferencia = suma - med["total_documento"]
            estado = "coincide" if abs(diferencia) <= 0.01 else f"diferencia {_dinero(diferencia)}"
            motivos.append(f"total del documento {_dinero(med['total_documento'])} ({estado})")
        return corto, " — ".join(motivos)

    def _refrescar_partidas(self) -> None:
        self.arbol_partidas.clear()
        self.lista_avisos.clear()
        med_id = self._medicion_elegida()
        if self.proyecto is None or med_id is None:
            self.total_medicion.setText("")
            return
        capitulos: dict[tuple, QTreeWidgetItem] = {}
        for p in self.proyecto.partidas(med_id):
            padre = self.arbol_partidas.invisibleRootItem()
            ruta: tuple = ()
            for codigo, resumen in p["capitulo"]:
                ruta += (codigo,)
                if ruta not in capitulos:
                    item = QTreeWidgetItem([codigo, resumen])
                    fuente = item.font(0)
                    fuente.setBold(True)
                    item.setFont(0, fuente)
                    item.setFont(1, fuente)
                    padre.addChild(item)
                    capitulos[ruta] = item
                padre = capitulos[ruta]
            item = QTreeWidgetItem(
                [
                    p["etiqueta"] or p["codigo"] or "",
                    p["resumen"] or NO_CONSTA,
                    p["unidad"] or "",
                    "" if p["cantidad"] is None else escribir_numero(p["cantidad"]),
                    _dinero(p["precio"]) if p["precio"] is not None else NO_CONSTA,
                    _dinero(p["importe"]),
                    ESTADO_PARTIDA[p["estado"]],
                    p["localizador"],
                ]
            )
            item.setData(0, Qt.UserRole, p["id"])
            if p["estado"] == "a_revisar":
                # Lo que no ha superado las comprobaciones se ve, y dice por qué.
                item.setToolTip(6, "\n".join(p["motivos"]))
                for col in range(item.columnCount()):
                    item.setForeground(col, QColor("#b35900"))
            padre.addChild(item)
        self.arbol_partidas.expandAll()
        med = next(m for m in self.proyecto.mediciones() if m["id"] == med_id)
        for a in med["avisos"]:
            self.lista_avisos.addItem(f"⚠ {a}")
        revisar = [p for p in self.proyecto.partidas(med_id) if p["estado"] == "a_revisar"]
        for p in revisar:
            self.lista_avisos.addItem(
                f"⚠ A revisar «{(p['resumen'] or '')[:50]}»: {'; '.join(p['motivos'])}"
            )
        corto, explicacion = self._texto_total(med)
        texto = f"<b>Total: {corto}</b>"
        if explicacion:
            texto += f" — {explicacion}"
        self.total_medicion.setText(texto)

    def _partida_elegida(self) -> dict | None:
        items = self.arbol_partidas.selectedItems()
        pid = items[0].data(0, Qt.UserRole) if items else None
        med = self._medicion_elegida()
        if pid is None or med is None:
            return None
        return next((p for p in self.proyecto.partidas(med) if p["id"] == pid), None)

    def accion_confirmar_partida(self) -> None:
        p = self._partida_elegida()
        if p is None:
            return
        if self.preguntas.confirmar(
            "Confirmar partida",
            f"«{p['resumen']}» no superó estas comprobaciones:\n- "
            + "\n- ".join(p["motivos"])
            + f"\n\n¿La has revisado en el documento ({p['localizador']}) y es correcta?",
        ):
            self._ejecutar(ConfirmarPartida(p["id"]))

    def _al_elegir_medicion(self) -> None:
        self._refrescar_partidas()
        self._actualizar_estado()

    def accion_leer_medicion(self) -> None:
        docs = self._documentos_legibles()
        if not docs:
            self.preguntas.aviso(
                "Leer medición",
                "Primero incorpora el documento (paso Documentación). Formatos que ya se "
                f"leen: {', '.join(self.proyecto.FORMATOS_MEDICION)}.",
            )
            return
        r = self.preguntas.leer_medicion(docs)
        if r is None:
            return
        doc_id, clase, proveedor = r
        doc = next(d for d in docs if d["id"] == doc_id)
        # Decisión del usuario: ningún documento sale del equipo sin su permiso expreso.
        if doc["extension"] in self.proyecto.FORMATOS_CON_IA and not self.preguntas.confirmar(
            "Leer con IA",
            f"«{doc['nombre_original']}» se leerá con Claude (Claude Code con tu "
            "suscripción): su contenido se envía a Anthropic. Las líneas que no superen "
            "las comprobaciones quedarán «a revisar». Puede tardar unos minutos. "
            "¿Continuar?",
        ):
            return
        _, avisos = self.proyecto.leer_medicion(
            doc_id, clase, proveedor, esperar=self._en_segundo_plano
        )
        self.refrescar()
        if "mediciones" in [p[0] for p in PASOS if self.proyecto.encargo in p[2]]:
            self.ir_a_paso("mediciones")
        if avisos:
            self.preguntas.informacion(
                "Leído con avisos",
                f"Se ha leído con {len(avisos)} aviso(s). Revísalos debajo de las partidas.",
            )

    def accion_exportar_excel(self) -> None:
        sugerido = self.proyecto.carpeta.exportaciones / f"{self.proyecto.nombre} - partidas.xlsx"
        destino = self.preguntas.destino_excel(sugerido)
        if destino is None:
            return
        ruta = self.proyecto.exportar_excel(destino)
        self.statusBar().showMessage(f"Excel guardado: {ruta}", 10000)

    def accion_quitar_medicion(self) -> None:
        med_id = self._medicion_elegida()
        if med_id is None:
            return
        if self.preguntas.confirmar(
            "Quitar medición",
            "Se quitan del proyecto las partidas leídas de este documento (el documento se "
            "conserva). Se puede deshacer. ¿Continuar?",
        ):
            self._ejecutar(QuitarMedicion(med_id))

    # --- Modificados -------------------------------------------------------------------------

    def _modificado_elegido(self) -> str | None:
        fila = self.tabla_modificados.currentRow()
        item = self.tabla_modificados.item(fila, 0) if fila >= 0 else None
        return item.data(Qt.UserRole) if item else None

    def _cambio_elegido(self) -> str | None:
        fila = self.tabla_cambios.currentRow()
        item = self.tabla_cambios.item(fila, 0) if fila >= 0 else None
        return item.data(Qt.UserRole) if item else None

    def _refrescar_modificados(self) -> None:
        elegido = self._modificado_elegido()
        self.tabla_modificados.blockSignals(True)
        try:
            if self.proyecto is None:
                _llenar(self.tabla_modificados, [])
            else:
                mods = self.proyecto.modificados()
                filas = []
                for m in mods:
                    r = self.proyecto.resumen_modificado(m["id"])
                    filas.append(
                        [
                            str(m["numero"]),
                            m["titulo"],
                            m["base_nombre"],
                            str(m["n_cambios"]),
                            _dinero(r.diferencia) + (" (parcial)" if r.parcial else ""),
                        ]
                    )
                ids = [m["id"] for m in mods]
                _llenar(self.tabla_modificados, filas, ids)
                if elegido in ids:
                    self.tabla_modificados.setCurrentCell(ids.index(elegido), 0)
                elif ids:
                    self.tabla_modificados.setCurrentCell(len(ids) - 1, 0)
        finally:
            self.tabla_modificados.blockSignals(False)
        self._refrescar_cambios()

    def _refrescar_cambios(self) -> None:
        mod = self._modificado_elegido()
        if self.proyecto is None or mod is None:
            _llenar(self.tabla_cambios, [])
            self.total_modificado.setText("")
            return
        r = self.proyecto.resumen_modificado(mod)

        def n(v):
            return "" if v is None else escribir_numero(round(v, 6))

        filas = [
            [
                TIPOS_MODIFICADO[x.tipo],
                x.codigo or "",
                x.resumen or NO_CONSTA,
                x.unidad or "",
                n(x.cantidad_contrato),
                n(x.cantidad_modificada),
                n(x.diferencia_cantidad),
                _dinero(x.precio) if x.precio is not None else NO_CONSTA,
                _dinero(x.diferencia_importe),
                x.motivo or "",
                x.justificacion or "",
            ]
            for x in r.cambios
        ]
        _llenar(self.tabla_cambios, filas, [x.cambio_id for x in r.cambios])
        texto = (
            f"Contrato: <b>{_dinero(r.total_contrato)}</b> · Modificado: "
            f"<b>{_dinero(r.total_modificado)}</b> · Diferencia: <b>{_dinero(r.diferencia)}</b>"
        )
        if r.parcial:
            texto += " (parcial)"
        notas = r.notas()
        if notas:
            # Las mismas notas que el Excel (Resumen.notas): las dos salidas dicen lo mismo.
            texto += "<br>" + "<br>".join(f"⚠ {html.escape(n)}" for n in notas)
        self.total_modificado.setText(texto)

    def _al_elegir_modificado(self) -> None:
        self._refrescar_cambios()
        self._actualizar_estado()

    def accion_nuevo_modificado(self) -> None:
        r = self.preguntas.nuevo_modificado(self.proyecto.mediciones())
        if r is None:
            return
        orden = CrearModificado(*r)
        if self._ejecutar(orden):
            self.ir_a_paso("modificados")
            ids = [m["id"] for m in self.proyecto.modificados()]
            self.tabla_modificados.setCurrentCell(ids.index(orden.id), 0)

    def accion_variar(self) -> None:
        mod = self.proyecto.modificado(self._modificado_elegido())
        ya = {x.partida_id for x in self.proyecto.resumen_modificado(mod["id"]).cambios}
        partidas = [
            p
            for p in self.proyecto.partidas(mod["medicion_id"])
            if p["estado"] in ESTADOS_FIABLES and p["cantidad"] is not None and p["id"] not in ya
        ]
        if not partidas:
            self.preguntas.aviso(
                "Cambiar cantidad",
                "No quedan partidas de la base que se puedan variar: las que tienen cantidad "
                "fiable ya están en este modificado (o están «a revisar»).",
            )
            return
        d = self.preguntas.variacion(partidas)
        if d is not None:
            self._ejecutar(
                VariarPartida(mod["id"], d.partida_id, d.cantidad, d.motivo, d.justificacion)
            )

    def _lineas_de_oferta(self, modificado_id: str) -> list[dict]:
        """Líneas de oferta que aún se pueden añadir a este modificado: ni ya añadidas ni de
        la propia medición de base."""
        mod = self.proyecto.modificado(modificado_id)
        if mod is None:
            return []
        ya = {
            x.partida_id
            for x in self.proyecto.resumen_modificado(modificado_id).cambios
            if x.tipo == "nueva"
        }
        return [
            p
            for p in self.proyecto.ofertas_utilizables()
            if p["id"] not in ya and p["medicion_id"] != mod["medicion_id"]
        ]

    def accion_partida_nueva(self) -> None:
        mod = self._modificado_elegido()
        d = self.preguntas.partida_nueva(self._lineas_de_oferta(mod))
        if d is not None:
            self._ejecutar(
                AnadirPartidaNueva(mod, d.partida_id, d.cantidad, d.motivo, d.justificacion)
            )

    def accion_quitar_cambio(self) -> None:
        cambio = self._cambio_elegido()
        if cambio is not None:
            self._ejecutar(QuitarCambio(cambio))

    def accion_borrar_modificado(self) -> None:
        mod = self.proyecto.modificado(self._modificado_elegido())
        if mod and self.preguntas.confirmar(
            "Borrar modificado",
            f"Se borra el modificado nº {mod['numero']} «{mod['titulo']}» con sus "
            f"{mod['n_cambios']} cambio(s). Se puede deshacer. ¿Continuar?",
        ):
            self._ejecutar(BorrarModificado(mod["id"]))

    def _nombre_salida(self, mod: dict) -> str:
        return f"{self.proyecto.nombre} - modificado {mod['numero']}"

    def accion_exportar_mod_excel(self) -> None:
        mod = self.proyecto.modificado(self._modificado_elegido())
        sugerido = self.proyecto.carpeta.exportaciones / f"{self._nombre_salida(mod)}.xlsx"
        destino = self.preguntas.destino_excel(sugerido)
        if destino is not None:
            ruta = self.proyecto.exportar_modificado_excel(mod["id"], destino)
            self.statusBar().showMessage(f"Excel guardado: {ruta}", 10000)

    def accion_exportar_mod_bc3(self) -> None:
        mod = self.proyecto.modificado(self._modificado_elegido())
        sugerido = self.proyecto.carpeta.exportaciones / f"{self._nombre_salida(mod)}.bc3"
        destino = self.preguntas.destino_bc3(sugerido)
        if destino is None:
            return
        ruta, avisos = self.proyecto.exportar_modificado_bc3(mod["id"], destino)
        self.statusBar().showMessage(f"BC3 guardado: {ruta}", 10000)
        self.preguntas.informacion(
            "BC3 guardado",
            f"{ruta}\n\nSe ha vuelto a leer: códigos, cantidades y precios de todas las "
            "partidas son los del modificado, y el lector no encuentra descuadres nuevos."
            + ("\n\nAvisos:\n- " + "\n- ".join(avisos) if avisos else ""),
        )

    def accion_historial(self) -> None:
        self.dock_historial.setVisible(not self.dock_historial.isVisible())

    def accion_revisado(self) -> None:
        paso = self.paso_actual()
        if paso is None or self.proyecto is None:
            return
        if self.proyecto.estado_paso(paso).estado != "desactualizado":
            self.preguntas.informacion("Dar por revisado", "Este paso no está desactualizado.")
            return
        self.proyecto.dar_por_revisado(paso)
        self.refrescar()

    def accion_encargo(self) -> None:
        nuevo = self.preguntas.encargo(self.proyecto.encargo)
        if nuevo is not None and nuevo != self.proyecto.encargo:
            self._ejecutar(CambiarEncargo(nuevo))

    def _refrescar_arbol(self, seleccionar: str | None) -> None:
        self.arbol.blockSignals(True)
        try:
            self.arbol.clear()
            if self.proyecto is not None:
                # Niveles, espacios y obstáculos viven en el paso «Planos».
                elementos = [
                    e for e in self.proyecto.elementos() if e["tipo"] not in TIPOS_DE_PLANO
                ]
                nodos: dict[str, QTreeWidgetItem] = {}
                pendientes = list(elementos)
                # Padres antes que hijos, sea cual sea el orden alfabético.
                while pendientes:
                    resto = []
                    for e in pendientes:
                        padre = e["padre_id"]
                        if padre and padre not in nodos:
                            resto.append(e)
                            continue
                        item = QTreeWidgetItem(
                            [e["codigo"], tipo_de(e["tipo"]).etiqueta, ETIQUETA_ESTADO[e["estado"]]]
                        )
                        item.setData(0, Qt.UserRole, e["id"])
                        (nodos[padre] if padre else self.arbol.invisibleRootItem()).addChild(item)
                        nodos[e["id"]] = item
                    if len(resto) == len(pendientes):
                        raise RuntimeError("Jerarquía de elementos con referencias circulares.")
                    pendientes = resto
                self.arbol.expandAll()
                if seleccionar in nodos:
                    nodos[seleccionar].setSelected(True)
                    self.arbol.setCurrentItem(nodos[seleccionar])
        finally:
            self.arbol.blockSignals(False)

    def _refrescar_propiedades(self) -> None:
        el = self.elemento_seleccionado()
        if el is None:
            self.cabecera.setText("<i>Selecciona un elemento.</i>")
            _llenar(self.tabla_propiedades, [])
            return
        t = tipo_de(el["tipo"])
        self.cabecera.setText(
            f"<b>{el['codigo']}</b> · {t.etiqueta} · estado: <b>{ETIQUETA_ESTADO[el['estado']]}</b>"
        )
        valores = {p["clave"]: p for p in self.proyecto.propiedades(el["id"])}
        filas, ids = [], []
        for d in t.propiedades:
            p = valores.get(d.clave)
            etiqueta = d.etiqueta + (" *" if d.obligatoria_para_aprobar else "")
            if p is None:
                filas.append([etiqueta, NO_CONSTA, "", "", ""])
            else:
                v = p["valor"]
                texto = escribir_numero(v) if isinstance(v, int | float) else v
                if p["documento_id"]:
                    fuente = f"{p['documento_nombre']} · {p['localizador']}"
                    if p["nota"]:
                        fuente += f" · {p['nota']}"
                else:
                    fuente = p["nota"] or ""
                filas.append(
                    [etiqueta, texto, p["unidad"] or "", ETIQUETA_ORIGEN[p["origen"]], fuente]
                )
            ids.append(d.clave)
        _llenar(self.tabla_propiedades, filas, ids)

    def _refrescar_documentos(self) -> None:
        if self.proyecto is None:
            _llenar(self.tabla_documentos, [])
            return
        docs = self.proyecto.documentos()
        filas = []
        for d in docs:
            usos = self.proyecto.usos_de_documento(d["id"])
            filas.append(
                [
                    d["nombre_original"],
                    d["clasificacion"] or "",
                    "" if d["paginas"] is None else str(d["paginas"]),
                    _fecha(d["incorporado"]),
                    str(len(usos)),
                ]
            )
        _llenar(self.tabla_documentos, filas, [d["id"] for d in docs])

    def _refrescar_historial(self) -> None:
        if self.proyecto is None:
            _llenar(self.tabla_historial, [])
            return
        cambios = self.proyecto.cambios()
        # Códigos también de elementos ya quitados (el registro guarda su fila): si no, sus
        # cambios salían sin decir a qué afectaban (revisión 07-11-2026).
        codigos = {}
        for c in cambios:
            if c["entidad"] == "elemento":
                f = json.loads(c["despues"] or c["antes"])
                codigos.setdefault(f["id"], f["codigo"])
        codigos.update({e["id"]: e["codigo"] for e in self.proyecto.elementos()})
        filas = []
        for c in cambios:
            fila = json.loads(c["despues"] or c["antes"])
            afecta = codigos.get(fila.get("elemento_id") or fila.get("id"), "")
            if c["entidad"] == "propiedad":
                afecta = f"{afecta} · {fila['clave']}"
            elif c["entidad"] == "documento":
                afecta = fila["nombre_original"]
            elif c["entidad"] == "medicion":
                afecta = f"medición «{fila['nombre']}»"
            elif c["entidad"] == "partida":
                afecta = f"partida {fila['codigo'] or fila['orden']}"
            elif c["entidad"] == "meta":
                afecta = f"proyecto · {fila['clave']}"
            elif c["entidad"] == "pendiente":
                afecta = afecta or "pendiente"
            elif c["entidad"] == "plano":
                afecta = "plano (capas y unidad)"
            elif c["entidad"] == "geometria":
                afecta = f"{afecta} · contorno (entidad {fila['handle']})"
            elif c["entidad"] == "registro_calculo":
                afecta = f"registro de cálculo · {fila['motor']}"
            filas.append([_fecha(c["fecha"]), c["autor"], c["orden"], afecta, c["campo"] or ""])
        _llenar(self.tabla_historial, filas)

    def _refrescar_pendientes(self) -> None:
        if self.proyecto is None:
            _llenar(self.tabla_pendientes, [])
            return
        codigos = {e["id"]: e["codigo"] for e in self.proyecto.elementos()}
        ps = self.proyecto.pendientes()
        _llenar(
            self.tabla_pendientes,
            [
                [p["descripcion"], codigos.get(p["elemento_id"], ""), _fecha(p["creado"])]
                for p in ps
            ],
            [p["id"] for p in ps],
        )

    def _al_seleccionar(self) -> None:
        self._refrescar_propiedades()
        self._actualizar_estado()

    # --- Ejecución de órdenes ------------------------------------------------------------

    def _ejecutar(self, orden: Orden) -> bool:
        try:
            self.proyecto.ejecutar(orden)
        except OrdenRechazada as exc:
            self.preguntas.aviso("No se ha aplicado", str(exc))
            return False
        self.refrescar()
        return True

    # --- Acciones: proyecto --------------------------------------------------------------

    def accion_nueva_obra(self) -> None:
        """Echar todos los documentos recibidos y montar la obra (docs/modules/obra.md, 4c)."""
        from traza.ui import crear_obra

        crear_obra.nueva_obra(self)

    def accion_anadir_documentos(self) -> None:
        from traza.ui import crear_obra

        crear_obra.anadir_documentos(self)

    def accion_nuevo_proyecto(self) -> None:
        r = self.preguntas.nuevo_proyecto()
        if r is None:
            return
        destino, nombre, encargo = r
        try:
            p = Proyecto.crear(destino, nombre, encargo)
        except Exception as exc:
            self.preguntas.aviso("No se ha creado el proyecto", str(exc))
            return
        self._usar_proyecto(p)

    def accion_abrir_proyecto(self) -> None:
        raiz = self.preguntas.proyecto_existente()
        if raiz is None:
            return
        self.abrir(raiz)

    def abrir(self, raiz: Path) -> bool:
        try:
            p = Proyecto.abrir(raiz)
        except Exception as exc:
            self.preguntas.aviso("No se ha abierto el proyecto", str(exc))
            return False
        self._usar_proyecto(p)
        return True

    def _usar_proyecto(self, p: Proyecto) -> None:
        if self.proyecto is not None:
            self.proyecto.cerrar()
        self.proyecto = p
        self.refrescar()
        self.statusBar().showMessage(f"Proyecto: {p.carpeta.raiz}")

    def accion_cerrar_proyecto(self) -> None:
        if self.proyecto is not None:
            self.proyecto.cerrar()
            self.proyecto = None
        self.refrescar()
        self.statusBar().clearMessage()

    def accion_copia(self) -> None:
        ruta = self.proyecto.copia_de_seguridad()
        self.statusBar().showMessage(f"Copia guardada: {ruta.name}", 8000)

    def accion_emitir_revision(self) -> None:
        """Congela el diseño con un nombre («Para oferta»): luego se compara con él."""
        nombre = self.preguntas.texto(
            "Emitir revisión", "Nombre de la revisión (p. ej. «Para oferta», «Planos rev. B»):"
        )
        if not nombre:
            return
        nota = self.preguntas.texto("Emitir revisión", "Nota (opcional): qué cambia o para qué es")
        r = self.proyecto.emitir_revision(nombre, nota or "")
        self.refrescar()
        self.preguntas.informacion(
            "Revisión emitida",
            f"Rev. {r.numero} · {r.nombre}. Queda congelada en la carpeta «revisiones» del "
            "proyecto; se compara con «Archivo → Comparar con una revisión…».",
        )

    def accion_comparar(self) -> None:
        from traza.ui.paso_redes import _archivo

        revisiones = self.proyecto.revisiones()
        if not revisiones:
            return
        etiquetas = [f"Rev. {r.numero} · {r.nombre} ({r.fecha[:10]})" for r in revisiones]
        i = self.preguntas.elegir("Comparar", "Desde la revisión:", etiquetas)
        if i is None:
            return
        destinos = ["Estado actual del proyecto"] + [e for k, e in enumerate(etiquetas) if k != i]
        numeros = [None] + [r.numero for k, r in enumerate(revisiones) if k != i]
        j = self.preguntas.elegir("Comparar", "Hasta:", destinos)
        if j is None:
            return
        antes, ahora = revisiones[i].numero, numeros[j]
        nombre = f"Rev {antes} a {'actual' if ahora is None else f'Rev {ahora}'}"
        destino = self.preguntas.destino_excel(
            self.proyecto.carpeta.raiz.parent
            / f"{_archivo(self.proyecto.nombre)} - comparación {nombre}.xlsx"
        )
        if destino is None:
            return
        # Una sola comparación (recalcula cargas, redes y sistemas de las dos versiones).
        cambios = self.proyecto.comparar_revisiones(antes, ahora)
        ruta = self.proyecto.exportar_comparacion(antes, ahora, destino, cambios)
        if not cambios:
            texto = "No hay cambios en los datos ni en los resultados que deciden."
        else:
            from collections import Counter

            por = Counter(c.apartado for c in cambios)
            texto = f"{len(cambios)} cambios: " + "; ".join(f"{a} {n}" for a, n in por.items())
        self.preguntas.informacion(
            "Comparación", f"{etiquetas[i]} → {destinos[j]}\n\n{texto}\n\nDetalle en {ruta}"
        )

    def accion_restaurar(self) -> None:
        copias = list(reversed(self.proyecto.copias()))  # la más reciente primero
        if not copias:
            self.preguntas.aviso("Restaurar copia", "Este proyecto no tiene copias de seguridad.")
            return
        etiquetas = [_etiqueta_copia(c) for c in copias]
        i = self.preguntas.elegir("Restaurar copia", "Copia a restaurar:", etiquetas)
        if i is None:
            return
        copia = copias[i]
        if not self.preguntas.confirmar(
            "Restaurar copia",
            f"Se cerrará el proyecto y se sustituirá por la copia «{etiquetas[i]}». El estado "
            "actual se guarda antes como copia «antes de restaurar». Se perderá la lista de "
            "deshacer de esta sesión. ¿Continuar?",
        ):
            return
        raiz = self.proyecto.carpeta.raiz
        self.accion_cerrar_proyecto()
        try:
            Proyecto.restaurar_copia(raiz, copia)
        except Exception as exc:
            self.preguntas.aviso("No se ha restaurado", str(exc))
        self.abrir(raiz)

    def accion_deshacer(self) -> None:
        nombre = self.proyecto.deshacer()
        self.refrescar()
        if nombre:
            self.statusBar().showMessage(f"Deshecho: {nombre}", 5000)

    def accion_rehacer(self) -> None:
        nombre = self.proyecto.rehacer()
        self.refrescar()
        if nombre:
            self.statusBar().showMessage(f"Rehecho: {nombre}", 5000)

    # --- Acciones: elementos -------------------------------------------------------------

    def accion_nuevo_elemento(self) -> None:
        r = self.preguntas.nuevo_elemento(
            [t for t in tipos() if t.nombre not in TIPOS_DE_PLANO],
            [e for e in self.proyecto.elementos() if e["tipo"] not in TIPOS_DE_PLANO],
        )
        if r is None:
            return
        tipo, codigo, padre = r
        orden = CrearElemento(tipo, codigo, padre)
        if self._ejecutar(orden):
            self.seleccionar(orden.id)

    def seleccionar(self, elemento_id: str) -> None:
        self._refrescar_arbol(elemento_id)
        self._al_seleccionar()

    def accion_fijar_valor(self) -> None:
        el = self.elemento_seleccionado()
        if el is None or el["estado"] == Estado.APROBADO:
            return
        datos = self.preguntas.valor(
            tipo_de(el["tipo"]), self.proyecto.documentos(), self._clave_seleccionada()
        )
        if datos is None:
            return
        self._ejecutar(
            FijarPropiedad(el["id"], datos.clave, datos.valor, datos.unidad, datos.procedencia)
        )

    def accion_borrar_valor(self) -> None:
        el, clave = self.elemento_seleccionado(), self._clave_seleccionada()
        if el is None or clave is None:
            self.preguntas.aviso("Borrar valor", "Selecciona la fila de la propiedad.")
            return
        self._ejecutar(BorrarPropiedad(el["id"], clave))

    def accion_confirmar_propuesta(self) -> None:
        el, clave = self.elemento_seleccionado(), self._clave_seleccionada()
        if el is None or clave is None:
            self.preguntas.aviso("Confirmar propuesta", "Selecciona la fila de la propuesta.")
            return
        self._ejecutar(ConfirmarPropuesta(el["id"], clave))

    def accion_aprobar(self) -> None:
        el = self.elemento_seleccionado()
        if el is None:
            return
        motivo = self.preguntas.texto(f"Aprobar {el['codigo']}", "Motivo de la aprobación:")
        if motivo is not None:
            self._ejecutar(Aprobar(el["id"], motivo))

    def accion_reabrir(self) -> None:
        el = self.elemento_seleccionado()
        if el is None:
            return
        motivo = self.preguntas.texto(
            f"Reabrir {el['codigo']}", "Motivo para reabrir un elemento aprobado:"
        )
        if motivo is not None:
            self._ejecutar(Reabrir(el["id"], motivo))

    # --- Acciones: documentos y pendientes -----------------------------------------------

    def accion_incorporar_documento(self) -> None:
        r = self.preguntas.documento()
        if r is None:
            return
        ruta, clasificacion = r
        try:
            self.proyecto.incorporar_documento(ruta, clasificacion)
        except (OrdenRechazada, OSError) as exc:
            self.preguntas.aviso("No se ha incorporado", str(exc))
            return
        self.refrescar()

    def accion_abrir_documento(self) -> None:
        fila = self.tabla_documentos.currentRow()
        if fila < 0:
            return
        doc_id = self.tabla_documentos.item(fila, 0).data(Qt.UserRole)
        ruta = self.proyecto.ruta_documento(doc_id)
        if ruta.suffix.lower() not in EXTENSIONES_ABRIBLES:
            # Abrir con el programa asociado de Windows EJECUTARÍA un .bat, .exe o .lnk.
            self.preguntas.aviso(
                "Abrir documento",
                f"Por seguridad no se abren ficheros «{ruta.suffix}» desde TRAZA. "
                f"Está guardado en: {ruta}",
            )
            return
        if not ruta.is_file():
            self.preguntas.aviso("Abrir documento", f"No se encuentra el fichero: {ruta}")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(ruta))):
            self.preguntas.aviso("Abrir documento", f"Windows no ha podido abrir {ruta.name}.")

    def accion_nuevo_pendiente(self) -> None:
        el = self.elemento_seleccionado()
        texto = self.preguntas.texto("Información pendiente", "¿Qué falta por confirmar?")
        if texto is not None:
            self._ejecutar(CrearPendiente(texto, el["id"] if el else None))

    def accion_resolver_pendiente(self) -> None:
        fila = self.tabla_pendientes.currentRow()
        if fila < 0:
            return
        pid = self.tabla_pendientes.item(fila, 0).data(Qt.UserRole)
        texto = self.preguntas.texto("Resolver pendiente", "¿Cómo se ha resuelto?")
        if texto is not None:
            self._ejecutar(ResolverPendiente(pid, texto))

    def accion_acerca(self) -> None:
        self.preguntas.informacion(
            "Acerca de TRAZA",
            f"TRAZA {__version__}\nEntorno personal de ingeniería de instalaciones.\n"
            "Cada valor indica de dónde sale; lo aprobado no se modifica sin reabrirlo.",
        )

    # --- Cierre --------------------------------------------------------------------------

    def closeEvent(self, evento) -> None:  # noqa: N802 (nombre impuesto por Qt)
        if self.proyecto is not None:
            self.proyecto.cerrar()
            self.proyecto = None
        super().closeEvent(evento)
