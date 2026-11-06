"""Diálogos y preguntas al usuario.

Toda pregunta pasa por la clase `Preguntas`. La ventana no abre diálogos por su cuenta:
así las pruebas sustituyen `Preguntas` por respuestas preparadas y recorren la interfaz
entera sin intervención, y lo que se prueba es el mismo código que usa el ingeniero.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
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

from traza.app.ordenes import CLASES_MEDICION, ENCARGOS
from traza.core.numeros import leer_numero
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

    def destino_excel(self, sugerido: Path) -> Path | None:
        ruta, _ = QFileDialog.getSaveFileName(
            self.v, "Exportar Excel con todo", str(sugerido), "Excel (*.xlsx)"
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

    def confirmar(self, titulo: str, texto: str) -> bool:
        return QMessageBox.question(self.v, titulo, texto) == QMessageBox.Yes

    def aviso(self, titulo: str, texto: str) -> None:
        QMessageBox.warning(self.v, titulo, texto)

    def informacion(self, titulo: str, texto: str) -> None:
        QMessageBox.information(self.v, titulo, texto)
