"""Paso «Cargas y ventilación» (encargos con diseño). docs/modules/cargas.md.

Flujo (decisiones del usuario, 07-11-2026), sin fricción:
1. «Clima y obra…»: la guía del IDAE (PDF de Documentación), la estación, la provincia y
   altitud de la obra y el tipo de construcción. Con eso ya se calcula todo.
2. Cada espacio sale con un uso propuesto por su nombre y con todo lo de ese uso propuesto
   con su fuente; «Datos del espacio…» cambia el uso o cualquier valor, y corrige fachadas.
3. Las fachadas salen del plano y se ven en rojo en el visor para revisarlas.
4. Informe en Excel (todo el detalle) y PDF (presentable).

La página no habla con la base de datos: todo pasa por `Proyecto` y las preguntas por
`ventana.preguntas` (las pruebas las sustituyen).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSplitter, QTabWidget, QVBoxLayout, QWidget

from traza.app import cargas as calculo_cargas
from traza.app.ordenes import OrdenRechazada
from traza.core.numeros import escribir_numero
from traza.rules.usos import POR_CLAVE
from traza.ui.visor_plano import VisorPlano

URL_GUIA = (
    "https://www.idae.es/uploads/documentos/documentos_12_Guia_tecnica_condiciones_climaticas_"
    "exteriores_de_proyecto_e4e5b769.pdf"
)
ORIGEN = {calculo_cargas.USUARIO: "tuyo", calculo_cargas.PROPUESTA: "propuesto"}


def _n(v, decimales: int = 1) -> str:
    return "" if v is None else escribir_numero(round(float(v), decimales))


class PaginaCargas(QWidget):
    def __init__(self, ventana) -> None:
        super().__init__()
        self.v = ventana
        from traza.ui.ventana import _barra, _tabla

        self.resumen = QLabel()
        self.resumen.setWordWrap(True)
        # Presentación limpia (usuario, 07-11-2026): en la tabla, lo que decide; el detalle
        # del espacio (nivel, personas, hora punta, fachadas, partidas) en su pestaña.
        self.tabla_espacios = _tabla(
            [
                "Código",
                "Espacio",
                "Uso",
                "m²",
                "Calefacción (kW)",
                "Refrigeración (kW)",
                "W/m²",
                "Aire exterior (m³/h)",
            ]
        )
        self.tabla_partidas = _tabla(["Estación", "Concepto", "Sensible (W)", "Latente (W)"])
        self.tabla_datos = _tabla(["Dato", "Valor", "Unidad", "Origen", "Fuente"])
        self.tabla_espacios.itemSelectionChanged.connect(self._al_elegir)
        self.detalle = QLabel()
        self.detalle.setWordWrap(True)
        desglose = QWidget()
        caja_desglose = QVBoxLayout(desglose)
        caja_desglose.setContentsMargins(0, 4, 0, 0)
        caja_desglose.addWidget(self.detalle)
        caja_desglose.addWidget(self.tabla_partidas, 1)
        self.pestanas = QTabWidget()
        self.pestanas.addTab(self.tabla_espacios, "Espacios")
        self.pestanas.addTab(desglose, "Desglose del espacio")
        self.pestanas.addTab(self.tabla_datos, "Datos y fuentes")
        self.visor = VisorPlano()
        self._crear_acciones()
        division = QSplitter(Qt.Horizontal)
        division.addWidget(self.pestanas)
        division.addWidget(self.visor)
        division.setStretchFactor(0, 3)
        division.setStretchFactor(1, 2)
        caja = QVBoxLayout(self)
        caja.addWidget(
            _barra([self.a_clima, self.a_espacio, self.a_calcular, self.a_excel, self.a_pdf])
        )
        caja.addWidget(self.resumen)
        caja.addWidget(division, 1)
        self._resultado: calculo_cargas.ResultadoCargas | None = None
        self._encuadrado = False
        self._nivel_dibujado: str | None = None

    def _crear_acciones(self) -> None:
        m = self.v.menu_cargas
        a = self.v._accion
        self.a_clima = a(m, "Clima y obra…", self.accion_clima)
        self.a_espacio = a(m, "Datos del espacio…", self.accion_espacio)
        self.a_calcular = a(m, "Calcular", self.accion_calcular)
        m.addSeparator()
        self.a_excel = a(m, "Exportar informe Excel…", self.accion_excel)
        self.a_pdf = a(m, "Exportar informe PDF…", self.accion_pdf)

    @property
    def proyecto(self):
        return self.v.proyecto

    def _esperar(self, mensaje: str):
        return lambda f: self.v._en_segundo_plano(f, mensaje, "Cargas")

    # --- Acciones ----------------------------------------------------------------------

    def accion_clima(self) -> None:
        guias = [d for d in self.proyecto.documentos() if d["extension"].lower() == ".pdf"]
        if not guias:
            self.v.preguntas.aviso(
                "Clima y obra",
                "Incorpora antes en «Documentación» el PDF de la guía del IDAE «Condiciones "
                f"climáticas exteriores de proyecto» (se descarga de {URL_GUIA}).",
            )
            return
        r = self.v.preguntas.clima_obra(
            guias,
            lambda doc_id: self.proyecto.estaciones(doc_id, self._esperar("Leyendo la guía…")),
            self.proyecto.cargas_config(),
        )
        if r is not None:
            self.proyecto.fijar_cargas(**r)
            self.v.refrescar()

    def accion_espacio(self) -> None:
        e = self._espacio_elegido()
        if e is None:
            self.v.preguntas.informacion(
                "Datos del espacio", "Elige un espacio de la lista (se crean en el paso Planos)."
            )
            return
        guardado = self.proyecto.datos_cargas_espacios().get(e["id"])
        uso = (
            guardado["uso"]
            if guardado
            else calculo_cargas.uso_por_nombre(e["nombre"] or e["codigo"])
        )
        area = e["superficie"]

        def propuestas_de(clave: str) -> dict:
            p = calculo_cargas.propuestas(POR_CLAVE[clave], area)
            return {k: (valor, fuente) for k, (_c, valor, _u, fuente) in p.items()}

        r = self.v.preguntas.cargas_espacio(
            f"{e['codigo']} {e['nombre'] or ''}".strip(),
            uso or "",
            guardado["ajustes"] if guardado else {},
            guardado["fachadas"] if guardado else {},
            propuestas_de,
        )
        if r is not None:
            self.proyecto.fijar_cargas_espacio(e["id"], r.uso, r.ajustes, r.fachadas)
            self.v.refrescar()

    def accion_calcular(self) -> None:
        config = self.proyecto.cargas_config()
        if config is None:
            self.v.preguntas.informacion(
                "Calcular", "Primero «Clima y obra…»: la guía del IDAE y la obra."
            )
            return
        self.proyecto.estaciones(config["guia_documento_id"], self._esperar("Leyendo la guía…"))
        self.refrescar()

    def _destino(self, metodo: str, extension: str) -> Path | None:
        sugerido = self.proyecto.carpeta.raiz.parent / f"{self.proyecto.nombre} - cargas{extension}"
        return getattr(self.v.preguntas, metodo)(sugerido)

    def accion_excel(self) -> None:
        destino = self._destino("destino_excel", ".xlsx")
        if destino is not None:
            ruta = self.proyecto.exportar_cargas_excel(destino)
            self.v.preguntas.informacion("Informe Excel", f"Guardado en {ruta}")

    def accion_pdf(self) -> None:
        destino = self._destino("destino_pdf", ".pdf")
        if destino is not None:
            ruta = self.proyecto.exportar_cargas_pdf(destino)
            self.v.preguntas.informacion("Informe PDF", f"Guardado en {ruta}")

    # --- Contenido -----------------------------------------------------------------------

    def _espacio_elegido(self) -> dict | None:
        f = self.tabla_espacios.currentRow()
        item = self.tabla_espacios.item(f, 0) if f >= 0 else None
        if item is None:
            return None
        ident = item.data(Qt.UserRole)
        return next((e for e in self.proyecto.espacios() if e["id"] == ident), None)

    def _carga(self, espacio_id: str) -> calculo_cargas.CargaEspacio | None:
        if self._resultado is None:
            return None
        return next((c for c in self._resultado.espacios if c.espacio_id == espacio_id), None)

    def refrescar(self) -> None:
        from traza.ui.ventana import _llenar

        elegido = None
        f = self.tabla_espacios.currentRow()
        if f >= 0 and self.tabla_espacios.item(f, 0) is not None:
            elegido = self.tabla_espacios.item(f, 0).data(Qt.UserRole)
        self._resultado = None
        if self.proyecto is None:
            _llenar(self.tabla_espacios, [])
            self._al_elegir()
            self.visor.vacio()
            # Que el próximo proyecto se encuadre (salía a 1 m = 1 px; revisión 07-11-2026).
            self._encuadrado = False
            self._nivel_dibujado = None
            self.resumen.clear()
            return
        espacios = self.proyecto.espacios()
        config = self.proyecto.cargas_config()
        mensaje = ""
        if not espacios:
            mensaje = "No hay espacios: se crean en el paso «Planos y espacios»."
        elif config is None:
            mensaje = "Falta el clima y la obra: «Cargas → Clima y obra…»."
        elif not self.proyecto.guia_leida(config["guia_documento_id"]):
            mensaje = "Pulsa «Calcular» para leer la guía del IDAE y calcular."
        else:
            try:
                self._resultado = self.proyecto.calcular_cargas()
            except OrdenRechazada as exc:
                mensaje = f"⚠ {exc}"
            except Exception as exc:  # noqa: BLE001 — un dato roto no tumba la ventana
                # Si escapara, el resto del refresco de la ventana (historial, pendientes,
                # menús) no llegaría a ejecutarse (revisión 07-11-2026).
                mensaje = f"⚠ No se ha podido calcular: {type(exc).__name__}: {exc}"
        datos = self.proyecto.datos_cargas_espacios()
        filas, ids, propuestos = [], [], []
        for e in espacios:
            c = self._carga(e["id"])
            if c is not None:
                propuesto = c.uso_origen == calculo_cargas.PROPUESTA
                filas.append(
                    [
                        e["codigo"],
                        c.nombre,
                        c.uso.nombre,
                        _n(c.superficie_m2),
                        _n(c.invierno.total_w / 1000, 2),
                        _n(c.verano.total_w / 1000, 2),
                        _n(c.verano.total_w / c.superficie_m2, 0),
                        _n(c.aire_exterior_m3h, 0),
                    ]
                )
            else:
                guardado = datos.get(e["id"])
                clave = (
                    guardado["uso"]
                    if guardado
                    else calculo_cargas.uso_por_nombre(e["nombre"] or e["codigo"])
                )
                propuesto = not guardado
                uso = POR_CLAVE[clave].nombre if clave else "— elige —"
                filas.append(
                    [e["codigo"], e["nombre"] or "", uso, _n(e["superficie"]), "", "", "", ""]
                )
            propuestos.append(propuesto)
            ids.append(e["id"])
        _llenar(self.tabla_espacios, filas, ids)
        for fila, propuesto in enumerate(propuestos):
            item = self.tabla_espacios.item(fila, 2)
            if propuesto and item is not None:
                # Uso propuesto por el nombre: en gris, hasta que el usuario lo confirme.
                item.setForeground(Qt.gray)
                item.setToolTip("Propuesto por el nombre: confírmalo en «Datos del espacio…».")
        if elegido in ids:
            self.tabla_espacios.setCurrentCell(ids.index(elegido), 0)
        r = self._resultado
        if r is not None:
            mensaje = (
                f"Zona {r.zona} · calefacción {_n(r.invierno_total_w / 1000)} kW · "
                f"refrigeración {_n(r.verano_simultaneo_w / 1000)} kW (simultánea, "
                f"{r.hora_simultanea} h solar)"
            )
            self.resumen.setToolTip(
                f"Clima: {r.estacion.nombre} ({r.estacion.provincia}), guía del IDAE p. "
                f"{r.estacion.pagina}. Obra en {r.provincia} a {_n(r.altitud_obra_m, 0)} m."
            )
            if r.avisos:
                mensaje += "\n⚠ " + "\n⚠ ".join(r.avisos)
        self.resumen.setText(mensaje)
        elegido_e = next((e for e in espacios if e["id"] == elegido), None)
        self._dibujar(espacios, elegido_e["padre_id"] if elegido_e else None)
        self._al_elegir()

    def _dibujar(self, espacios: list[dict], nivel_id: str | None = None) -> None:
        """Un nivel cada vez (el del espacio elegido): con varias plantas superpuestas no se
        sabía de quién era cada fachada (revisión 07-11-2026)."""
        if not espacios:
            self.visor.vacio("Sin espacios")
            self._encuadrado = False
            self._nivel_dibujado = None
            return
        if nivel_id is None or all(e["padre_id"] != nivel_id for e in espacios):
            nivel_id = espacios[0]["padre_id"]
        del_nivel = [e for e in espacios if e["padre_id"] == nivel_id]
        self.visor.dibujar(
            [], 1.0, None, [e["contorno"] for e in del_nivel], [], encuadrar=not self._encuadrado
        )
        self._encuadrado = True
        self._nivel_dibujado = nivel_id
        ids = {e["id"] for e in del_nivel}
        if self._resultado is not None:
            self.visor.marcar_fachadas(
                [
                    (t.inicio, t.fin)
                    for c in self._resultado.espacios
                    if c.espacio_id in ids
                    for t in c.tramos
                ]
            )

    def _al_elegir(self) -> None:
        from traza.ui.ventana import _llenar

        e = self._espacio_elegido() if self.proyecto is not None else None
        c = self._carga(e["id"]) if e is not None else None
        if c is None:
            _llenar(self.tabla_partidas, [])
            _llenar(self.tabla_datos, [])
            self.detalle.clear()
        else:
            personas = next(d.valor for d in c.datos if d.concepto == "Ocupación")
            fachadas = " · ".join(f"{s} {_n(v, 0)}" for s, v in c.fachadas_m.items()) or "ninguna"
            self.detalle.setText(
                f"{c.nivel} · {_n(personas)} personas · punta de verano a las "
                f"{c.verano.hora_solar} h solar ({_n(c.verano.t_exterior_c)} °C) · fachadas "
                f"(m): {fachadas}"
            )
            partidas = [
                [estacion, p.concepto, _n(p.sensible_w, 0), _n(p.latente_w, 0)]
                for estacion, res in (("Invierno", c.invierno), ("Verano", c.verano))
                for p in res.partidas
            ]
            _llenar(self.tabla_partidas, partidas)
            _llenar(
                self.tabla_datos,
                [
                    [
                        d.concepto,
                        d.valor if isinstance(d.valor, str) else _n(d.valor, 2),
                        d.unidad,
                        d.origen,
                        d.fuente,
                    ]
                    for d in c.datos
                ],
            )
        if e is not None and e["padre_id"] != self._nivel_dibujado:
            self._dibujar(self.proyecto.espacios(), e["padre_id"])
        self.visor.resaltar(e["contorno"] if e is not None else None, centrar=False)

    def actualizar_estado(self, hay: bool) -> None:
        from traza.ui.ventana import PASOS

        con_paso = hay and any(
            clave == "cargas" and self.proyecto.encargo in encargos for clave, _, encargos in PASOS
        )
        self.v.menu_cargas.menuAction().setVisible(con_paso)
        for a in (self.a_clima, self.a_espacio, self.a_calcular):
            a.setEnabled(con_paso)
        hay_resultado = con_paso and self._resultado is not None
        self.a_excel.setEnabled(hay_resultado)
        self.a_pdf.setEnabled(hay_resultado)
