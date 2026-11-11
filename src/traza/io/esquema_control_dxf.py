"""Esquema de principio de control en DXF R2013 (docs/modules/control.md, parte 2).

Usuario (11-11-2026): «sacar esquemas si no hay (hay el qué pero no el cómo)». Sin escala,
en mm de papel (texto 2 mm, Arial), como el esquema hidráulico y el unifilar. Una banda por
sistema:

- a la izquierda, cada equipo en un recuadro con sus señales; cada señal con su símbolo
  (entrada en círculo, salida en cuadrado; leyenda al final) y su texto;
- cada señal llega con una línea de trazos al controlador del sistema, a la derecha, con
  su tipo (ED, SD, EA, SA) y la cantidad si es más de una;
- el controlador lleva el recuento por tipo;
- debajo, la secuencia de funcionamiento («el cómo») cuando se conoce: la de la propuesta
  de TRAZA. Un listado del usuario no la tiene (TRAZA no sabe qué equipos son).
"""

from __future__ import annotations

import textwrap
from collections import Counter
from pathlib import Path

import ezdxf
import ezdxf.zoom
from ezdxf.enums import TextEntityAlignment

from traza.engines.control import Punto, simbolo
from traza.rules import control as rc

APPID = "TRAZA"
ESTILO = "TRAZA"  # Arial: la fuente SHX por defecto no tiene «Δ» ni «₂»
CAPAS = {
    "equipos": ("TRAZA-C-EQUIPOS", 3),
    "simbolos": ("TRAZA-C-SIMBOLOS", 1),
    "senales": ("TRAZA-C-SENALES", 5),
    "controlador": ("TRAZA-C-CONTROLADOR", 4),
    "textos": ("TRAZA-C-TEXTOS", 7),
    "secuencia": ("TRAZA-C-SECUENCIA", 7),
    "leyenda": ("TRAZA-C-LEYENDA", 8),
}
ALTO = 2.0
PASO = 6.0  # entre señales
X_SIMBOLO = 64.0
X_CONTROLADOR = 200.0
ANCHO_CONTROLADOR = 50.0
COLUMNAS_SECUENCIA = 120  # caracteres por línea
X_TRAZOS = 174.0  # donde empieza la línea de trazos de cada señal
#: Caracteres por línea de una señal: a 1,4 mm de alto (Arial, ~0,9 mm por carácter de
#: media) caben de X_SIMBOLO + 4 a X_TRAZOS.
LARGO_SENAL = 95
ALTO_CONTROLADOR = 28.0  # título y cuatro líneas de recuento


class _D:
    def __init__(self, msp, ident: str) -> None:
        self.msp, self.ident = msp, ident

    def _x(self, e):
        e.set_xdata(APPID, [(1000, self.ident)])
        return e

    def linea(self, pts, capa, cerrada=False, trazos=False):
        attrs = {"layer": CAPAS[capa][0]}
        if trazos:
            attrs["linetype"] = "DASHED"
        self._x(self.msp.add_lwpolyline(pts, close=cerrada, dxfattribs=attrs))

    def caja(self, x0, y0, x1, y1, capa):
        self.linea([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], capa, cerrada=True)

    def circulo(self, x, y, r, capa):
        self._x(self.msp.add_circle((x, y), r, dxfattribs={"layer": CAPAS[capa][0]}))

    def texto(self, t, x, y, capa="textos", alto=ALTO, alinear="MIDDLE_LEFT"):
        e = self.msp.add_text(
            t, dxfattribs={"layer": CAPAS[capa][0], "height": alto, "style": ESTILO}
        )
        e.set_placement((x, y), align=TextEntityAlignment[alinear])
        self._x(e)


def _por_sistema(puntos: list[Punto]) -> dict[str, dict[str, list[Punto]]]:
    """Sistema → equipo → puntos, en el orden en que aparecen."""
    salida: dict[str, dict[str, list[Punto]]] = {}
    for p in puntos:
        salida.setdefault(p.sistema, {}).setdefault(p.equipo, []).append(p)
    return salida


def _simbolo(d: _D, p: Punto, x: float, y: float) -> None:
    rotulo = simbolo(p.senal, p.tipo)
    if p.tipo in ("ED", "EA"):
        d.circulo(x, y, 2.5, "simbolos")
    else:
        d.caja(x - 2.5, y - 2.5, x + 2.5, y + 2.5, "simbolos")
    d.texto(rotulo, x, y, "simbolos", 1.4 if len(rotulo) > 1 else 1.8, "MIDDLE_CENTER")


