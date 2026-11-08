"""Salida a AutoCAD de una red de aire calculada: DXF R2013 y LISP (ADR-0008, ADR-0009).

- DXF R2013 (AC1027), el que abren AutoCAD 2013–2017: la salida principal, que se comprueba
  en las pruebas releyéndola.
- LISP: dibuja lo mismo DENTRO del plano que el usuario tiene abierto (APPLOAD y el comando
  TRAZA_RED), en sus coordenadas. Solo funciones de AutoLISP existentes en 2013 (lista
  blanca vigilada por una prueba).

Qué se dibuja (presentación limpia: lo que se lee en un plano de instalaciones):
- capa …-EJES: el eje de cada tramo;
- capa …-CONDUCTO: el conducto a su ancho (dos líneas a ±ancho/2 con esquinas a inglete);
- capa …-TEXTOS: «600×300 · 2835 m³/h» en cada tramo y «D01 · 1418 m³/h» en cada terminal.
Cada entidad lleva en XDATA (APPID TRAZA) el id de la red y del tramo o terminal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ezdxf
import ezdxf.zoom
from ezdxf.enums import TextEntityAlignment

APPID = "TRAZA"
#: $INSUNITS del DXF por unidad del plano.
INSUNITS = {"mm": 4, "cm": 5, "m": 6, "dm": 14}
#: Color ACI por tipo de red: impulsión azul, retorno verde, extracción naranja.
COLOR = {"impulsion": 5, "retorno": 3, "extraccion": 30}
PREFIJO_CAPA = {"impulsion": "IMP", "retorno": "RET", "extraccion": "EXT"}
ALTURA_TEXTO_M = 0.15
INGLETE_MAXIMO = 4.0  # longitud máxima de la esquina, en veces el semiancho
COS_45 = math.cos(math.radians(45))

Punto = tuple[float, float]


@dataclass(frozen=True)
class Linea:
    capa: str
    puntos: tuple[Punto, ...]  # en metros
    ident: str


@dataclass(frozen=True)
class Texto:
    capa: str
    texto: str
    x: float  # metros
    y: float
    angulo_rad: float
    ident: str


def capas(tipo: str) -> dict[str, str]:
    p = PREFIJO_CAPA[tipo]
    return {k: f"TRAZA-{p}-{k.upper()}" for k in ("ejes", "conducto", "textos")}


def _desplazada(pts: list[Punto], d: float) -> list[Punto]:
    """Polilínea paralela a distancia d (positiva a la izquierda), con esquinas a inglete."""
    normales = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
        largo = math.hypot(x1 - x0, y1 - y0)
        normales.append((-(y1 - y0) / largo, (x1 - x0) / largo) if largo > 0 else (0.0, 0.0))
    salida = [(pts[0][0] + normales[0][0] * d, pts[0][1] + normales[0][1] * d)]
    for i in range(1, len(pts) - 1):
        n0, n1 = normales[i - 1], normales[i]
        bx, by = n0[0] + n1[0], n0[1] + n1[1]
        norma = math.hypot(bx, by)
        coseno = (n0[0] * n1[0] + n0[1] * n1[1] + 1) / 2  # cos² del medio ángulo
        if norma < 1e-9 or coseno < 1e-9:
            salida.append((pts[i][0] + n1[0] * d, pts[i][1] + n1[1] * d))
            continue
        k = math.copysign(min(abs(d) / math.sqrt(coseno), INGLETE_MAXIMO * abs(d)), d)
        salida.append((pts[i][0] + bx / norma * k, pts[i][1] + by / norma * k))
    salida.append((pts[-1][0] + normales[-1][0] * d, pts[-1][1] + normales[-1][1] * d))
    return salida


def _dir(desde: Punto, hacia: Punto) -> Punto:
    dx, dy = hacia[0] - desde[0], hacia[1] - desde[1]
    largo = math.hypot(dx, dy) or 1.0
    return dx / largo, dy / largo


def _clave(p: Punto) -> tuple[int, int]:
    return round(p[0] * 1000), round(p[1] * 1000)  # al milímetro


def _extremos(tramos, calc) -> dict[tuple[int, int], list[tuple[str, float, Punto]]]:
    """Por cada punto de unión: (tramo, ancho, dirección que sale del punto)."""
    nodos: dict[tuple[int, int], list[tuple[str, float, Punto]]] = {}
    for g in tramos:
        pts, ancho = g.puntos, calc[g.tramo.id].seccion.a_m
        nodos.setdefault(_clave(pts[0]), []).append((g.tramo.id, ancho, _dir(pts[0], pts[1])))
        nodos.setdefault(_clave(pts[-1]), []).append((g.tramo.id, ancho, _dir(pts[-1], pts[-2])))
    return nodos


def _recorte(nodos, tramo_id: str, punto: Punto, sentido: Punto, lado: float) -> float:
    """Cuánto acortar el lado `lado` (+ izquierda, − derecha del sentido del tramo) en ese
    extremo: el medio ancho del conducto más ancho que llega de lado (45° a 135°) por ese
    mismo costado, o que es el conducto en el que acaba este (entonces, los dos lados)."""
    normal = (-sentido[1] * math.copysign(1, lado), sentido[0] * math.copysign(1, lado))
    propios = nodos.get(_clave(punto), ())
    if len(propios) == 2:
        return 0.0  # codo entre dos tramos: se une a inglete (ver _unir_codos), no se recorta
    recorte = 0.0
    for otro, ancho, d in propios:
        if otro == tramo_id:
            continue
        coseno = abs(sentido[0] * d[0] + sentido[1] * d[1])
        if coseno >= COS_45 - 1e-9:
            continue  # sigue en la misma dirección: no cruza
        de_su_lado = normal[0] * d[0] + normal[1] * d[1] > 0.3
        # Si todos los demás cruzan (este acaba en una T contra el conducto), se recortan
        # los dos lados; si hay uno que sigue recto, solo el lado por el que llega el otro.
        alguno_recto = any(
            o != tramo_id and abs(sentido[0] * e[0] + sentido[1] * e[1]) >= COS_45 - 1e-9
            for o, _a, e in propios
        )
        if de_su_lado or not alguno_recto:
            recorte = max(recorte, ancho / 2)
    return recorte


def _recortar(pts: list[Punto], inicio: float, fin: float) -> list[Punto]:
    """Acorta la polilínea `inicio` metros por el principio y `fin` por el final."""

    def por_el_principio(p: list[Punto], d: float) -> list[Punto]:
        while d > 0 and len(p) >= 2:
            (x0, y0), (x1, y1) = p[0], p[1]
            largo = math.hypot(x1 - x0, y1 - y0)
            if largo > d:
                f = d / largo
                return [(x0 + (x1 - x0) * f, y0 + (y1 - y0) * f), *p[1:]]
            d -= largo
            p = p[1:]
        return p

    return list(reversed(por_el_principio(list(reversed(por_el_principio(pts, inicio))), fin)))


def _cruce(p: Punto, u: Punto, q: Punto, v: Punto) -> Punto | None:
    """Punto de corte de las rectas p + s·u y q + t·v (None si son paralelas)."""
    det = u[0] * v[1] - u[1] * v[0]
    if abs(det) < 1e-9:
        return None
    s = ((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / det
    return (p[0] + s * u[0], p[1] + s * u[1])


def _unir_codos(contornos: dict, tramos) -> None:
    """Donde solo se encuentran dos tramos (uno acaba y el otro empieza, p. ej. con un
    difusor en la esquina), cada lado se prolonga hasta cortar al del otro: la esquina
    queda cerrada (revisión 08-11-2026: quedaba abierta por fuera)."""
    por_punto: dict[tuple[int, int], list] = {}
    for g in tramos:
        por_punto.setdefault(_clave(g.puntos[-1]), []).append(("fin", g.tramo.id))
        por_punto.setdefault(_clave(g.puntos[0]), []).append(("ini", g.tramo.id))
    for extremos in por_punto.values():
        if sorted(e[0] for e in extremos) != ["fin", "ini"]:
            continue
        a = next(e[1] for e in extremos if e[0] == "fin")
        b = next(e[1] for e in extremos if e[0] == "ini")
        for (tid, lado), ca in list(contornos.items()):
            cb = contornos.get((b, lado))
            if tid != a or cb is None or len(ca) < 2 or len(cb) < 2:
                continue
            u, v = _dir(ca[-2], ca[-1]), _dir(cb[0], cb[1])
            if abs(u[0] * v[0] + u[1] * v[1]) > 0.999:
                continue  # siguen rectos: no hay esquina
            punto = _cruce(ca[-1], u, cb[0], v)
            if punto is not None:
                contornos[(a, lado)] = [*ca[:-1], punto]
                contornos[(b, lado)] = [punto, *cb[1:]]


def _legible(angulo: float) -> float:
    """Texto que se lee de izquierda a derecha (entre −90° y 90°)."""
    while angulo > math.pi / 2:
        angulo -= math.pi
    while angulo <= -math.pi / 2:
        angulo += math.pi
    return angulo


def _numero(v: float) -> str:
    return f"{v:.0f}"


def entidades(r: Any) -> tuple[list[Linea], list[Texto]]:
    """Líneas y textos (en metros) de una red calculada (`app.redes.ResultadoRedAire`)."""
    red, c, top = r.red, r.calculo, r.topologia
    if c is None or top is None:
        raise ValueError("La red no está calculada: no hay nada que dibujar.")
    cp = capas(red["tipo"])
    calc = {t.tramo.id: t for t in c.tramos}
    lineas: list[Linea] = []
    textos: list[Texto] = []
    dibujables = [
        g for g in top.tramos if g.tramo.id in calc and g.tramo.longitud_m > 0
    ]  # los de longitud 0 son el ramal a un difusor sobre el conducto
    extremos = _extremos(dibujables, calc)
    contornos: dict[tuple[str, float], list[Punto]] = {}
    for geo in dibujables:
        t = calc[geo.tramo.id]
        # Sin puntos repetidos: un lado de longitud 0 descolocaba el inglete.
        pts = [q for i, q in enumerate(geo.puntos) if i == 0 or q != geo.puntos[i - 1]]
        if len(pts) < 2:
            continue
        ident = f"{red['id']}:{geo.tramo.id}"
        lineas.append(Linea(cp["ejes"], tuple(pts), ident))
        medio = t.seccion.a_m / 2
        # El conducto acaba en la cara del que cruza en una derivación, no en su eje.
        sentido_ini, sentido_fin = _dir(pts[0], pts[1]), _dir(pts[-2], pts[-1])
        for lado in (medio, -medio):
            # Solo se abre el lado que da al conducto que llega: el opuesto sigue entero.
            recorte_ini = _recorte(extremos, geo.tramo.id, pts[0], sentido_ini, lado)
            recorte_fin = _recorte(extremos, geo.tramo.id, pts[-1], sentido_fin, lado)
            contornos[(geo.tramo.id, lado)] = _recortar(
                _desplazada(pts, lado), recorte_ini, recorte_fin
            )
        # Etiqueta centrada en el lado más largo, por encima del conducto según se lee (con
        # el texto enderezado, «encima» cambia de lado: antes quedaba pegado al conducto).
        (x0, y0), (x1, y1) = max(
            zip(pts, pts[1:], strict=False),
            key=lambda s: math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1]),
        )
        angulo = _legible(math.atan2(y1 - y0, x1 - x0))
        arriba = (-math.sin(angulo), math.cos(angulo))
        separacion = medio + ALTURA_TEXTO_M
        textos.append(
            Texto(
                cp["textos"],
                f"{t.seccion.texto()} · {_numero(t.tramo.caudal_m3s * 3600)} m³/h",
                (x0 + x1) / 2 + arriba[0] * separacion,
                (y0 + y1) / 2 + arriba[1] * separacion,
                angulo,
                ident,
            )
        )
    _unir_codos(contornos, dibujables)
    for (tid, _lado), contorno in contornos.items():  # en orden: tramo a tramo, + y −
        if len(contorno) >= 2:
            lineas.append(Linea(cp["conducto"], tuple(contorno), f"{red['id']}:{tid}"))
    for term in r.terminales:
        if term.codigo not in c.caminos:
            continue  # sin conectar: no se rotula
        textos.append(
            Texto(
                cp["textos"],
                f"{term.codigo} · {_numero(term.caudal_m3h)} m³/h",
                term.x,
                term.y - ALTURA_TEXTO_M * 3,  # debajo: encima van las de los tramos
                0.0,
                f"{red['id']}:{term.codigo}",
            )
        )
    return lineas, textos


# --- DXF ------------------------------------------------------------------------------


def escribir_dxf(destino: Path, r: Any, unidad: str) -> Path:
    """DXF R2013 en las unidades y coordenadas del plano de partida (para superponerlo)."""
    destino = Path(destino)
    if destino.suffix.lower() != ".dxf":
        destino = destino.with_name(destino.name + ".dxf")
    f = {"mm": 0.001, "cm": 0.01, "dm": 0.1, "m": 1.0}[unidad]
    lineas, textos = entidades(r)
    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = INSUNITS[unidad]
    doc.appids.new(APPID)
    color = COLOR[r.red["tipo"]]
    for nombre in capas(r.red["tipo"]).values():
        doc.layers.add(nombre, color=7 if nombre.endswith("TEXTOS") else color)
    msp = doc.modelspace()
    for ln in lineas:
        e = msp.add_lwpolyline(
            [(x / f, y / f) for x, y in ln.puntos], dxfattribs={"layer": ln.capa}
        )
        e.set_xdata(APPID, [(1000, ln.ident)])
    for tx in textos:
        e = msp.add_text(
            tx.texto,
            dxfattribs={
                "layer": tx.capa,
                "height": ALTURA_TEXTO_M / f,
                "rotation": math.degrees(tx.angulo_rad),
            },
        )
        e.set_placement((tx.x / f, tx.y / f), align=TextEntityAlignment.MIDDLE_CENTER)
        e.set_xdata(APPID, [(1000, tx.ident)])
    # Que se abra encuadrado en la red (las coordenadas del plano están lejos del origen).
    ezdxf.zoom.extents(msp)
    doc.saveas(destino)
    return destino


# --- LISP -----------------------------------------------------------------------------

#: Funciones de AutoLISP que puede usar el LISP generado: todas existen en AutoCAD 2013
#: (y en R14). Una prueba comprueba que no se cuela ninguna otra.
FUNCIONES_LISP = frozenset(
    {
        "defun",
        "if",
        "not",
        "tblsearch",
        "entmake",
        "list",
        "cons",
        "regapp",
        "princ",
        "quote",
        "append",
        "mapcar",
        "lambda",
        "length",
    }
)
#: Las que define el propio LISP (prefijo traza-), y el comando.
PROPIAS_LISP = frozenset({"traza-capa", "traza-pol", "traza-texto", "c:TRAZA_RED"})


def _cadena(texto: str) -> str:
    return '"' + texto.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _coord(v: float) -> str:
    return f"{v:.4f}"


def escribir_lisp(destino: Path, r: Any, unidad: str) -> Path:
    """LISP que dibuja la red en el plano abierto: APPLOAD y escribir TRAZA_RED."""
    destino = Path(destino)
    if destino.suffix.lower() != ".lsp":
        destino = destino.with_name(destino.name + ".lsp")
    f = {"mm": 0.001, "cm": 0.01, "dm": 0.1, "m": 1.0}[unidad]
    lineas, textos = entidades(r)
    color = COLOR[r.red["tipo"]]
    partes = [
        f";;; TRAZA · red «{' '.join(r.red['nombre'].split())}». Cárgalo con APPLOAD y "
        "escribe TRAZA_RED:",
        f";;; dibuja la red en este plano, en sus coordenadas (unidad del plano: {unidad}).",
        "(defun traza-capa (nombre color)",
        '  (if (not (tblsearch "LAYER" nombre))',
        '    (entmake (list (cons 0 "LAYER") (cons 100 "AcDbSymbolTableRecord")',
        '                   (cons 100 "AcDbLayerTableRecord") (cons 2 nombre) (cons 70 0)',
        '                   (cons 62 color) (cons 6 "Continuous")))))',
        "(defun traza-pol (capa puntos id)",
        "  (entmake (append",
        '    (list (cons 0 "LWPOLYLINE") (cons 100 "AcDbEntity") (cons 8 capa)',
        '          (cons 100 "AcDbPolyline") (cons 90 (length puntos)) (cons 70 0))',
        "    (mapcar (quote (lambda (p) (cons 10 p))) puntos)",
        '    (list (list -3 (list "TRAZA" (cons 1000 id)))))))',
        "(defun traza-texto (capa x y altura angulo texto id)",
        # Centrado en (x, y): 72 = 1 (centro) y 73 = 2 (medio), con el punto en 11.
        '  (entmake (list (cons 0 "TEXT") (cons 8 capa) (list 10 x y 0.0) (cons 40 altura)',
        "                 (cons 1 texto) (cons 50 angulo) (cons 72 1) (list 11 x y 0.0)",
        "                 (cons 73 2)",
        f'                 (list -3 (list "{APPID}" (cons 1000 id))))))',
        "(defun c:TRAZA_RED ()",
        f'  (regapp "{APPID}")',
    ]
    for nombre in capas(r.red["tipo"]).values():
        partes.append(
            f"  (traza-capa {_cadena(nombre)} {7 if nombre.endswith('TEXTOS') else color})"
        )
    for ln in lineas:
        puntos = " ".join(f"(list {_coord(x / f)} {_coord(y / f)})" for x, y in ln.puntos)
        partes.append(f"  (traza-pol {_cadena(ln.capa)} (list {puntos}) {_cadena(ln.ident)})")
    for tx in textos:
        partes.append(
            f"  (traza-texto {_cadena(tx.capa)} {_coord(tx.x / f)} {_coord(tx.y / f)} "
            f"{_coord(ALTURA_TEXTO_M / f)} {tx.angulo_rad:.6f} {_cadena(tx.texto)} "
            f"{_cadena(tx.ident)})"
        )
    # El nombre, escapado: con una comilla o una barra el .lsp no cargaba (revisión
    # 08-11-2026).
    partes += [
        f'  (princ "\\nTRAZA: red «{_cadena(r.red["nombre"])[1:-1]}» dibujada.")',
        "  (princ))",
        '(princ "\\nTRAZA: escribe TRAZA_RED para dibujar la red.")',
        "(princ)",
        "",
    ]
    # AutoCAD 2013 lee los .lsp en la página de códigos de Windows (ANSI, cp1252).
    destino.write_bytes("\r\n".join(partes).encode("cp1252", errors="replace"))
    return destino
