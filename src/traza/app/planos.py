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

from traza.core.geometria import Contorno
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
    roles = {c: "espacio" for c in capas_espacios} | {c: "obstaculo" for c in capas_obstaculos}
    textos = [t for t in plano.textos if not capas_textos or t.capa in capas_textos]
    salida = []
    for c in plano.contornos:
        rol = roles.get(c.capa)
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
