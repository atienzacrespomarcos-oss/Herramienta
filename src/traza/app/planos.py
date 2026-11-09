"""Paso «Planos»: propuestas de contornos, bloques por espacio y longitudes por capa.

Puro sobre lo leído (un `PlanoDxf`) y lo confirmado (filas del proyecto): no escribe nada.
Lo usan la pantalla y el Excel, para que digan lo mismo.

Decisiones del usuario (06-11-2026, docs/modules/geometria.md): los planos son ajenos y el
usuario dice qué capa es qué. Cada contorno cerrado de una capa de espacios u obstáculos se
PROPONE con su superficie y los textos que caen dentro; nada entra sin confirmarlo.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from traza.core.geometria import Contorno, mismo_contorno
from traza.io.dxf import UNIDADES, PlanoDxf

ROLES = {"espacio": "Espacio", "obstaculo": "Obstáculo"}
FUERA = "Fuera de los espacios confirmados"


@dataclass(frozen=True)
class TextoDentro:
    handle: str
    capa: str
    texto: str


@dataclass(frozen=True)
class Propuesta:
    handle: str
    capa: str
    rol: str  # espacio | obstaculo
    entidad: str
    contorno: Contorno  # en metros
    marcada_cerrada: bool
    autointersecante: bool
    textos: tuple[TextoDentro, ...]

    @property
    def superficie(self) -> float:
        return self.contorno.area

    @property
    def perimetro(self) -> float:
        return self.contorno.perimetro

    @property
    def nombre_sugerido(self) -> TextoDentro | None:
        """Solo si cae dentro UN texto: con varios, elegir uno sería suponer."""
        return self.textos[0] if len(self.textos) == 1 else None


def factor(unidad: str) -> float:
    return UNIDADES[unidad]


def propuestas(
    plano: PlanoDxf,
    unidad: str,
    capas_espacios: list[str],
    capas_obstaculos: list[str],
    capas_textos: list[str],
    confirmados: set[str],
    descartados: set[str],
) -> list[Propuesta]:
    f = factor(unidad)
    # Los nombres de capa de AutoCAD no distinguen mayúsculas: una entidad puede citar «muros»
    # y la tabla de capas llamarla «MUROS».
    roles = {c.casefold(): "espacio" for c in capas_espacios} | {
        c.casefold(): "obstaculo" for c in capas_obstaculos
    }
    de_textos = {c.casefold() for c in capas_textos}
    textos = [t for t in plano.textos if not de_textos or t.capa.casefold() in de_textos]
    salida = []
    for c in plano.contornos:
        rol = roles.get(c.capa.casefold())
        if rol is None or c.handle in confirmados or c.handle in descartados:
            continue
        m = c.contorno.escalado(f)
        dentro = tuple(
            TextoDentro(t.handle, t.capa, t.texto) for t in textos if m.contiene(t.x * f, t.y * f)
        )
        salida.append(
            Propuesta(
                c.handle, c.capa, rol, c.entidad, m, c.marcada_cerrada, c.autointersecante, dentro
            )
        )
    return salida


@dataclass
class EspacioConfirmado:
    elemento_id: str
    codigo: str
    nombre: str
    contorno: Contorno  # en metros


@dataclass
class FilaBloques:
    bloque: str
    capa: str
    espacio: str  # «ESP-001 Almacén» o FUERA
    cantidad: int


@dataclass
class Bloques:
    filas: list[FilaBloques] = field(default_factory=list)
    en_varios: int = 0  # bloques que caen en más de un espacio (espacios solapados)


def bloques_por_espacio(plano: PlanoDxf, unidad: str, espacios: list[EspacioConfirmado]) -> Bloques:
    """Cuántos bloques de cada nombre hay por capa y espacio, por su punto de inserción.

    Si un punto cae en varios espacios (uno dentro de otro, o solapados), cuenta en el más
    pequeño, y se dice cuántos son.
    """
    f = factor(unidad)
    r = Bloques()
    cuenta: Counter = Counter()
    for b in plano.bloques:
        x, y = b.x * f, b.y * f
        dentro = [e for e in espacios if e.contorno.contiene(x, y)]
        if len(dentro) > 1:
            r.en_varios += 1
        if dentro:
            e = min(dentro, key=lambda e: e.contorno.area)
            donde = f"{e.codigo} {e.nombre}".strip()
        else:
            donde = FUERA
        cuenta[(b.nombre, b.capa, donde)] += 1
    r.filas = [
        FilaBloques(nombre, capa, donde, n)
        for (nombre, capa, donde), n in sorted(
            cuenta.items(), key=lambda kv: (kv[0][2] == FUERA, kv[0][2], kv[0][0], kv[0][1])
        )
    ]
    return r


@dataclass
class FilaLongitud:
    capa: str
    visible: bool
    longitud_m: float
    sin_medir: int  # SPLINE y ELLIPSE de la capa, que no se miden


def longitudes_por_capa(plano: PlanoDxf, unidad: str) -> list[FilaLongitud]:
    f = factor(unidad)
    return [
        FilaLongitud(c.nombre, c.visible, c.longitud * f, c.sin_medir)
        for c in sorted(plano.capas.values(), key=lambda c: c.nombre.lower())
        if c.longitud or c.sin_medir
    ]


# --- Plano revisado (docs/modules/flujo.md, 1c) ----------------------------------------
#
# Usuario (09-11-2026): «quiero poder yo proponer planos de ampliación o modificación y que
# se recalcule todo». Cada espacio u obstáculo confirmado se busca en el plano revisado:
# es «el mismo» el contorno del mismo papel (espacio/obstáculo) que contiene un punto
# interior del antiguo y cuyo punto interior está dentro del antiguo (los dos se solapan
# de verdad, no solo se tocan); si hay varios, el de superficie más parecida. Los handles
# no sirven: un DXF guardado otra vez, o exportado de otro programa, los renumera.


def punto_interior(contorno: Contorno) -> tuple[float, float]:
    """Un punto dentro del contorno: el centroide si cae dentro; si no (una L, una U), el
    centro del primer tramo interior de una horizontal que corta el contorno."""
    pts = contorno.aplanado()
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1], strict=True):
        k = x1 * y2 - x2 * y1
        a += k
        cx += (x1 + x2) * k
        cy += (y1 + y2) * k
    if a:
        cx, cy = cx / (3 * a), cy / (3 * a)
        if contorno.contiene(cx, cy):
            return cx, cy
    ys = [y for _, y in pts]
    y0, y1 = min(ys), max(ys)
    for f in (0.5, 0.25, 0.75, 0.125, 0.375, 0.625, 0.875):
        y = y0 + f * (y1 - y0)
        cortes = sorted(
            x1 + (y - ya) * (x2 - x1) / (yb - ya)
            for (x1, ya), (x2, yb) in zip(pts, pts[1:] + pts[:1], strict=True)
            if (ya > y) != (yb > y)
        )
        for xa, xb in zip(cortes[::2], cortes[1::2], strict=False):
            if contorno.contiene((xa + xb) / 2, y):
                return (xa + xb) / 2, y
    x, y = pts[0]
    return x, y


@dataclass(frozen=True)
class Confirmado:
    """Un espacio u obstáculo confirmado sobre el plano que se revisa."""

    elemento_id: str
    codigo: str
    nombre: str
    rol: str  # espacio | obstaculo
    contorno: Contorno  # en metros
    aprobado: bool = False

    @property
    def rotulo(self) -> str:
        return f"{self.codigo} {self.nombre}".strip()


@dataclass(frozen=True)
class Pareja:
    antes: Confirmado
    despues: Propuesta

    @property
    def cambia(self) -> bool:
        """Lo mismo que decide la orden RevisarPlano (core/geometria.mismo_contorno)."""
        return not mismo_contorno(self.antes.contorno, self.despues.contorno)


@dataclass
class Emparejamiento:
    iguales: list[Pareja] = field(default_factory=list)
    cambiados: list[Pareja] = field(default_factory=list)
    desaparecidos: list[Confirmado] = field(default_factory=list)
    nuevas: list[Propuesta] = field(default_factory=list)  # se confirman después, como siempre
    avisos: list[str] = field(default_factory=list)  # lo rellena Proyecto (redes, etc.)

    @property
    def aprobados_que_cambian(self) -> list[Confirmado]:
        """Lo aprobado no se modifica sin reabrirlo (línea roja 5): se dice antes de aplicar."""
        return [x.antes for x in self.cambiados if x.antes.aprobado] + [
            c for c in self.desaparecidos if c.aprobado
        ]


def emparejar(confirmados: list[Confirmado], revisado: list[Propuesta]) -> Emparejamiento:
    interior_nueva = {p.handle: punto_interior(p.contorno) for p in revisado}
    candidatas: list[tuple[float, int, Confirmado, Propuesta]] = []
    for n, c in enumerate(confirmados):
        xc, yc = punto_interior(c.contorno)
        for p in revisado:
            if p.rol != c.rol or not p.contorno.contiene(xc, yc):
                continue
            if not c.contorno.contiene(*interior_nueva[p.handle]):
                continue
            candidatas.append((abs(p.superficie - c.contorno.area), n, c, p))
    r = Emparejamiento()
    usados_c: set[str] = set()
    usadas_p: set[str] = set()
    for _, _, c, p in sorted(candidatas, key=lambda t: (t[0], t[1])):
        if c.elemento_id in usados_c or p.handle in usadas_p:
            continue
        usados_c.add(c.elemento_id)
        usadas_p.add(p.handle)
        pareja = Pareja(c, p)
        (r.cambiados if pareja.cambia else r.iguales).append(pareja)
    r.desaparecidos = [c for c in confirmados if c.elemento_id not in usados_c]
    r.nuevas = [p for p in revisado if p.handle not in usadas_p]
    orden = {c.elemento_id: i for i, c in enumerate(confirmados)}
    r.iguales.sort(key=lambda x: orden[x.antes.elemento_id])
    r.cambiados.sort(key=lambda x: orden[x.antes.elemento_id])
    return r
