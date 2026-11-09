"""Paso «Subcuadros de clima» (Etapa 8, docs/modules/electricidad.md).

Presentación limpia: en pantalla la alimentación y una fila por salida con lo que se pide
y se comprueba (sección, protecciones, caída); el detalle, en el unifilar DXF.
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from traza.app.ordenes import OrdenRechazada
from traza.core.numeros import escribir_numero
from traza.io.unifilar_dxf import cable
from traza.ui.paso_redes import _archivo


def _n(v, d: int = 1) -> str:
    return "" if v is None else escribir_numero(round(float(v), d))


class PaginaSubcuadros(QWidget):
    def __init__(self, ventana) -> None:
        super().__init__()
        self.v = ventana
        from traza.ui.ventana import _barra, _tabla

        self.selector = QComboBox()
        self.selector.currentIndexChanged.connect(
            lambda _i: self.v._proteger("Subcuadro", self._refrescar_contenido)
        )
        self.resumen = QLabel()
        self.resumen.setWordWrap(True)
        self.tabla = _tabla(
            ["Salida", "kW", "Ib (A)", "Cable", "Magnetotérmico", "Diferencial", "ΔU total (%)", ""]
        )
        m = self.v.menu_subcuadros
        a = self.v._accion
        self.a_nuevo = a(m, "Nuevo subcuadro…", self.accion_nuevo)
        self.a_cambiar = a(m, "Cambiar subcuadro…", self.accion_cambiar)
        self.a_borrar = a(m, "Borrar subcuadro", self.accion_borrar)
        m.addSeparator()
        self.a_unifilar = a(m, "Exportar esquema unifilar (DXF)…", self.accion_unifilar)
        cabecera = QHBoxLayout()
        cabecera.addWidget(QLabel("Subcuadro:"))
        cabecera.addWidget(self.selector, 1)
        caja = QVBoxLayout(self)
        caja.addWidget(_barra([self.a_nuevo, self.a_cambiar, self.a_borrar, self.a_unifilar]))
        caja.addLayout(cabecera)
        caja.addWidget(self.resumen)
        caja.addWidget(self.tabla, 1)

    @property
    def proyecto(self):
        return self.v.proyecto

    def subcuadro_id(self) -> str | None:
        return self.selector.currentData()

    def _pedir(self, actual: dict | None) -> None:
        # Si la orden rechaza algo, el diálogo vuelve con lo escrito.
        while True:
            r = self.v.preguntas.subcuadro(self.proyecto.salidas_propuestas, actual)
            if r is None:
                return
            try:
                sid = self.proyecto.definir_subcuadro(**r)
            except OrdenRechazada as exc:
                self.v.preguntas.aviso("Subcuadro de clima", str(exc))
                actual = {**r, "nombre": r["titulo"], "id": r.get("id")}
                continue
            break
        self.v.refrescar()
        i = self.selector.findData(sid)
        if i >= 0:
            self.selector.setCurrentIndex(i)

    def accion_nuevo(self) -> None:
        self._pedir(None)

    def accion_cambiar(self) -> None:
        if self.subcuadro_id() is None:
            self.v.preguntas.informacion("Cambiar subcuadro", "No hay ningún subcuadro elegido.")
            return
        self._pedir(self.proyecto.subcuadro(self.subcuadro_id()))

    def accion_borrar(self) -> None:
        if self.subcuadro_id() is None:
            return
        s = self.proyecto.subcuadro(self.subcuadro_id())
        if self.v.preguntas.confirmar(
            "Borrar subcuadro", f"Se borra «{s['nombre']}». Se puede deshacer. ¿Continuar?"
        ):
            self.proyecto.borrar_subcuadro(s["id"])
            self.v.refrescar()

    def accion_unifilar(self) -> None:
        if self.subcuadro_id() is None:
            return
        s = self.proyecto.subcuadro(self.subcuadro_id())
        destino = self.v.preguntas.destino_dxf(
            self.proyecto.carpeta.raiz.parent
            / f"{_archivo(self.proyecto.nombre)} - {_archivo(s['nombre'])} - unifilar.dxf"
        )
        if destino is not None:
            ruta = self.proyecto.exportar_unifilar(s["id"], destino)
            self.v.preguntas.informacion(
                "Esquema unifilar", f"Guardado en {ruta}\n\nSe abre en AutoCAD 2013 o posterior."
            )

    def refrescar(self) -> None:
        elegido = self.subcuadro_id()
        self.selector.blockSignals(True)
        try:
            self.selector.clear()
            if self.proyecto is not None:
                for s in self.proyecto.subcuadros():
                    self.selector.addItem(s["nombre"], s["id"])
                i = self.selector.findData(elegido)
                if i >= 0:
                    self.selector.setCurrentIndex(i)
        finally:
            self.selector.blockSignals(False)
        self._refrescar_contenido()

    def _refrescar_contenido(self) -> None:
        from traza.ui.ventana import _llenar

        if self.proyecto is None or self.subcuadro_id() is None:
            _llenar(self.tabla, [])
            self.resumen.setText(
                ""
                if self.proyecto is None
                else "Crea un subcuadro: «Electricidad → Nuevo subcuadro…»."
            )
            return
        try:
            r = self.proyecto.calcular_subcuadro(self.subcuadro_id())
        except Exception as exc:  # noqa: BLE001 — un dato roto no tumba la ventana
            _llenar(self.tabla, [])
            m = str(exc) if isinstance(exc, OrdenRechazada) else f"{type(exc).__name__}: {exc}"
            self.resumen.setText(f"⚠ No se ha podido calcular el subcuadro: {m}")
            return
        a = r.alimentacion
        texto = (
            f"Alimentación: {cable(a)} · {_n(a.longitud_m, 0)} m · IG {a.calibre_a or '>160'} A · "
            f"ΔU {_n(a.caida_pct, 2)} % · límite {_n(r.limite_pct)} % · "
            + ("CUMPLE" if r.cumple else "NO CUMPLE")
        )
        if r.avisos:
            texto += "\n⚠ " + "\n⚠ ".join(r.avisos)
        self.resumen.setText(texto)
        _llenar(
            self.tabla,
            [
                [
                    s.nombre,
                    _n(s.potencia_kw, 2),
                    _n(s.intensidad_a),
                    cable(s).removeprefix("RZ1-K 0,6/1 kV "),
                    f"{s.curva}{s.calibre_a}",
                    f"{s.diferencial_ma} mA {s.diferencial_tipo}",
                    _n(s.caida_total_pct, 2),
                    "CUMPLE" if s.cumple else "NO CUMPLE",
                ]
                for s in r.salidas
            ],
        )

    def actualizar_estado(self, hay: bool) -> None:
        from traza.ui.ventana import PASOS

        con_paso = hay and any(
            clave == "subcuadros" and self.proyecto.encargo in encargos
            for clave, _, encargos in PASOS
        )
        self.v.menu_subcuadros.menuAction().setVisible(con_paso)
        self.a_nuevo.setEnabled(con_paso)
        hay_sub = con_paso and self.subcuadro_id() is not None
        for a in (self.a_cambiar, self.a_borrar, self.a_unifilar):
            a.setEnabled(hay_sub)
