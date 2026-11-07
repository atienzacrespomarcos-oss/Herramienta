"""Diálogos del paso «Cargas y ventilación» (docs/modules/cargas.md).

- Clima y obra: la guía del IDAE (un PDF de Documentación), su estación, la provincia y la
  altitud de la obra, y las hipótesis de conjunto.
- Espacio: uso y lo que el usuario cambia de su propuesta. En blanco = lo propuesto (se ve
  como texto de ayuda con su fuente), sin fricción.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from traza.app.ordenes import AJUSTE_SIN_CALEFACCION, AJUSTES_CARGAS, SECTORES_FACHADA
from traza.core.numeros import escribir_numero
from traza.io.informe_cargas import MESES
from traza.rules import cerramientos
from traza.rules.usos import USOS
from traza.ui.dialogos_planos import _numero_opcional

ESTADOS_FACHADA = ("Según el plano", "Es fachada", "No es fachada")


def _cifra(v) -> str:
    # Sin redondear a 2 decimales: al aceptar sin tocar nada, 0,125 se guardaba como 0,12
    # (revisión 07-11-2026). 6 decimales quitan solo el ruido de coma flotante.
    return "" if v is None else escribir_numero(round(float(v), 6))


class DialogoClima(QDialog):
    """`cargar(doc_id)` devuelve las estaciones de esa guía (o lanza un error con mensaje)."""

    def __init__(self, padre: QWidget, guias: list[dict], cargar, actual: dict | None) -> None:
        super().__init__(padre)
        self.setWindowTitle("Clima y obra")
        self.resultado: dict | None = None
        self._cargar = cargar
        self._estaciones: list = []
        self.guia = QComboBox()
        for d in guias:
            self.guia.addItem(d["nombre_original"], d["id"])
        self.estacion = QComboBox()
        self.provincia = QComboBox()
        self.provincia.addItems(sorted(cerramientos.ZONAS))
        self.altitud = QLineEdit()
        self.tipo = QComboBox()
        for clave, texto in cerramientos.TIPOS.items():
            self.tipo.addItem(texto, clave)
        self.norte = QLineEdit("0")
        self.norte.setToolTip(
            "Hacia dónde apunta el norte en el dibujo: grados desde «arriba», en sentido "
            "horario (0 si el norte está arriba; 90 si apunta a la derecha)."
        )
        self.mes = QComboBox()
        self.mes.addItems([m.capitalize() for m in MESES])
        self.mes.setCurrentIndex(6)
        self.color = QComboBox()
        self.color.addItem("Oscuro (del lado de la seguridad)", "oscuro")
        self.color.addItem("Claro", "claro")
        self.recuperador = QLineEdit("0")
        self.recuperador.setToolTip("Eficiencia sensible del recuperador, en %. 0 = sin él.")
        self.zona = QLabel()
        self.error = QLabel()
        self.error.setStyleSheet("color: #c0392b")
        self.error.setWordWrap(True)
        f = QFormLayout(self)
        f.addRow("Guía del IDAE (PDF)", self.guia)
        f.addRow("Estación", self.estacion)
        f.addRow("Provincia de la obra", self.provincia)
        f.addRow("Altitud de la obra (m)", self.altitud)
        f.addRow("Zona climática (CTE)", self.zona)
        f.addRow("Tipo de construcción", self.tipo)
        f.addRow("Norte del plano (°)", self.norte)
        f.addRow("Mes de proyecto (verano)", self.mes)
        f.addRow("Color de los cerramientos", self.color)
        f.addRow("Recuperador de calor (%)", self.recuperador)
        f.addRow(self.error)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        f.addRow(botones)
        self.guia.currentIndexChanged.connect(lambda _i: self._al_cambiar_guia())
        self.estacion.currentIndexChanged.connect(lambda _i: self._al_cambiar_estacion())
        self.provincia.currentIndexChanged.connect(lambda _i: self._zona())
        self.altitud.textChanged.connect(lambda _t: self._zona())
        if actual:
            self.guia.setCurrentIndex(max(self.guia.findData(actual["guia_documento_id"]), 0))
        self._al_cambiar_guia(actual)

    def _al_cambiar_guia(self, actual: dict | None = None) -> None:
        self.estacion.blockSignals(True)
        self.estacion.clear()
        self._estaciones = []
        try:
            if self.guia.currentData():
                self._estaciones = self._cargar(self.guia.currentData())
            self.error.clear()
        except Exception as exc:  # noqa: BLE001 — el mensaje es para el usuario
            self.error.setText(str(exc))
        for e in self._estaciones:
            self.estacion.addItem(f"{e.provincia} — {e.nombre} ({e.altitud_m:g} m)", e.pagina)
        self.estacion.blockSignals(False)
        if actual:
            self.estacion.setCurrentIndex(max(self.estacion.findData(actual["estacion_pagina"]), 0))
            self.provincia.setCurrentText(actual["provincia"])
            self.altitud.setText(_cifra(actual["altitud_obra"]))
            self.tipo.setCurrentIndex(max(self.tipo.findData(actual["tipo_construccion"]), 0))
            self.norte.setText(_cifra(actual["norte"]))
            self.mes.setCurrentIndex(actual["mes"] - 1)
            self.color.setCurrentIndex(max(self.color.findData(actual["color"]), 0))
            self.recuperador.setText(_cifra(actual["recuperacion"] * 100))
            self._zona()
        else:
            self._al_cambiar_estacion()

    def _al_cambiar_estacion(self) -> None:
        i = self.estacion.currentIndex()
        if 0 <= i < len(self._estaciones):
            e = self._estaciones[i]
            self.provincia.setCurrentText(
                cerramientos.ALIAS_PROVINCIA.get(e.provincia, e.provincia)
            )
            self.altitud.setText(_cifra(e.altitud_m))
        self._zona()

    def _zona(self) -> None:
        try:
            alt = _numero_opcional(self.altitud.text(), "Altitud")
            texto = (
                cerramientos.zona_climatica(self.provincia.currentText(), alt)
                if alt is not None
                else "—"
            )
        except (ValueError, KeyError):
            texto = "—"
        self.zona.setText(texto)

    def _aceptar(self) -> None:
        if self.estacion.currentIndex() < 0:
            self.error.setText("Elige una guía del IDAE y una estación.")
            return
        try:
            altitud = _numero_opcional(self.altitud.text(), "Altitud")
            norte = _numero_opcional(self.norte.text(), "Norte") or 0.0
            rec = _numero_opcional(self.recuperador.text(), "Recuperador") or 0.0
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        if altitud is None:
            self.error.setText("Escribe la altitud de la obra.")
            return
        if not 0 <= rec < 100:
            self.error.setText("El recuperador va de 0 a 100 % (sin llegar a 100).")
            return
        self.resultado = {
            "guia_documento_id": self.guia.currentData(),
            "estacion_pagina": self.estacion.currentData(),
            "provincia": self.provincia.currentText(),
            "altitud_obra": altitud,
            "tipo_construccion": self.tipo.currentData(),
            "norte": norte,
            "mes": self.mes.currentIndex() + 1,
            "color": self.color.currentData(),
            "recuperacion": rec / 100,
        }
        self.accept()


@dataclass(frozen=True)
class DatosEspacioCargas:
    uso: str
    ajustes: dict = field(default_factory=dict)
    fachadas: dict = field(default_factory=dict)


class DialogoEspacioCargas(QDialog):
    """`propuestas`: {clave de ajuste: (valor propuesto, fuente)} del uso actual.
    `cambiar_uso(clave)` devuelve las propuestas de otro uso (se ven al cambiarlo)."""

    def __init__(
        self,
        padre: QWidget,
        espacio: str,
        uso: str,
        ajustes: dict,
        fachadas: dict,
        propuestas_de,
    ) -> None:
        super().__init__(padre)
        self.setWindowTitle(f"Cargas de {espacio}")
        self.resultado: DatosEspacioCargas | None = None
        self._propuestas_de = propuestas_de
        caja = QVBoxLayout(self)
        f = QFormLayout()
        self.uso = QComboBox()
        for u in USOS:
            self.uso.addItem(f"{u.grupo} · {u.nombre}", u.clave)
        self.uso.setCurrentIndex(max(self.uso.findData(uso), 0))
        f.addRow("Uso", self.uso)
        ayuda = QLabel("En blanco = lo propuesto para el uso (pasa el ratón para ver la fuente).")
        ayuda.setWordWrap(True)
        f.addRow(ayuda)
        self.campos: dict[str, QLineEdit] = {}
        for clave, (etiqueta, _neg) in AJUSTES_CARGAS.items():
            campo = QLineEdit(_cifra(ajustes.get(clave)))
            self.campos[clave] = campo
            f.addRow(etiqueta, campo)
        self.sin_calefaccion = QCheckBox("Sin calefacción")
        self.sin_calefaccion.setChecked(bool(ajustes.get(AJUSTE_SIN_CALEFACCION)))
        f.addRow(self.sin_calefaccion)
        caja.addLayout(f)
        grupo = QGroupBox("Fachadas por orientación")
        rejilla = QGridLayout(grupo)
        self.fachadas: dict[str, QComboBox] = {}
        for i, s in enumerate(SECTORES_FACHADA):
            combo = QComboBox()
            combo.addItems(ESTADOS_FACHADA)
            if s in fachadas:
                combo.setCurrentIndex(1 if fachadas[s] else 2)
            self.fachadas[s] = combo
            rejilla.addWidget(QLabel(s), i // 4, (i % 4) * 2)
            rejilla.addWidget(combo, i // 4, (i % 4) * 2 + 1)
        caja.addWidget(grupo)
        self.error = QLabel()
        self.error.setStyleSheet("color: #c0392b")
        self.error.setWordWrap(True)
        caja.addWidget(self.error)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        caja.addWidget(botones)
        self.uso.currentIndexChanged.connect(lambda _i: self._mostrar_propuestas())
        self._mostrar_propuestas()

    def _mostrar_propuestas(self) -> None:
        propuestas = self._propuestas_de(self.uso.currentData())
        for clave, campo in self.campos.items():
            valor, fuente = propuestas.get(clave, (None, ""))
            campo.setPlaceholderText(f"Propuesto: {_cifra(valor)}" if valor is not None else "")
            campo.setToolTip(fuente)

    def _aceptar(self) -> None:
        ajustes: dict = {}
        try:
            for clave, campo in self.campos.items():
                v = _numero_opcional(campo.text(), AJUSTES_CARGAS[clave][0])
                if v is not None:
                    ajustes[clave] = v
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        if self.sin_calefaccion.isChecked():
            if "t_invierno_c" in ajustes:
                self.error.setText("Sin calefacción no lleva temperatura de invierno.")
                return
            ajustes[AJUSTE_SIN_CALEFACCION] = True
        fachadas = {
            s: c.currentIndex() == 1 for s, c in self.fachadas.items() if c.currentIndex() != 0
        }
        self.resultado = DatosEspacioCargas(self.uso.currentData(), ajustes, fachadas)
        self.accept()
