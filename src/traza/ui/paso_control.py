"""Paso «Control» (docs/modules/control.md).

Presentación limpia: en pantalla el número de puntos por tipo y las comprobaciones del
RITE; las categorías de cada espacio y el listado de puntos, en pestañas. Todo, en el Excel.

Se calcula solo con el paso a la vista (página actual): necesita las cargas, las redes y
los sistemas hidráulicos, y la ventana refresca todas las páginas a cada cambio.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from traza.app.ordenes import OrdenRechazada
from traza.rules import control as rc
from traza.ui.paso_redes import _archivo


def _resultado(v: bool | None) -> str:
    return "No aplica" if v is None else ("CUMPLE" if v else "NO CUMPLE")


class PaginaControl(QWidget):
    def __init__(self, ventana) -> None:
        super().__init__()
        self.v = ventana
        from traza.ui.ventana import _barra, _tabla

        self.resumen = QLabel()
        self.resumen.setWordWrap(True)
        self.tabla_comprobaciones = _tabla(["Requisito", "Norma", "Resultado", "Detalle"])
        self.tabla_categorias = _tabla(["Espacio", "Uso", "THM-C", "IDA-C"])
        self.tabla_puntos = _tabla(["Sistema", "Equipo", "Señal", "Tipo", "Cantidad"])
        self.pestanas = QTabWidget()
        self.pestanas.addTab(self.tabla_comprobaciones, "Comprobaciones")
        self.pestanas.addTab(self.tabla_categorias, "Categorías por espacio")
        self.pestanas.addTab(self.tabla_puntos, "Puntos")
        m = self.v.menu_control
        self.a_excel = self.v._accion(
            m, "Exportar propuesta de control (Excel)…", self.accion_excel
        )
        caja = QVBoxLayout(self)
        caja.addWidget(_barra([self.a_excel]))
        caja.addWidget(self.resumen)
        caja.addWidget(self.pestanas, 1)
        self._pendiente = True
        self.v.paginas.currentChanged.connect(self._al_cambiar_de_paso)

    @property
    def proyecto(self):
        return self.v.proyecto

    def accion_excel(self) -> None:
        destino = self.v.preguntas.destino_excel(
            self.proyecto.carpeta.raiz.parent
            / f"{_archivo(self.proyecto.nombre)} - propuesta de control.xlsx"
        )
        if destino is not None:
            ruta = self.proyecto.exportar_control_excel(destino)
            self.v.preguntas.informacion("Propuesta de control", f"Guardado en {ruta}")

    def _a_la_vista(self) -> bool:
        return self.v.paginas.currentWidget() is self

    def refrescar(self) -> None:
        self._pendiente = True
        if self._a_la_vista():
            self.calcular()

    def _al_cambiar_de_paso(self, _indice: int) -> None:
        if self._pendiente and self._a_la_vista():
            self.calcular()

    def calcular(self) -> None:
        from traza.ui.ventana import _llenar

        self._pendiente = False
        tablas = (self.tabla_comprobaciones, self.tabla_categorias, self.tabla_puntos)
        if self.proyecto is None:
            for t in tablas:
                _llenar(t, [])
            self.resumen.setText("")
            return
        try:
            p = self.proyecto.propuesta_control()
        except Exception as exc:  # noqa: BLE001 — un dato roto no tumba la ventana
            for t in tablas:
                _llenar(t, [])
            m = str(exc) if isinstance(exc, OrdenRechazada) else f"{type(exc).__name__}: {exc}"
            self.resumen.setText(f"⚠ No se ha podido proponer el control: {m}")
            return
        r = p.resultado
        if not r.puntos:
            texto = (
                "Nada que controlar todavía: diseña los espacios (con sus cargas), las redes de "
                "aire o el sistema hidráulico."
            )
        else:
            n = r.resumen
            evaluadas = [c for c in r.comprobaciones if c.cumple is not None]
            fallan = [c for c in evaluadas if not c.cumple]
            if fallan:
                rite = f"RITE IT 1.2.4.3: NO CUMPLE en {len(fallan)} de {len(evaluadas)}"
            elif evaluadas:
                rite = f"RITE IT 1.2.4.3: CUMPLE ({len(evaluadas)} comprobaciones)"
            else:
                rite = "RITE IT 1.2.4.3: ninguna exigencia aplica todavía"
            puntos = " · ".join(f"{t} {n[t]}" for t in rc.TIPOS_PUNTO)
            texto = f"{puntos} · total {sum(n.values())} puntos. {rite}"
        if p.avisos:
            texto += "\n⚠ " + "\n⚠ ".join(p.avisos)
        self.resumen.setText(texto)
        _llenar(
            self.tabla_comprobaciones,
            [[c.requisito, c.norma, _resultado(c.cumple), c.detalle] for c in r.comprobaciones],
        )
        _llenar(
            self.tabla_categorias,
            [[c.espacio, c.uso, c.thm or "—", c.ida or "—"] for c in r.categorias],
        )
        _llenar(
            self.tabla_puntos,
            [[x.sistema, x.equipo, x.senal, x.tipo, str(x.cantidad)] for x in r.puntos],
        )

    def actualizar_estado(self, hay: bool) -> None:
        from traza.ui.ventana import PASOS

        con_paso = hay and any(
            clave == "control" and self.proyecto.encargo in encargos for clave, _, encargos in PASOS
        )
        self.v.menu_control.menuAction().setVisible(con_paso)
        self.a_excel.setEnabled(con_paso)
