"""Pasos de Obra: «Venta» y «Coste objetivo» (docs/modules/obra.md, bloque 1).

Presentación limpia: en pantalla, lo que decide (venta, objetivo, margen previsto y el
objetivo por paquete); lo que no casa entre venta y coste, en una línea de aviso.
"""

from __future__ import annotations

from collections import defaultdict

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from traza.app.ordenes import OrdenRechazada
from traza.core.numeros import escribir_numero


def _eur(v: float | None) -> str:
    """Como el resto de importes de la aplicación (ventana._dinero): «1.234,50 €»."""
    from traza.ui.ventana import _dinero

    return "—" if v is None else f"{_dinero(v)} €"


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{escribir_numero(round(v, 1))} %"


def _es_obra(pagina, hay: bool) -> bool:
    return hay and pagina.proyecto.encargo == "obra"


class _Pagina(QWidget):
    def __init__(self, ventana, columnas: list[str], acciones) -> None:
        super().__init__()
        self.v = ventana
        from traza.ui.ventana import _barra, _tabla

        self.resumen = QLabel()
        self.resumen.setWordWrap(True)
        self.avisos = QLabel()
        self.avisos.setWordWrap(True)
        self.tabla = _tabla(columnas)
        caja = QVBoxLayout(self)
        caja.addWidget(_barra(acciones))
        caja.addWidget(self.resumen)
        caja.addWidget(self.tabla, 1)
        caja.addWidget(self.avisos)

    @property
    def proyecto(self):
        return self.v.proyecto


class PaginaVenta(_Pagina):
    def __init__(self, ventana) -> None:
        m = ventana.menu_obra
        self.a_contratado = ventana._accion(
            m, "Presupuesto contratado…", lambda: self.accion_contratado()
        )
        self.a_quitar = ventana._accion(
            m, "Quitar presupuesto contratado", lambda: self.accion_quitar()
        )
        super().__init__(ventana, ["Capítulo", "Partidas", "Venta"], [self.a_contratado])

    def accion_contratado(self) -> None:
        meds = self.proyecto.mediciones()
        if not meds:
            self.v.preguntas.aviso(
                "Presupuesto contratado",
                "No hay ningún presupuesto leído: léelo antes en «Mediciones y ofertas» "
                "(BC3 o Excel de Presto, o el PDF del cliente).",
            )
            return
        i = self.v.preguntas.elegir(
            "Presupuesto contratado",
            "Presupuesto de venta de la obra:",
            [f"{m['documento_nombre']} · {m['nombre']}" for m in meds],
        )
        if i is not None:
            self.proyecto.fijar_venta_contratada(meds[i]["id"])
            self.v.refrescar()

    def accion_quitar(self) -> None:
        # Para volver a leer su documento o elegir otro; se puede deshacer.
        self.proyecto.quitar_venta_contratada()
        self.v.refrescar()

    def refrescar(self) -> None:
        from traza.ui.ventana import _llenar

        self.avisos.clear()
        if self.proyecto is None:
            self.resumen.clear()
            _llenar(self.tabla, [])
            return
        venta = self.proyecto.venta_contratada()
        if venta is None:
            self.resumen.setText(
                "Elige el presupuesto contratado: «Obra → Presupuesto contratado…»."
            )
            _llenar(self.tabla, [])
            return
        partidas = self.proyecto.partidas(venta["id"])
        por_capitulo: dict[str, list[float]] = defaultdict(lambda: [0, 0.0])
        for p in partidas:
            # Capítulo de primer nivel: [(código, resumen), …] desde la raíz.
            cap = " ".join(x for x in p["capitulo"][0] if x) if p["capitulo"] else "(sin capítulo)"
            por_capitulo[cap][0] += 1
            por_capitulo[cap][1] += round(p["importe"] or 0.0, 2)
        r = self.proyecto.resumen_obra()
        self.resumen.setText(
            f"Presupuesto contratado: {venta['documento_nombre']} · Venta: {_eur(r.venta)} "
            f"({len(partidas)} partidas)."
        )
        _llenar(
            self.tabla,
            [[cap, str(n), _eur(imp)] for cap, (n, imp) in por_capitulo.items()],
        )
        self.avisos.setText("\n".join(f"⚠ {a}" for a in r.avisos_venta))

    def actualizar_estado(self, hay: bool) -> None:
        con = _es_obra(self, hay)
        self.a_contratado.setEnabled(con)
        self.a_quitar.setEnabled(con and self.proyecto.venta_contratada() is not None)


