"""Diálogos de Obra: factura, previsión, certificación y futurible (docs/modules/obra.md)."""

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
            venta = _importe(self.venta.text(), "Venta")
            coste = _importe(self.coste.text(), "Coste")
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        if venta < 0 or coste < 0:
            self.error.setText("Los totales previstos no pueden ser negativos.")
            return
        self.resultado = {
            "venta_total": venta,
            "coste_total": coste,
            "nota": self.nota.text().strip(),
        }
        self.accept()


class DialogoCertificacion(QDialog):
    """Antes de importar: lo que TRAZA ha entendido del Excel (qué columna es qué, total a
    origen y avisos) y el número y la fecha de la certificación."""

    def __init__(self, padre: QWidget, explicacion: str, numero: int) -> None:
        from PySide6.QtWidgets import QSpinBox

        super().__init__(padre)
        self.setWindowTitle("Importar certificación")
        self.resultado: dict | None = None
        from PySide6.QtWidgets import QPlainTextEdit

        # Con muchos avisos, una etiqueta se salía de la pantalla: texto con barra.
        texto = QPlainTextEdit(explicacion)
        texto.setReadOnly(True)
        texto.setMinimumSize(560, 220)
        self.numero = QSpinBox()
        self.numero.setRange(1, 999)
        self.numero.setValue(numero)
        self.fecha = QDateEdit()
        self.fecha.setCalendarPopup(True)
        self.fecha.setDisplayFormat("dd-MM-yyyy")
        hoy = date.today()
        self.fecha.setDate(QDate(hoy.year, hoy.month, hoy.day))
        f = QFormLayout(self)
        f.addRow(texto)
        f.addRow("Nº de certificación", self.numero)
        f.addRow("Fecha", self.fecha)
        _botones(f, self, self._aceptar)

    def _aceptar(self) -> None:
        self.resultado = {
            "numero": self.numero.value(),
            "fecha": self.fecha.date().toString("yyyy-MM-dd"),
        }
        self.accept()


class DialogoFuturible(QDialog):
    """Una oferta o un modificado pendiente: título, de dónde sale la venta (la escribe el
    usuario o es la de un modificado de TRAZA) y el coste que estima el usuario."""

    def __init__(self, padre: QWidget, modificados: list[dict], actual: dict | None) -> None:
        super().__init__(padre)
        self.setWindowTitle("Corregir futurible" if actual else "Futurible")
        self.resultado: dict | None = None
        self._modificados = modificados
        self.titulo = QLineEdit()
        self.titulo.setPlaceholderText("P. ej. «Ampliación oficinas planta 1»")
        self.origen = QComboBox()
        self.origen.addItem("La escribo yo")
        self.origen.addItems([f"Modificado nº {m['numero']} · {m['titulo']}" for m in modificados])
        self.venta = QLineEdit()
        self.venta.setPlaceholderText("Venta de la oferta (€); en negativo si quita alcance")
        self.coste = QLineEdit()
        self.coste.setPlaceholderText("Tu estimación (€)")
        self.nota = QLineEdit()
        self.nota.setPlaceholderText("Opcional: estado, a quién se envió…")
        self.error = QLabel()
        self.error.setStyleSheet("color: #c0392b")
        actual = actual or {}
        self._id = actual.get("id")
        self.titulo.setText(actual.get("titulo") or "")
        if actual.get("modificado_id"):
            i = next(
                (n for n, m in enumerate(modificados) if m["id"] == actual["modificado_id"]), None
            )
            if i is not None:
                self.origen.setCurrentIndex(i + 1)
        if actual.get("venta") is not None:
            self.venta.setText(escribir_numero(actual["venta"]))
        if actual.get("coste") is not None:
            self.coste.setText(escribir_numero(actual["coste"]))
        self.nota.setText(actual.get("nota") or "")
        self.origen.currentIndexChanged.connect(self._origen)
        f = QFormLayout(self)
        f.addRow("Futurible", self.titulo)
        f.addRow("Venta", self.origen)
        f.addRow("Venta (€)", self.venta)
        f.addRow("Coste estimado (€)", self.coste)
        f.addRow("Nota", self.nota)
        f.addRow(self.error)
        _botones(f, self, self._aceptar)
        self._origen()

    def _origen(self) -> None:
        # La venta de un modificado la calcula TRAZA (al día): no se escribe.
        self.venta.setEnabled(self.origen.currentIndex() == 0)

    def _aceptar(self) -> None:
        if not self.titulo.text().strip():
            self.error.setText("Ponle un título al futurible.")
            return
        i = self.origen.currentIndex()
        try:
            venta = _importe(self.venta.text(), "Venta") if i == 0 else None
            coste = _importe(self.coste.text(), "Coste estimado")
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        self.resultado = {
            "titulo": self.titulo.text().strip(),
            "venta": venta,
            "modificado_id": None if i == 0 else self._modificados[i - 1]["id"],
            "coste": coste,
            "nota": self.nota.text().strip(),
        }
        if self._id:
            self.resultado["id"] = self._id
        self.accept()


