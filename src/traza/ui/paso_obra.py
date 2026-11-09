"""Pasos de Obra: «Venta» y «Coste objetivo» (docs/modules/obra.md, bloque 1).

Presentación limpia: en pantalla, lo que decide (venta, objetivo, margen previsto y el
objetivo por paquete); lo que no casa entre venta y coste, en una línea de aviso.
"""

from __future__ import annotations

from collections import defaultdict

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

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