class PaginaCosteObjetivo(_Pagina):
    def __init__(self, ventana) -> None:
        m = ventana.menu_obra
        self.a_importar = ventana._accion(
            m, "Importar coste objetivo (Excel de Presto)…", lambda: self.accion_importar()
        )
        super().__init__(ventana, ["Paquete", "Objetivo", "% del objetivo"], [self.a_importar])

    def accion_importar(self) -> None:
        docs = [
            d for d in self.proyecto.documentos() if d["extension"].lower() in (".xlsx", ".xlsm")
        ]
        if not docs:
            self.v.preguntas.aviso(
                "Coste objetivo",
                "Incorpora antes en «Documentación» el Excel de coste objetivo que exportas de "
                "Presto (agrupado por paquetes).",
            )
            return
        i = self.v.preguntas.elegir(
            "Coste objetivo", "Excel de coste objetivo:", [d["nombre_original"] for d in docs]
        )
        if i is None:
            return
        try:
            self.proyecto.importar_coste_objetivo(docs[i]["id"])
        finally:
            self.v.refrescar()

    def refrescar(self) -> None:
        from traza.ui.ventana import _llenar

        self.avisos.clear()
        if self.proyecto is None:
            self.resumen.clear()
            _llenar(self.tabla, [])
            return
        coste = self.proyecto.coste_objetivo()
        if coste is None:
            self.resumen.setText(
                "Importa el coste objetivo: «Obra → Importar coste objetivo (Excel de Presto)…»."
            )
            _llenar(self.tabla, [])
            return
        r = self.proyecto.resumen_obra()
        texto = (
            f"Coste objetivo ({coste['documento_nombre']}, hoja «{coste['hoja']}»): "
            f"{_eur(r.objetivo)}"
        )
        if r.venta is not None:
            texto += (
                f" · Venta: {_eur(r.venta)} · Margen previsto: {_eur(r.margen)} "
                f"({_pct(r.margen_pct)})"
            )
        self.resumen.setText(texto + ".")
        total = r.objetivo or 0.0

        def pct(imp: float) -> str:
            # Con objetivo 0 (p. ej. fórmulas sin resultado guardado) no hay porcentaje.
            return _pct(100 * imp / total if total else None)

        filas = [[nombre, _eur(imp), pct(imp)] for nombre, imp in r.paquetes.items()]
        sin_paquete = total - sum(r.paquetes.values())
        if round(abs(sin_paquete), 2) > 0.01:  # la misma tolerancia que el lector
            filas.append(["(sin repartir en paquetes)", _eur(sin_paquete), pct(sin_paquete)])
        _llenar(self.tabla, filas)
        avisos = []
        if r.solo_en_venta or r.solo_en_coste:
            avisos.append(
                f"Partidas que no casan por código: {len(r.solo_en_venta)} solo en la venta, "
                f"{len(r.solo_en_coste)} solo en el coste: revisa sus códigos en Presto."
            )
        if r.venta_sin_codigo:
            avisos.append(
                f"{r.venta_sin_codigo} partida(s) de venta sin código no se pueden enlazar."
            )
        # Las líneas añadidas a mano, en un solo renglón (una por línea saturaba la
        # pantalla); el detalle, en el aviso de cada una al importar.
        manuales = [a for a in r.avisos_coste if a.startswith("Línea añadida a mano")]
        if manuales:
            avisos.append(f"{len(manuales)} línea(s) añadida(s) a mano cuentan en el objetivo.")
        avisos += [a for a in r.avisos_coste if a not in manuales]
        self.avisos.setText("\n".join(f"⚠ {a}" for a in avisos))

    def actualizar_estado(self, hay: bool) -> None:
        con = _es_obra(self, hay)
        self.a_importar.setEnabled(con)
        # Con un proyecto abierto, solo en Obra (como sus pasos); sin proyecto se ve
        # deshabilitado, como los demás menús.
        self.v.menu_obra.menuAction().setVisible(not hay or con)


