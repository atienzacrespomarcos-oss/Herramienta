"""Esquema de principio del sistema hidráulico en DXF R2013 (docs/modules/hidronica.md).

Pedido del usuario (08-11-2026): esquema de principio en DXF, completo, para abrir en su
AutoCAD 2013–2017. Es un esquema, no un plano: sin escala, en mm de papel (texto 2,5 mm).
Una banda por servicio (dos con 4 tubos): generador y primario a la izquierda, depósito de
inercia en paralelo, colectores y un ramal por circuito hasta sus unidades; debajo,
expansión, seguridad y llenado. Lleva su propia leyenda de símbolos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import ezdxf
import ezdxf.zoom
from ezdxf.enums import TextEntityAlignment

from traza.engines.hidraulica import SERVICIOS, CircuitoCalculado, Servicio

APPID = "TRAZA"
CAPAS = {
    "impulsion": ("TRAZA-H-IMPULSION", 1),  # rojo
    "retorno": ("TRAZA-H-RETORNO", 5),  # azul
    "equipos": ("TRAZA-H-EQUIPOS", 7),
    "valvuleria": ("TRAZA-H-VALVULERIA", 3),  # verde
    "textos": ("TRAZA-H-TEXTOS", 7),
    "leyenda": ("TRAZA-H-LEYENDA", 8),
}
TEXTO, ROTULO = 2.5, 2.0  # alturas en mm de papel
#: Estilo de texto TrueType: la fuente SHX por defecto (txt.shx) no tiene «Δ» ni «≥» y en
#: AutoCAD salían como «?» (revisión 08-11-2026). Arial viene con Windows.
ESTILO = "TRAZA"
ALTO_BANDA = 230.0  # la banda va de y0 − 25 (llenado) a y0 + 200 (título)
LARGO_NOMBRE = 18  # caracteres del nombre del circuito en su caja (el completo, en el Excel)
PASO_CIRCUITO = 48.0


def _n(v: float, d: int = 1) -> str:
    return f"{v:.{d}f}".replace(".", ",")


class _Dibujo:
    def __init__(self, msp, ident: str) -> None:
        self.msp = msp
        self.ident = ident

    def _xdata(self, e) -> None:
        e.set_xdata(APPID, [(1000, self.ident)])

    def linea(self, puntos, capa: str, ancho: float = 0.0, cerrada: bool = False) -> None:
        e = self.msp.add_lwpolyline(
            puntos, close=cerrada, dxfattribs={"layer": CAPAS[capa][0], "const_width": ancho}
        )
        self._xdata(e)

    def circulo(self, x, y, r, capa: str) -> None:
        self._xdata(self.msp.add_circle((x, y), r, dxfattribs={"layer": CAPAS[capa][0]}))

    def texto(self, t, x, y, capa="textos", alto=ROTULO, giro=0.0, alinear="MIDDLE_LEFT"):
        e = self.msp.add_text(
            t,
            dxfattribs={"layer": CAPAS[capa][0], "height": alto, "rotation": giro, "style": ESTILO},
        )
        e.set_placement((x, y), align=TextEntityAlignment[alinear])
        self._xdata(e)

    def caja(self, x0, y0, x1, y1, capa="equipos") -> None:
        self.linea([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], capa, cerrada=True)

    # --- Símbolos (centrados en (x, y), sobre una tubería horizontal o vertical) ---
    def _girar(self, puntos, x, y, vertical):
        if not vertical:
            return [(x + a, y + b) for a, b in puntos]
        return [(x - b, y + a) for a, b in puntos]

    def valvula(self, x, y, vertical=False, marca: str = "") -> None:
        """Dos triángulos enfrentados; `marca` distingue el tipo (E equilibrado, S
        seguridad, A alivio, M motorizada de control)."""
        s = 2.0
        self.linea(
            self._girar([(-s, s), (s, -s), (s, s), (-s, -s)], x, y, vertical),
            "valvuleria",
            cerrada=True,
        )
        if marca:
            dx, dy = (3.2, 0) if vertical else (0, 3.2)
            self.texto(marca, x + dx, y + dy, "valvuleria", 1.6, alinear="MIDDLE_CENTER")

    def retencion(self, x, y, vertical=False, sentido=1) -> None:
        """Válvula con una barra en el lado de aguas abajo (`sentido` ±1 del flujo)."""
        self.valvula(x, y, vertical)
        b = 2.0 * sentido
        self.linea(self._girar([(b, -2.6), (b, 2.6)], x, y, vertical), "valvuleria")

    def manguito(self, x, y, vertical=False) -> None:
        """Manguito antivibratorio: dos barras paralelas que cortan la tubería."""
        for a in (-0.8, 0.8):
            self.linea(self._girar([(a, -2.2), (a, 2.2)], x, y, vertical), "valvuleria")

    def bomba(self, x, y, vertical=False, sentido=1) -> None:
        """Círculo con triángulo en el sentido del flujo (`sentido` ±1)."""
        self.circulo(x, y, 3.0, "equipos")
        t = [(-1.6 * sentido, -1.8), (2.2 * sentido, 0), (-1.6 * sentido, 1.8)]
        self.linea(self._girar(t, x, y, vertical), "equipos", cerrada=True)

    def filtro(self, x, y, vertical=False) -> None:
        self.linea(
            self._girar([(-2.5, 0), (0, 2.5), (2.5, 0), (0, -2.5)], x, y, vertical),
            "valvuleria",
            cerrada=True,
        )
        self.linea(self._girar([(-1.5, -1.5), (1.5, 1.5)], x, y, vertical), "valvuleria")

    def instrumento(self, x, y, letra: str, desde) -> None:
        """Termómetro (T), manómetro (P), contador (M), presostato (PS): círculo unido a la
        tubería en `desde`."""
        self.linea([desde, (x, y)], "valvuleria")
        self.circulo(x, y, 2.2, "valvuleria")
        self.texto(letra, x, y, "valvuleria", 1.5, alinear="MIDDLE_CENTER")

    def purgador(self, x, y) -> None:
        self.linea([(x, y), (x, y + 3)], "valvuleria")
        self.linea([(x - 1.5, y + 3), (x + 1.5, y + 3), (x, y + 5.5)], "valvuleria", cerrada=True)

    def punto(self, x, y, capa) -> None:
        self.linea([(x - 0.01, y), (x + 0.01, y)], capa, ancho=1.6)


def _rotulo_tubo(c: CircuitoCalculado) -> str:
    return (
        f"{c.tubo.tubo.nombre} · {_n(c.caudal_m3s * 3600, 2)} m³/h · "
        f"bomba {_n(c.altura_bomba_pa / 9806.65)} m c.a."
    )


def _banda(d: _Dibujo, s: Servicio, y0: float, titulo: str, grande: bool) -> float:
    """Dibuja un servicio con su base en y0. Devuelve la x donde acaba."""
    yr, yi = y0 + 40.0, y0 + 90.0  # retorno e impulsión del primario y colectores
    p = s.presiones
    d.texto(titulo, 0, y0 + 200, alto=TEXTO * 1.4)
    # Generador.
    generador = {
        "frio": "ENFRIADORA",
        "calor": "GENERADOR DE CALOR",
        "frio_calor": "BOMBA DE CALOR",
    }[s.clave]
    d.caja(0, yr - 8, 30, yi + 8)
    d.texto(generador, 15, (yr + yi) / 2 + 5, alto=ROTULO, alinear="MIDDLE_CENTER")
    d.texto(f"{_n(s.potencia_kw)} kW", 15, (yr + yi) / 2, alinear="MIDDLE_CENTER")
    d.texto(f"{_n(s.caudal_m3s * 3600, 2)} m³/h", 15, (yr + yi) / 2 - 5, alinear="MIDDLE_CENTER")
    # Primario: impulsión (generador → inercia) y retorno (inercia → generador).
    xi = 120.0  # cara izquierda del depósito
    d.linea([(30, yi), (xi, yi)], "impulsion")
    d.linea([(xi, yr), (30, yr)], "retorno")
    d.valvula(38, yi)
    d.instrumento(46, yi + 8, "T", (46, yi))
    d.instrumento(54, yi + 8, "P", (54, yi))
    d.linea([(64, yi), (64, yi + 12)], "impulsion")
    d.valvula(64, yi + 14, vertical=True, marca="S")
    d.texto(f"Seguridad {_n(p.seguridad)} bar", 67, yi + 17)
    d.texto(f"Primario {s.primario.tubo.nombre}", 72, yi + 4)
    for x, simbolo in (
        (112, "corte"),
        (102, "bomba"),
        (92, "ret"),
        (84, "corte"),
        (74, "filtro"),
        (38, "corte"),
    ):
        if simbolo == "corte":
            d.valvula(x, yr)
        elif simbolo == "bomba":
            d.bomba(x, yr, sentido=-1)
        elif simbolo == "ret":
            d.retencion(x, yr, sentido=-1)
        else:
            d.filtro(x, yr)
    d.instrumento(102, yr + 9, "ΔP", (102, yr + 3))
    for x in (107, 97):  # manguitos de la bomba de primario
        d.manguito(x, yr)
    d.manguito(33, yi)  # manguitos del generador
    d.manguito(33, yr)
    d.instrumento(46, yr - 8, "T", (46, yr))
    d.instrumento(54, yr - 8, "P", (54, yr))
    d.texto(f"Bomba primario {_n(s.altura_primario_pa / 9806.65)} m c.a.", 86, yr + 15)
    # Vaciado total (punto bajo del primario).
    d.linea([(62, yr), (62, yr - 10)], "retorno")
    d.valvula(62, yr - 12, vertical=True, marca="V")
    # Depósito de inercia en paralelo.
    d.caja(xi, yr - 6, xi + 16, yi + 6)
    d.texto(
        f"INERCIA ≥ {_n(s.inercia_l, 0)} l" if s.inercia_l > 0 else "SEPARADOR",
        xi + 8,
        yi + 19,
        alinear="MIDDLE_CENTER",
    )
    d.texto(f"bocas {s.bocas_inercia.tubo.nombre}", xi + 8, yi + 15, alinear="MIDDLE_CENTER")
    d.purgador(xi + 8, yi + 6)
    d.linea([(xi + 8, yr - 6), (xi + 8, yr - 11)], "retorno")  # vaciado del depósito
    d.valvula(xi + 8, yr - 13, vertical=True, marca="V")
    # Colectores.
    n = len(s.circuitos)
    xc0, xc1 = xi + 30, xi + 40 + (n + 0.6) * PASO_CIRCUITO
    d.linea([(xi + 16, yi), (xc1, yi)], "impulsion", ancho=1.2)
    d.linea([(xi + 16, yr), (xc1, yr)], "retorno", ancho=1.2)
    xt = xc0 + 12 + max(n - 1, 0) * PASO_CIRCUITO + 20  # tras el último retorno
    d.texto(f"Colector impulsión {s.colector.tubo.nombre}", xt, yi - 4)
    d.texto(f"Colector retorno {s.colector.tubo.nombre}", xt, yr - 4)
    d.instrumento(xc0 - 6, yi + 8, "T", (xc0 - 6, yi))
    d.instrumento(xc0 - 6, yr - 8, "T", (xc0 - 6, yr))
    d.purgador(xc1 - 3, yi)
    d.purgador(xc1 - 3, yr + 0.5)
    d.texto("reserva", xc1 - 3, yi - 4, alinear="MIDDLE_CENTER")
    # Circuitos.
    ytop = y0 + 168.0
    for i, c in enumerate(s.circuitos):
        x = xc0 + 12 + i * PASO_CIRCUITO
        xr = x + 14
        d.punto(x, yi, "impulsion")
        d.punto(xr, yr, "retorno")
        d.linea([(x, yi), (x, ytop)], "impulsion")
        d.linea([(xr, ytop), (xr, yr)], "retorno")
        d.valvula(x, yi + 6, vertical=True)
        d.bomba(x, yi + 16, vertical=True)
        d.instrumento(x - 7, yi + 16, "ΔP", (x - 3, yi + 16))
        d.retencion(x, yi + 25, vertical=True, sentido=1)
        d.manguito(x, yi + 11, vertical=True)
        d.manguito(x, yi + 21, vertical=True)
        d.valvula(x, yi + 33, vertical=True)
        d.purgador(x, ytop)
        # Valvulería de cada unidad (RITE IT 1.3.4.2.12 y 1.3.4.2.8.2): corte, filtro de
        # 0,25 mm si va, control a la entrada; equilibrado a la salida.
        d.valvula(x, ytop - 26, vertical=True)
        if c.conexion.tubo.dn > 15:
            d.filtro(x, ytop - 17, vertical=True)
        d.valvula(x, ytop - 8, vertical=True, marca="M")
        d.valvula(xr, ytop - 8, vertical=True, marca="E")
        d.texto(f"×{c.datos.unidades}", x + 3, ytop - 17, alto=1.4)
        # Del circuito, en el retorno: termómetro, equilibrado y filtro.
        d.instrumento(xr + 7, ytop - 17, "T", (xr, ytop - 17))
        d.valvula(xr, ytop - 26, vertical=True, marca="E")
        d.filtro(xr, ytop - 35, vertical=True)
        d.valvula(xr, yr + 8, vertical=True)
        d.linea([(xr, yr + 14), (xr + 5, yr + 14)], "retorno")
        d.valvula(xr + 7, yr + 14, marca="V")
        d.texto(_rotulo_tubo(c), x - 13, yi + 6, giro=90)
        # Unidades terminales.
        d.caja(x - 6, ytop + 2, xr + 6, ytop + 22)
        nombre = c.datos.nombre
        if len(nombre) > LARGO_NOMBRE:
            nombre = nombre[: LARGO_NOMBRE - 1] + "…"
        d.texto(nombre, (x + xr) / 2, ytop + 18, alinear="MIDDLE_CENTER")
        d.texto(
            f"{c.datos.unidades} ud · {c.conexion.tubo.nombre}",
            (x + xr) / 2,
            ytop + 13,
            alinear="MIDDLE_CENTER",
            alto=1.6,
        )
        valvula = (
            f"PICV {_n(c.caudal_m3s / c.datos.unidades * 3600, 2)} m³/h"
            if grande
            else f"2 vías Kv ≥ {_n(c.kv_valvula, 2)}"
        )
        d.texto(valvula, (x + xr) / 2, ytop + 7, alinear="MIDDLE_CENTER", alto=1.4)
    # Expansión, alivio y llenado (bajo el retorno del primario, junto a la aspiración).
    ye = y0 + 12.0
    d.linea([(116, yr), (116, ye)], "retorno")
    d.caja(110, ye - 14, 122, ye)
    d.texto("VASO", 116, ye - 4, alinear="MIDDLE_CENTER")
    d.texto(f"≥ {_n(s.vaso_l, 1)} l", 116, ye - 9, alinear="MIDDLE_CENTER", alto=1.6)
    d.instrumento(126, ye - 6, "P", (122, ye - 6))
    d.texto(
        f"Precarga {_n(p.inicial_vaso)} · llenado {_n(p.llenado)} · máx. {_n(p.maxima_servicio)} "
        f"· prueba {_n(p.prueba)} bar · PN{p.nominal}",
        130,
        ye - 12,
    )
    d.linea([(10, ye), (116, ye)], "retorno")
    d.texto("RED", 4, ye, alinear="MIDDLE_CENTER")
    for x, cosa in ((18, "corte"), (28, "filtro"), (38, "M"), (50, "DES"), (66, "A"), (80, "PS")):
        if cosa == "corte":
            d.valvula(x, ye)
        elif cosa == "filtro":
            d.filtro(x, ye)
        elif cosa == "DES":
            d.caja(x - 4, ye - 3, x + 4, ye + 3, "valvuleria")
            d.texto("DES", x, ye, "valvuleria", 1.4, alinear="MIDDLE_CENTER")
        elif cosa == "A":
            d.linea([(x, ye), (x, ye - 6)], "retorno")
            d.valvula(x, ye - 8, vertical=True, marca="A")
            d.texto(f"Alivio {_n(p.alivio)} bar", x + 4, ye - 12)
        else:
            d.instrumento(x, ye + 8 if cosa == "PS" else ye + 7, cosa, (x, ye))
    d.texto("Llenado manual: corte, filtro, contador, desconector (RITE IT 1.3.4.2.2)", 10, ye - 20)
    return xc1


LEYENDA = (
    ("valvula", "Válvula de corte (E equilibrado, M control, V vaciado, S seguridad, A alivio)"),
    ("retencion", "Válvula de retención (barra aguas abajo)"),
    ("manguito", "Manguito antivibratorio"),
    ("bomba", "Bomba (flecha: sentido del flujo)"),
    ("filtro", "Filtro"),
    ("T", "Termómetro con vaina"),
    ("P", "Manómetro (ΔP: diferencial; M: contador; PS: presostato)"),
    ("purgador", "Purgador automático"),
    ("DES", "Desconector"),
)


def _leyenda(d: _Dibujo, x0: float, y0: float) -> None:
    d.texto("LEYENDA", x0, y0, "leyenda", TEXTO)
    for i, (simbolo, texto) in enumerate(LEYENDA):
        y = y0 - 9 - i * 8
        if simbolo == "valvula":
            d.valvula(x0 + 3, y)
        elif simbolo == "retencion":
            d.retencion(x0 + 3, y)
        elif simbolo == "manguito":
            d.linea([(x0, y), (x0 + 6, y)], "retorno")
            d.manguito(x0 + 3, y)
        elif simbolo == "bomba":
            d.bomba(x0 + 3, y)
        elif simbolo == "filtro":
            d.filtro(x0 + 3, y)
        elif simbolo == "purgador":
            d.purgador(x0 + 3, y - 2)
        elif simbolo == "DES":
            d.caja(x0, y - 2.5, x0 + 6, y + 2.5, "valvuleria")
        else:
            d.circulo(x0 + 3, y, 2.2, "valvuleria")
            d.texto(simbolo, x0 + 3, y, "valvuleria", 1.5, alinear="MIDDLE_CENTER")
        d.texto(texto, x0 + 10, y, "leyenda")
    y = y0 - 9 - len(LEYENDA) * 8
    d.linea([(x0, y), (x0 + 7, y)], "impulsion")
    d.texto("Impulsión", x0 + 10, y, "leyenda")
    d.linea([(x0, y - 7), (x0 + 7, y - 7)], "retorno")
    d.texto("Retorno", x0 + 10, y - 7, "leyenda")
    d.texto("Cruce de líneas sin punto: no hay conexión", x0, y - 15, "leyenda")
    d.texto("×n: valvulería de cada unidad, n unidades", x0, y - 22, "leyenda")


def escribir_esquema(destino: Path, proyecto: str, r: Any) -> Path:
    """`r`: app.hidronica.ResultadoSistema."""
    destino = Path(destino)
    if destino.suffix.lower() != ".dxf":
        destino = destino.with_name(destino.name + ".dxf")
    if not r.servicios:
        raise ValueError("El sistema no tiene ningún servicio calculado: no hay esquema.")
    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 4  # mm (de papel)
    doc.appids.new(APPID)
    doc.styles.new(ESTILO, dxfattribs={"font": "arial.ttf"})
    for nombre, color in CAPAS.values():
        doc.layers.add(nombre, color=color)
    msp = doc.modelspace()
    d = _Dibujo(msp, f"{r.sistema['id']}:esquema")
    grande = r.potencia_total_kw > 70
    fin = 0.0
    for k, s in enumerate(r.servicios):
        titulo = f"{proyecto} · {r.sistema['nombre']} · {SERVICIOS[s.clave]}"
        fin = max(fin, _banda(d, s, -k * ALTO_BANDA, titulo, grande))
    _leyenda(d, fin + 25, 170)
    d.texto(
        "Esquema de principio sin escala. Diámetros, caudales, alturas y presiones: listado "
        "Excel de TRAZA (RITE, guía IDAE nº 18).",
        0,
        -(len(r.servicios) - 1) * ALTO_BANDA - 32,
        "leyenda",
    )
    ezdxf.zoom.extents(msp)
    doc.saveas(destino)
    return destino
