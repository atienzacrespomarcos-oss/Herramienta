"""Visor 2D del plano: referencia visual, no edición CAD (RF-041).

Dibuja los trazos del DXF (gris) y, encima, los contornos confirmados (espacios en azul,
obstáculos en marrón) y la propuesta elegida (naranja). Rueda = zoom alrededor del cursor;
arrastrar = desplazar. Coordenadas en metros con la unidad confirmada; el eje Y del dibujo
crece hacia arriba y el de la pantalla hacia abajo, así que se invierte.

Los trazos ya vienen aplanados por el lector (aproximación solo de dibujo, declarada en
io/dxf.py): el visor no mide nada.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from traza.core.geometria import Contorno

COLOR_TRAZO = QColor(140, 140, 140)
COLOR_ESPACIO = QColor(52, 120, 200)
COLOR_OBSTACULO = QColor(150, 90, 40)
COLOR_PROPUESTA = QColor(230, 126, 34)


def _poligono(c: Contorno) -> QPolygonF:
    return QPolygonF([QPointF(x, -y) for x, y in c.aplanado()])


class VisorPlano(QGraphicsView):
    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self._resaltado = None
        self._por_encuadrar = False
        self.vacio()

    def vacio(self, texto: str = "Sin plano leído") -> None:
        self.scene().clear()
        self._resaltado = None
        self.resetTransform()  # tras un zoom, el texto podía quedar fuera de cuadro
        self._por_encuadrar = False
        # clear() no borra el rectángulo de escena fijado por dibujar(): con un plano lejos
        # del origen, el texto en (0, 0) quedaba fuera de la vista.
        self.scene().setSceneRect(QRectF())
        self.scene().addText(texto)

    def dibujar(
        self,
        trazos: list[tuple[str, list[tuple[float, float]]]],
        factor: float,
        capas_visibles: set[str] | None,
        espacios: list[Contorno],
        obstaculos: list[Contorno],
        encuadrar: bool = True,
    ) -> None:
        """`trazos` en unidades del dibujo; `factor` = metros por unidad. Contornos en m."""
        escena = self.scene()
        escena.clear()
        self._resaltado = None
        camino = QPainterPath()
        for capa, pts in trazos:
            if capas_visibles is not None and capa not in capas_visibles or len(pts) < 2:
                continue
            camino.moveTo(pts[0][0] * factor, -pts[0][1] * factor)
            for x, y in pts[1:]:
                camino.lineTo(x * factor, -y * factor)
        pluma = QPen(COLOR_TRAZO)
        pluma.setCosmetic(True)  # grosor en píxeles, no en metros
        escena.addPath(camino, pluma)
        for contornos, color in ((espacios, COLOR_ESPACIO), (obstaculos, COLOR_OBSTACULO)):
            relleno = QColor(color)
            relleno.setAlpha(60)
            borde = QPen(color)
            borde.setCosmetic(True)
            borde.setWidth(2)
            for c in contornos:
                escena.addPolygon(_poligono(c), borde, QBrush(relleno))
        rect = escena.itemsBoundingRect()
        if not rect.isEmpty():
            escena.setSceneRect(
                rect.adjusted(
                    -rect.width() * 0.05,
                    -rect.height() * 0.05,
                    rect.width() * 0.05,
                    rect.height() * 0.05,
                )
            )
            # Encuadrar con el visor sin mostrar no sirve (aún no tiene tamaño): se deja para
            # cuando se muestre (showEvent). Y no en cada refresco: se perdía el zoom.
            self._por_encuadrar = self._por_encuadrar or encuadrar
            self._encuadrar_si_toca()

    def _encuadrar_si_toca(self) -> None:
        if self._por_encuadrar and self.isVisible():
            self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
            self._por_encuadrar = False

    def showEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        super().showEvent(evento)
        self._encuadrar_si_toca()

    def resaltar(self, contorno: Contorno | None, centrar: bool = True) -> None:
        escena = self.scene()
        if self._resaltado is not None:
            escena.removeItem(self._resaltado)
            self._resaltado = None
        if contorno is None:
            return
        pluma = QPen(COLOR_PROPUESTA)
        pluma.setCosmetic(True)
        pluma.setWidth(3)
        relleno = QColor(COLOR_PROPUESTA)
        relleno.setAlpha(70)
        self._resaltado = escena.addPolygon(_poligono(contorno), pluma, QBrush(relleno))
        if centrar:
            self.centerOn(self._resaltado)

    def wheelEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        f = 1.25 if evento.angleDelta().y() > 0 else 0.8
        self.scale(f, f)