def _fecha_es(iso: str | None) -> str:
    """AAAA-MM-DD(…) → DD-MM-AAAA."""
    if not iso:
        return ""
    a, m, d = iso[:10].split("-")
    return f"{d}-{m}-{a}"


class PaginaCosteReal(QWidget):
    """Facturas por paquete y estado de cada paquete (docs/modules/obra.md, bloque 2a).
    Arriba los paquetes (objetivo frente a facturado: dónde se descuadra); abajo, las
    facturas del paquete elegido."""

    def __init__(self, ventana) -> None:
        super().__init__()
        self.v = ventana
        from traza.ui.ventana import _barra, _tabla

        m = ventana.menu_obra
        m.addSeparator()
        a = ventana._accion
        self.a_factura = a(m, "Nueva factura…", lambda: self.accion_factura())
        self.a_corregir = a(m, "Corregir factura…", lambda: self.accion_corregir())
        self.a_quitar = a(m, "Quitar factura", lambda: self.accion_quitar())
        self.a_cerrar = a(m, "Cerrar paquete", lambda: self.accion_cerrar(True))
        self.a_reabrir = a(m, "Reabrir paquete", lambda: self.accion_cerrar(False))
        self.resumen = QLabel()
        self.resumen.setWordWrap(True)
        self.tabla = _tabla(["Paquete", "Objetivo", "Facturado", "Diferencia", "Estado"])
        self.tabla.itemSelectionChanged.connect(lambda: self._refrescar_facturas())
        self.facturas = _tabla(["Fecha", "Proveedor", "Nº", "Importe"])
        self.avisos = QLabel()
        self.avisos.setWordWrap(True)
        caja = QVBoxLayout(self)
        caja.addWidget(
            _barra([self.a_factura, self.a_corregir, self.a_quitar, self.a_cerrar, self.a_reabrir])
        )
        caja.addWidget(self.resumen)
        caja.addWidget(self.tabla, 2)
        caja.addWidget(QLabel("Facturas del paquete elegido:"))
        caja.addWidget(self.facturas, 1)
        caja.addWidget(self.avisos)

    @property
    def proyecto(self):
        return self.v.proyecto

    def paquete(self) -> str | None:
        fila = self.tabla.currentRow()
        item = self.tabla.item(fila, 0) if fila >= 0 else None
        return item.text() if item else None

    def factura_id(self) -> str | None:
        from PySide6.QtCore import Qt

        fila = self.facturas.currentRow()
        item = self.facturas.item(fila, 0) if fila >= 0 else None
        return item.data(Qt.UserRole) if item else None

    # --- Acciones ------------------------------------------------------------------------

    def _pedir(self, actual: dict | None) -> None:
        paquetes = list(self.proyecto.coste_objetivo()["paquetes"])
        if actual and actual.get("paquete") and actual["paquete"] not in paquetes:
            # Factura de un paquete que ya no está en el objetivo: el diálogo lo enseña tal
            # cual (no lo cambia en silencio por el primero); la orden pide elegir otro.
            paquetes.append(actual["paquete"])
        # Si la orden rechaza algo, el diálogo vuelve con lo escrito.
        while True:
            datos = self.v.preguntas.factura(paquetes, actual)
            if datos is None:
                return
            try:
                self.proyecto.registrar_factura(**datos)
            except OrdenRechazada as exc:
                self.v.preguntas.aviso("Factura", str(exc))
                actual = {**datos, "id": datos.get("id")}
                continue
            break
        self.v.refrescar()
        self._elegir(datos["paquete"])

    def accion_factura(self) -> None:
        # Con un paquete elegido en la lista, el diálogo sale con él.
        self._pedir({"paquete": self.paquete()} if self.paquete() else None)

    def accion_corregir(self) -> None:
        fid = self.factura_id()
        if fid is None:
            self.v.preguntas.aviso("Corregir factura", "Elige una factura de la lista de abajo.")
            return
        self._pedir(next(f for f in self.proyecto.facturas() if f["id"] == fid))

    def accion_quitar(self) -> None:
        fid = self.factura_id()
        if fid is None:
            self.v.preguntas.aviso("Quitar factura", "Elige una factura de la lista de abajo.")
            return
        paquete = self.paquete()
        self.proyecto.quitar_factura(fid)
        self.v.refrescar()
        self._elegir(paquete)

    def accion_cerrar(self, cerrar: bool) -> None:
        paquete = self.paquete()
        if paquete is None:
            self.v.preguntas.aviso("Paquete", "Elige un paquete de la lista.")
            return
        self.proyecto.cerrar_paquete(paquete, cerrar)
        self.v.refrescar()
        self._elegir(paquete)

    def _elegir(self, paquete: str | None) -> None:
        for i in range(self.tabla.rowCount()):
            if self.tabla.item(i, 0).text() == paquete:
                self.tabla.setCurrentCell(i, 0)
                return

    # --- Estado --------------------------------------------------------------------------

    def refrescar(self) -> None:
        from traza.ui.ventana import _llenar

        elegido = self.paquete()
        self.avisos.clear()
        if self.proyecto is None or self.proyecto.coste_objetivo() is None:
            self.resumen.setText(
                ""
                if self.proyecto is None
                else "Importa antes el coste objetivo: las facturas se apuntan a sus paquetes."
            )
            _llenar(self.tabla, [])
            _llenar(self.facturas, [])
            return
        f = self.proyecto.foto_obra()
        self.resumen.setText(
            f"Objetivo: {_eur(f.objetivo)} · Facturado: {_eur(f.facturado)} · "
            f"Diferencia: {_eur((f.objetivo or 0) - f.facturado)}."
        )
        _llenar(
            self.tabla,
            [
                [
                    x.nombre,
                    _eur(x.objetivo),
                    _eur(x.facturado),
                    _eur(x.diferencia),
                    ("Cerrado" if x.cerrado else "Abierto")
                    + ("" if x.en_objetivo else " · ya no está en el objetivo"),
                ]
                for x in f.paquetes
            ],
        )
        avisos = []
        if f.descuadrados:
            avisos.append(
                "Se han pasado del objetivo: "
                + ", ".join(f"{x.nombre} ({_eur(-x.diferencia)})" for x in f.descuadrados)
                + "."
            )
        if f.huerfanas:
            avisos.append(
                "Facturas de paquetes que ya no están en el coste objetivo: "
                + ", ".join(f"{n} ({_eur(v)})" for n, v in f.huerfanas.items())
                + "."
            )
        self.avisos.setText("\n".join(f"⚠ {a}" for a in avisos))
        self._elegir(elegido)
        self._refrescar_facturas()

    def _refrescar_facturas(self) -> None:
        from traza.ui.ventana import _llenar

        paquete = self.paquete()
        filas = [x for x in self.proyecto.facturas() if x["paquete"] == paquete] if paquete else []
        _llenar(
            self.facturas,
            [
                [_fecha_es(x["fecha"]), x["proveedor"], x["numero"], _eur(x["importe"])]
                for x in filas
            ],
            [x["id"] for x in filas],
        )

    def actualizar_estado(self, hay: bool) -> None:
        con = _es_obra(self, hay) and self.proyecto.coste_objetivo() is not None
        for a in (self.a_factura, self.a_corregir, self.a_quitar, self.a_cerrar, self.a_reabrir):
            a.setEnabled(con)


