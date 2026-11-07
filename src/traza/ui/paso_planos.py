"""Paso «Planos y espacios» (encargos con diseño). docs/modules/geometria.md, ADR-0014.

Flujo (decisiones del usuario, 06-11-2026):
1. «Leer plano DXF…»: se elige un DXF ya incorporado en Documentación, se confirma la unidad
   viendo cuánto mide el dibujo y se marcan las capas de espacios, obstáculos y nombres.
2. Las propuestas (contornos cerrados de esas capas) se ven en la lista y en el visor; cada
   una se confirma (con su nivel y nombre) o se descarta.
3. Niveles con cota y altura libre; los espacios heredan la altura salvo excepción.
4. Bloques por espacio y longitudes por capa, y su Excel.

La página no habla con la base de datos: todo pasa por `Proyecto` y órdenes, y las
preguntas por `ventana.preguntas` (las pruebas las sustituyen).
"""

from __future__ import annotations

from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from traza.app import planos as calculo_planos
from traza.app.ordenes import CrearNivel, FijarAlturaEspacio, QuitarDePlano, RecuperarPropuesta
from traza.core.numeros import escribir_numero
from traza.io.dxf import UNIDADES
from traza.ui.dialogos_planos import CapaInfo, DatosCapas, InfoPlano
from traza.ui.visor_plano import VisorPlano

NO_CONSTA = "no consta"


def _m(v: float | None, decimales: int = 2) -> str:
    return NO_CONSTA if v is None else escribir_numero(round(v, decimales))


