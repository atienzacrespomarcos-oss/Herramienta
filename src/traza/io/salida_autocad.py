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


def _sin_repetidos(pts) -> list[Punto]:
    """Sin puntos repetidos ni casi repetidos (< 1 µm): un lado de longitud nula da una
    dirección nula, que descolocaba el inglete y hacía «cruzar» a un tramo que sigue recto
    (revisión 08-11-2026)."""
    salida = [tuple(pts[0])]
    for q in pts[1:]:
        if math.hypot(q[0] - salida[-1][0], q[1] - salida[-1][1]) > 1e-6:
            salida.append(tuple(q))
    return salida


def _extremos(ejes: dict[str, list[Punto]], anchos: dict[str, float]):
    """Por cada punto de unión: (tramo, ancho, dirección que sale del punto)."""
    nodos: dict[tuple[int, int], list[tuple[str, float, Punto]]] = {}
    for tid, pts in ejes.items():
        ancho = anchos[tid]
        nodos.setdefault(_clave(pts[0]), []).append((tid, ancho, _dir(pts[0], pts[1])))
        nodos.setdefault(_clave(pts[-1]), []).append((tid, ancho, _dir(pts[-1], pts[-2])))
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


def _punta(c: list[Punto], extremo: str) -> tuple[Punto, Punto]:
    """(punto del contorno en el nodo, el anterior a él)."""
    return (c[-1], c[-2]) if extremo == "fin" else (c[0], c[1])


def _cambiar_punta(c: list[Punto], extremo: str, p: Punto) -> list[Punto]:
    return [*c[:-1], p] if extremo == "fin" else [p, *c[1:]]


def _alargar(c: list[Punto], extremo: str, p: Punto) -> list[Punto]:
    return [*c, p] if extremo == "fin" else [p, *c]


def _producto(p: Punto, q: Punto) -> float:
    return p[0] * q[0] + p[1] * q[1]


def _unir_codos(
    contornos: dict[tuple[str, int], list[Punto]],
    ejes: dict[str, list[Punto]],
    medios: dict[str, float],
) -> None:
    """Cierra los contornos donde se encuentran solo dos tramos, p. ej. con un difusor en
    la esquina o con dos salidas del equipo (revisión 08-11-2026: quedaban abiertos):
    - en un giro, cada lado se prolonga hasta cortar al del otro;
    - si el giro es tan cerrado que el inglete pasaría de INGLETE_MAXIMO semianchos (o el
      lado interior se cruzaría consigo mismo), se achaflana uniendo las dos puntas;
    - si siguen rectos con distinto ancho, se dibuja el escalón de la reducción.
    En una T, se dibuja también el escalón del lado opuesto al ramal cuando el conducto
    cambia de ancho en ella.
    Los lados se emparejan por su signo (izquierda/derecha), no por su semiancho: con
    anchos distintos no casaban y la esquina quedaba abierta."""
    por_punto: dict[tuple[int, int], list[tuple[str, str, Punto, Punto]]] = {}
    for tid, pts in ejes.items():
        por_punto.setdefault(_clave(pts[0]), []).append((tid, "ini", pts[0], _dir(pts[0], pts[1])))
        por_punto.setdefault(_clave(pts[-1]), []).append(
            (tid, "fin", pts[-1], _dir(pts[-1], pts[-2]))
        )
    for extremos in por_punto.values():
        if len(extremos) == 2:
            parejas = [(extremos[0], extremos[1], True)]
        else:  # T o cruz: solo el escalón de los que siguen rectos
            parejas = [
                (e, f, False)
                for i, e in enumerate(extremos)
                for f in extremos[i + 1 :]
                if _producto(e[3], f[3]) < -0.999
            ]
        for (a, ext_a, nodo, _da), (b, ext_b, _nb, _db), codo in parejas:
            if a == b:
                continue  # un tramo cerrado sobre sí mismo: no es una unión
            limite = INGLETE_MAXIMO * max(medios[a], medios[b])
            for lado in (1, -1):
                # Si uno acaba y el otro empieza, izquierda con izquierda; si los dos acaban
                # (o empiezan) en el nodo, la izquierda de uno es la derecha del otro.
                lado_b = lado if ext_a != ext_b else -lado
                ca, cb = contornos.get((a, lado)), contornos.get((b, lado_b))
                if not ca or not cb or len(ca) < 2 or len(cb) < 2:
                    continue
                pa, previo_a = _punta(ca, ext_a)
                pb, previo_b = _punta(cb, ext_b)
                u, v = _dir(previo_a, pa), _dir(previo_b, pb)
                if abs(_producto(u, v)) > 0.999:  # siguen rectos
                    en_nodo = (
                        abs(_producto((pa[0] - nodo[0], pa[1] - nodo[1]), u)) < 1e-6
                        and abs(_producto((pb[0] - nodo[0], pb[1] - nodo[1]), v)) < 1e-6
                    )
                    if en_nodo and math.hypot(pa[0] - pb[0], pa[1] - pb[1]) > 1e-6:
                        contornos[(a, lado)] = _alargar(ca, ext_a, pb)  # escalón
                    continue
                if not codo:
                    continue
                punto = _cruce(pa, u, pb, v)
                if punto is None:
                    continue
                if _producto((punto[0] - pa[0], punto[1] - pa[1]), u) >= 0:  # lado exterior
                    valido = math.hypot(punto[0] - nodo[0], punto[1] - nodo[1]) <= limite
                else:  # lado interior: el corte no puede quedar detrás del vértice anterior
                    valido = (
                        _producto((punto[0] - previo_a[0], punto[1] - previo_a[1]), u) > 0
                        and _producto((punto[0] - previo_b[0], punto[1] - previo_b[1]), v) > 0
                    )
                if valido:
                    contornos[(a, lado)] = _cambiar_punta(ca, ext_a, punto)
                    contornos[(b, lado_b)] = _cambiar_punta(cb, ext_b, punto)
                else:
                    contornos[(a, lado)] = _alargar(ca, ext_a, pb)  # chaflán


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
    # Los de longitud 0 son el ramal a un difusor sobre el conducto: no se dibujan.
    ejes: dict[str, list[Punto]] = {}
    for g in top.tramos:
        if g.tramo.id in calc and g.tramo.longitud_m > 0:
            pts = _sin_repetidos(g.puntos)
            if len(pts) >= 2:
                ejes[g.tramo.id] = pts
    medios = {tid: calc[tid].seccion.a_m / 2 for tid in ejes}
    extremos = _extremos(ejes, {tid: calc[tid].seccion.a_m for tid in ejes})
    contornos: dict[tuple[str, int], list[Punto]] = {}  # (tramo, +1 izquierda / −1 derecha)
    for tid, pts in ejes.items():
        t = calc[tid]
        ident = f"{red['id']}:{tid}"
        lineas.append(Linea(cp["ejes"], tuple(pts), ident))
        medio = medios[tid]
        # El conducto acaba en la cara del que cruza en una derivación, no en su eje.
        sentido_ini, sentido_fin = _dir(pts[0], pts[1]), _dir(pts[-2], pts[-1])
        for signo in (1, -1):
            lado = signo * medio
            # Solo se abre el lado que da al conducto que llega: el opuesto sigue entero.
            recorte_ini = _recorte(extremos, tid, pts[0], sentido_ini, lado)
            recorte_fin = _recorte(extremos, tid, pts[-1], sentido_fin, lado)
            contornos[(tid, signo)] = _recortar(_desplazada(pts, lado), recorte_ini, recorte_fin)
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
    _unir_codos(contornos, ejes, medios)
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
