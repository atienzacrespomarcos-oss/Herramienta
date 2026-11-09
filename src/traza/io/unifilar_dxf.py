"""Esquema unifilar del subcuadro de clima en DXF R2013 (docs/modules/electricidad.md).

Pedido del usuario (08-11-2026): «Esquema unifilar en DXF». Sin escala, en mm de papel
(texto 2 mm, Arial). Arriba, la alimentación desde el cuadro general con su interruptor
general y el embarrado; debajo, una salida por equipo con su magnetotérmico, su
diferencial, el cable y el receptor, todo rotulado. Cada línea en su capa, con leyenda.
"""

from __future__ import annotations

from pathlib import Path

import ezdxf
import ezdxf.zoom
from ezdxf.enums import TextEntityAlignment

from traza.engines.subcuadro import Linea, ResultadoSubcuadro, interruptor
from traza.rules import electricidad as re

APPID = "TRAZA"
ESTILO = "TRAZA"  # Arial: la fuente SHX por defecto no tiene «Δ», «φ» ni «×»
CAPAS = {
    "lineas": ("TRAZA-E-LINEAS", 7),
    "aparamenta": ("TRAZA-E-APARAMENTA", 1),
    "receptores": ("TRAZA-E-RECEPTORES", 3),
    "textos": ("TRAZA-E-TEXTOS", 7),
    "leyenda": ("TRAZA-E-LEYENDA", 8),
}
PASO = 34.0  # entre salidas
ALTO = 2.0


def _n(v: float, d: int = 1) -> str:
    return f"{v:.{d}f}".replace(".", ",")


def _seccion(s: float) -> str:
    return _n(s, 1).replace(",0", "")


def cable(linea: Linea) -> str:
    """Designación: RZ1-K 0,6/1 kV; «5G» (3F+N+PE) o «3G» (F+N+PE) si el conductor de
    protección es de la misma sección; si no, fases y neutro más «TT» de protección."""
    activos = 4 if linea.fases == 3 else 2
    s, pe = _seccion(linea.seccion), _seccion(linea.seccion_pe)
    if linea.seccion_pe == linea.seccion:
        return f"RZ1-K 0,6/1 kV {activos + 1}G{s}"
    return f"RZ1-K 0,6/1 kV {activos}×{s}+TT{pe}"


def polos(linea: Linea) -> str:
    return "4P" if linea.fases == 3 else "2P"


class _D:
    def __init__(self, msp, ident: str) -> None:
        self.msp, self.ident = msp, ident

    def _x(self, e):
        e.set_xdata(APPID, [(1000, self.ident)])
        return e

    def linea(self, pts, capa="lineas", ancho=0.0, cerrada=False):
        self._x(
            self.msp.add_lwpolyline(
                pts, close=cerrada, dxfattribs={"layer": CAPAS[capa][0], "const_width": ancho}
            )
        )

    def circulo(self, x, y, r, capa="receptores"):
        self._x(self.msp.add_circle((x, y), r, dxfattribs={"layer": CAPAS[capa][0]}))

    def texto(self, t, x, y, capa="textos", alto=ALTO, giro=0.0, alinear="MIDDLE_LEFT"):
        e = self.msp.add_text(
            t,
            dxfattribs={"layer": CAPAS[capa][0], "height": alto, "rotation": giro, "style": ESTILO},
        )
        e.set_placement((x, y), align=TextEntityAlignment[alinear])
        self._x(e)

    def interruptor(self, x, y, rotulo: str):
        """Contacto abierto (barra inclinada) con aspa de disparo, sobre una línea vertical
        de y a y − 10."""
        self.linea([(x, y), (x, y - 3)])
        self.linea([(x, y - 3), (x + 3, y - 8)], "aparamenta")
        self.linea([(x - 1, y - 2), (x + 1, y - 4)], "aparamenta")
        self.linea([(x + 1, y - 2), (x - 1, y - 4)], "aparamenta")
        self.linea([(x, y - 8), (x, y - 10)])
        self.texto(rotulo, x + 4, y - 5, "aparamenta", 1.6)

    def diferencial(self, x, y, rotulo: str):
        """Interruptor con óvalo de toroidal, de y a y − 12."""
        self.interruptor(x, y, "")
        self.linea([(x - 3, y - 10.5), (x + 3, y - 10.5), (x + 3, y - 11.5), (x - 3, y - 11.5)],
                   "aparamenta", cerrada=True)  # fmt: skip
        self.linea([(x, y - 10), (x, y - 12)])
        self.texto(rotulo, x + 4, y - 6, "aparamenta", 1.6)