SIN_PAQUETE = "— elige —"


class DialogoFacturasErp(QDialog):
    """Lo leído del listado del ERP antes de importar: qué columna es qué, y por factura si
    se importa y a qué paquete (TRAZA propone; el usuario decide). Las ya apuntadas se
    enseñan sin marcar, con el motivo."""

    def __init__(self, padre: QWidget, explicacion: str, propuestas: list, paquetes: list[str]):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QPlainTextEdit, QTableWidget, QTableWidgetItem

        from traza.ui.ventana import _dinero

        super().__init__(padre)
        self.setWindowTitle("Importar facturas del ERP")
        self.resultado: list[dict] | None = None
        self._propuestas = propuestas
        texto = QPlainTextEdit(explicacion)
        texto.setReadOnly(True)
        texto.setMaximumHeight(110)
        self.tabla = QTableWidget(len(propuestas), 7)
        self.tabla.setHorizontalHeaderLabels(
            ["", "Proveedor", "Nº", "Fecha", "Importe", "Paquete", "Nota"]
        )
        self.tabla.setMinimumSize(820, 320)
        self._combos: list[QComboBox] = []
        for r, p in enumerate(propuestas):
            x = p.leida
            marca = QTableWidgetItem()
            nueva = p.estado == "nueva"
            marca.setFlags(
                (Qt.ItemIsUserCheckable | Qt.ItemIsEnabled) if nueva else Qt.ItemIsUserCheckable
            )
            marca.setCheckState(Qt.Checked if nueva else Qt.Unchecked)
            self.tabla.setItem(r, 0, marca)
            fecha = "-".join(reversed(x.fecha.split("-")))
            for c, v in enumerate(
                [x.proveedor, x.numero, fecha, f"{_dinero(x.importe)} €"], start=1
            ):
                item = QTableWidgetItem(v)
                item.setFlags(Qt.ItemIsEnabled)
                self.tabla.setItem(r, c, item)
            combo = QComboBox()
            combo.addItems([SIN_PAQUETE, *paquetes])
            if p.paquete:
                if p.paquete not in paquetes:
                    combo.addItem(p.paquete)
                combo.setCurrentText(p.paquete)
            combo.setEnabled(nueva)
            self._combos.append(combo)
            self.tabla.setCellWidget(r, 5, combo)
            nota = QTableWidgetItem(p.motivo)
            nota.setFlags(Qt.ItemIsEnabled)
            self.tabla.setItem(r, 6, nota)
        self.tabla.resizeColumnsToContents()
        self.error = QLabel()
        self.error.setStyleSheet("color: #c0392b")
        self.error.setWordWrap(True)
        f = QFormLayout(self)
        f.addRow(texto)
        f.addRow(self.tabla)
        f.addRow(self.error)
        _botones(f, self, self._aceptar)

    def marcada(self, fila: int) -> bool:
        from PySide6.QtCore import Qt

        return self.tabla.item(fila, 0).checkState() == Qt.Checked

    def _aceptar(self) -> None:
        elegidas, sin = [], 0
        for r, p in enumerate(self._propuestas):
            if p.estado != "nueva" or not self.marcada(r):
                continue
            paquete = self._combos[r].currentText()
            if paquete == SIN_PAQUETE:
                sin += 1
                continue
            x = p.leida
            elegidas.append(
                {
                    "paquete": paquete,
                    "proveedor": x.proveedor,
                    "numero": x.numero,
                    "fecha": x.fecha,
                    "importe": x.importe,
                }
            )
        if sin:
            self.error.setText(
                f"Elige el paquete de {sin} factura(s) marcada(s), o desmárcalas para no "
                "importarlas."
            )
            return
        if not elegidas:
            self.error.setText("No hay ninguna factura marcada para importar.")
            return
        self.resultado = elegidas
        self.accept()
