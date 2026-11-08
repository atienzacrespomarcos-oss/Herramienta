"""Paso «Sistema hidráulico» (Etapa 7, docs/modules/hidronica.md).

Presentación limpia (usuario, 07-11-2026): en pantalla lo que decide (generador, primario,
colectores, inercia, vaso, presiones y cada circuito); la lista completa de elementos, en
su pestaña y en el Excel.
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QTabWidget, QVBoxLayout, QWidget

from traza.app.ordenes import TIPOS_SISTEMA, OrdenRechazada
from traza.core.numeros import escribir_numero
from traza.engines.hidraulica import SERVICIOS
from traza.ui.paso_redes import _archivo

MCA = 9806.65


def _n(v, decimales: int = 1) -> str:
    return "" if v is None else escribir_numero(round(float(v), decimales))


def _circuitos(n: int) -> str:
    return f"{n} circuito" if n == 1 else f"{n} circuitos"


class PaginaHidronica(QWidget):
    def __init__(self, ventana) -> None:
        super().__init__()
        self.v = ventana
        from traza.ui.ventana import _barra, _tabla

        self.selector = QComboBox()
        self.selector.currentIndexChanged.connect(
            lambda _i: self.v._proteger("Sistema hidráulico", self._refrescar_contenido)
        )
        self.resumen = QLabel()
        self.resumen.setWordWrap(True)
        self.tabla_resumen = _tabla(["Servicio", "Concepto", "Valor"])
        self.tabla_circuitos = _tabla(
            [
                "Servicio",
                "Circuito",
                "Caudal (m³/h)",
                "Tubería",
                "m/s",
                "Pa/m",
                "Bomba (m c.a.)",
                "Conexión",
                "Kv",
            ]
        )
        self.tabla_elementos = _tabla(["Zona", "Elemento", "Especificación", "DN", "Cantidad"])
        self.pestanas = QTabWidget()
        self.pestanas.addTab(self.tabla_resumen, "Sala de máquinas")
        self.pestanas.addTab(self.tabla_circuitos, "Circuitos")
        self.pestanas.addTab(self.tabla_elementos, "Elementos")
        m = self.v.menu_hidronica
        a = self.v._accion
        self.a_nuevo = a(m, "Nuevo sistema…", self.accion_nuevo)
        self.a_cambiar = a(m, "Cambiar sistema…", self.accion_cambiar)
        self.a_borrar = a(m, "Borrar sistema", self.accion_borrar)
        m.addSeparator()
        self.a_excel = a(m, "Exportar listado Excel…", self.accion_excel)
        cabecera = QHBoxLayout()
        cabecera.addWidget(QLabel("Sistema:"))
        cabecera.addWidget(self.selector, 1)
        caja = QVBoxLayout(self)
        caja.addWidget(_barra([self.a_nuevo, self.a_cambiar, self.a_borrar, self.a_excel]))
        caja.addLayout(cabecera)
        caja.addWidget(self.resumen)
        caja.addWidget(self.pestanas, 1)
        self._resultado = None

    @property
    def proyecto(self):
        return self.v.proyecto

    def sistema_id(self) -> str | None:
        return self.selector.currentData()

    # --- Acciones ----------------------------------------------------------------------

    def _pedir(self, actual: dict | None) -> None:
        espacios = [
            {"id": e["id"], "codigo": e["codigo"], "nombre": e["nombre"]}
            for e in self.proyecto.espacios()
        ]
        if not espacios:
            self.v.preguntas.aviso(
                "Sistema hidráulico",
                "Primero confirma los espacios en «Planos y espacios» y calcula sus cargas.",
            )
            return
        r = self.v.preguntas.sistema_hidraulico(espacios, actual)
        if r is None:
            return
        sid = self.proyecto.definir_sistema_hidraulico(**r)
        self.v.refrescar()
        self._elegir(sid)

    def accion_nuevo(self) -> None:
        self._pedir(None)

    def accion_cambiar(self) -> None:
        if self.sistema_id() is None:
            self.v.preguntas.informacion("Cambiar sistema", "No hay ningún sistema elegido.")
            return
        self._pedir(self.proyecto.sistema_hidraulico(self.sistema_id()))

    def accion_borrar(self) -> None:
        if self.sistema_id() is None:
            return
        s = self.proyecto.sistema_hidraulico(self.sistema_id())
        if self.v.preguntas.confirmar(
            "Borrar sistema", f"Se borra el sistema «{s['nombre']}». Se puede deshacer. ¿Continuar?"
        ):
            self.proyecto.borrar_sistema_hidraulico(s["id"])
            self.v.refrescar()

    def accion_excel(self) -> None:
        if self.sistema_id() is None:
            return
        s = self.proyecto.sistema_hidraulico(self.sistema_id())
        destino = self.v.preguntas.destino_excel(
            self.proyecto.carpeta.raiz.parent
            / f"{_archivo(self.proyecto.nombre)} - {_archivo(s['nombre'])}.xlsx"
        )
        if destino is not None:
            ruta = self.proyecto.exportar_sistema_hidraulico_excel(s["id"], destino)
            self.v.preguntas.informacion("Listado Excel", f"Guardado en {ruta}")

    # --- Contenido -----------------------------------------------------------------------

    def _elegir(self, sid: str) -> None:
        i = self.selector.findData(sid)
        if i >= 0:
            self.selector.setCurrentIndex(i)

    def refrescar(self) -> None:
        elegido = self.sistema_id()
        self.selector.blockSignals(True)
        try:
            self.selector.clear()
            if self.proyecto is not None:
                for s in self.proyecto.sistemas_hidraulicos():
                    self.selector.addItem(f"{s['nombre']} ({TIPOS_SISTEMA[s['tipo']]})", s["id"])
                if elegido is not None:
                    self._elegir(elegido)
        finally:
            self.selector.blockSignals(False)
        self._refrescar_contenido()

    def _refrescar_contenido(self) -> None:
        from traza.ui.ventana import _llenar

        self._resultado = None
        tablas = (self.tabla_resumen, self.tabla_circuitos, self.tabla_elementos)
        if self.proyecto is None or self.sistema_id() is None:
            for t in tablas:
                _llenar(t, [])
            self.resumen.setText(
                ""
                if self.proyecto is None
                else "Crea un sistema: «Agua → Nuevo sistema…» (circuitos por grupos de espacios)."
            )
            return
        try:
            r = self.proyecto.calcular_sistema_hidraulico(self.sistema_id())
        except Exception as exc:  # noqa: BLE001 — un dato roto no tumba la ventana
            for t in tablas:
                _llenar(t, [])
            mensaje = (
                str(exc) if isinstance(exc, OrdenRechazada) else f"{type(exc).__name__}: {exc}"
            )
            self.resumen.setText(f"⚠ No se ha podido calcular el sistema: {mensaje}")
            return
        self._resultado = r
        resumen, circuitos = [], []
        for s in r.servicios:
            n = SERVICIOS[s.clave]
            p = s.presiones
            resumen += [
                [n, "Generador", f"{_n(s.potencia_kw)} kW · {_n(s.caudal_m3s * 3600, 2)} m³/h"],
                [
                    n,
                    "Primario",
                    f"{s.primario.tubo.nombre} · bomba {_n(s.altura_primario_pa / MCA)} m c.a.",
                ],
                [
                    n,
                    "Colectores",
                    f"{s.colector.tubo.nombre} ({_circuitos(len(s.circuitos))} + reserva)",
                ],
                [
                    n,
                    "Depósito de inercia",
                    f"≥ {_n(s.inercia_l, 0)} l · bocas {s.bocas_inercia.tubo.nombre}",
                ],
                [
                    n,
                    "Vaso de expansión",
                    f"≥ {_n(s.vaso_l, 1)} l · precarga {_n(p.inicial_vaso, 2)} bar",
                ],
                [
                    n,
                    "Presiones (bar)",
                    f"llenado {_n(p.llenado, 2)} · máxima {_n(p.maxima_servicio, 2)} · "
                    f"seguridad {_n(p.seguridad, 2)} · PN{p.nominal}",
                ],
            ]
            for c in s.circuitos:
                circuitos.append(
                    [
                        n,
                        c.datos.nombre,
                        _n(c.caudal_m3s * 3600, 2),
                        c.tubo.tubo.nombre,
                        _n(c.tubo.velocidad_m_s, 2),
                        _n(c.tubo.friccion_pa_m, 0),
                        _n(c.altura_bomba_pa / MCA),
                        c.conexion.tubo.nombre,
                        _n(c.kv_valvula, 2),
                    ]
                )
        _llenar(self.tabla_resumen, resumen)
        _llenar(self.tabla_circuitos, circuitos)
        _llenar(
            self.tabla_elementos,
            [
                [e.zona, e.elemento, e.especificacion, f"DN{e.dn}" if e.dn else "", str(e.cantidad)]
                for e in r.elementos
            ],
        )
        texto = f"{_n(r.potencia_total_kw)} kW · {len(r.elementos)} elementos en el esquema"
        if r.avisos:
            texto += "\n⚠ " + "\n⚠ ".join(r.avisos)
        self.resumen.setText(texto)

    def actualizar_estado(self, hay: bool) -> None:
        from traza.ui.ventana import PASOS

        con_paso = hay and any(
            clave == "hidronica" and self.proyecto.encargo in encargos
            for clave, _, encargos in PASOS
        )
        self.v.menu_hidronica.menuAction().setVisible(con_paso)
        self.a_nuevo.setEnabled(con_paso)
        hay_sistema = con_paso and self.sistema_id() is not None
        for a in (self.a_cambiar, self.a_borrar, self.a_excel):
            a.setEnabled(hay_sistema)
