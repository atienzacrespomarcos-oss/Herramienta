"""Diálogo de un subcuadro de clima: suministro, alimentación y salidas
(docs/modules/electricidad.md)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from traza.core.numeros import escribir_numero, leer_numero
from traza.rules.electricidad import COS_PHI_DEFECTO, METODOS, SUMINISTROS

COLUMNAS = [
    "Salida",
    "kW eléctricos",
    "Fases",
    "Longitud (m)",
    "cos φ",
    "Motor",
    "Variador",
    "Método",
]


def _num(texto: str, nombre: str) -> float:
    try:
        return float(leer_numero(texto.strip()))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"«{nombre}»: «{texto}» no es un número.") from exc


class DialogoSubcuadro(QDialog):
    """`propuestas()` → salidas de los equipos ya dimensionados."""

    def __init__(self, padre: QWidget | None, propuestas, actual: dict | None) -> None:
        super().__init__(padre)
        self.setWindowTitle("Subcuadro de clima")
        self.resultado: dict | None = None
        self._actual = actual
        self._propuestas = propuestas
        v = actual or {}
        self.nombre = QLineEdit(v.get("nombre", ""))
        self.nombre.setPlaceholderText("SC Clima, SC Enfriadora…")
        self.suministro = QComboBox()
        for k, t in SUMINISTROS.items():
            self.suministro.addItem(t, k)
        self.longitud = QLineEdit(escribir_numero(v.get("longitud_alimentacion_m", 20)))
        self.metodo = QComboBox()
        for k, t in METODOS.items():
            self.metodo.addItem(t, k)
        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        mas, menos = QPushButton("Añadir salida"), QPushButton("Quitar salida")
        proponer = QPushButton("Proponer desde los equipos")
        proponer.setToolTip(
            "Añade una salida por generador, bomba, unidades y ventilador ya dimensionados. "
            "La potencia eléctrica, la de la ficha del modelo elegido."
        )
        mas.clicked.connect(lambda: self.anadir())
        menos.clicked.connect(self._quitar)
        proponer.clicked.connect(self._proponer)
        self.error = QLabel()
        self.error.setStyleSheet("color: #c0392b")
        self.error.setWordWrap(True)
        f = QFormLayout()
        f.addRow("Nombre", self.nombre)
        f.addRow("Suministro", self.suministro)
        f.addRow("Alimentación desde el cuadro general (m)", self.longitud)
        f.addRow("Instalación de la alimentación", self.metodo)
        fila = QHBoxLayout()
        for b in (mas, menos, proponer):
            fila.addWidget(b)
        fila.addStretch(1)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        caja = QVBoxLayout(self)
        caja.addLayout(f)
        caja.addWidget(QLabel("Salidas (una por equipo o grupo de unidades):"))
        caja.addWidget(self.tabla)
        caja.addLayout(fila)
        caja.addWidget(self.error)
        caja.addWidget(botones)
        if actual:
            self.suministro.setCurrentIndex(max(self.suministro.findData(actual["suministro"]), 0))
            self.metodo.setCurrentIndex(max(self.metodo.findData(actual["metodo_alimentacion"]), 0))
            for s in actual["salidas"]:
                self.anadir(s)

    def anadir(self, s: dict | None = None) -> None:
        fila = self.tabla.rowCount()
        self.tabla.insertRow(fila)
        s = s or {}
        textos = [
            s.get("nombre", f"Salida {fila + 1}"),
            escribir_numero(s.get("potencia_kw", 0)) if s.get("potencia_kw") else "",
            str(s.get("fases", 3)),
            escribir_numero(s.get("longitud_m", 20)),
            escribir_numero(s.get("cos_phi", COS_PHI_DEFECTO)),
        ]
        for col, t in enumerate(textos):
            self.tabla.setItem(fila, col, QTableWidgetItem(t))
        for col, clave, defecto in ((5, "motor", True), (6, "variador", False)):
            item = QTableWidgetItem()
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if s.get(clave, defecto) else Qt.Unchecked)
            self.tabla.setItem(fila, col, item)
        combo = QComboBox()
        for k, texto in METODOS.items():
            combo.addItem(texto, k)
        combo.setCurrentIndex(max(combo.findData(s.get("metodo", "E")), 0))
        self.tabla.setCellWidget(fila, 7, combo)

    def _quitar(self) -> None:
        if self.tabla.currentRow() >= 0:
            self.tabla.removeRow(self.tabla.currentRow())

    def _proponer(self) -> None:
        existentes = {self._texto(f, 0).casefold() for f in range(self.tabla.rowCount())}
        nuevas = [s for s in self._propuestas() if s["nombre"].casefold() not in existentes]
        for s in nuevas:
            self.anadir(s)
        self.error.setText(
            f"{len(nuevas)} salidas propuestas: pon la potencia eléctrica de la ficha de cada "
            "equipo."
            if nuevas
            else "No hay equipos dimensionados nuevos que proponer."
        )

    def _texto(self, fila: int, col: int) -> str:
        item = self.tabla.item(fila, col)
        return item.text().strip() if item else ""

    def _aceptar(self) -> None:
        try:
            if not self.nombre.text().strip():
                raise ValueError("El subcuadro necesita un nombre.")
            salidas, nombres = [], set()
            for fila in range(self.tabla.rowCount()):
                nombre = self._texto(fila, 0)
                if not nombre or nombre.casefold() in nombres:
                    raise ValueError(f"Fila {fila + 1}: cada salida necesita un nombre propio.")
                nombres.add(nombre.casefold())
                if not self._texto(fila, 1):
                    raise ValueError(f"{nombre}: pon la potencia eléctrica (kW) de su ficha.")
                fases = self._texto(fila, 2)
                if fases not in ("1", "3"):
                    raise ValueError(f"{nombre}: fases 1 o 3.")
                salidas.append(
                    {
                        "nombre": nombre,
                        "potencia_kw": _num(self._texto(fila, 1), f"{nombre}, potencia"),
                        "fases": int(fases),
                        "longitud_m": _num(self._texto(fila, 3), f"{nombre}, longitud"),
                        "cos_phi": _num(self._texto(fila, 4), f"{nombre}, cos φ"),
                        "motor": self.tabla.item(fila, 5).checkState() == Qt.Checked,
                        "variador": self.tabla.item(fila, 6).checkState() == Qt.Checked,
                        "metodo": self.tabla.cellWidget(fila, 7).currentData(),
                    }
                )
            self.resultado = {
                "titulo": self.nombre.text().strip(),
                "suministro": self.suministro.currentData(),
                "longitud_alimentacion_m": _num(self.longitud.text(), "Alimentación"),
                "metodo_alimentacion": self.metodo.currentData(),
                "salidas": salidas,
            }
        except ValueError as exc:
            self.resultado = None
            self.error.setText(str(exc))
            return
        if self._actual and self._actual.get("id"):
            self.resultado["id"] = self._actual["id"]
        self.accept()
