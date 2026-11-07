"""Diálogos del paso «Planos» (decisiones del usuario, 06-11-2026; docs/modules/geometria.md).

- Capas y unidad: el usuario dice qué capa es qué (planos ajenos) y confirma la unidad
  viendo cuánto mide el dibujo con ella.
- Nivel: nombre, cota y altura libre.
- Confirmar un contorno: nivel, nombre (un texto del plano o uno propio) y, si es un
  obstáculo, su altura y cota inferior (vacías = no constan).
- Altura de un espacio: la del nivel, propia, o cubierta inclinada.

Se llaman siempre a través de `ui/dialogos.Preguntas`.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from traza.app.ordenes import MODOS_ALTURA
from traza.core.numeros import escribir_numero, leer_numero

UNIDADES = ("mm", "cm", "dm", "m")
COLUMNAS_CAPAS = ["Capa", "Contornos", "Textos", "Entidades", "Espacios", "Obstáculos", "Nombres"]


@dataclass(frozen=True)
class CapaInfo:
    nombre: str
    contornos: int
    textos: int
    entidades: int
    visible: bool


@dataclass(frozen=True)
class InfoPlano:
    """Lo que el usuario necesita ver para decidir capas y unidad."""

    documento: str
    capas: tuple[CapaInfo, ...]
    unidad_propuesta: str | None
    medidas: dict  # unidad → (ancho, fondo) en m, o None si el dibujo está vacío
    avisos: tuple[str, ...] = ()


@dataclass(frozen=True)
class DatosCapas:
    unidad: str
    espacios: list[str]
    obstaculos: list[str]
    textos: list[str]


def _cifra(v: float) -> str:
    return escribir_numero(round(v, 2))


def _numero_opcional(texto: str, nombre: str) -> float | None:
    if not texto.strip():
        return None
    try:
        return float(leer_numero(texto))
    except ValueError as exc:
        raise ValueError(f"{nombre}: {exc}") from None


class DialogoCapasPlano(QDialog):
    def __init__(self, padre: QWidget, info: InfoPlano, actual: DatosCapas | None = None):
        super().__init__(padre)
        self.setWindowTitle(f"Cómo leer «{info.documento}»")
        self.resize(820, 560)
        self.info = info
        self.resultado: DatosCapas | None = None
        self.unidad = QComboBox()
        for u in UNIDADES:
            self.unidad.addItem(u, u)
        inicial = (actual.unidad if actual else None) or info.unidad_propuesta
        if inicial in UNIDADES:
            self.unidad.setCurrentIndex(UNIDADES.index(inicial))
        self.medida = QLabel()
        self.medida.setWordWrap(True)
        self.unidad.currentIndexChanged.connect(self._actualizar_medida)
        propuesta = (
            f"El DXF declara «{info.unidad_propuesta}» ($INSUNITS), pero eso es solo una "
            "propuesta: compruébala con la medida."
            if info.unidad_propuesta
            else "El DXF no declara una unidad métrica: elígela tú."
        )
        self.tabla = QTableWidget(len(info.capas), len(COLUMNAS_CAPAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS_CAPAS)
        self.tabla.setSelectionMode(QAbstractItemView.NoSelection)
        self.tabla.verticalHeader().setVisible(False)
        marcadas = {
            4: {c.casefold() for c in (actual.espacios if actual else [])},
            5: {c.casefold() for c in (actual.obstaculos if actual else [])},
            6: {c.casefold() for c in (actual.textos if actual else [])},
        }
        for i, c in enumerate(info.capas):
            nombre = QTableWidgetItem(c.nombre + ("" if c.visible else " (apagada)"))
            nombre.setData(Qt.UserRole, c.nombre)
            nombre.setFlags(Qt.ItemIsEnabled)
            self.tabla.setItem(i, 0, nombre)
            for j, n in ((1, c.contornos), (2, c.textos), (3, c.entidades)):
                item = QTableWidgetItem(str(n))
                item.setFlags(Qt.ItemIsEnabled)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tabla.setItem(i, j, item)
            for j in (4, 5, 6):
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.Checked if c.nombre.casefold() in marcadas[j] else Qt.Unchecked
                )
                self.tabla.setItem(i, j, item)
        self.tabla.resizeColumnsToContents()
        self.tabla.itemChanged.connect(self._exclusivo)
        self.error = QLabel()
        self.error.setStyleSheet("color: #c0392b")
        self.error.setWordWrap(True)
        avisos = QLabel("\n".join(f"⚠ {a}" for a in info.avisos))
        avisos.setWordWrap(True)
        f = QFormLayout()
        f.addRow("Unidad del dibujo", self.unidad)
        f.addRow("", QLabel(propuesta))
        f.addRow("Medida total", self.medida)
        caja = QVBoxLayout(self)
        caja.addLayout(f)
        caja.addWidget(
            QLabel(
                "Marca qué capas tienen los contornos de los espacios, los de los obstáculos "
                "(pilares…) y los textos con los nombres de los espacios."
            )
        )
        caja.addWidget(self.tabla)
        if info.avisos:
            caja.addWidget(avisos)
        caja.addWidget(self.error)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        caja.addWidget(botones)
        self._actualizar_medida()

    def _actualizar_medida(self) -> None:
        m = self.info.medidas.get(self.unidad.currentData())
        self.medida.setText(
            "El dibujo está vacío."
            if m is None
            else f"Con «{self.unidad.currentData()}», el dibujo mide {_cifra(m[0])} × "
            f"{_cifra(m[1])} m. Si no es lo que mide la nave, la unidad no es esa."
        )

    def _exclusivo(self, item: QTableWidgetItem) -> None:
        """Una capa no puede ser a la vez de espacios y de obstáculos."""
        if item.column() not in (4, 5) or item.checkState() != Qt.Checked:
            return
        otra = self.tabla.item(item.row(), 9 - item.column())
        if otra is not None and otra.checkState() == Qt.Checked:
            self.tabla.blockSignals(True)
            otra.setCheckState(Qt.Unchecked)
            self.tabla.blockSignals(False)

    def marcar(self, capa: str, columna: str, marcado: bool = True) -> None:
        """Para las pruebas: marca una capa en «espacios», «obstaculos» o «textos»."""
        j = {"espacios": 4, "obstaculos": 5, "textos": 6}[columna]
        for i in range(self.tabla.rowCount()):
            if self.tabla.item(i, 0).data(Qt.UserRole) == capa:
                self.tabla.item(i, j).setCheckState(Qt.Checked if marcado else Qt.Unchecked)
                return
        raise KeyError(capa)

    def _marcadas(self, j: int) -> list[str]:
        return [
            self.tabla.item(i, 0).data(Qt.UserRole)
            for i in range(self.tabla.rowCount())
            if self.tabla.item(i, j).checkState() == Qt.Checked
        ]

    def _aceptar(self) -> None:
        espacios, obstaculos = self._marcadas(4), self._marcadas(5)
        if not espacios and not obstaculos:
            self.error.setText("Marca al menos una capa de espacios o de obstáculos.")
            return
        self.resultado = DatosCapas(
            self.unidad.currentData(), espacios, obstaculos, self._marcadas(6)
        )
        self.accept()


class DialogoNivel(QDialog):
    def __init__(self, padre: QWidget) -> None:
        super().__init__(padre)
        self.setWindowTitle("Nuevo nivel")
        self.resultado: tuple[str, float, float] | None = None
        self.nombre = QLineEdit()
        self.nombre.setPlaceholderText("Planta baja, entreplanta, sótano…")
        self.cota = QLineEdit("0")
        self.altura = QLineEdit()
        self.altura.setPlaceholderText("Altura libre hasta el techo o la cubierta")
        self.error = QLabel()
        self.error.setStyleSheet("color: #c0392b")
        f = QFormLayout(self)
        f.addRow("Nombre", self.nombre)
        f.addRow("Cota del suelo (m)", self.cota)
        f.addRow("Altura libre (m)", self.altura)
        f.addRow(self.error)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        f.addRow(botones)

    def _aceptar(self) -> None:
        if not self.nombre.text().strip():
            self.error.setText("El nivel necesita un nombre.")
            return
        try:
            cota = float(leer_numero(self.cota.text()))
            altura = float(leer_numero(self.altura.text()))
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        self.resultado = (self.nombre.text().strip(), cota, altura)
        self.accept()


@dataclass(frozen=True)
class DatosContorno:
    nivel_id: str
    nombre: str | None
    texto_handle: str | None  # el nombre es ese texto del plano
    altura: float | None = None
    cota_inferior: float | None = None


OTRO_NOMBRE = "Escribir otro nombre…"


class DialogoContorno(QDialog):
    """`propuesta`: dict con rol, capa, superficie y textos [(handle, texto)]."""

    def __init__(self, padre: QWidget, propuesta: dict, niveles: list[dict]) -> None:
        super().__init__(padre)
        es_espacio = propuesta["rol"] == "espacio"
        self.setWindowTitle("Confirmar espacio" if es_espacio else "Confirmar obstáculo")
        self.resultado: DatosContorno | None = None
        self.es_espacio = es_espacio
        self.nivel = QComboBox()
        for n in niveles:
            self.nivel.addItem(f"{n['codigo']} {n['nombre'] or ''}".strip(), n["id"])
        self.nombre = QComboBox()
        for handle, texto in propuesta["textos"]:
            self.nombre.addItem(f"«{texto}» (texto del plano)", handle)
        self.nombre.addItem(OTRO_NOMBRE, None)
        self.propio = QLineEdit()
        self.propio.setPlaceholderText("Nombre del espacio" if es_espacio else "Pilar, cercha…")
        self.nombre.currentIndexChanged.connect(self._actualizar)
        self.altura = QLineEdit()
        self.altura.setPlaceholderText("Vacío = toda la altura del nivel")
        self.cota = QLineEdit()
        self.cota.setPlaceholderText("Vacío = no consta (desde el suelo)")
        self.error = QLabel()
        self.error.setStyleSheet("color: #c0392b")
        self.error.setWordWrap(True)
        f = QFormLayout(self)
        f.addRow(
            "Contorno",
            QLabel(f"capa «{propuesta['capa']}», {_cifra(propuesta['superficie'])} m²"),
        )
        f.addRow("Nivel", self.nivel)
        f.addRow("Nombre", self.nombre)
        f.addRow("", self.propio)
        if not es_espacio:
            f.addRow("Altura (m)", self.altura)
            f.addRow("Cota inferior (m)", self.cota)
        f.addRow(self.error)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        f.addRow(botones)
        self._actualizar()

    def _actualizar(self) -> None:
        self.propio.setEnabled(self.nombre.currentData() is None)

    def _aceptar(self) -> None:
        if self.nivel.currentIndex() < 0:
            self.error.setText("Crea antes un nivel (planta baja…).")
            return
        handle = self.nombre.currentData()
        propio = (self.propio.text().strip() or None) if handle is None else None
        if self.es_espacio and handle is None and not propio:
            self.error.setText("El espacio necesita un nombre: el del plano o uno tuyo.")
            return
        try:
            altura = None if self.es_espacio else _numero_opcional(self.altura.text(), "Altura")
            cota = None if self.es_espacio else _numero_opcional(self.cota.text(), "Cota")
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        self.resultado = DatosContorno(self.nivel.currentData(), propio, handle, altura, cota)
        self.accept()


class DialogoAltura(QDialog):
    def __init__(self, padre: QWidget, espacio: dict) -> None:
        super().__init__(padre)
        self.setWindowTitle(f"Altura de {espacio['codigo']} {espacio['nombre'] or ''}".strip())
        self.resultado: tuple[str, float | None, float | None, float | None] | None = None
        self.grupo = QButtonGroup(self)
        self.opciones = {}
        caja = QVBoxLayout(self)
        for clave, texto in MODOS_ALTURA.items():
            b = QRadioButton(texto)
            self.grupo.addButton(b)
            self.opciones[clave] = b
            caja.addWidget(b)
        self.altura = QLineEdit()
        self.minima = QLineEdit()
        self.maxima = QLineEdit()
        f = QFormLayout()
        f.addRow("Altura propia (m)", self.altura)
        f.addRow("Mínima (m)", self.minima)
        f.addRow("Máxima (m)", self.maxima)
        caja.addLayout(f)
        modo = espacio.get("altura_origen")
        modo = {"propia": "propia", "inclinada": "inclinada"}.get(modo, "nivel")
        self.opciones[modo].setChecked(True)
        if modo == "propia" and espacio.get("altura") is not None:
            self.altura.setText(escribir_numero(espacio["altura"]))
        for campo, clave in ((self.minima, "altura_minima"), (self.maxima, "altura_maxima")):
            if espacio.get(clave) is not None:
                campo.setText(escribir_numero(espacio[clave]))
        self.error = QLabel()
        self.error.setStyleSheet("color: #c0392b")
        self.error.setWordWrap(True)
        caja.addWidget(self.error)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        caja.addWidget(botones)

    def _aceptar(self) -> None:
        modo = next(k for k, b in self.opciones.items() if b.isChecked())
        try:
            altura = _numero_opcional(self.altura.text(), "Altura") if modo == "propia" else None
            mi = _numero_opcional(self.minima.text(), "Mínima") if modo == "inclinada" else None
            ma = _numero_opcional(self.maxima.text(), "Máxima") if modo == "inclinada" else None
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        if modo == "propia" and altura is None:
            self.error.setText("Escribe la altura propia.")
            return
        if modo == "inclinada" and (mi is None or ma is None):
            self.error.setText("Escribe la altura mínima y la máxima.")
            return
        self.resultado = (modo, altura, mi, ma)
        self.accept()
