"""Paso «Entregables» (docs/modules/flujo.md, bloque 2): saca de una vez lo del diseño a una
carpeta (DXF/LISP, Excel, PDF de cargas) y la justificación de cálculos en Word sobre la
plantilla del usuario (Aliter). Solo en Diseño y Ampliación.

Presentación limpia: qué se va a generar, con qué plantilla y un botón; el resultado, en un
aviso con la carpeta y lo que no se ha podido generar.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from traza.app import flujo
from traza.core.ficheros import nombre_valido

#: La plantilla es del usuario, no del proyecto: se recuerda en este equipo.
CLAVE_PLANTILLA = "memoria/plantilla"


def ajustes_por_defecto() -> QSettings:
    """Los ajustes de este equipo. Las pruebas lo sustituyen (tests/conftest.py) para no
    leer ni escribir los del usuario."""
    return QSettings("TRAZA", "TRAZA")


class PaginaEntregables(QWidget):
    def __init__(self, ventana, ajustes: QSettings | None = None) -> None:
        super().__init__()
        self.v = ventana
        self._ajustes = ajustes
        from traza.ui.ventana import _barra

        m = self.v.menu_entregables
        a = self.v._accion
        self.a_generar = a(m, "Generar entregables…", self.accion_generar)
        self.a_memoria = a(m, "Solo la justificación de cálculos (Word)…", self.accion_memoria)
        m.addSeparator()
        self.a_plantilla = a(m, "Plantilla de Word…", self.accion_plantilla)
        self.a_sin_plantilla = a(m, "Sin plantilla", self.accion_sin_plantilla)
        self.resumen = QLabel()
        self.resumen.setWordWrap(True)
        self.plantilla_texto = QLabel()
        self.plantilla_texto.setWordWrap(True)
        caja = QVBoxLayout(self)
        caja.addWidget(_barra([self.a_generar, self.a_memoria, self.a_plantilla]))
        caja.addWidget(self.resumen)
        caja.addWidget(self.plantilla_texto)
        caja.addStretch(1)

    @property
    def proyecto(self):
        return self.v.proyecto

    @property
    def ajustes(self) -> QSettings:
        if self._ajustes is None:
            self._ajustes = ajustes_por_defecto()
        return self._ajustes

    def plantilla(self) -> Path | None:
        valor = self.ajustes.value(CLAVE_PLANTILLA, "")
        return Path(valor) if valor else None

    # --- Acciones ------------------------------------------------------------------------

    def _preparar(self, titulo: str) -> bool:
        """Lee la guía del IDAE si hace falta (en segundo plano) y avisa de lo
        desactualizado antes de generar: la justificación diría números que ya no valen."""
        config = self.proyecto.cargas_config()
        if config is not None and not self.proyecto.guia_leida(config["guia_documento_id"]):
            self.proyecto.estaciones(
                config["guia_documento_id"],
                lambda f: self.v._en_segundo_plano(f, "Leyendo la guía del IDAE…", titulo),
            )
        viejos = [
            flujo.NOMBRES[p]
            for p in flujo.DEPENDE
            if self.proyecto.estado_paso(p).estado == flujo.DESACTUALIZADO
        ]
        if viejos:
            return self.v.preguntas.confirmar(
                titulo,
                f"Hay pasos desactualizados: {', '.join(viejos)}. Se generan con lo calculado "
                "ahora, y la justificación lo dice. ¿Generar igualmente?",
            )
        return True

    def accion_generar(self) -> None:
        carpeta = self.v.preguntas.carpeta_entregables()
        if carpeta is None or not self._preparar("Generar entregables"):
            return
        sub, hechos = self.proyecto.generar_entregables(carpeta, self._plantilla_existente())
        n = sum(len(rutas) for _, rutas, _ in hechos)
        fallos = [f"• {nombre}: {error}" for nombre, _, error in hechos if error]
        texto = f"{n} fichero(s) en «{sub}»."
        if fallos:
            texto += "\n\nNo generados:\n" + "\n".join(fallos)
        self.v.preguntas.informacion("Entregables", texto)

    def accion_memoria(self) -> None:
        sugerido = Path.home() / nombre_valido(
            f"{self.proyecto.nombre} - Justificación de cálculos.docx", "TRAZA"
        )
        destino = self.v.preguntas.destino_word(sugerido)
        if destino is None or not self._preparar("Justificación de cálculos"):
            return
        ruta = self.proyecto.exportar_memoria(destino, self._plantilla_existente())
        self.v.preguntas.informacion("Justificación de cálculos", f"Guardada en «{ruta}».")

    def _plantilla_existente(self) -> Path | None:
        p = self.plantilla()
        if p is not None and not p.exists():
            # Se dice y se genera sin ella: no se pierde el trabajo por una ruta movida.
            self.v.preguntas.aviso(
                "Plantilla de Word",
                f"No se encuentra la plantilla «{p}»: el documento sale sin ella. Elígela otra "
                "vez en «Entregables → Plantilla de Word…».",
            )
            return None
        return p

    def accion_plantilla(self) -> None:
        ruta = self.v.preguntas.plantilla_word()
        if ruta is not None:
            self.ajustes.setValue(CLAVE_PLANTILLA, str(ruta))
            self.refrescar()

    def accion_sin_plantilla(self) -> None:
        self.ajustes.remove(CLAVE_PLANTILLA)
        self.refrescar()

    # --- Estado --------------------------------------------------------------------------

    def refrescar(self) -> None:
        p = self.plantilla()
        self.plantilla_texto.setText(
            f"Plantilla de Word: {p.name}" + ("" if p.exists() else " (no se encuentra)")
            if p is not None
            else "Plantilla de Word: ninguna (documento en blanco). Elige la tuya en "
            "«Entregables → Plantilla de Word…»."
        )
        if self.proyecto is None:
            self.resumen.clear()
            return
        partes = []
        for texto, n in (
            ("plano(s) (Excel)", len(self.proyecto.planos())),
            ("red(es) de aire (DXF, LISP y Excel)", len(self.proyecto.redes())),
            (
                "sistema(s) hidráulico(s) (Excel y esquema DXF)",
                len(self.proyecto.sistemas_hidraulicos()),
            ),
            ("subcuadro(s) (unifilar DXF)", len(self.proyecto.subcuadros())),
        ):
            if n:
                partes.append(f"{n} {texto}")
        if self.proyecto.cargas_config() is not None and self.proyecto.espacios():
            partes.insert(0, "cargas (Excel y PDF)")
        if self.proyecto.redes() or self.proyecto.sistemas_hidraulicos():
            partes.append("propuesta de control (Excel)")
        partes.append("justificación de cálculos (Word)")
        self.resumen.setText("Se generan, en una carpeta nueva: " + "; ".join(partes) + ".")

    def actualizar_estado(self, hay: bool) -> None:
        from traza.ui.ventana import CON_ENTREGABLES

        # Solo en Diseño y Ampliación, como el paso (en Oferta, el menú no se ve).
        con = hay and self.proyecto.encargo in CON_ENTREGABLES
        self.v.menu_entregables.menuAction().setVisible(not hay or con)
        for a in (self.a_generar, self.a_memoria, self.a_plantilla, self.a_sin_plantilla):
            a.setEnabled(con)