def escribir_unifilar(destino: Path, proyecto: str, r: ResultadoSubcuadro, ident: str) -> Path:
    destino = Path(destino)
    if destino.suffix.lower() != ".dxf":
        destino = destino.with_name(destino.name + ".dxf")
    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 4
    doc.appids.new(APPID)
    doc.styles.new(ESTILO, dxfattribs={"font": "arial.ttf"})
    for nombre, color in CAPAS.values():
        doc.layers.add(nombre, color=color)
    d = _D(doc.modelspace(), ident)
    a = r.alimentacion
    n = len(r.salidas)
    ancho = max(n * PASO, 60.0)
    x0, yb = 20.0, 0.0  # inicio del embarrado
    # Título y alimentación.
    d.texto(f"{proyecto} · {a.nombre} · esquema unifilar", 0, 72, alto=3.0)
    xa = x0 + 10
    d.linea([(xa, 60), (xa, 52)])
    d.texto("Desde cuadro general", xa + 3, 60)
    d.texto(
        f"{cable(a)} · {_n(a.longitud_m, 0)} m · ΔU {_n(a.caida_pct, 2)} %", xa + 3, 56, alto=1.6
    )
    d.interruptor(xa, 52, f"IG {a.calibre_a or '>160'} A {polos(a)} (corte en carga)")
    d.linea([(xa, 42), (xa, yb)])
    d.texto(
        f"Ib {_n(a.intensidad_a)} A · diseño {_n(a.intensidad_diseno_a)} A (ITC-BT-47)",
        xa + 3,
        38,
        alto=1.6,
    )
    # Embarrado.
    d.linea([(x0, yb), (x0 + ancho, yb)], ancho=0.8)
    # A la derecha de la bajada de la alimentación (antes la cruzaba).
    d.texto(
        f"Embarrado 3F+N+PE 400/230 V · {re.SUMINISTROS[r.suministro]}", xa + 3, yb + 3, alto=1.6
    )
    # Salidas.
    for i, s in enumerate(r.salidas):
        x = x0 + PASO / 2 + i * PASO
        d.linea([(x, yb), (x, yb - 4)])
        d.interruptor(x, yb - 4, f"{interruptor(s)} {polos(s)}")
        d.linea([(x, yb - 14), (x, yb - 16)])
        d.diferencial(x, yb - 16, f"{s.diferencial_ma} mA tipo {s.diferencial_tipo}")
        d.linea([(x, yb - 28), (x, yb - 90)])  # largo: el rótulo del cable no pisa al receptor
        d.texto(
            f"{cable(s)} · {_n(s.longitud_m, 0)} m · ΔU {_n(s.caida_total_pct, 2)} %",
            x - 2,
            yb - 31,
            alto=1.5,
            giro=270,
        )
        if s.motor:
            d.circulo(x, yb - 94, 4)
            d.texto("M", x, yb - 94, "receptores", 2.5, alinear="MIDDLE_CENTER")
        else:
            d.linea([(x - 4, yb - 90), (x + 4, yb - 90), (x + 4, yb - 98), (x - 4, yb - 98)],
                    "receptores", cerrada=True)  # fmt: skip
        d.texto(s.nombre, x, yb - 101, giro=270, alto=1.8)
        d.texto(f"{_n(s.potencia_kw, 2)} kW · {_n(s.intensidad_a)} A", x + 2.5, yb - 101,
                giro=270, alto=1.5)  # fmt: skip
    # Leyenda y notas.
    xl = x0 + ancho + 15
    notas = (
        "LEYENDA",
        "Interruptor automático: curva (D motores de arranque directo, C resto), calibre y polos",
        "Diferencial: sensibilidad y tipo (A; B en trifásicos con variador; F en monofásicos)",
        "M: motor · rectángulo: otros receptores",
        "Cable de cobre RZ1-K 0,6/1 kV (XLPE); «G» incluye el conductor de protección",
        f"ΔU: caída total desde el origen (alimentación + salida), límite {_n(r.limite_pct)} %",
        "Secciones por intensidad admisible (GUÍA-BT-19 tablas A y E) y caída de tensión",
        "(GUÍA-BT Anexo 2); protección Ib ≤ In ≤ Iz (GUÍA-BT-22); diferencial (GUÍA-BT-24)",
        f"Tierra (TT, RA·Ia ≤ 50 V): RA ≤ {re.resistencia_tierra_maxima(300):.0f} Ω con 300 mA; "
        f"≤ {re.resistencia_tierra_maxima(30):.0f} Ω con 30 mA",
    )
    for k, t in enumerate(notas):
        d.texto(t, xl, 60 - k * 5, "leyenda", 2.2 if k == 0 else 1.6)
    ezdxf.zoom.extents(doc.modelspace())
    doc.saveas(destino)
    return destino
