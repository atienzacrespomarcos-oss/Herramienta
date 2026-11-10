"""Diálogos y preguntas al usuario.

Toda pregunta pasa por la clase `Preguntas`. La ventana no abre diálogos por su cuenta:
así las pruebas sustituyen `Preguntas` por respuestas preparadas y recorren la interfaz
entera sin intervención, y lo que se prueba es el mismo código que usa el ingeniero.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from traza.app.ordenes import CLASES_MEDICION, ENCARGOS, MOTIVOS
from traza.core.numeros import escribir_numero, leer_numero
from traza.core.procedencia import Origen, Procedencia, ProcedenciaInvalida
from traza.core.tipos import Clase, TipoElemento

CLASIFICACIONES = [
    "oferta",
    "presupuesto",
    "medición",
    "plano",
    "pliego",
    "memoria",
    "ficha técnica",
    "catálogo",
    "manual",
    "normativa",
    "otro",
]

# Orígenes que el usuario puede elegir a mano. «Cálculo» lo escribe un motor y
# «propuesta de IA» la IA: no se ofrecen aquí (línea roja 7 y regla de motores).
ORIGENES_MANUALES = [
    (Origen.USUARIO, "Lo indico yo"),
    (Origen.DOCUMENTO, "Documento del proyecto"),
    (Origen.CATALOGO, "Catálogo de fabricante"),
    (Origen.HIPOTESIS, "Hipótesis de diseño (justificada)"),
]


@dataclass(frozen=True)
class DatosValor:
    clave: str
    valor: str | int | float
    unidad: str | None
    procedencia: Procedencia


class DialogoValor(QDialog):
    """Fijar el valor de una propiedad con su procedencia."""

    def __init__(
        self,
        padre: QWidget,
        tipo: TipoElemento,
        documentos: list[dict],
        clave_inicial: str | None = None,
    ) -> None:
        super().__init__(padre)
        self.setWindowTitle("Fijar valor")
        self.tipo = tipo
        self.documentos = documentos
        self.resultado: DatosValor | None = None

        self.propiedad = QComboBox()
        for p in tipo.propiedades:
            self.propiedad.addItem(p.etiqueta, p.clave)
        if clave_inicial:
            self.propiedad.setCurrentIndex(max(0, self.propiedad.findData(clave_inicial)))
        self.valor = QLineEdit()
        self.unidad = QLineEdit()
        self.origen = QComboBox()
        for o, texto in ORIGENES_MANUALES:
            self.origen.addItem(texto, o)
        self.documento = QComboBox()
        for d in documentos:
            self.documento.addItem(d["nombre_original"], d["id"])
        self.localizador = QLineEdit()
        self.localizador.setPlaceholderText("p. 14, tabla 3")
        self.nota = QLineEdit()
        self.error = QLabel()
        self.error.setStyleSheet("color: #c0392b")
        self.error.setWordWrap(True)

        f = QFormLayout(self)
        f.addRow("Propiedad", self.propiedad)
        f.addRow("Valor", self.valor)
        f.addRow("Unidad", self.unidad)
        f.addRow("Procedencia", self.origen)
        f.addRow("Documento", self.documento)
        f.addRow("Localización", self.localizador)
        f.addRow("Justificación / nota", self.nota)
        f.addRow(self.error)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        f.addRow(botones)

        self.propiedad.currentIndexChanged.connect(self._actualizar)
        self.origen.currentIndexChanged.connect(self._actualizar)
        self._actualizar()

    def _defn(self):
        return self.tipo.propiedad(self.propiedad.currentData())

    def _actualizar(self) -> None:
        d = self._defn()
        numerica = d.clase is Clase.NUMERO
        self.unidad.setEnabled(numerica)
        self.unidad.setPlaceholderText(f"magnitud de referencia: {d.unidad_si}" if numerica else "")
        cita = self.origen.currentData() in (Origen.DOCUMENTO, Origen.CATALOGO)
        self.documento.setEnabled(cita)
        self.localizador.setEnabled(cita)

    def _aceptar(self) -> None:
        try:
            d = self._defn()
            if d.clase is Clase.NUMERO:
                valor: str | int | float = leer_numero(self.valor.text())
                unidad = self.unidad.text().strip() or None
            else:
                valor, unidad = self.valor.text(), None
            origen = self.origen.currentData()
            cita = origen in (Origen.DOCUMENTO, Origen.CATALOGO)
            if cita and self.documento.count() == 0:
                raise ValueError("No hay documentos incorporados que citar.")
            procedencia = Procedencia(
                origen,
                documento_id=self.documento.currentData() if cita else None,
                localizador=self.localizador.text() if cita else None,
                nota=self.nota.text().strip() or None,
            )
        except (ValueError, ProcedenciaInvalida) as exc:
            self.error.setText(str(exc))
            return
        self.resultado = DatosValor(d.clave, valor, unidad, procedencia)
        self.accept()


class DialogoElemento(QDialog):
    def __init__(self, padre: QWidget, tipos: list[TipoElemento], elementos: list[dict]) -> None:
        super().__init__(padre)
        self.setWindowTitle("Nuevo elemento")
        self.resultado: tuple[str, str, str | None] | None = None
        self.tipo = QComboBox()
        for t in tipos:
            self.tipo.addItem(t.etiqueta, t.nombre)
        self.codigo = QLineEdit()
        self.codigo.setPlaceholderText("UTA-01")
        self.padre = QComboBox()
        self.padre.addItem("(ninguno)", None)
        for e in elementos:
            self.padre.addItem(e["codigo"], e["id"])
        f = QFormLayout(self)
        f.addRow("Tipo", self.tipo)
        f.addRow("Código", self.codigo)
        f.addRow("Forma parte de", self.padre)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        f.addRow(botones)

    def _aceptar(self) -> None:
        self.resultado = (self.tipo.currentData(), self.codigo.text(), self.padre.currentData())
        self.accept()


class DialogoMedicion(QDialog):
    """Elegir qué documento leer como medición, oferta o presupuesto, y de qué proveedor."""

    def __init__(self, padre: QWidget, documentos: list[dict]) -> None:
        super().__init__(padre)
        self.setWindowTitle("Leer medición u oferta")
        self.resultado: tuple[str, str, str | None] | None = None
        self.documento = QComboBox()
        for d in documentos:
            self.documento.addItem(d["nombre_original"], d["id"])
        self.clase = QComboBox()
        for clave, texto in CLASES_MEDICION.items():
            self.clase.addItem(texto, clave)
        self.proveedor = QLineEdit()
        self.proveedor.setPlaceholderText("opcional")
        f = QFormLayout(self)
        f.addRow("Documento", self.documento)
        f.addRow("Es una", self.clase)
        f.addRow("Proveedor", self.proveedor)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        f.addRow(botones)

    def _aceptar(self) -> None:
        self.resultado = (
            self.documento.currentData(),
            self.clase.currentData(),
            self.proveedor.text().strip() or None,
        )
        self.accept()


@dataclass(frozen=True)
class DatosCambio:
    partida_id: str
    cantidad: float
    motivo: str
    justificacion: str


def _cifra(v: float) -> str:
    """Cifra legible en español, sin notación científica (con «:g», 1234567 salía
    «1.23457e+06»)."""
    return escribir_numero(round(v, 6))


def _texto_partida(p: dict) -> str:
    cantidad = (
        "" if p.get("cantidad") is None else f" · {_cifra(p['cantidad'])} {p.get('unidad') or ''}"
    )
    precio = "" if p.get("precio") is None else f" · {_cifra(p['precio'])} €"
    origen = f"{p['documento_nombre']} · " if p.get("documento_nombre") else ""
    # Capítulo y nº de línea: una misma partida repetida en dos capítulos (habitual en un
    # BC3) tenía el mismo texto y no se distinguía.
    capitulo = " / ".join(c[1] or c[0] for c in p.get("capitulo") or [])
    donde = f" [{capitulo + ', ' if capitulo else ''}línea {p['orden']}]" if "orden" in p else ""
    return f"{origen}{p.get('codigo') or '—'} — {p.get('resumen') or ''}{cantidad}{precio}{donde}"


class DialogoCambio(QDialog):
    """Cambio de un modificado: variación de una partida de la base o partida nueva de una
    oferta. El buscador filtra por cualquier parte del texto (código, descripción, oferta)."""

    def __init__(
        self, padre: QWidget, titulo: str, partidas: list[dict], etiqueta_cantidad: str
    ) -> None:
        super().__init__(padre)
        self.setWindowTitle(titulo)
        self.resize(720, 0)
        self.resultado: DatosCambio | None = None
        self.partida = QComboBox()
        self.partida.setEditable(True)
        self.partida.setInsertPolicy(QComboBox.NoInsert)
        vistos: dict[str, int] = {}
        for p in partidas:
            texto = _texto_partida(p)
            # Textos únicos: el elegido se identifica por su texto si el usuario lo escribe.
            vistos[texto] = vistos.get(texto, 0) + 1
            if vistos[texto] > 1:
                texto = f"{texto} ({vistos[texto]})"
            self.partida.addItem(texto, p["id"])
        buscador = self.partida.completer()
        buscador.setFilterMode(Qt.MatchContains)
        buscador.setCompletionMode(QCompleter.PopupCompletion)
        self.cantidad = QLineEdit()
        self.motivo = QComboBox()
        for clave, texto in MOTIVOS.items():
            self.motivo.addItem(texto, clave)
        self.justificacion = QLineEdit()
        self.justificacion.setPlaceholderText("Obligatoria: por qué se cambia")
        self.error = QLabel()
        self.error.setStyleSheet("color: #c0392b")
        self.error.setWordWrap(True)
        f = QFormLayout(self)
        f.addRow("Partida", self.partida)
        f.addRow(etiqueta_cantidad, self.cantidad)
        f.addRow("Motivo", self.motivo)
        f.addRow("Justificación", self.justificacion)
        f.addRow(self.error)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        f.addRow(botones)

    def _aceptar(self) -> None:
        # El índice elegido manda; el texto solo si el usuario lo ha escrito a mano. Antes
        # findText devolvía la PRIMERA con ese texto, aunque se eligiera otra igual
        # (revisión 06-11-2026).
        indice = self.partida.currentIndex()
        if indice < 0 or self.partida.itemText(indice) != self.partida.currentText():
            indice = self.partida.findText(self.partida.currentText(), Qt.MatchExactly)
        if indice < 0:
            self.error.setText("Elige una partida de la lista.")
            return
        try:
            cantidad = float(leer_numero(self.cantidad.text()))
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        if not self.justificacion.text().strip():
            self.error.setText("La justificación es obligatoria.")
            return
        self.resultado = DatosCambio(
            self.partida.itemData(indice),
            cantidad,
            self.motivo.currentData(),
            self.justificacion.text().strip(),
        )
        self.accept()


class Preguntas:
    """Implementación real con diálogos de Qt."""

    def __init__(self, ventana: QWidget) -> None:
        self.v = ventana

    def nuevo_proyecto(self) -> tuple[Path, str, str] | None:
        nombre, ok = QInputDialog.getText(self.v, "Nuevo proyecto", "Nombre del proyecto:")
        if not ok or not nombre.strip():
            return None
        encargo = self.encargo(None)
        if encargo is None:
            return None
        carpeta = QFileDialog.getExistingDirectory(self.v, "Carpeta donde crear el proyecto")
        return (Path(carpeta) / nombre.strip(), nombre.strip(), encargo) if carpeta else None

    def nueva_obra(self) -> tuple[Path, str] | None:
        nombre, ok = QInputDialog.getText(self.v, "Nueva obra", "Nombre de la obra:")
        if not ok or not nombre.strip():
            return None
        carpeta = QFileDialog.getExistingDirectory(self.v, "Carpeta donde crear la obra")
        return (Path(carpeta) / nombre.strip(), nombre.strip()) if carpeta else None

    def ficheros(self, titulo: str) -> list[Path]:
        rutas, _ = QFileDialog.getOpenFileNames(self.v, titulo)
        return [Path(r) for r in rutas]

    def plan_obra(self, propuestas: list):
        from traza.ui.dialogos_obra import DialogoPlanObra

        d = DialogoPlanObra(self.v, propuestas)
        return d.resultado if d.exec() == QDialog.Accepted else None

    def encargo(self, actual: str | None) -> str | None:
        claves = list(ENCARGOS)
        textos = [ENCARGOS[k] for k in claves]
        inicial = claves.index(actual) if actual in claves else 0
        texto, ok = QInputDialog.getItem(
            self.v, "Tipo de encargo", "¿Qué incluye este encargo?", textos, inicial, False
        )
        return claves[textos.index(texto)] if ok else None

    def leer_medicion(self, documentos: list[dict]) -> tuple[str, str, str | None] | None:
        d = DialogoMedicion(self.v, documentos)
        return d.resultado if d.exec() == QDialog.Accepted else None

    def nuevo_modificado(self, mediciones: list[dict]) -> tuple[str, str] | None:
        opciones = [f"{m['documento_nombre']} ({CLASES_MEDICION[m['clase']]})" for m in mediciones]
        texto, ok = QInputDialog.getItem(
            self.v,
            "Nuevo modificado",
            "Medición o presupuesto de base (el contratado):",
            opciones,
            0,
            False,
        )
        if not ok:
            return None
        titulo, ok = QInputDialog.getText(self.v, "Nuevo modificado", "Título:")
        if not ok or not titulo.strip():
            return None
        return mediciones[opciones.index(texto)]["id"], titulo.strip()

    def variacion(self, partidas: list[dict]) -> DatosCambio | None:
        d = DialogoCambio(self.v, "Cambiar cantidad", partidas, "Cantidad nueva (total)")
        return d.resultado if d.exec() == QDialog.Accepted else None

    def partida_nueva(self, lineas_oferta: list[dict]) -> DatosCambio | None:
        d = DialogoCambio(self.v, "Añadir partida de una oferta", lineas_oferta, "Cantidad")
        return d.resultado if d.exec() == QDialog.Accepted else None

    def destino_bc3(self, sugerido: Path) -> Path | None:
        ruta, _ = QFileDialog.getSaveFileName(
            self.v, "Exportar BC3 del presupuesto actualizado", str(sugerido), "BC3 (*.bc3)"
        )
        return Path(ruta) if ruta else None

    def destino_excel(self, sugerido: Path) -> Path | None:
        ruta, _ = QFileDialog.getSaveFileName(
            self.v, "Exportar Excel con todo", str(sugerido), "Excel (*.xlsx)"
        )
        return Path(ruta) if ruta else None

    def carpeta_entregables(self) -> Path | None:
        carpeta = QFileDialog.getExistingDirectory(
            self.v, "Carpeta donde dejar los entregables (se crea una subcarpeta)"
        )
        return Path(carpeta) if carpeta else None

    def destino_word(self, sugerido: Path) -> Path | None:
        ruta, _ = QFileDialog.getSaveFileName(
            self.v, "Justificación de cálculos", str(sugerido), "Word (*.docx)"
        )
        return Path(ruta) if ruta else None

    def plantilla_word(self) -> Path | None:
        ruta, _ = QFileDialog.getOpenFileName(
            self.v, "Plantilla de Word", "", "Word (*.docx *.dotx)"
        )
        return Path(ruta) if ruta else None

    def proyecto_existente(self) -> Path | None:
        carpeta = QFileDialog.getExistingDirectory(self.v, "Abrir proyecto (carpeta .traza)")
        return Path(carpeta) if carpeta else None

    def documento(self) -> tuple[Path, str] | None:
        ruta, _ = QFileDialog.getOpenFileName(self.v, "Incorporar documento")
        if not ruta:
            return None
        clase, ok = QInputDialog.getItem(
            self.v, "Clasificación", "Tipo de documento:", CLASIFICACIONES, 0, False
        )
        return (Path(ruta), clase) if ok else None

    def nuevo_elemento(self, tipos, elementos) -> tuple[str, str, str | None] | None:
        d = DialogoElemento(self.v, tipos, elementos)
        return d.resultado if d.exec() == QDialog.Accepted else None

    def valor(self, tipo, documentos, clave_inicial=None) -> DatosValor | None:
        d = DialogoValor(self.v, tipo, documentos, clave_inicial)
        return d.resultado if d.exec() == QDialog.Accepted else None

    def texto(self, titulo: str, etiqueta: str) -> str | None:
        texto, ok = QInputDialog.getMultiLineText(self.v, titulo, etiqueta)
        return texto if ok and texto.strip() else None

    def elegir(self, titulo: str, etiqueta: str, opciones: list[str]) -> int | None:
        if not opciones:
            return None
        texto, ok = QInputDialog.getItem(self.v, titulo, etiqueta, opciones, 0, False)
        return opciones.index(texto) if ok else None

    # --- Planos ---------------------------------------------------------------------

    def capas_plano(self, info, actual=None):
        from traza.ui.dialogos_planos import DialogoCapasPlano

        d = DialogoCapasPlano(self.v, info, actual)
        return d.resultado if d.exec() == QDialog.Accepted else None

    # --- Obra ----------------------------------------------------------------------------

    def factura(self, paquetes: list[str], actual: dict | None = None):
        from traza.ui.dialogos_obra import DialogoFactura

        d = DialogoFactura(self.v, paquetes, actual)
        return d.resultado if d.exec() == QDialog.Accepted else None

    def certificacion(self, explicacion: str, numero: int):
        from traza.ui.dialogos_obra import DialogoCertificacion

        d = DialogoCertificacion(self.v, explicacion, numero)
        return d.resultado if d.exec() == QDialog.Accepted else None

    def prevision(self, actual: dict | None):
        from traza.ui.dialogos_obra import DialogoPrevision

        d = DialogoPrevision(self.v, actual)
        return d.resultado if d.exec() == QDialog.Accepted else None

    def facturas_erp(self, explicacion: str, propuestas: list, paquetes: list[str]):
        from traza.ui.dialogos_obra import DialogoFacturasErp

        d = DialogoFacturasErp(self.v, explicacion, propuestas, paquetes)
        return d.resultado if d.exec() == QDialog.Accepted else None

    def futurible(self, modificados: list[dict], actual: dict | None = None):
        from traza.ui.dialogos_obra import DialogoFuturible

        d = DialogoFuturible(self.v, modificados, actual)
        return d.resultado if d.exec() == QDialog.Accepted else None

    def nuevo_nivel(self):
        from traza.ui.dialogos_planos import DialogoNivel

        d = DialogoNivel(self.v)
        return d.resultado if d.exec() == QDialog.Accepted else None

    def confirmar_contorno(self, propuesta: dict, niveles: list[dict]):
        from traza.ui.dialogos_planos import DialogoContorno

        d = DialogoContorno(self.v, propuesta, niveles)
        return d.resultado if d.exec() == QDialog.Accepted else None

    def altura_espacio(self, espacio: dict):
        from traza.ui.dialogos_planos import DialogoAltura

        d = DialogoAltura(self.v, espacio)
        return d.resultado if d.exec() == QDialog.Accepted else None

    # --- Cargas y ventilación ----------------------------------------------------------

    def clima_obra(self, guias: list[dict], cargar, actual: dict | None):
        from traza.ui.dialogos_cargas import DialogoClima

        d = DialogoClima(self.v, guias, cargar, actual)
        return d.resultado if d.exec() == QDialog.Accepted else None

    def cargas_espacio(self, espacio: str, uso: str, ajustes, fachadas, propuestas_de):
        from traza.ui.dialogos_cargas import DialogoEspacioCargas

        d = DialogoEspacioCargas(self.v, espacio, uso, ajustes, fachadas, propuestas_de)
        return d.resultado if d.exec() == QDialog.Accepted else None

    def red_aire(self, planos: list[dict], niveles: list[dict], info, actual: dict | None):
        from traza.ui.dialogos_redes import DialogoRed

        d = DialogoRed(self.v, planos, niveles, info, actual)
        return d.resultado if d.exec() == QDialog.Accepted else None

    def sistema_hidraulico(self, espacios: list[dict], actual: dict | None):
        from traza.ui.dialogos_hidronica import DialogoSistema

        d = DialogoSistema(self.v, espacios, actual)
        return d.resultado if d.exec() == QDialog.Accepted else None

    def subcuadro(self, propuestas, actual: dict | None):
        from traza.ui.dialogos_subcuadros import DialogoSubcuadro

        d = DialogoSubcuadro(self.v, propuestas, actual)
        return d.resultado if d.exec() == QDialog.Accepted else None

    def destino_dxf(self, sugerido: Path) -> Path | None:
        ruta, _ = QFileDialog.getSaveFileName(
            self.v, "Exportar a AutoCAD (DXF y LISP)", str(sugerido), "DXF (*.dxf)"
        )
        return Path(ruta) if ruta else None

    def destino_pdf(self, sugerido: Path) -> Path | None:
        ruta, _ = QFileDialog.getSaveFileName(
            self.v, "Exportar informe PDF", str(sugerido), "PDF (*.pdf)"
        )
        return Path(ruta) if ruta else None

    def confirmar(self, titulo: str, texto: str) -> bool:
        return QMessageBox.question(self.v, titulo, texto) == QMessageBox.Yes

    def aviso(self, titulo: str, texto: str) -> None:
        QMessageBox.warning(self.v, titulo, texto)

    def informacion(self, titulo: str, texto: str) -> None:
        QMessageBox.information(self.v, titulo, texto)
