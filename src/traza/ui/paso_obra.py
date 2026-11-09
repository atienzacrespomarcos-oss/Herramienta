"""Pasos de Obra: «Venta» y «Coste objetivo» (docs/modules/obra.md, bloque 1).

Presentación limpia: en pantalla, lo que decide (venta, objetivo, margen previsto y el
objetivo por paquete); lo que no casa entre venta y coste, en una línea de aviso.
"""

from __future__ import annotations

from collections import defaultdict

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from traza.core.numeros import escribir_numero


def _eur(v: float | None) -> str:
    return "—" if v is None else f"{escribir_numero(round(v, 2))} €"


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
            por_capitulo[cap][1] += p["importe"] or 0.0
        r = self.proyecto.resumen_obra()
        self.resumen.setText(
            f"Presupuesto contratado: {venta['documento_nombre']} · Venta: {_eur(r.venta)} "
            f"({len(partidas)} partidas)."
        )
        _llenar(
            self.tabla,
            [[cap, str(n), _eur(imp)] for cap, (n, imp) in por_capitulo.items()],
        )
        self.avisos.setText(" ".join(f"⚠ {a}" for a in r.avisos if "venta" in a.lower()))

    def actualizar_estado(self, hay: bool) -> None:
        self.a_contratado.setEnabled(_es_obra(self, hay))


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
        texto = f"Coste objetivo ({coste['documento_nombre']}): {_eur(r.objetivo)}"
        if r.venta is not None:
            texto += (
                f" · Venta: {_eur(r.venta)} · Margen previsto: {_eur(r.margen)} "
                f"({_pct(r.margen_pct)})"
            )
        self.resumen.setText(texto + ".")
        total = r.objetivo or 0.0
        filas = [
            [nombre, _eur(imp), _pct(100 * imp / total if total else None)]
            for nombre, imp in r.paquetes.items()
        ]
        sin_paquete = total - sum(r.paquetes.values())
        if abs(sin_paquete) > 0.005:
            filas.append(
                ["(sin repartir en paquetes)", _eur(sin_paquete), _pct(100 * sin_paquete / total)]
            )
        _llenar(self.tabla, filas)
        avisos = []
        if r.solo_en_venta or r.solo_en_coste:
            avisos.append(
                f"Partidas que no casan por código: {len(r.solo_en_venta)} solo en la venta, "
                f"{len(r.solo_en_coste)} solo en el coste: revisa sus códigos en Presto."
            )
        avisos += [a for a in coste["avisos"]]
        self.avisos.setText("\n".join(f"⚠ {a}" for a in avisos))

    def actualizar_estado(self, hay: bool) -> None:
        con = _es_obra(self, hay)
        self.a_importar.setEnabled(con)
        # Solo en Obra, como sus pasos (como el menú Entregables en Oferta).
        self.v.menu_obra.menuAction().setVisible(not hay or con)
