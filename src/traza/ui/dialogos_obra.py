"""Diálogos de Obra: factura de un paquete y previsión del usuario (docs/modules/obra.md)."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

from traza.core.numeros import escribir_numero, leer_numero


def _botones(f: QFormLayout, dialogo: QDialog, aceptar) -> None:
    b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    b.accepted.connect(aceptar)
    b.rejected.connect(dialogo.reject)
    f.addRow(b)


def _importe(texto: str, nombre: str) -> float:
    try:
        return float(leer_numero(texto))
    except ValueError as exc:
        raise ValueError(f"{nombre}: {exc}") from None


class DialogoFactura(QDialog):
    """Proveedor, nº, fecha e importe sin IVA (negativo si es un abono)."""

    def __init__(self, padre: QWidget, paquetes: list[str], actual: dict | None) -> None:
        super().__init__(padre)
        self.setWindowTitle("Corregir factura" if actual and actual.get("id") else "Factura")
        self.resultado: dict | None = None
        self.paquete = QComboBox()
        self.paquete.addItems(paquetes)
        self.proveedor = QLineEdit()
        self.numero = QLineEdit()
        self.fecha = QDateEdit()
        self.fecha.setCalendarPopup(True)
        self.fecha.setDisplayFormat("dd-MM-yyyy")
        hoy = date.today()
        self.fecha.setDate(QDate(hoy.year, hoy.month, hoy.day))
        self.importe = QLineEdit()
        self.importe.setPlaceholderText("Sin IVA; un abono, en negativo")
        self.error = QLabel()
        self.error.setStyleSheet("color: #c0392b")
        actual = actual or {}
        if actual.get("paquete"):
            self.paquete.setCurrentText(actual["paquete"])
        self.proveedor.setText(actual.get("proveedor") or "")
        self.numero.setText(actual.get("numero") or "")
        if actual.get("fecha"):
            a, m, d = (int(x) for x in actual["fecha"].split("-"))
            self.fecha.setDate(QDate(a, m, d))
        if actual.get("importe") is not None:
            self.importe.setText(escribir_numero(actual["importe"]))
        self._id = actual.get("id")
        f = QFormLayout(self)
        f.addRow("Paquete", self.paquete)
        f.addRow("Proveedor", self.proveedor)
        f.addRow("Nº de factura", self.numero)
        f.addRow("Fecha", self.fecha)
        f.addRow("Importe (€)", self.importe)
        f.addRow(self.error)
        _botones(f, self, self._aceptar)

    def _aceptar(self) -> None:
        if not self.proveedor.text().strip() or not self.numero.text().strip():
            self.error.setText("Escribe el proveedor y el número de la factura.")
            return
        try:
            importe = _importe(self.importe.text(), "Importe")
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        self.resultado = {
            "paquete": self.paquete.currentText(),
            "proveedor": self.proveedor.text().strip(),
            "numero": self.numero.text().strip(),
            "fecha": self.fecha.date().toString("yyyy-MM-dd"),
            "importe": importe,
        }
        if self._id:
            self.resultado["id"] = self._id
        self.accept()


class DialogoPrevision(QDialog):
    """La previsión del usuario: dos totales a fin de obra (TRAZA no la estima)."""

    def __init__(self, padre: QWidget, actual: dict | None) -> None:
        super().__init__(padre)
        self.setWindowTitle("Tu previsión a fin de obra")
        self.resultado: dict | None = None
        self.venta = QLineEdit()
        self.coste = QLineEdit()
        self.nota = QLineEdit()
        self.nota.setPlaceholderText("Opcional: de dónde sale (p. ej. «tras la reunión del 15»)")
        if actual is not None:
            self.venta.setText(escribir_numero(actual["venta_total"]))
            self.coste.setText(escribir_numero(actual["coste_total"]))
            self.nota.setText(actual["nota"] or "")
        self.error = QLabel()
        self.error.setStyleSheet("color: #c0392b")
        f = QFormLayout(self)
        f.addRow("Venta total prevista (€)", self.venta)
        f.addRow("Coste total previsto (€)", self.coste)
        f.addRow("Nota", self.nota)
        f.addRow(self.error)
        _botones(f, self, self._aceptar)

    def _aceptar(self) -> None:
        try:
            cert = _importe(self.venta.text(), "Venta")
            coste = _importe(self.coste.text(), "Coste")
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        if cert < 0 or coste < 0:
            self.error.setText("Los totales previstos no pueden ser negativos.")
            return
        self.resultado = {
            "venta_total": cert,
            "coste_total": coste,
            "nota": self.nota.text().strip(),
        }
        self.accept()
