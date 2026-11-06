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
- Textos (TEXT, MTEXT), para dar nombre a los espacios.
- Bloques insertados (INSERT): nombre, capa, punto, giro, escala y atributos.
- Longitud por capa de LINE, ARC, CIRCLE, LWPOLYLINE y POLYLINE, medida **en planta**
  (proyección XY). SPLINE y ELLIPSE no se miden: se cuentan y se avisa.

Coordenadas: las entidades planas (LWPOLYLINE, POLYLINE 2D, CIRCLE, ARC, TEXT, INSERT) se
guardan en su sistema de coordenadas de objeto (OCS) y se pasan al universal (WCS) con su
dirección de extrusión. Con la extrusión (0,0,-1) (dibujos en espejo) el arco cambia de
sentido y su bulge de signo. Una entidad cuya extrusión no es vertical no está en planta:
se omite y se avisa.

Lo que NO se lee, y se avisa:
- el contenido de los bloques (si el plano entero está dentro de un bloque, se dice cuál);
- las referencias externas (xref);
- el espacio papel.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import ezdxf
from ezdxf import recover
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


class DxfError(RuntimeError):
    pass


@dataclass(frozen=True)
class ContornoDxf:
    handle: str
    capa: str
    entidad: str
    contorno: Contorno  # en unidades del dibujo, coordenadas universales (WCS) en planta
    elevacion: float
    #: False si la polilínea no traía el bit «Closed» pero su último punto es el primero.
    marcada_cerrada: bool = True


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
    rotacion: float
    escala_x: float
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


def leer_dxf(ruta: Path) -> PlanoDxf:
    try:
        doc, auditor = recover.readfile(str(ruta))
    except (OSError, ezdxf.DXFStructureError) as exc:
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

    fuera_de_planta = 0
    for e in doc.modelspace():
        tipo = e.dxftype()
        nombre_capa = e.dxf.get("layer", "0")
        capa = plano.capas.setdefault(nombre_capa, CapaDxf(nombre_capa))
        capa.entidades[tipo] += 1
        try:
            if not _en_planta(e):
                fuera_de_planta += 1
                continue
            _leer_entidad(plano, capa, e, tipo)
        except (ContornoInvalido, ValueError, ZeroDivisionError) as exc:
            plano.avisos.append(f"Entidad {tipo} {e.dxf.handle} (capa «{nombre_capa}»): {exc}")
    if fuera_de_planta:
        plano.avisos.append(
            f"{fuera_de_planta} entidad(es) no están dibujadas en planta (extrusión no "
            "vertical): se omiten."
        )
    sin_medir = sum(c.sin_medir for c in plano.capas.values())
    if sin_medir:
        plano.avisos.append(
            f"{sin_medir} SPLINE/ELLIPSE no se miden (su longitud no tiene fórmula cerrada): "
            "no están en las longitudes por capa."
        )
    _avisos_de_bloques(doc, plano)
    _extension(plano)
    return plano


def _en_planta(e) -> bool:
    extrusion = e.dxf.get("extrusion", None)
    if extrusion is None:
        return True
    z = Vec3(extrusion).normalize()
    return math.isclose(abs(z.z), 1.0, abs_tol=1e-9)


def _espejo(e) -> bool:
    extrusion = e.dxf.get("extrusion", None)
    return extrusion is not None and Vec3(extrusion).z < 0


def _wcs(e, x: float, y: float) -> tuple[float, float]:
    extrusion = e.dxf.get("extrusion", None)
    if extrusion is None:
        return x, y
    p = OCS(extrusion).to_wcs(Vec3(x, y, 0))
    return p.x, p.y


def _vertices(e, puntos) -> list[Vertice]:
    """(x, y, bulge) en OCS → vértices en WCS. En espejo el arco cambia de sentido."""
    signo = -1.0 if _espejo(e) else 1.0
    return [Vertice(*_wcs(e, x, y), signo * b) for x, y, b in puntos]


