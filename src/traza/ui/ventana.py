"""Ventana principal de TRAZA.

Distribución clásica de ingeniería (decisión del usuario, 06-11-2026): árbol de elementos
a la izquierda, propiedades con su procedencia en el centro, y abajo pestañas de
Documentos, Historial y Pendientes. Los paneles se pueden mover.

Regla de la interfaz: no hay ninguna acción visible sin función real detrás (lo comprueba
un test) y toda cifra muestra de dónde sale en la misma fila.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QHeaderView,
    QLabel,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from traza import __version__
from traza.app.ordenes import (
    Aprobar,
    BorrarPropiedad,
    ConfirmarPropuesta,
    CrearElemento,
    CrearPendiente,
    FijarPropiedad,
    Orden,
    OrdenRechazada,
    Reabrir,
    ResolverPendiente,
)
from traza.app.proyecto import Proyecto
from traza.core.estados import Estado
from traza.core.numeros import escribir_numero
from traza.core.tipos import tipo as tipo_de
from traza.core.tipos import tipos
from traza.ui.dialogos import Preguntas

ETIQUETA_ORIGEN = {
    "usuario": "Usuario",
    "documento": "Documento",
    "catalogo": "Catálogo",
    "calculo": "Cálculo",
    "hipotesis": "Hipótesis",
    "ia_propuesta": "Propuesta IA — sin confirmar",
}
ETIQUETA_ESTADO = {
    "borrador": "Borrador",
    "propuesto": "Propuesto",
    "calculado": "Calculado",
    "comprobado": "Comprobado",
    "aprobado": "Aprobado",
}
NO_CONSTA = "— no consta —"


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


def _fecha(iso: str) -> str:
    # Se guarda en UTC; se muestra tal cual con la marca para no inventar zona horaria.
    return iso.replace("T", " ").replace("+00:00", " UTC")


class VentanaPrincipal(QMainWindow):
    def __init__(self, preguntas: Preguntas | None = None) -> None:
        super().__init__()
        self.proyecto: Proyecto | None = None
        self.preguntas = preguntas or Preguntas(self)
        self.resize(1400, 850)
        self._construir()
        self._actualizar_estado()

    # --- Construcción --------------------------------------------------------------------

    def _construir(self) -> None:
        # Centro: propiedades del elemento seleccionado.
        centro = QWidget()
        lay = QVBoxLayout(centro)
        self.cabecera = QLabel()
        self.cabecera.setTextFormat(Qt.RichText)
        lay.addWidget(self.cabecera)
        self.tabla_propiedades = _tabla(
            ["Propiedad", "Valor", "Unidad", "Procedencia", "Fuente / justificación"]
        )
        self.tabla_propiedades.doubleClicked.connect(lambda _i: self.accion_fijar_valor())
        lay.addWidget(self.tabla_propiedades)
        self.setCentralWidget(centro)

        # Izquierda: árbol de elementos.
        self.arbol = QTreeWidget()
        self.arbol.setHeaderLabels(["Código", "Tipo", "Estado"])
        self.arbol.itemSelectionChanged.connect(self._al_seleccionar)
        self._dock("Elementos", self.arbol, Qt.LeftDockWidgetArea)

        # Abajo: documentos, historial, pendientes.
        self.tabla_documentos = _tabla(
            ["Documento", "Tipo", "Páginas", "Incorporado", "Valores que lo citan"]
        )
        self.tabla_documentos.doubleClicked.connect(lambda _i: self.accion_abrir_documento())
        self.tabla_historial = _tabla(["Fecha", "Autor", "Orden", "Afecta a", "Campos"])
        self.tabla_pendientes = _tabla(["Pendiente", "Elemento", "Creado"])
        d1 = self._dock("Documentos", self.tabla_documentos, Qt.BottomDockWidgetArea)
        d2 = self._dock("Historial", self.tabla_historial, Qt.BottomDockWidgetArea)
        d3 = self._dock("Pendientes", self.tabla_pendientes, Qt.BottomDockWidgetArea)
        self.tabifyDockWidget(d1, d2)
        self.tabifyDockWidget(d2, d3)
        d1.raise_()

        self._crear_acciones()
        self.tabla_documentos.itemSelectionChanged.connect(self._actualizar_estado)
        self.tabla_pendientes.itemSelectionChanged.connect(self._actualizar_estado)
        self.statusBar()

    def _dock(self, titulo: str, widget: QWidget, zona) -> QDockWidget:
        d = QDockWidget(titulo, self)
        d.setObjectName(f"dock_{titulo}")
        d.setWidget(widget)
        self.addDockWidget(zona, d)
        return d

    def _accion(self, menu, texto: str, funcion: Callable[[], None], atajo=None) -> QAction:
        a = QAction(texto, self)
        if atajo is not None:
            a.setShortcut(QKeySequence(atajo))
        a.triggered.connect(lambda _marcado=False: funcion())
        menu.addAction(a)
        return a

    def _crear_acciones(self) -> None:
        mb = self.menuBar()
        m = mb.addMenu("&Archivo")
        self.a_nuevo = self._accion(
            m, "Nuevo proyecto…", self.accion_nuevo_proyecto, QKeySequence.New
        )
        self.a_abrir = self._accion(
            m, "Abrir proyecto…", self.accion_abrir_proyecto, QKeySequence.Open
        )
        self.a_cerrar = self._accion(m, "Cerrar proyecto", self.accion_cerrar_proyecto)
        m.addSeparator()
        self.a_copia = self._accion(m, "Hacer copia de seguridad", self.accion_copia)
        self.a_restaurar = self._accion(m, "Restaurar copia de seguridad…", self.accion_restaurar)
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
        el = self.elemento_seleccionado() if hay else None
        aprobado = el is not None and el["estado"] == Estado.APROBADO
        for a in (
            self.a_cerrar,
            self.a_copia,
            self.a_nuevo_elemento,
            self.a_incorporar,
            self.a_nuevo_pendiente,
        ):
            a.setEnabled(hay)
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
            titulo += f" — {self.proyecto.nombre}"
        self.setWindowTitle(titulo)

    def refrescar(self) -> None:
        seleccion = self.elemento_seleccionado()
        self._refrescar_arbol(seleccion["id"] if seleccion else None)
        self._refrescar_propiedades()
        self._refrescar_documentos()
        self._refrescar_historial()
        self._refrescar_pendientes()
        self._actualizar_estado()

    def _refrescar_arbol(self, seleccionar: str | None) -> None:
        self.arbol.blockSignals(True)
        self.arbol.clear()
        if self.proyecto is not None:
            elementos = self.proyecto.elementos()
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
        codigos = {e["id"]: e["codigo"] for e in self.proyecto.elementos()}
        filas = []
        for c in self.proyecto.cambios():
            fila = json.loads(c["despues"] or c["antes"])
            afecta = codigos.get(fila.get("elemento_id") or fila.get("id"), "")
            if c["entidad"] == "propiedad":
                afecta = f"{afecta} · {fila['clave']}"
            elif c["entidad"] == "documento":
                afecta = fila["nombre_original"]
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

    def accion_nuevo_proyecto(self) -> None:
        r = self.preguntas.nuevo_proyecto()
        if r is None:
            return
        destino, nombre = r
        try:
            p = Proyecto.crear(destino, nombre)
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

    def accion_restaurar(self) -> None:
        copias = self.proyecto.copias()
        i = self.preguntas.elegir(
            "Restaurar copia", "Copia a restaurar:", [c.name for c in reversed(copias)]
        )
        if i is None:
            return
        copia = list(reversed(copias))[i]
        if not self.preguntas.confirmar(
            "Restaurar copia",
            f"Se cerrará el proyecto y se sustituirá por «{copia.name}». El estado actual se "
            "guarda antes como copia «antes-de-restaurar». ¿Continuar?",
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
        r = self.preguntas.nuevo_elemento(list(tipos()), self.proyecto.elementos())
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
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.proyecto.ruta_documento(doc_id))))

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
