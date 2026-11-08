"""Diálogo de un sistema hidráulico: tipo, criterios y circuitos (docs/modules/hidronica.md)."""

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

from traza.app.ordenes import TIPOS_SISTEMA
from traza.core.numeros import escribir_numero, leer_numero
from traza.rules.hidraulica import MATERIALES

COLUMNAS = [
    "Circuito",
    "Espacios (códigos)",
    "Unidades",
    "Longitud ida (m)",
    "Pérdida unidad (kPa)",
    "Exterior",
]


def _num(texto: str, nombre: str) -> float:
    try:
        return float(leer_numero(texto.strip()))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"«{nombre}»: «{texto}» no es un número.") from exc


class DialogoSistema(QDialog):
    """`espacios`: [{id, codigo, nombre}] del proyecto."""

    def __init__(self, padre: QWidget | None, espacios: list[dict], actual: dict | None) -> None:
        super().__init__(padre)
        self.setWindowTitle("Sistema hidráulico")
        self.resultado: dict | None = None
        self._actual = actual
        self._por_codigo = {e["codigo"].casefold(): e["id"] for e in espacios}
        self._codigo = {e["id"]: e["codigo"] for e in espacios}
        self.nombre = QLineEdit(actual["nombre"] if actual else "")
        self.nombre.setPlaceholderText("Climatización oficinas, Agua fría nave…")
        self.tipo = QComboBox()
        for k, v in TIPOS_SISTEMA.items():
            self.tipo.addItem(v, k)
        self.material = QComboBox()
        for k, v in MATERIALES.items():
            self.material.addItem(v, k)
        v = actual or {}
        self.frio = QLineEdit(self._par_texto(v, "frio", 7, 12))
        self.calor = QLineEdit(self._par_texto(v, "calor", 45, 40))
        self.altura = QLineEdit(escribir_numero(v.get("altura_m", 0)))
        self.primario = QLineEdit(escribir_numero(v.get("longitud_primario_m", 10)))
        self.minimo = QLineEdit(escribir_numero(v.get("volumen_minimo_l_kw", 3.5)))
        self.minimo.setToolTip(
            "Del fabricante del generador; 3,5 l/kW por defecto (Carrier, aire acondicionado)."
        )
        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.horizontalHeader().setStretchLastSection(False)
        mas, menos = QPushButton("Añadir circuito"), QPushButton("Quitar circuito")
        mas.clicked.connect(lambda: self.anadir())
        menos.clicked.connect(self._quitar)
        self.error = QLabel()
        self.error.setStyleSheet("color: #c0392b")
        self.error.setWordWrap(True)
        f = QFormLayout()
        f.addRow("Nombre", self.nombre)
        f.addRow("Tipo", self.tipo)
        f.addRow("Tubería", self.material)
        f.addRow("Frío, impulsión/retorno (°C)", self.frio)
        f.addRow("Calor, impulsión/retorno (°C)", self.calor)
        f.addRow("Altura sobre la sala (m)", self.altura)
        f.addRow("Longitud del primario (m)", self.primario)
        f.addRow("Volumen mínimo del generador (l/kW)", self.minimo)
        botones_tabla = QHBoxLayout()
        botones_tabla.addWidget(mas)
        botones_tabla.addWidget(menos)
        botones_tabla.addStretch(1)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        caja = QVBoxLayout(self)
        caja.addLayout(f)
        caja.addWidget(QLabel("Circuitos secundarios (uno por grupo de unidades):"))
        caja.addWidget(self.tabla)
        caja.addLayout(botones_tabla)
        caja.addWidget(self.error)
        caja.addWidget(botones)
        if actual:
            self.tipo.setCurrentIndex(max(self.tipo.findData(actual["tipo"]), 0))
            self.material.setCurrentIndex(max(self.material.findData(actual["material"]), 0))
            for c in actual["circuitos"]:
                self.anadir(c)
        else:
            self.anadir()

    @staticmethod
    def _par_texto(v: dict, clave: str, impulsion: float, retorno: float) -> str:
        i = escribir_numero(v.get(f"{clave}_impulsion", impulsion))
        r = escribir_numero(v.get(f"{clave}_retorno", retorno))
        return f"{i}/{r}"

    def anadir(self, c: dict | None = None) -> None:
        fila = self.tabla.rowCount()
        self.tabla.insertRow(fila)
        c = c or {}
        # Un espacio borrado después no se enseña por su id interno: se quita y se avisa
        # (revisión 08-11-2026: salía un UUID y Aceptar fallaba sin poder corregirlo).
        conocidos = [e for e in c.get("espacios", []) if e in self._codigo]
        if len(conocidos) < len(c.get("espacios", [])):
            self.error.setText(
                f"{c.get('nombre', '')}: se han quitado espacios que ya no existen en el proyecto."
            )
        codigos = ", ".join(self._codigo[e] for e in conocidos)
        valores = [
            c.get("nombre", f"C{fila + 1}"),
            codigos,
            str(c.get("unidades", 1)),
            escribir_numero(c.get("longitud_m", 20)),
            escribir_numero(c.get("perdida_terminal_kpa", 15)),
        ]
        for col, texto in enumerate(valores):
            self.tabla.setItem(fila, col, QTableWidgetItem(texto))
        exterior = QTableWidgetItem()
        exterior.setFlags(exterior.flags() | Qt.ItemIsUserCheckable)
        exterior.setCheckState(Qt.Checked if c.get("exterior") else Qt.Unchecked)
        self.tabla.setItem(fila, 5, exterior)

    def _quitar(self) -> None:
        if self.tabla.currentRow() >= 0:
            self.tabla.removeRow(self.tabla.currentRow())

    def _texto(self, fila: int, col: int) -> str:
        item = self.tabla.item(fila, col)
        return item.text().strip() if item else ""

    def _par(self, campo: QLineEdit, nombre: str) -> tuple[float, float]:
        partes = campo.text().split("/")
        if len(partes) != 2:
            raise ValueError(f"«{nombre}»: escribe impulsión/retorno, p. ej. 7/12.")
        return _num(partes[0], nombre), _num(partes[1], nombre)

    def _aceptar(self) -> None:
        try:
            if not self.nombre.text().strip():
                raise ValueError("El sistema necesita un nombre.")
            fi, fr = self._par(self.frio, "Frío")
            ci, cr = self._par(self.calor, "Calor")
            circuitos = []
            for fila in range(self.tabla.rowCount()):
                nombre = self._texto(fila, 0)
                espacios = []
                for codigo in filter(None, (x.strip() for x in self._texto(fila, 1).split(","))):
                    eid = self._por_codigo.get(codigo.casefold())
                    if eid is None:
                        raise ValueError(f"{nombre}: no hay ningún espacio «{codigo}».")
                    espacios.append(eid)
                unidades = _num(self._texto(fila, 2), f"{nombre}, unidades")
                if unidades != int(unidades):
                    raise ValueError(f"{nombre}: las unidades son un número entero.")
                circuitos.append(
                    {
                        "nombre": nombre,
                        "espacios": espacios,
                        "unidades": int(unidades),
                        "longitud_m": _num(self._texto(fila, 3), f"{nombre}, longitud"),
                        "perdida_terminal_kpa": _num(self._texto(fila, 4), f"{nombre}, pérdida"),
                        "exterior": self.tabla.item(fila, 5).checkState() == Qt.Checked,
                    }
                )
            self.resultado = {
                "titulo": self.nombre.text().strip(),
                "tipo": self.tipo.currentData(),
                "material": self.material.currentData(),
                "frio_impulsion": fi,
                "frio_retorno": fr,
                "calor_impulsion": ci,
                "calor_retorno": cr,
                "altura_m": _num(self.altura.text(), "Altura"),
                "longitud_primario_m": _num(self.primario.text(), "Longitud del primario"),
                "volumen_minimo_l_kw": _num(self.minimo.text(), "Volumen mínimo"),
                "circuitos": circuitos,
            }
        except ValueError as exc:
            self.resultado = None
            self.error.setText(str(exc))
            return
        if self._actual and self._actual.get("id"):  # al reabrir uno nuevo no hay id
            self.resultado["id"] = self._actual["id"]
        self.accept()