class PaginaPlanos(QWidget):
    def __init__(self, ventana) -> None:
        super().__init__()
        self.v = ventana
        from traza.ui.ventana import _barra, _tabla  # mismas tablas y barras que el resto

        self.selector = QComboBox()
        self.selector.currentIndexChanged.connect(
            lambda _i: self.v._proteger("Plano", self._al_cambiar_plano)
        )
        self.resumen = QLabel()
        self.resumen.setWordWrap(True)
        self.tabla_propuestas = _tabla(
            ["Tipo", "Capa", "Superficie (m²)", "Nombre del plano", "Revisar"]
        )
        self.tabla_espacios = _tabla(
            [
                "Código",
                "Nombre",
                "Nivel",
                "Superficie (m²)",
                "Perímetro (m)",
                "Altura (m)",
                "Altura de",
            ]
        )
        self.tabla_obstaculos = _tabla(
            [
                "Código",
                "Nombre",
                "Nivel",
                "Superficie (m²)",
                "Cota inferior (m)",
                "Altura (m)",
                "Altura de",
            ]
        )
        self.tabla_niveles = _tabla(["Código", "Nombre", "Cota (m)", "Altura libre (m)"])
        self.tabla_bloques = _tabla(["Bloque", "Capa", "Espacio", "Cantidad"])
        self.tabla_longitudes = _tabla(["Capa", "Longitud en planta (m)", "Visible", "Sin medir"])
        for t in (self.tabla_propuestas, self.tabla_espacios, self.tabla_obstaculos):
            t.itemSelectionChanged.connect(self._al_elegir_fila)
        self.pestanas = QTabWidget()
        for tabla, titulo in (
            (self.tabla_propuestas, "Propuestas"),
            (self.tabla_espacios, "Espacios"),
            (self.tabla_obstaculos, "Obstáculos"),
            (self.tabla_niveles, "Niveles"),
            (self.tabla_bloques, "Bloques"),
            (self.tabla_longitudes, "Longitudes por capa"),
        ):
            self.pestanas.addTab(tabla, titulo)
        self.pestanas.currentChanged.connect(lambda _i: self._al_elegir_fila())
        self.visor = VisorPlano()

        self._crear_acciones()
        cabecera = QHBoxLayout()
        cabecera.addWidget(QLabel("Plano:"))
        cabecera.addWidget(self.selector, 1)
        division = QSplitter(Qt.Horizontal)
        izquierda = QWidget()
        li = QVBoxLayout(izquierda)
        li.setContentsMargins(0, 0, 0, 0)
        li.addWidget(self.pestanas)
        division.addWidget(izquierda)
        division.addWidget(self.visor)
        division.setStretchFactor(0, 2)
        division.setStretchFactor(1, 3)
        caja = QVBoxLayout(self)
        caja.addWidget(
            _barra(
                [
                    self.a_leer,
                    self.a_capas,
                    self.a_nivel,
                    self.a_confirmar,
                    self.a_descartar,
                    self.a_altura,
                    self.a_quitar,
                    self.a_exportar,
                ]
            )
        )
        caja.addLayout(cabecera)
        caja.addWidget(self.resumen)
        caja.addWidget(division, 1)
        self._propuestas: list[calculo_planos.Propuesta] = []
        self._espacios: list[dict] = []
        self._obstaculos: list[dict] = []

    # --- Acciones ----------------------------------------------------------------------

    def _crear_acciones(self) -> None:
        m = self.v.menu_planos
        a = self.v._accion
        self.a_leer = a(m, "Leer plano DXF…", self.accion_leer)
        self.a_capas = a(m, "Capas y unidad…", self.accion_capas)
        m.addSeparator()
        self.a_nivel = a(m, "Nuevo nivel…", self.accion_nivel)
        self.a_confirmar = a(m, "Confirmar propuesta…", self.accion_confirmar)
        self.a_descartar = a(m, "Descartar propuesta", self.accion_descartar)
        self.a_recuperar = a(m, "Recuperar propuestas descartadas…", self.accion_recuperar)
        self.a_altura = a(m, "Altura del espacio…", self.accion_altura)
        self.a_quitar = a(m, "Quitar espacio, obstáculo o nivel", self.accion_quitar)
        m.addSeparator()
        self.a_exportar = a(m, "Exportar Excel del plano…", self.accion_exportar)

    @property
    def proyecto(self):
        return self.v.proyecto

    def _dxf_por_leer(self) -> list[dict]:
        leidos = {p["documento_id"] for p in self.proyecto.planos()}
        return [
            d
            for d in self.proyecto.documentos()
            if d["extension"].lower() == ".dxf" and d["id"] not in leidos
        ]

    def _info(self, documento: dict) -> InfoPlano:
        plano = self.proyecto.plano_dxf(
            documento["id"],
            esperar=lambda f: self.v._en_segundo_plano(f, "Leyendo el plano DXF…", "Leer plano"),
        )
        contornos = Counter(c.capa for c in plano.contornos)
        textos = Counter(t.capa for t in plano.textos)
        capas = tuple(
            CapaInfo(
                c.nombre,
                contornos.get(c.nombre, 0),
                textos.get(c.nombre, 0),
                sum(c.entidades.values()),
                c.visible,
            )
            for c in sorted(plano.capas.values(), key=lambda c: c.nombre.lower())
            if sum(c.entidades.values())
        )
        return InfoPlano(
            documento["nombre_original"],
            capas,
            plano.unidad_propuesta,
            {u: plano.medida_total(u) for u in UNIDADES},
            tuple(plano.avisos),
        )

    def accion_leer(self) -> None:
        docs = self._dxf_por_leer()
        if not docs:
            self.v.preguntas.aviso(
                "Leer plano DXF",
                "No hay ningún DXF sin leer. Incorpora antes el plano en «Documentación» "
                "(en AutoCAD: Guardar como… DXF).",
            )
            return
        i = self.v.preguntas.elegir(
            "Leer plano DXF", "Plano:", [d["nombre_original"] for d in docs]
        )
        if i is None:
            return
        doc = docs[i]
        datos = self.v.preguntas.capas_plano(self._info(doc))
        if datos is None:
            return
        plano_id = self.proyecto.leer_plano(
            doc["id"], datos.unidad, datos.espacios, datos.obstaculos, datos.textos
        )
        self.v.refrescar()
        self._elegir_plano(plano_id)

    def accion_capas(self) -> None:
        p = self.proyecto.plano(self.plano_id())
        doc = next(d for d in self.proyecto.documentos() if d["id"] == p["documento_id"])
        actual = DatosCapas(
            p["unidad"], p["capas_espacios"], p["capas_obstaculos"], p["capas_textos"]
        )
        datos = self.v.preguntas.capas_plano(self._info(doc), actual)
        if datos is not None:
            self.proyecto.cambiar_plano(
                p["id"], datos.unidad, datos.espacios, datos.obstaculos, datos.textos
            )

    def accion_nivel(self) -> None:
        r = self.v.preguntas.nuevo_nivel()
        if r is not None:
            self.v._ejecutar(CrearNivel(*r))

    def accion_confirmar(self) -> None:
        prop = self._propuesta_elegida()
        if prop is None:
            return
        if not self.proyecto.niveles():
            self.v.preguntas.informacion(
                "Primero un nivel",
                "Los espacios y obstáculos cuelgan de un nivel (planta baja, entreplanta…). "
                "Créalo ahora.",
            )
            self.accion_nivel()
            if not self.proyecto.niveles():
                return
        datos = self.v.preguntas.confirmar_contorno(
            {
                "rol": prop.rol,
                "capa": prop.capa,
                "superficie": prop.superficie,
                "textos": [(t.handle, t.texto) for t in prop.textos],
            },
            self.proyecto.niveles(),
        )
        if datos is None:
            return
        self.proyecto.confirmar_contorno(
            self.plano_id(),
            prop.handle,
            datos.nivel_id,
            nombre=datos.nombre,
            texto_handle=datos.texto_handle,
            altura=datos.altura,
            cota_inferior=datos.cota_inferior,
        )

    def accion_descartar(self) -> None:
        prop = self._propuesta_elegida()
        if prop is not None:
            self.proyecto.descartar_propuesta(self.plano_id(), prop.handle)

    def accion_recuperar(self) -> None:
        p = self.proyecto.plano(self.plano_id())
        if not p["descartados"]:
            self.v.preguntas.informacion("Recuperar", "No hay propuestas descartadas.")
            return
        i = self.v.preguntas.elegir(
            "Recuperar propuesta", "Entidad del DXF:", list(p["descartados"])
        )
        if i is not None:
            self.v._ejecutar(RecuperarPropuesta(p["id"], p["descartados"][i]))

    def accion_altura(self) -> None:
        e = self._fila_elegida(self.tabla_espacios, self._espacios)
        if e is None:
            return
        r = self.v.preguntas.altura_espacio(e)
        if r is not None:
            modo, altura, minima, maxima = r
            self.v._ejecutar(FijarAlturaEspacio(e["id"], modo, altura, minima, maxima))

    def accion_quitar(self) -> None:
        pestana = self.pestanas.currentWidget()
        fuentes = {
            self.tabla_espacios: self._espacios,
            self.tabla_obstaculos: self._obstaculos,
            self.tabla_niveles: self.proyecto.niveles(),
        }
        if pestana not in fuentes:
            return
        el = self._fila_elegida(pestana, fuentes[pestana])
        if el is not None and self.v.preguntas.confirmar(
            "Quitar",
            f"Se quita «{el['codigo']} {el.get('nombre') or ''}». Un espacio u obstáculo "
            "vuelve a las propuestas. Se puede deshacer. ¿Continuar?",
        ):
            self.v._ejecutar(QuitarDePlano(el["id"]))

    def accion_exportar(self) -> None:
        p = self.proyecto.plano(self.plano_id())
        nombre = p["documento_nombre"].rsplit(".", 1)[0]
        sugerido = self.proyecto.carpeta.exportaciones / f"{self.proyecto.nombre} - {nombre}.xlsx"
        destino = self.v.preguntas.destino_excel(sugerido)
        if destino is not None:
            ruta = self.proyecto.exportar_plano_excel(p["id"], destino)
            self.v.statusBar().showMessage(f"Excel guardado: {ruta}", 10000)

    # --- Selección ---------------------------------------------------------------------

    def plano_id(self) -> str | None:
        return self.selector.currentData()

    def _elegir_plano(self, plano_id: str) -> None:
        i = self.selector.findData(plano_id)
        if i >= 0:
            self.selector.setCurrentIndex(i)

    @staticmethod
    def _fila_elegida(tabla, filas: list):
        f = tabla.currentRow()
        if f < 0 or f >= len(filas):
            return None
        item = tabla.item(f, 0)
        ident = item.data(Qt.UserRole) if item else None
        return next(
            (x for x in filas if (x["id"] if isinstance(x, dict) else x.handle) == ident), None
        )

    def _propuesta_elegida(self) -> calculo_planos.Propuesta | None:
        p = self._fila_elegida(self.tabla_propuestas, self._propuestas)
        if p is None:
            self.v.preguntas.aviso("Propuestas", "Elige una propuesta de la lista.")
        return p

    def _al_elegir_fila(self) -> None:
        pestana = self.pestanas.currentWidget()
        contorno = None
        if pestana is self.tabla_propuestas:
            p = self._fila_elegida(self.tabla_propuestas, self._propuestas)
            contorno = p.contorno if p else None
        elif pestana is self.tabla_espacios:
            e = self._fila_elegida(self.tabla_espacios, self._espacios)
            contorno = e["contorno"] if e else None
        elif pestana is self.tabla_obstaculos:
            o = self._fila_elegida(self.tabla_obstaculos, self._obstaculos)
            contorno = o["contorno"] if o else None
        self.visor.resaltar(contorno)
        self.actualizar_estado(self.proyecto is not None)

    def _al_cambiar_plano(self) -> None:
        self._refrescar_contenido()
        self.actualizar_estado(self.proyecto is not None)

    # --- Refresco ----------------------------------------------------------------------

    def refrescar(self) -> None:
        elegido = self.plano_id()
        self.selector.blockSignals(True)
        try:
            self.selector.clear()
            if self.proyecto is not None:
                for p in self.proyecto.planos():
                    self.selector.addItem(p["documento_nombre"], p["id"])
                if elegido is not None:
                    self._elegir_plano(elegido)
        finally:
            self.selector.blockSignals(False)
        self._refrescar_contenido()

    def _refrescar_contenido(self) -> None:
        from traza.ui.ventana import _llenar

        plano_id = self.plano_id() if self.proyecto is not None else None
        if plano_id is None:
            for t in (
                self.tabla_propuestas,
                self.tabla_espacios,
                self.tabla_obstaculos,
                self.tabla_bloques,
                self.tabla_longitudes,
            ):
                _llenar(t, [])
            _llenar(
                self.tabla_niveles,
                [] if self.proyecto is None else self._filas_niveles()[0],
                None if self.proyecto is None else self._filas_niveles()[1],
            )
            self._propuestas, self._espacios, self._obstaculos = [], [], []
            self.resumen.setText("" if self.proyecto is None else "Lee un plano DXF para empezar.")
            self.visor.vacio()
            return
        p = self.proyecto.plano(plano_id)
        plano = self.proyecto.plano_dxf(p["documento_id"])
        f = UNIDADES[p["unidad"]]
        self._propuestas = self.proyecto.propuestas(plano_id)
        self._espacios = [e for e in self.proyecto.espacios() if e["plano_id"] == plano_id]
        self._obstaculos = [o for o in self.proyecto.obstaculos() if o["plano_id"] == plano_id]
        _llenar(
            self.tabla_propuestas,
            [
                [
                    calculo_planos.ROLES[x.rol],
                    x.capa,
                    _m(x.superficie),
                    x.nombre_sugerido.texto
                    if x.nombre_sugerido
                    else (f"{len(x.textos)} textos: elige" if x.textos else ""),
                    "; ".join(
                        a
                        for a, si in (
                            ("se corta a sí mismo", x.autointersecante),
                            ("no venía cerrada", not x.marcada_cerrada),
                        )
                        if si
                    ),
                ]
                for x in self._propuestas
            ],
            [x.handle for x in self._propuestas],
        )
        _llenar(
            self.tabla_espacios,
            [
                [
                    e["codigo"],
                    e["nombre"] or NO_CONSTA,
                    e["nivel_nombre"] or "",
                    _m(e["superficie"]),
                    _m(e["perimetro"]),
                    self._altura(e),
                    e["altura_origen"] or "",
                ]
                for e in self._espacios
            ],
            [e["id"] for e in self._espacios],
        )
        _llenar(
            self.tabla_obstaculos,
            [
                [
                    o["codigo"],
                    o["nombre"] or "",
                    o["nivel_nombre"] or "",
                    _m(o["superficie"], 3),
                    _m(o["cota_inferior"]),
                    self._altura(o),
                    o["altura_origen"] or "",
                ]
                for o in self._obstaculos
            ],
            [o["id"] for o in self._obstaculos],
        )
        filas, ids = self._filas_niveles()
        _llenar(self.tabla_niveles, filas, ids)
        bloques = self.proyecto.bloques_por_espacio(plano_id)
        _llenar(
            self.tabla_bloques,
            [[b.bloque, b.capa, b.espacio, str(b.cantidad)] for b in bloques.filas],
        )
        _llenar(
            self.tabla_longitudes,
            [
                [x.capa, _m(x.longitud_m), "Sí" if x.visible else "No", str(x.sin_medir or "")]
                for x in self.proyecto.longitudes_por_capa(plano_id)
            ],
        )
        n_espacios = len([x for x in self._propuestas if x.rol == "espacio"])
        n_obstaculos = len(self._propuestas) - n_espacios
        superficie = sum(e["superficie"] or 0 for e in self._espacios)
        self.resumen.setText(
            f"Unidad «{p['unidad']}» · espacios: {', '.join(p['capas_espacios']) or '—'} · "
            f"obstáculos: {', '.join(p['capas_obstaculos']) or '—'} · nombres: "
            f"{', '.join(p['capas_textos']) or 'todas'}. Pendientes de revisar: {n_espacios} "
            f"espacio(s) y {n_obstaculos} obstáculo(s). Confirmados: {len(self._espacios)} "
            f"espacio(s), {_m(superficie)} m²."
            + (
                f" ⚠ {len(plano.avisos)} aviso(s) de lectura (ver Excel, hoja Información)."
                if plano.avisos
                else ""
            )
        )
        self.visor.dibujar(
            plano.trazos,
            f,
            None,
            [e["contorno"] for e in self._espacios],
            [o["contorno"] for o in self._obstaculos],
        )

    def _filas_niveles(self) -> tuple[list[list[str]], list[str]]:
        niveles = self.proyecto.niveles()
        return (
            [
                [n["codigo"], n["nombre"] or "", _m(n["cota"]), _m(n["altura_libre"])]
                for n in niveles
            ],
            [n["id"] for n in niveles],
        )

    @staticmethod
    def _altura(e: dict) -> str:
        if e["altura_origen"] == "inclinada":
            return f"{_m(e['altura_minima'])} a {_m(e['altura_maxima'])}"
        return _m(e["altura"])

    def actualizar_estado(self, hay: bool) -> None:
        plano = hay and self.plano_id() is not None
        self.a_leer.setEnabled(hay)
        self.a_nivel.setEnabled(hay)
        for a in (self.a_capas, self.a_exportar, self.a_recuperar):
            a.setEnabled(plano)
        pestana = self.pestanas.currentWidget()
        hay_prop = (
            plano and pestana is self.tabla_propuestas and self.tabla_propuestas.currentRow() >= 0
        )
        self.a_confirmar.setEnabled(hay_prop)
        self.a_descartar.setEnabled(hay_prop)
        self.a_altura.setEnabled(
            hay and pestana is self.tabla_espacios and self.tabla_espacios.currentRow() >= 0
        )
        self.a_quitar.setEnabled(
            hay
            and pestana in (self.tabla_espacios, self.tabla_obstaculos, self.tabla_niveles)
            and pestana.currentRow() >= 0
        )