class PaginaPrevision(QWidget):
    """Foto de lo real y previsión del usuario (dos totales; TRAZA no la estima)."""

    def __init__(self, ventana) -> None:
        super().__init__()
        self.v = ventana
        from traza.ui.ventana import _barra, _tabla

        m = ventana.menu_obra
        m.addSeparator()
        self.a_prevision = ventana._accion(
            m, "Actualizar mi previsión…", lambda: self.accion_prevision()
        )
        self.resumen = QLabel()
        self.resumen.setWordWrap(True)
        self.tabla = _tabla(["", "Contrato y objetivo", "Real a hoy", "Tu previsión"])
        caja = QVBoxLayout(self)
        caja.addWidget(_barra([self.a_prevision]))
        caja.addWidget(self.resumen)
        caja.addWidget(self.tabla, 1)

    @property
    def proyecto(self):
        return self.v.proyecto

    def accion_prevision(self) -> None:
        datos = self.v.preguntas.prevision(self.proyecto.prevision())
        if datos is not None:
            self.proyecto.fijar_prevision(**datos)
            self.v.refrescar()

    def refrescar(self) -> None:
        from traza.ui.ventana import _llenar

        if self.proyecto is None:
            self.resumen.clear()
            _llenar(self.tabla, [])
            return
        f = self.proyecto.foto_obra()
        p = f.prevision
        margen_obj = None if f.venta is None or f.objetivo is None else f.venta - f.objetivo
        filas = [
            [
                "Venta",
                _eur(f.venta),
                _eur(f.certificado),
                _eur(p["venta_total"]) if p else "—",
            ],
            ["Coste", _eur(f.objetivo), _eur(f.facturado), _eur(p["coste_total"]) if p else "—"],
            ["Margen", _eur(margen_obj), _eur(f.margen_real), _eur(f.margen_previsto)],
            [
                "Margen (%)",
                _pct(100 * margen_obj / f.venta if margen_obj is not None and f.venta else None),
                "—",
                _pct(f.margen_previsto_pct),
            ],
        ]
        _llenar(self.tabla, filas)
        texto = (
            f"Tu previsión: actualizada el {_fecha_es(p['fecha'])}."
            + (f" {p['nota']}" if p and p["nota"] else "")
            if p
            else "Aún no has puesto tu previsión: «Obra → Actualizar mi previsión…»."
        )
        if f.certificado is None:
            texto += " La venta real (lo certificado) llegará con las certificaciones."
        self.resumen.setText(texto)

    def actualizar_estado(self, hay: bool) -> None:
        self.a_prevision.setEnabled(_es_obra(self, hay))


