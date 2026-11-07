"""Lector de planos DXF: lo que hay en el dibujo, sin interpretarlo todavía.

Decisiones del usuario (06-11-2026): los planos vienen del arquitecto o del cliente, con
sus capas, y por eso aquí no se supone ningún nombre de capa. El lector hace inventario y el
usuario dice qué capa es qué. Los espacios se proponen y el usuario los confirma.

Qué se lee, del ESPACIO MODELO (fuente: Autodesk, «DXF Reference», consultada el
06-11-2026 en help.autodesk.com/cloudhelp/2018/ENU/AutoCAD-DXF/):
- Unidades: `$INSUNITS` (4 = mm, 5 = cm, 6 = m, 14 = dm…) y `$MEASUREMENT` (0 inglés,
  1 métrico). La referencia define `$INSUNITS` como «unidades por defecto para bloques de
  DesignCenter», no como la unidad del dibujo, así que **solo se propone**. La unidad la
  confirma el usuario, con la medida total del dibujo a la vista para comprobarla.
- Contornos cerrados: LWPOLYLINE y POLYLINE 2D con el bit 1 de su código 70 («Closed»), y
  CIRCLE. Los arcos de las polilíneas van con su «bulge» (código 42, ver core/geometria.py).
- Textos (TEXT, MTEXT), para dar nombre a los espacios. La posición de un TEXT es la de su
  justificación: para todas menos la izquierda es el punto de alineación (código 11).
- Bloques insertados (INSERT): nombre, capa, punto, giro, escala y atributos.
- Longitud por capa de LINE, ARC, CIRCLE, LWPOLYLINE y POLYLINE, medida **en planta**
  (proyección XY). SPLINE y ELLIPSE no se miden: se cuentan y se avisa.

Coordenadas: las entidades planas (LWPOLYLINE, POLYLINE 2D, CIRCLE, ARC, TEXT, INSERT) se
guardan en su sistema de coordenadas de objeto (OCS) y se pasan al universal (WCS) con su
dirección de extrusión: puntos, cotas y giro de los bloques. Con la extrusión (0,0,-1)
(dibujos en espejo) el arco cambia de sentido y su bulge de signo. Una de esas entidades
cuya extrusión no es vertical no está en planta: se omite y se avisa. En LINE, MTEXT y
POLYLINE 3D la extrusión no mueve la geometría (está en WCS) y no se mira.

Aproximaciones, todas solo para DIBUJAR en el visor (nunca para medir): polilíneas y
círculos se aplanan con una flecha de una milésima de su tamaño; los arcos sueltos, en pasos
de 5°.

Lo que NO se lee, y se avisa:
- el contenido de los bloques (si el plano entero está dentro de un bloque, se dice cuál);
- las referencias externas (xref);
- lo dibujado en el espacio papel;
- los tipos de entidad que no son trazos ni textos (sombreados, sólidos, cotas…), con
  cuántos hay;
- las polilíneas ajustadas con PEDIT (Curva o Spline) se toman por los vértices de su curva
  generada, que es una aproximación de la curva.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import ezdxf
from ezdxf import recover
from ezdxf.enums import TextEntityAlignment
from ezdxf.math import OCS, Vec3

from traza.core.geometria import (
    Contorno,
    ContornoInvalido,
    Vertice,
    aplanar,
    longitud_polilinea,
)

LECTOR = "dxf"
VERSION = "1.0.0"

#: $INSUNITS métricos → (nombre, metros por unidad). Fuente: DXF Reference, HEADER.
UNIDADES_METRICAS = {4: ("mm", 0.001), 5: ("cm", 0.01), 6: ("m", 1.0), 14: ("dm", 0.1)}
#: Las que el usuario puede elegir al confirmar.
UNIDADES = {"mm": 0.001, "cm": 0.01, "dm": 0.1, "m": 1.0}
_MEDIDAS = ("LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE")
_NO_MEDIDAS = ("SPLINE", "ELLIPSE")
_LEIDAS = {*_MEDIDAS, *_NO_MEDIDAS, "TEXT", "MTEXT", "INSERT"}
#: Entidades en coordenadas de objeto (OCS): las únicas a las que la extrusión mueve.
_OCS = {"LWPOLYLINE", "CIRCLE", "ARC", "TEXT", "INSERT"}  # y POLYLINE 2D


class DxfError(RuntimeError):
    pass


@dataclass(frozen=True)
class ContornoDxf:
    handle: str
    capa: str
    entidad: str
    contorno: Contorno  # en unidades del dibujo, coordenadas universales (WCS) en planta
    elevacion: float  # cota Z en WCS, en unidades del dibujo
    #: False si la polilínea no traía el bit «Closed» pero su último punto es el primero.
    marcada_cerrada: bool = True
    #: Se corta a sí mismo: su superficie no tiene sentido físico (se avisa).
    autointersecante: bool = False


@dataclass(frozen=True)
class TextoDxf:
    handle: str
    capa: str
    texto: str
    x: float
    y: float
    altura: float


@dataclass(frozen=True)
class BloqueDxf:
    handle: str
    capa: str
    nombre: str
    x: float
    y: float
    rotacion: float  # grados, en WCS
    escala_x: float  # como en el DXF (negativa = simetría)
    escala_y: float
    atributos: tuple[tuple[str, str], ...] = ()


@dataclass
class CapaDxf:
    nombre: str
    visible: bool = True
    entidades: Counter = field(default_factory=Counter)
    longitud: float = 0.0  # en unidades del dibujo, en planta
    sin_medir: int = 0  # SPLINE y ELLIPSE


@dataclass
class PlanoDxf:
    version: str
    insunits: int
    medicion: int | None
    capas: dict[str, CapaDxf] = field(default_factory=dict)
    contornos: list[ContornoDxf] = field(default_factory=list)
    textos: list[TextoDxf] = field(default_factory=list)
    bloques: list[BloqueDxf] = field(default_factory=list)
    trazos: list[tuple[str, list[tuple[float, float]]]] = field(default_factory=list)
    extension: tuple[float, float, float, float] | None = None
    avisos: list[str] = field(default_factory=list)

    @property
    def unidad_propuesta(self) -> str | None:
        """La de `$INSUNITS` si es métrica. Solo una propuesta (ver el docstring del módulo)."""
        u = UNIDADES_METRICAS.get(self.insunits)
        return u[0] if u else None

    def medida_total(self, unidad: str) -> tuple[float, float] | None:
        """Ancho y fondo del dibujo en metros con esa unidad, para que el usuario compruebe
        que la unidad es la buena (una nave de 80 m no puede medir 80 km ni 8 cm)."""
        if self.extension is None:
            return None
        f = UNIDADES[unidad]
        x0, y0, x1, y1 = self.extension
        return (x1 - x0) * f, (y1 - y0) * f


@dataclass
class _Cuenta:
    fuera_de_planta: int = 0
    ajustadas: int = 0
    sin_superficie: int = 0
    autointersecantes: int = 0
    no_leidas: Counter = field(default_factory=Counter)


def leer_dxf(ruta: Path) -> PlanoDxf:
    try:
        doc, auditor = recover.readfile(str(ruta))
    except (OSError, ezdxf.DXFError, UnicodeDecodeError, ValueError) as exc:
        raise DxfError(f"No se puede leer el DXF: {exc}") from exc
    cab = doc.header
    plano = PlanoDxf(
        version=doc.dxfversion,
        insunits=int(cab.get("$INSUNITS", 0) or 0),
        medicion=int(cab["$MEASUREMENT"]) if "$MEASUREMENT" in cab else None,
    )
    if auditor.has_errors or auditor.has_fixes:
        plano.avisos.append(
            f"El DXF tenía defectos de formato: {len(auditor.errors)} sin arreglar y "
            f"{len(auditor.fixes)} arreglados al leerlo. Revisa el resultado."
        )
    if plano.unidad_propuesta is None:
        plano.avisos.append(
            f"El DXF no declara una unidad métrica ($INSUNITS = {plano.insunits}): tendrás "
            "que decir en qué unidad está dibujado."
        )
    for capa in doc.layers:
        plano.capas[capa.dxf.name] = CapaDxf(
            capa.dxf.name, visible=capa.is_on() and not capa.is_frozen()
        )

    cuenta = _Cuenta()
    for e in doc.modelspace():
        tipo = e.dxftype()
        nombre_capa = e.dxf.get("layer", "0")
        capa = plano.capas.setdefault(nombre_capa, CapaDxf(nombre_capa))
        capa.entidades[tipo] += 1
        if tipo not in _LEIDAS:
            cuenta.no_leidas[tipo] += 1
            continue
        try:
            if _es_ocs(e, tipo) and not _en_planta(e):
                cuenta.fuera_de_planta += 1
                continue
            _leer_entidad(plano, capa, e, tipo, cuenta)
        except Exception as exc:  # noqa: BLE001
            # Una entidad rara no puede tumbar la lectura del plano entero: se dice cuál y
            # por qué, con el tipo de error para poder investigarlo.
            plano.avisos.append(
                f"Entidad {tipo} {e.dxf.handle} (capa «{nombre_capa}») no leída: "
                f"{type(exc).__name__}: {exc}"
            )
    _avisos_de_cuenta(plano, cuenta)
    _avisos_de_papel(doc, plano)
    _avisos_de_bloques(doc, plano)
    _extension(plano)
    return plano


def _avisos_de_cuenta(plano: PlanoDxf, cuenta: _Cuenta) -> None:
    if cuenta.fuera_de_planta:
        plano.avisos.append(
            f"{cuenta.fuera_de_planta} entidad(es) no están dibujadas en planta (extrusión no "
            "vertical): se omiten."
        )
    sin_medir = sum(c.sin_medir for c in plano.capas.values())
    if sin_medir:
        plano.avisos.append(
            f"{sin_medir} SPLINE/ELLIPSE no se miden (su longitud no tiene fórmula cerrada): "
            "no están en las longitudes por capa."
        )
    if cuenta.ajustadas:
        plano.avisos.append(
            f"{cuenta.ajustadas} polilínea(s) ajustada(s) con PEDIT (Curva o Spline): se toman "
            "por los vértices de su curva generada, que es una aproximación de la curva."
        )
    if cuenta.sin_superficie:
        plano.avisos.append(
            f"{cuenta.sin_superficie} contorno(s) cerrado(s) sin superficie (vértices en línea "
            "o arcos que se anulan): no se proponen."
        )
    if cuenta.autointersecantes:
        plano.avisos.append(
            f"{cuenta.autointersecantes} contorno(s) se cortan a sí mismos: su superficie no "
            "tiene sentido físico. Se marcan para que los revises."
        )
    if cuenta.no_leidas:
        tipos = ", ".join(f"{t} ({n})" for t, n in sorted(cuenta.no_leidas.items()))
        plano.avisos.append(
            f"Tipos de entidad que no se leen (ni miden ni proponen): {tipos}. Si los muros o "
            "los pilares están dibujados así (p. ej. sombreados), elige otra capa o dibuja "
            "su contorno con polilínea."
        )


def _es_ocs(e, tipo: str) -> bool:
    if tipo == "POLYLINE":
        return bool(e.is_2d_polyline)
    return tipo in _OCS


def _en_planta(e) -> bool:
    extrusion = e.dxf.get("extrusion", None)
    if extrusion is None:
        return True
    z = Vec3(extrusion).normalize()
    return math.isclose(abs(z.z), 1.0, abs_tol=1e-9)


def _espejo(e) -> bool:
    extrusion = e.dxf.get("extrusion", None)
    return extrusion is not None and Vec3(extrusion).z < 0


def _wcs3(e, x: float, y: float, z: float = 0.0) -> Vec3:
    extrusion = e.dxf.get("extrusion", None)
    if extrusion is None:
        return Vec3(x, y, z)
    return OCS(extrusion).to_wcs(Vec3(x, y, z))


def _wcs(e, x: float, y: float) -> tuple[float, float]:
    p = _wcs3(e, x, y)
    return p.x, p.y


def _vertices(e, puntos) -> list[Vertice]:
    """(x, y, bulge) en OCS → vértices en WCS. En espejo el arco cambia de sentido."""
    signo = -1.0 if _espejo(e) else 1.0
    return [Vertice(*_wcs(e, x, y), signo * b) for x, y, b in puntos]


def _leer_entidad(plano: PlanoDxf, capa: CapaDxf, e, tipo: str, cuenta: _Cuenta) -> None:
    h = e.dxf.handle
    if tipo == "LWPOLYLINE":
        vs = _vertices(e, e.get_points(format="xyb"))
        cota = _wcs3(e, 0, 0, float(e.dxf.get("elevation", 0) or 0)).z
        _polilinea(plano, capa, e, tipo, vs, bool(e.closed), cota, cuenta)
    elif tipo == "POLYLINE":
        if not (e.is_2d_polyline or e.is_3d_polyline):
            cuenta.no_leidas["POLYLINE (malla)"] += 1
            return
        vertices = list(e.vertices)
        if e.dxf.get("flags", 0) & 6:  # 2 = ajustada con curva, 4 = con spline (pág. POLYLINE)
            cuenta.ajustadas += 1
            # VERTEX 16 = «Spline frame control point»: es el polígono de control, no la
            # curva. Se quitan; quedan los vértices de la curva generada.
            vertices = [v for v in vertices if not v.dxf.get("flags", 0) & 16]
        puntos = [
            (v.dxf.location.x, v.dxf.location.y, v.dxf.get("bulge", 0.0) or 0.0) for v in vertices
        ]
        if e.is_3d_polyline:
            # Las 3D están en WCS y no admiten arcos: se miden en planta, sin contorno.
            vs = [Vertice(x, y) for x, y, _ in puntos]
            capa.longitud += longitud_polilinea(vs, e.is_closed)
            plano.trazos.append((capa.nombre, [(v.x, v.y) for v in vs]))
            return
        z = e.dxf.get("elevation", Vec3()).z if e.dxf.hasattr("elevation") else 0.0
        cota = _wcs3(e, 0, 0, float(z)).z
        _polilinea(plano, capa, e, tipo, _vertices(e, puntos), e.is_closed, cota, cuenta)
    elif tipo == "LINE":
        a, b = e.dxf.start, e.dxf.end
        capa.longitud += math.hypot(b.x - a.x, b.y - a.y)
        plano.trazos.append((capa.nombre, [(a.x, a.y), (b.x, b.y)]))
    elif tipo == "CIRCLE":
        r = float(e.dxf.radius)
        centro = _wcs3(e, e.dxf.center.x, e.dxf.center.y, e.dxf.center.z)
        capa.longitud += 2 * math.pi * r
        if r <= 0:
            cuenta.sin_superficie += 1
            return
        cx, cy = centro.x, centro.y
        contorno = Contorno((Vertice(cx - r, cy, 1.0), Vertice(cx + r, cy, 1.0)))
        plano.contornos.append(ContornoDxf(h, capa.nombre, tipo, contorno, centro.z))
        plano.trazos.append((capa.nombre, contorno.aplanado(r / 100)))
    elif tipo == "ARC":
        r = float(e.dxf.radius)
        bruto = float(e.dxf.end_angle) - float(e.dxf.start_angle)
        barrido = bruto % 360.0
        if barrido == 0 and bruto != 0:
            barrido = 360.0  # 0° → 360°: vuelta entera, no un arco nulo
        capa.longitud += r * math.radians(barrido)
        cx, cy = e.dxf.center.x, e.dxf.center.y
        pasos = max(2, math.ceil(barrido / 5))
        a0 = math.radians(float(e.dxf.start_angle))
        pts = [
            _wcs(e, cx + r * math.cos(a0 + math.radians(barrido) * k / pasos),
                 cy + r * math.sin(a0 + math.radians(barrido) * k / pasos))
            for k in range(pasos + 1)
        ]  # fmt: skip
        plano.trazos.append((capa.nombre, pts))
    elif tipo in ("TEXT", "MTEXT"):
        texto = e.plain_text().strip()
        if not texto:
            return
        if tipo == "MTEXT":  # MTEXT está en WCS (no es entidad OCS)
            x, y = e.dxf.insert.x, e.dxf.insert.y
            altura = float(e.dxf.get("char_height", 0) or 0)
        else:
            x, y = _posicion_texto(e)
            altura = float(e.dxf.get("height", 0) or 0)
        plano.textos.append(TextoDxf(h, capa.nombre, texto, x, y, altura))
    elif tipo == "INSERT":
        x, y = _wcs(e, e.dxf.insert.x, e.dxf.insert.y)
        atributos = tuple((a.dxf.tag, a.dxf.text) for a in e.attribs)
        plano.bloques.append(
            BloqueDxf(
                h,
                capa.nombre,
                e.dxf.name,
                x,
                y,
                _giro_wcs(e, float(e.dxf.get("rotation", 0) or 0)),
                float(e.dxf.get("xscale", 1) or 1),
                float(e.dxf.get("yscale", 1) or 1),
                atributos,
            )
        )
    elif tipo in _NO_MEDIDAS:
        capa.sin_medir += 1


def _posicion_texto(e) -> tuple[float, float]:
    """Punto de un TEXT según su justificación (DXF Reference, TEXT; ezdxf get_placement):
    izquierda → código 10; ALIGNED y FIT → punto medio entre los dos puntos; el resto →
    punto de alineación (código 11). En OCS: se pasa a WCS."""
    alineacion, p1, p2 = e.get_placement()
    if alineacion in (TextEntityAlignment.ALIGNED, TextEntityAlignment.FIT) and p2 is not None:
        p1 = (p1 + p2) / 2
    return _wcs(e, p1.x, p1.y)


def _giro_wcs(e, grados: float) -> float:
    """Giro de un bloque en WCS: la dirección del eje X del bloque, pasada de OCS a WCS. En
    espejo (extrusión (0,0,-1)) 30° pasan a 150°."""
    if e.dxf.get("extrusion", None) is None:
        return grados
    d = OCS(e.dxf.extrusion).to_wcs(Vec3.from_deg_angle(grados))
    return math.degrees(math.atan2(d.y, d.x)) % 360.0


def _polilinea(plano, capa, e, tipo, vs: list[Vertice], cerrada: bool, cota: float, cuenta):
    if len(vs) < 2:
        return
    capa.longitud += longitud_polilinea(vs, cerrada)
    plano.trazos.append((capa.nombre, aplanar(vs, cerrada, _flecha(vs))))
    marcada = cerrada
    vuelve = (vs[0].x, vs[0].y) == (vs[-1].x, vs[-1].y)
    # Con 3 vértices (A, B, A) solo encierra algo si tiene arcos.
    if not cerrada and vuelve and (len(vs) >= 4 or any(v.bulge for v in vs[:-1])):
        # Abierta pero con el último punto en el primero: en planos ajenos es habitual. Se
        # propone como contorno (sin el vértice repetido), diciendo que no venía marcada.
        vs, cerrada = vs[:-1], True
    if not cerrada:
        return
    try:
        contorno = Contorno(tuple(vs))
    except ContornoInvalido:
        cuenta.sin_superficie += 1
        return
    tamano = _flecha(vs) * 1000
    if _en_linea(vs):
        # Todos los vértices en línea y sin arcos: no encierra nada (no es que se corte).
        cuenta.sin_superficie += 1
        return
    # Primero si se corta: en una corbata simétrica los lóbulos se anulan y la superficie
    # sale 0, pero no es un contorno «sin superficie», es uno que hay que revisar.
    corta = contorno.autointersecante(tamano / 1000)
    if corta:
        cuenta.autointersecantes += 1
    elif contorno.area <= 1e-9 * tamano * tamano:
        cuenta.sin_superficie += 1
        return
    plano.contornos.append(
        ContornoDxf(
            e.dxf.handle,
            capa.nombre,
            tipo,
            contorno,
            cota,
            marcada_cerrada=marcada,
            autointersecante=corta,
        )
    )


def _en_linea(vs: list[Vertice]) -> bool:
    if any(v.bulge for v in vs):
        return False
    a = vs[0]
    b = next((v for v in vs if (v.x, v.y) != (a.x, a.y)), None)
    if b is None:
        return True
    return all((b.x - a.x) * (v.y - a.y) == (b.y - a.y) * (v.x - a.x) for v in vs)


def _flecha(vs: list[Vertice]) -> float:
    """Flecha de dibujo: una milésima del tamaño de la polilínea (solo para el visor)."""
    xs = [v.x for v in vs]
    ys = [v.y for v in vs]
    return max(max(xs) - min(xs), max(ys) - min(ys), 1e-9) / 1000


def _avisos_de_papel(doc, plano: PlanoDxf) -> None:
    """Lo dibujado en el espacio papel (presentaciones) no se lee: se dice dónde hay algo."""
    con_dibujo = []
    for nombre in doc.layout_names():
        if nombre.lower() == "model":
            continue
        n = sum(1 for x in doc.layouts.get(nombre) if x.dxftype() != "VIEWPORT")
        if n:
            con_dibujo.append(f"«{nombre}» ({n})")
    if con_dibujo:
        plano.avisos.append(
            "Hay entidades dibujadas en el espacio papel, que no se lee: "
            + ", ".join(con_dibujo)
            + ". Si el plano está ahí, pásalo al espacio modelo (CAMBIOESPACIO) en AutoCAD."
        )


def _geometria_de_bloque(doc, nombre: str, vistos: set[str]) -> int:
    """Trazos de un bloque contando los de los bloques que tiene dentro."""
    definicion = doc.blocks.get(nombre)
    if definicion is None or nombre in vistos:
        return 0
    vistos = vistos | {nombre}
    total = 0
    for x in definicion:
        if x.dxftype() in _MEDIDAS:
            total += 1
        elif x.dxftype() == "INSERT":
            total += _geometria_de_bloque(doc, x.dxf.name, vistos)
    return total


def _avisos_de_bloques(doc, plano: PlanoDxf) -> None:
    geometria_modelo = sum(
        sum(n for t, n in c.entidades.items() if t in _MEDIDAS) for c in plano.capas.values()
    )
    usados = Counter(b.nombre for b in plano.bloques)
    for nombre in usados:
        definicion = doc.blocks.get(nombre)
        if definicion is None:
            continue
        if definicion.block_record.is_xref:
            plano.avisos.append(
                f"«{nombre}» es una referencia externa (xref): su contenido no está en este "
                "DXF y no se lee. Únela al dibujo (UNIRREF) antes de exportar."
            )
            continue
        dentro = _geometria_de_bloque(doc, nombre, set())
        if dentro > 50 and dentro > geometria_modelo:
            plano.avisos.append(
                f"La mayor parte del dibujo parece estar dentro del bloque «{nombre}» ({dentro} "
                f"entidades, frente a {geometria_modelo} sueltas): TRAZA lee solo lo que está "
                "suelto en el espacio modelo. Descompón ese bloque (DESCOMP) en AutoCAD y "
                "vuelve a guardar el DXF."
            )


def _extension(plano: PlanoDxf) -> None:
    xs: list[float] = []
    ys: list[float] = []
    for _, pts in plano.trazos:
        for x, y in pts:
            xs.append(x)
            ys.append(y)
    for t in plano.textos:
        xs.append(t.x)
        ys.append(t.y)
    for b in plano.bloques:
        xs.append(b.x)
        ys.append(b.y)
    if xs:
        plano.extension = (min(xs), min(ys), max(xs), max(ys))
