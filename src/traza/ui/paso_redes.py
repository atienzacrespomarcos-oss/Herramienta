"""Paso «Redes de aire» (encargos con diseño). docs/modules/redes_aire.md.

Flujo (decisiones del usuario, 07-11-2026): el usuario dibuja los ejes en AutoCAD (una capa
por red) y los difusores/rejillas como bloques; aquí elige plano, capa y bloques, y TRAZA
lee el árbol, toma los caudales de las cargas (o del atributo CAUDAL), dimensiona por
pérdida de carga constante y da el camino crítico, el equilibrado y la medición.

La página no habla con la base de datos: todo pasa por `Proyecto` y las preguntas por
`ventana.preguntas`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from traza.app.ordenes import TIPOS_RED, OrdenRechazada
from traza.core.ficheros import nombre_valido
from traza.core.numeros import escribir_numero
from traza.engines.conductos import SFP
from traza.ui.visor_plano import VisorPlano

COLOR_EJES = QColor(40, 110, 200)
COLOR_CRITICO = QColor(200, 40, 40)
COLOR_ELEGIDO = QColor(230, 126, 34)


def _archivo(texto: str) -> str:
    return nombre_valido(texto, "red")


def _n(v, decimales: int = 1) -> str:
    return "" if v is None else escribir_numero(round(float(v), decimales))


class PaginaRedes(QWidget):
    def __init__(self, ventana) -> None:
        super().__init__()
        self.v = ventana
        from traza.ui.ventana import _barra, _tabla

        self.selector = QComboBox()
        self.selector.currentIndexChanged.connect(
            lambda _i: self.v._proteger("Red", self._refrescar_contenido)
        )
        self.resumen = QLabel()
        self.resumen.setWordWrap(True)
        # Presentación limpia (usuario, 07-11-2026): lo que decide en pantalla; accesorios,
        # clases y caminos completos, en el listado Excel.
        self.tabla_tramos = _tabla(
            [
                "Tramo",
                "Caudal (m³/h)",
                "Sección (mm)",
                "Velocidad (m/s)",
                "Pa/m",
                "Longitud (m)",
                "Pérdida (Pa)",
                "Terminal",
            ]
        )
        self.tabla_terminales = _tabla(["Terminal", "Espacio", "Caudal (m³/h)", "A disipar (Pa)"])
        self.tabla_medicion = _tabla(["Sección (mm)", "Longitud (m)", "Superficie (m²)"])
        self.tabla_tramos.itemSelectionChanged.connect(self._dibujar)
        self.pestanas = QTabWidget()
        self.pestanas.addTab(self.tabla_tramos, "Tramos")
        self.pestanas.addTab(self.tabla_terminales, "Terminales")
        self.pestanas.addTab(self.tabla_medicion, "Medición")
        self.visor = VisorPlano()
        self._crear_acciones()
        cabecera = QHBoxLayout()
        cabecera.addWidget(QLabel("Red:"))
        cabecera.addWidget(self.selector, 1)
        division = QSplitter(Qt.Horizontal)
        division.addWidget(self.pestanas)
        division.addWidget(self.visor)
        division.setStretchFactor(0, 3)
        division.setStretchFactor(1, 2)
        caja = QVBoxLayout(self)
        caja.addWidget(
            _barra([self.a_nueva, self.a_cambiar, self.a_borrar, self.a_excel, self.a_autocad])
        )
        caja.addLayout(cabecera)
        caja.addWidget(self.resumen)
        caja.addWidget(division, 1)
        self._resultado = None
        self._encuadrado: str | None = None

    def _crear_acciones(self) -> None:
        m = self.v.menu_redes
        a = self.v._accion
        self.a_nueva = a(m, "Nueva red…", self.accion_nueva)
        self.a_cambiar = a(m, "Cambiar red…", self.accion_cambiar)
        self.a_borrar = a(m, "Borrar red", self.accion_borrar)
        m.addSeparator()
        self.a_excel = a(m, "Exportar listado Excel…", self.accion_excel)
        self.a_autocad = a(m, "Exportar a AutoCAD (DXF y LISP)…", self.accion_autocad)

    @property
    def proyecto(self):
        return self.v.proyecto

    def red_id(self) -> str | None:
        return self.selector.currentData()

    # --- Acciones ----------------------------------------------------------------------

    def _info(self, plano_id: str):
        p = self.proyecto.plano(plano_id)
        leido = self.proyecto.plano_dxf(
            p["documento_id"],
            esperar=lambda f: self.v._en_segundo_plano(f, "Leyendo el plano DXF…", "Redes"),
        )
        capas = sorted(
            (c for c, info in leido.capas.items() if sum(info.entidades.values())), key=str.lower
        )
        bloques = sorted({b.nombre for b in leido.bloques}, key=str.lower)
        return capas, bloques

    def _pedir(self, actual: dict | None) -> None:
        planos = self.proyecto.planos()
        if not planos:
            self.v.preguntas.aviso(
                "Red de aire",
                "Primero lee el plano DXF con los ejes de conductos en el paso «Planos y "
                "espacios».",
            )
            return
        r = self.v.preguntas.red_aire(planos, self.proyecto.niveles(), self._info, actual)
        if r is None:
            return
        red_id = self.proyecto.definir_red(**r)
        self.v.refrescar()
        self._elegir(red_id)

    def accion_nueva(self) -> None:
        self._pedir(None)

    def accion_cambiar(self) -> None:
        if self.red_id() is None:
            self.v.preguntas.informacion("Cambiar red", "No hay ninguna red elegida.")
            return
        self._pedir(self.proyecto.red(self.red_id()))

    def accion_borrar(self) -> None:
        if self.red_id() is None:
            return
        red = self.proyecto.red(self.red_id())
        if self.v.preguntas.confirmar(
            "Borrar red", f"Se borra la red «{red['nombre']}». Se puede deshacer. ¿Continuar?"
        ):
            self.proyecto.borrar_red(red["id"])
            self.v.refrescar()

    def accion_excel(self) -> None:
        if self.red_id() is None:
            return
        red = self.proyecto.red(self.red_id())
        destino = self.v.preguntas.destino_excel(
            self.proyecto.carpeta.raiz.parent
            / f"{_archivo(self.proyecto.nombre)} - {_archivo(red['nombre'])}.xlsx"
        )
        if destino is not None:
            ruta = self.proyecto.exportar_red_excel(red["id"], destino)
            self.v.preguntas.informacion("Listado Excel", f"Guardado en {ruta}")

    def accion_autocad(self) -> None:
        if self.red_id() is None:
            return
        red = self.proyecto.red(self.red_id())
        destino = self.v.preguntas.destino_dxf(
            self.proyecto.carpeta.raiz.parent
            / f"{_archivo(self.proyecto.nombre)} - {_archivo(red['nombre'])}.dxf"
        )
        if destino is None:
            return
        dxf_ruta, lsp_ruta = self.proyecto.exportar_red_autocad(red["id"], destino)
        self.v.preguntas.informacion(
            "Exportar a AutoCAD",
            f"Guardados:\n{dxf_ruta}\n{lsp_ruta}\n\nEl DXF se abre en AutoCAD 2013 o "
            "posterior. Para dibujar la red dentro de tu plano: APPLOAD, carga el .lsp y "
            "escribe TRAZA_RED.",
        )

    # --- Contenido -----------------------------------------------------------------------

    def _elegir(self, red_id: str) -> None:
        i = self.selector.findData(red_id)
        if i >= 0:
            self.selector.setCurrentIndex(i)

    def refrescar(self) -> None:
        elegida = self.red_id()
        self.selector.blockSignals(True)
        try:
            self.selector.clear()
            if self.proyecto is not None:
                for r in self.proyecto.redes():
                    self.selector.addItem(f"{r['nombre']} ({TIPOS_RED[r['tipo']]})", r["id"])
                if elegida is not None:
                    self._elegir(elegida)
        finally:
            self.selector.blockSignals(False)
        self._refrescar_contenido()

    def _refrescar_contenido(self) -> None:
        from traza.ui.ventana import _llenar

        self._resultado = None
        tablas = (self.tabla_tramos, self.tabla_terminales, self.tabla_medicion)
        if self.proyecto is None or self.red_id() is None:
            for t in tablas:
                _llenar(t, [])
            self.resumen.setText(
                ""
                if self.proyecto is None
                else "Crea una red: «Redes → Nueva red…» (ejes dibujados en una capa del DXF)."
            )
            self.visor.vacio("Sin red")
            self._encuadrado = None
            return
        try:
            r = self.proyecto.calcular_red(self.red_id())
        except Exception as exc:  # noqa: BLE001 — un dato roto no tumba la ventana
            for t in tablas:
                _llenar(t, [])
            mensaje = (
                str(exc) if isinstance(exc, OrdenRechazada) else f"{type(exc).__name__}: {exc}"
            )
            self.resumen.setText(f"⚠ No se ha podido calcular la red: {mensaje}")
            self.visor.vacio("No se puede calcular")
            return
        self._resultado = r
        c = r.calculo
        filas = []
        ids = []
        if c is not None:
            for t in c.tramos:
                filas.append(
                    [
                        t.tramo.id,
                        _n(t.tramo.caudal_m3s * 3600, 0),
                        t.seccion.texto(),
                        _n(t.velocidad_m_s, 1),
                        _n(t.friccion_pa_m, 2),
                        _n(t.tramo.longitud_m, 1),
                        _n(t.perdida_pa),
                        t.tramo.terminal or "",
                    ]
                )
                ids.append(t.tramo.id)
        _llenar(self.tabla_tramos, filas, ids)
        _llenar(
            self.tabla_terminales,
            [
                [
                    t.codigo,
                    t.espacio or "fuera",
                    _n(t.caudal_m3h, 0),
                    _n(c.exceso_pa.get(t.codigo)) if c else "",
                ]
                for t in r.terminales
            ],
        )
        for fila, term in enumerate(r.terminales):
            item = self.tabla_terminales.item(fila, 2)
            if item is not None:
                item.setToolTip(f"Caudal de: {term.origen_caudal}")
        _llenar(
            self.tabla_medicion,
            [[m.seccion, _n(m.longitud_m, 2), _n(m.superficie_m2, 2)] for m in r.medicion],
        )
        conectados = r.terminales_conectados
        sueltos = len(r.terminales) - conectados
        texto = f"{_n(r.caudal_total_m3h, 0)} m³/h · {conectados} terminales"
        if sueltos:
            texto += f" ({sueltos} sin conectar)"
        if c is not None:
            limite = dict(SFP)[r.sfp_exigida]
            texto += (
                f" · {_n(c.presion_necesaria_pa, 0)} Pa en la red (crítico {c.terminal_critico})"
                f" · ventilador SFP {r.sfp_exigida}: como mucho {_n(r.potencia_maxima_w, 0)} W"
            )
            self.resumen.setToolTip(
                f"Punto de trabajo para el selector del fabricante: caudal, presión de la red "
                f"(sin el equipo: filtros, baterías y rejillas exteriores, aparte) y potencia "
                f"eléctrica máxima. RITE IT 1.2.4.2.5: SFP {r.sfp_exigida} = como mucho "
                f"{limite} W por m³/s."
            )
        if r.avisos:
            texto += "\n⚠ " + "\n⚠ ".join(r.avisos)
        self.resumen.setText(texto)
        self._dibujar()

    def _dibujar(self) -> None:
        r = self._resultado
        if r is None or r.topologia is None:
            return
        red = r.red
        espacios = [
            e["contorno"]
            for e in self.proyecto.espacios()
            if e["plano_id"] == red["plano_id"]
            and (red["nivel_id"] is None or e["padre_id"] == red["nivel_id"])
        ]
        lineas = [list(t.puntos) for t in r.topologia.tramos]
        self.visor.dibujar(
            [("ejes", p) for p in lineas],
            1.0,
            None,
            espacios,
            [],
            encuadrar=self._encuadrado != red["id"],
        )
        self._encuadrado = red["id"]
        self.visor.marcar_lineas(lineas, COLOR_EJES, 2)
        if r.calculo is not None and r.calculo.terminal_critico:
            por_id = {t.tramo.id: t for t in r.topologia.tramos}
            critico = next(
                t for t in r.topologia.tramos if t.tramo.terminal == r.calculo.terminal_critico
            )
            camino = []
            while critico is not None:
                camino.append(list(critico.puntos))
                critico = por_id.get(critico.tramo.padre) if critico.tramo.padre else None
            self.visor.marcar_lineas(camino, COLOR_CRITICO, 3)
        f = self.tabla_tramos.currentRow()
        item = self.tabla_tramos.item(f, 0) if f >= 0 else None
        if item is not None:
            elegido = next(
                (t for t in r.topologia.tramos if t.tramo.id == item.data(Qt.UserRole)), None
            )
            if elegido is not None:
                self.visor.marcar_lineas([list(elegido.puntos)], COLOR_ELEGIDO, 5)

    def actualizar_estado(self, hay: bool) -> None:
        from traza.ui.ventana import PASOS

        con_paso = hay and any(
            clave == "redes" and self.proyecto.encargo in encargos for clave, _, encargos in PASOS
        )
        self.v.menu_redes.menuAction().setVisible(con_paso)
        self.a_nueva.setEnabled(con_paso)
        hay_red = con_paso and self.red_id() is not None
        for a in (self.a_cambiar, self.a_borrar, self.a_excel, self.a_autocad):
            a.setEnabled(hay_red)