def _leer_entidad(plano: PlanoDxf, capa: CapaDxf, e, tipo: str) -> None:
    h = e.dxf.handle
    if tipo == "LWPOLYLINE":
        vs = _vertices(e, e.get_points(format="xyb"))
        _polilinea(plano, capa, e, tipo, vs, bool(e.closed), float(e.dxf.get("elevation", 0)))
    elif tipo == "POLYLINE":
        if not (e.is_2d_polyline or e.is_3d_polyline):
            return  # mallas y caras: no son trazos en planta
        puntos = [
            (v.dxf.location.x, v.dxf.location.y, v.dxf.get("bulge", 0.0) or 0.0) for v in e.vertices
        ]
        if e.is_3d_polyline:
            # Las 3D están en WCS y no admiten arcos: se miden en planta, sin contorno.
            vs = [Vertice(x, y) for x, y, _ in puntos]
            capa.longitud += longitud_polilinea(vs, e.is_closed)
            plano.trazos.append((capa.nombre, [(v.x, v.y) for v in vs]))
            return
        elev = e.dxf.get("elevation", Vec3()).z if e.dxf.hasattr("elevation") else 0.0
        _polilinea(plano, capa, e, tipo, _vertices(e, puntos), e.is_closed, float(elev))
    elif tipo == "LINE":
        a, b = e.dxf.start, e.dxf.end
        capa.longitud += math.hypot(b.x - a.x, b.y - a.y)
        plano.trazos.append((capa.nombre, [(a.x, a.y), (b.x, b.y)]))
    elif tipo == "CIRCLE":
        r = float(e.dxf.radius)
        cx, cy = _wcs(e, e.dxf.center.x, e.dxf.center.y)
        capa.longitud += 2 * math.pi * r
        contorno = Contorno((Vertice(cx - r, cy, 1.0), Vertice(cx + r, cy, 1.0)))
        plano.contornos.append(ContornoDxf(h, capa.nombre, tipo, contorno, e.dxf.center.z))
        plano.trazos.append((capa.nombre, contorno.aplanado(r / 100)))
    elif tipo == "ARC":
        r = float(e.dxf.radius)
        barrido = (float(e.dxf.end_angle) - float(e.dxf.start_angle)) % 360.0
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
            x, y = _wcs(e, e.dxf.insert.x, e.dxf.insert.y)
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
                float(e.dxf.get("rotation", 0) or 0),
                float(e.dxf.get("xscale", 1) or 1),
                float(e.dxf.get("yscale", 1) or 1),
                atributos,
            )
        )
    elif tipo in _NO_MEDIDAS:
        capa.sin_medir += 1


def _polilinea(plano, capa, e, tipo, vs: list[Vertice], cerrada: bool, elevacion: float):
    if len(vs) < 2:
        return
    capa.longitud += longitud_polilinea(vs, cerrada)
    plano.trazos.append((capa.nombre, aplanar(vs, cerrada, _flecha(vs))))
    marcada = cerrada
    if not cerrada and len(vs) >= 4 and (vs[0].x, vs[0].y) == (vs[-1].x, vs[-1].y):
        # Abierta pero con el último punto en el primero: en planos ajenos es habitual. Se
        # propone como contorno (sin el vértice repetido), diciendo que no venía marcada.
        vs, cerrada = vs[:-1], True
    if not cerrada:
        return
    contorno = Contorno(tuple(vs))
    plano.contornos.append(
        ContornoDxf(e.dxf.handle, capa.nombre, tipo, contorno, elevacion, marcada_cerrada=marcada)
    )


def _flecha(vs: list[Vertice]) -> float:
    """Flecha de dibujo: una milésima del tamaño de la polilínea (solo para el visor)."""
    xs = [v.x for v in vs]
    ys = [v.y for v in vs]
    return max(max(xs) - min(xs), max(ys) - min(ys), 1e-9) / 1000


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
        dentro = sum(1 for x in definicion if x.dxftype() in _MEDIDAS)
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