def _banda(d: _D, titulo: str, equipos: dict[str, list[Punto]], secuencia, y: float) -> float:
    """Dibuja la banda desde `y` hacia abajo y devuelve dónde acaba.

    Revisión 11-11-2026: el controlador era más bajo que su recuento con pocas señales, una
    señal larga cruzaba su línea de trazos y el nombre largo de un equipo se cortaba. Ahora
    el controlador tiene altura mínima, la señal va en dos líneas de LARGO_SENAL caracteres
    (más, con «…»: el texto completo está en el listado) y el recuadro del equipo crece
    hasta que cabe su nombre entero.
    """
    d.texto(titulo, 0, y, alto=3.0)
    y -= 8
    arriba = y
    for equipo, puntos in equipos.items():
        nombre = textwrap.wrap(equipo, 28) or [""]
        alto = max(len(puntos) * PASO, 8.0, 3.0 * len(nombre) + 3)
        d.caja(0, y, 55, y - alto, "equipos")
        for linea_k, trozo in enumerate(nombre):
            d.texto(trozo, 2, y - 3 - linea_k * 3, "equipos", 1.8)
        for k, p in enumerate(puntos):
            yy = y - PASO / 2 - k * PASO
            d.linea([(55, yy), (X_SIMBOLO - 2.5, yy)], "senales")
            _simbolo(d, p, X_SIMBOLO, yy)
            lineas = textwrap.wrap(p.senal, LARGO_SENAL) or [""]
            if len(lineas) > 2:
                lineas = [lineas[0], lineas[1][: LARGO_SENAL - 1] + "…"]
            if len(lineas) == 1:
                d.texto(lineas[0], X_SIMBOLO + 4, yy, alto=1.6)
            else:
                d.texto(lineas[0], X_SIMBOLO + 4, yy + 1.1, alto=1.4)
                d.texto(lineas[1], X_SIMBOLO + 4, yy - 1.1, alto=1.4)
            d.linea([(X_TRAZOS, yy), (X_CONTROLADOR, yy)], "senales", trazos=True)
            d.texto(
                p.tipo + (f" ×{p.cantidad}" if p.cantidad > 1 else ""),
                X_CONTROLADOR - 2,
                yy + 1.5,
                "senales",
                1.5,
                "MIDDLE_RIGHT",
            )
        y -= alto + 4
    # Controlador del sistema, con el recuento por tipo (cabe siempre: altura mínima).
    abajo = min(y + 4, arriba - ALTO_CONTROLADOR)
    d.caja(X_CONTROLADOR, arriba, X_CONTROLADOR + ANCHO_CONTROLADOR, abajo, "controlador")
    xc = X_CONTROLADOR + 3
    d.texto("Controlador", xc, arriba - 4, "controlador", 2.2)
    cuenta: Counter[str] = Counter()
    for puntos in equipos.values():
        for p in puntos:
            cuenta[p.tipo] += p.cantidad
    for k, t in enumerate(rc.TIPOS_PUNTO):
        d.texto(f"{t}: {cuenta[t]}", xc, arriba - 10 - k * 4, "controlador", 1.8)
    y = min(y, abajo) - 6
    if secuencia:
        d.texto("Secuencia de funcionamiento", 0, y, "secuencia", 2.2)
        y -= 5
        for frase in secuencia:
            for k, trozo in enumerate(textwrap.wrap(frase, COLUMNAS_SECUENCIA)):
                d.texto(("· " if k == 0 else "  ") + trozo, 2, y, "secuencia", 1.6)
                y -= 3.2
            y -= 0.8
    return y - 12


def escribir(
    destino: Path,
    proyecto: str,
    puntos: list[Punto],
    secuencias: dict[str, list[str]] | None,
    ident: str,
    origen: str,
) -> Path:
    """`origen`: de dónde sale el listado (pie del dibujo: propuesta de TRAZA o fichero)."""
    destino = Path(destino)
    if destino.suffix.lower() != ".dxf":
        destino = destino.with_name(destino.name + ".dxf")
    if not puntos:
        raise ValueError("No hay puntos de control: no hay esquema que dibujar.")
    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 4  # mm (de papel)
    doc.appids.new(APPID)
    doc.styles.new(ESTILO, dxfattribs={"font": "arial.ttf"})
    for nombre, color in CAPAS.values():
        doc.layers.add(nombre, color=color)
    d = _D(doc.modelspace(), ident)
    y = 0.0
    for sistema, equipos in _por_sistema(puntos).items():
        y = _banda(d, f"{proyecto} · {sistema}", equipos, (secuencias or {}).get(sistema), y)
    _leyenda(d, X_CONTROLADOR + ANCHO_CONTROLADOR + 20, 0.0, origen)
    ezdxf.zoom.extents(doc.modelspace())
    doc.saveas(destino)
    return destino


def _leyenda(d: _D, x: float, y: float, origen: str) -> None:
    from traza.engines.control import SIMBOLOS_ENTRADA, SIMBOLOS_SALIDA

    nombres = {
        "CO₂": "calidad del aire (CO₂)",
        "HR": "humedad relativa",
        "ΔP": "presión diferencial / presostato",
        "Q": "caudal",
        "P": "presencia",
        "T": "temperatura",
        "E": "estado",
        "F": "fallo o alarma",
        "C": "consigna",
        "VF": "velocidad (variador)",
        "V": "válvula o compuerta",
        "M": "marcha / paro",
    }
    d.texto("LEYENDA", x, y, "leyenda", 2.5)
    y -= 6
    d.circulo(x + 2.5, y, 2.5, "leyenda")
    d.texto("Entrada (ED digital, EA analógica)", x + 7, y, "leyenda", 1.6)
    y -= 6
    d.caja(x, y - 2.5, x + 5, y + 2.5, "leyenda")
    d.texto("Salida (SD digital, SA analógica)", x + 7, y, "leyenda", 1.6)
    y -= 6
    for _, s in (*SIMBOLOS_ENTRADA, *SIMBOLOS_SALIDA):
        d.texto(f"{s}: {nombres[s]}", x, y, "leyenda", 1.6)
        y -= 3.5
    d.texto("Sin rótulo propio: el tipo de la señal", x, y, "leyenda", 1.6)
    y -= 6
    for nota in (
        "Esquema de principio sin escala.",
        f"Puntos: {origen}.",
        "Lo que exige el RITE (IT 1.2.4.3) lleva su artículo en la secuencia; lo demás es",
        "propuesta (práctica habitual) para confirmar con el integrador de control.",
    ):
        d.texto(nota, x, y, "leyenda", 1.6)
        y -= 3.5
