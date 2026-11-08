"""Diálogo de una red de aire: de qué plano, capa y bloques se lee y con qué criterios se
dimensiona (docs/modules/redes_aire.md)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QWidget,
)

from traza.app.ordenes import CRITERIOS_CAUDAL, FORMAS_CONDUCTO, TIPOS_RED
from traza.core.numeros import escribir_numero
from traza.ui.dialogos_planos import _numero_opcional

SIN_BLOQUE = "— sin bloque (el extremo libre) —"
TODOS_LOS_NIVELES = "— todos —"


class DialogoRed(QDialog):
    """`info(plano_id)` → (capas, bloques) del DXF de ese plano."""

    def __init__(
        self, padre: QWidget, planos: list[dict], niveles: list[dict], info, actual: dict | None
    ) -> None:
        super().__init__(padre)
        self.setWindowTitle("Red de aire")
        self.resultado: dict | None = None
        self._info = info
        self._actual = actual
        self.nombre = QLineEdit(actual["nombre"] if actual else "")
        self.nombre.setPlaceholderText("Impulsión UTA-1, Extracción aseos…")
        self.tipo = QComboBox()
        for k, v in TIPOS_RED.items():
            self.tipo.addItem(v, k)
        self.plano = QComboBox()
        for p in planos:
            self.plano.addItem(p["documento_nombre"], p["id"])
        self.nivel = QComboBox()
        self.nivel.addItem(TODOS_LOS_NIVELES, None)
        for n in niveles:
            self.nivel.addItem(f"{n['codigo']} {n['nombre'] or ''}".strip(), n["id"])
        self.capa = QComboBox()
        self.terminales = QListWidget()
        self.equipo = QComboBox()
        self.climatizacion = QCheckBox("Climatización (si no, ventilación simple)")
        self.climatizacion.setChecked(True)
        self.friccion = QLineEdit("0,8")
        self.alto = QLineEdit("400")
        self.forma = QComboBox()
        self.forma.addItems(FORMAS_CONDUCTO)
        self.salto = QLineEdit("10")
        self.criterio = QComboBox()
        for k, v in CRITERIOS_CAUDAL.items():
            self.criterio.addItem(v, k)
        self.criterio.setToolTip(
            "Ventilación ambiental (manual de S&P, cap. 3). Nunca baja del aire exterior "
            "del espacio (RITE o RD 486/1997)."
        )
        self.renovaciones = QLineEdit()
        self.renovaciones.setPlaceholderText("p. ej. 6")
        self.renovaciones.setToolTip(
            "Tabla 3.5 de S&P: fábricas y talleres de mecanizado 5–10, cocinas industriales "
            "15–20, fundiciones 20–30, naves con hornos y baños 30–60, pintura 40–60."
        )
        self.error = QLabel()
        self.error.setStyleSheet("color: #c0392b")
        self.error.setWordWrap(True)
        f = QFormLayout(self)
        f.addRow("Nombre", self.nombre)
        f.addRow("Tipo", self.tipo)
        f.addRow("Plano", self.plano)
        f.addRow("Nivel (sus espacios dan los caudales)", self.nivel)
        f.addRow("Capa de los ejes", self.capa)
        f.addRow("Bloques de difusores / rejillas", self.terminales)
        f.addRow("Bloque del equipo", self.equipo)
        f.addRow(self.climatizacion)
        f.addRow("Pérdida de carga objetivo (Pa/m)", self.friccion)
        f.addRow("Alto máximo del conducto (mm; vacío = hasta 3 m)", self.alto)
        f.addRow("Forma", self.forma)
        f.addRow("Salto térmico de impulsión (K)", self.salto)
        f.addRow("Caudal de cada espacio", self.criterio)
        f.addRow("Renovaciones por hora", self.renovaciones)
        f.addRow(self.error)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        f.addRow(botones)
        self.plano.currentIndexChanged.connect(lambda _i: self._cargar_plano())
        self.tipo.currentIndexChanged.connect(lambda _i: self._ajustar())
        self.climatizacion.toggled.connect(lambda _c: self._ajustar())
        self.criterio.currentIndexChanged.connect(lambda _i: self._ajustar())
        if actual:
            self.tipo.setCurrentIndex(max(self.tipo.findData(actual["tipo"]), 0))
            self.plano.setCurrentIndex(max(self.plano.findData(actual["plano_id"]), 0))
            self.nivel.setCurrentIndex(max(self.nivel.findData(actual["nivel_id"]), 0))
            self.climatizacion.setChecked(bool(actual["climatizacion"]))
            self.friccion.setText(escribir_numero(actual["friccion_objetivo"]))
            alto = actual["alto_maximo"]
            self.alto.setText("" if alto is None else escribir_numero(round(alto * 1000)))
            self.forma.setCurrentText(actual["forma"])
            self.salto.setText(escribir_numero(actual["salto_impulsion"]))
            criterio = actual.get("criterio_caudal") or "cargas"
            self.criterio.setCurrentIndex(max(self.criterio.findData(criterio), 0))
            if actual.get("renovaciones") is not None:
                self.renovaciones.setText(escribir_numero(actual["renovaciones"]))
        self._cargar_plano()
        self._ajustar()

    def _ajustar(self) -> None:
        """Las renovaciones son de ventilación: no en el retorno ni en la impulsión de
        climatización (la orden lo rechaza; aquí no se ofrece)."""
        tipo = self.tipo.currentData()
        admite = tipo == "extraccion" or (
            tipo == "impulsion" and not self.climatizacion.isChecked()
        )
        if not admite:
            self.criterio.setCurrentIndex(self.criterio.findData("cargas"))
        self.criterio.setEnabled(admite)
        self.renovaciones.setEnabled(admite and self.criterio.currentData() == "renovaciones")

    def _cargar_plano(self) -> None:
        self.capa.clear()
        self.terminales.clear()
        self.equipo.clear()
        self.equipo.addItem(SIN_BLOQUE, None)
        if self.plano.currentData() is None:
            return
        try:
            capas, bloques = self._info(self.plano.currentData())
            self.error.clear()
        except Exception as exc:  # noqa: BLE001 — el mensaje es para el usuario
            self.error.setText(str(exc))
            return
        self.capa.addItems(capas)
        elegidos = set(self._actual["bloques_terminales"]) if self._actual else set()
        for b in bloques:
            item = QListWidgetItem(b)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if b in elegidos else Qt.Unchecked)
            self.terminales.addItem(item)
            self.equipo.addItem(b, b)
        if self._actual:
            self.capa.setCurrentText(self._actual["capa_ejes"])
            i = self.equipo.findData(self._actual["bloque_equipo"])
            self.equipo.setCurrentIndex(max(i, 0))

    def _aceptar(self) -> None:
        if not self.nombre.text().strip():
            self.error.setText("La red necesita un nombre.")
            return
        bloques = [
            self.terminales.item(i).text()
            for i in range(self.terminales.count())
            if self.terminales.item(i).checkState() == Qt.Checked
        ]
        if not self.capa.currentText() or not bloques:
            self.error.setText("Elige la capa de los ejes y al menos un bloque de terminal.")
            return
        try:
            friccion = _numero_opcional(self.friccion.text(), "Pérdida de carga")
            alto = _numero_opcional(self.alto.text(), "Alto máximo")
            salto = _numero_opcional(self.salto.text(), "Salto térmico")
            renovaciones = _numero_opcional(self.renovaciones.text(), "Renovaciones por hora")
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        if friccion is None or salto is None:
            self.error.setText("Escribe la pérdida de carga objetivo y el salto térmico.")
            return
        self.resultado = {
            "titulo": self.nombre.text().strip(),
            "tipo": self.tipo.currentData(),
            "plano_id": self.plano.currentData(),
            "nivel_id": self.nivel.currentData(),
            "capa_ejes": self.capa.currentText(),
            "bloques_terminales": bloques,
            "bloque_equipo": self.equipo.currentData(),
            "climatizacion": self.climatizacion.isChecked(),
            "friccion_objetivo": friccion,
            "alto_maximo": None if alto is None else alto / 1000,
            "forma": self.forma.currentText(),
            "salto_impulsion": salto,
            "criterio_caudal": self.criterio.currentData(),
            "renovaciones": renovaciones if self.criterio.currentData() == "renovaciones" else None,
        }
        if self._actual:
            self.resultado["id"] = self._actual["id"]
        self.accept()