class PaginaCertificaciones(QWidget):
    """Certificaciones del usuario (o del cliente), leídas de su Excel: la venta real."""

    def __init__(self, ventana) -> None:
        super().__init__()
        self.v = ventana
        from traza.ui.ventana import _barra, _tabla

        m = ventana.menu_obra
        m.addSeparator()
        a = ventana._accion
        self.a_importar = a(m, "Importar certificación (Excel)…", lambda: self.accion_importar())
        self.a_quitar = a(m, "Quitar certificación", lambda: self.accion_quitar())
        self.resumen = QLabel()
        self.resumen.setWordWrap(True)
        self.tabla = _tabla(["Nº", "Fecha", "A origen", "De esta certificación", "% de la venta"])
        self.avisos = QLabel()
        self.avisos.setWordWrap(True)
        caja = QVBoxLayout(self)
        caja.addWidget(_barra([self.a_importar, self.a_quitar]))
        caja.addWidget(self.resumen)
        caja.addWidget(self.tabla, 1)
        caja.addWidget(self.avisos)

    @property
    def proyecto(self):
        return self.v.proyecto

    def accion_importar(self) -> None:
        docs = [
            d for d in self.proyecto.documentos() if d["extension"].lower() in (".xlsx", ".xlsm")
        ]
        if not docs:
            self.v.preguntas.aviso(
                "Certificación",
                "Incorpora antes en «Documentación» el Excel de la certificación.",
            )
            return
        i = self.v.preguntas.elegir(
            "Certificación", "Excel de la certificación:", [d["nombre_original"] for d in docs]
        )
        if i is None:
            return
        doc = docs[i]
        mapa, r = self.proyecto.leer_certificacion(
            doc["id"],
            lambda f: self.v._en_segundo_plano(
                f, "Preguntando a la IA qué columna es qué…", "Certificación"
            ),
        )
        from traza.io.certificacion_excel import descripcion

        venta = self.proyecto.resumen_obra().venta
        texto = (
            ("He entendido (por sus títulos): " if mapa.origen == "títulos" else "La IA dice: ")
            + descripcion(mapa)
            + f"\n\nCertificado a origen: {_eur(r.total)}"
            + (f" ({_pct(100 * r.total / venta)} de la venta)" if venta else "")
            + f", en {len(r.por_partida)} partida(s) de la venta."
            + (f" {r.capitulos} fila(s) de capítulo o subtotal no suman." if r.capitulos else "")
            + ("\n\n" + "\n".join(f"⚠ {a}" for a in r.avisos) if r.avisos else "")
        )
        hechas = self.proyecto.certificaciones()
        datos = self.v.preguntas.certificacion(texto, (hechas[-1]["numero"] + 1) if hechas else 1)
        if datos is None:
            return
        self.proyecto.importar_certificacion(doc["id"], datos["numero"], datos["fecha"], mapa, r)
        self.v.refrescar()

    def accion_quitar(self) -> None:
        fila = self.tabla.currentRow()
        item = self.tabla.item(fila, 0) if fila >= 0 else None
        if item is None:
            self.v.preguntas.aviso("Quitar certificación", "Elige una certificación de la lista.")
            return
        from PySide6.QtCore import Qt

        self.proyecto.quitar_certificacion(item.data(Qt.UserRole))
        self.v.refrescar()

    def refrescar(self) -> None:
        from traza.ui.ventana import _llenar

        self.avisos.clear()
        if self.proyecto is None:
            self.resumen.clear()
            _llenar(self.tabla, [])
            return
        certs = self.proyecto.certificaciones()
        venta = self.proyecto.resumen_obra().venta
        if not certs:
            self.resumen.setText(
                "Sin certificaciones. Importa el Excel de cada una (tuyo o del cliente): "
                "«Obra → Importar certificación (Excel)…»."
            )
        else:
            ultima = certs[-1]
            self.resumen.setText(
                f"Venta real (certificado a origen, nº {ultima['numero']}): "
                f"{_eur(ultima['total_origen'])}"
                + (
                    f" de {_eur(venta)} ({_pct(100 * ultima['total_origen'] / venta)})."
                    if venta
                    else "."
                )
            )
            self.avisos.setText("\n".join(f"⚠ {a}" for a in ultima["avisos"]))
        _llenar(
            self.tabla,
            [
                [
                    str(c["numero"]),
                    _fecha_es(c["fecha"]),
                    _eur(c["total_origen"]),
                    _eur(c["del_mes"]),
                    _pct(100 * c["total_origen"] / venta if venta else None),
                ]
                for c in certs
            ],
            [c["id"] for c in certs],
        )

    def actualizar_estado(self, hay: bool) -> None:
        con = _es_obra(self, hay)
        self.a_importar.setEnabled(con and self.proyecto.venta_contratada() is not None)
        self.a_quitar.setEnabled(con and bool(self.proyecto.certificaciones()))
