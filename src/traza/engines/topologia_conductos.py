"""De los ejes de conductos dibujados en AutoCAD a un árbol de tramos (motor puro).

Decisión del usuario (07-11-2026): el trazado lo dibuja el usuario; los difusores y rejillas
son bloques. Aquí no se inventa trazado: se lee el dibujo.

Reglas (docs/modules/redes_aire.md):
- Extremos a menos de UNION_M se consideran el mismo punto; un extremo sobre el interior de
  otra línea es una derivación (en T) y la parte.
- Un terminal (bloque) se conecta al extremo libre más cercano a menos de TERMINAL_M; si no
  hay ninguno, al punto más cercano de un eje a esa distancia.
- El equipo es el punto de conexión que marca su bloque; si no hay bloque y queda un solo
  extremo libre sin terminal, ese.
- Tramo = recorrido entre derivaciones (o equipo, o terminal). Sus codos son los cambios de
  dirección de más de 10° entre lados «largos» (≥ LADO_LARGO_M); los lados cortos son la
  aproximación por cuerdas de un arco y no cuentan como codo cada uno.
- En cada derivación sigue «recto» (paso) el hijo de dirección más parecida al padre si se
  desvía menos de 45°; los demás derivan.
- Clase: principal (el tronco que sigue al hijo de más caudal desde el equipo), terminal
  (acaba en un terminal) o ramal (el resto).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from traza.engines.conductos import Tramo

UNION_M = 0.05
TERMINAL_M = 1.0
EQUIPO_M = 2.0
LADO_LARGO_M = 0.5
CODO_MIN_GRADOS = 10.0
PASO_MAX_GRADOS = 45.0

Punto = tuple[float, float]


@dataclass(frozen=True)
class Terminal:
    codigo: str
    x: float
    y: float
    caudal_m3s: float


@dataclass(frozen=True)
class TramoGeometrico:
    tramo: Tramo
    puntos: tuple[Punto, ...]  # del lado del equipo hacia el terminal


@dataclass(frozen=True)
class Topologia:
    tramos: tuple[TramoGeometrico, ...]
    origen: Punto
    avisos: tuple[str, ...] = field(default=())


class TopologiaInvalida(ValueError):
    pass


def _dist(p: Punto, q: Punto) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _proyeccion(p: Punto, a: Punto, b: Punto) -> tuple[float, Punto]:
    dx, dy = b[0] - a[0], b[1] - a[1]
    largo2 = dx * dx + dy * dy
    if largo2 == 0:
        return 0.0, a
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / largo2))
    return t, (a[0] + t * dx, a[1] + t * dy)


def _angulo(u: Punto, v: Punto) -> float:
    """Ángulo (°) entre dos direcciones."""
    nu, nv = math.hypot(*u), math.hypot(*v)
    c = (u[0] * v[0] + u[1] * v[1]) / (nu * nv)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


class _Grafo:
    def __init__(self) -> None:
        self.nodos: list[Punto] = []
        self.ady: dict[int, set[int]] = defaultdict(set)

    def nodo(self, p: Punto) -> int:
        for i, q in enumerate(self.nodos):
            if _dist(p, q) <= UNION_M:
                return i
        self.nodos.append(p)
        return len(self.nodos) - 1

    def unir(self, i: int, j: int) -> None:
        if i != j:
            self.ady[i].add(j)
            self.ady[j].add(i)

    def aristas(self) -> list[tuple[int, int]]:
        return [(i, j) for i in self.ady for j in self.ady[i] if i < j]

    def partir(self, i: int, j: int, k: int) -> None:
        """Inserta el nodo k en la arista i–j."""
        self.ady[i].discard(j)
        self.ady[j].discard(i)
        self.unir(i, k)
        self.unir(k, j)

    def punto_en_eje(self, p: Punto, tolerancia: float) -> int | None:
        """Nodo en el punto de un eje más cercano a p (lo crea partiendo la arista)."""
        mejor = None
        for i, j in self.aristas():
            _t, q = _proyeccion(p, self.nodos[i], self.nodos[j])
            d = _dist(p, q)
            if d <= tolerancia and (mejor is None or d < mejor[0]):
                mejor = (d, i, j, q)
        if mejor is None:
            return None
        _d, i, j, q = mejor
        k = self.nodo(q)
        if k not in (i, j):
            self.partir(i, j, k)
        return k


def leer(
    polilineas: list[list[Punto]],
    terminales: list[Terminal],
    equipo: Punto | None,
) -> Topologia:
    g = _Grafo()
    for pl in polilineas:
        ids = [g.nodo(p) for p in pl]
        for a, b in zip(ids, ids[1:], strict=False):
            g.unir(a, b)
    if not g.aristas():
        raise TopologiaInvalida("No hay ejes de conductos en la capa elegida.")
    # Derivaciones en T: un extremo que cae dentro de otro eje.
    cambiado = True
    while cambiado:
        cambiado = False
        for n in [n for n in list(g.ady) if len(g.ady[n]) == 1]:
            for i, j in g.aristas():
                if n in (i, j):
                    continue
                t, q = _proyeccion(g.nodos[n], g.nodos[i], g.nodos[j])
                if 0 < t < 1 and _dist(g.nodos[n], q) <= UNION_M:
                    g.partir(i, j, n)
                    cambiado = True
                    break
            if cambiado:
                break

    avisos: list[str] = []
    en_nodo: dict[int, Terminal] = {}
    for term in terminales:
        p = (term.x, term.y)
        libres = [
            n
            for n in g.ady
            if len(g.ady[n]) == 1 and n not in en_nodo and _dist(g.nodos[n], p) <= TERMINAL_M
        ]
        if libres:
            n = min(libres, key=lambda k: _dist(g.nodos[k], p))
        else:
            n = g.punto_en_eje(p, TERMINAL_M)
        if n is None or n in en_nodo:
            avisos.append(f"Terminal {term.codigo}: no está junto a ningún eje; no se calcula.")
            continue
        en_nodo[n] = term

    if equipo is not None:
        raiz = min(g.ady, key=lambda n: _dist(g.nodos[n], equipo))
        if _dist(g.nodos[raiz], equipo) > EQUIPO_M:
            raiz = g.punto_en_eje(equipo, EQUIPO_M)
            if raiz is None:
                raise TopologiaInvalida("El bloque del equipo no está junto a ningún eje.")
    else:
        libres = [n for n in g.ady if len(g.ady[n]) == 1 and n not in en_nodo]
        if len(libres) != 1:
            raise TopologiaInvalida(
                "No se sabe dónde está el equipo: marca su bloque (hay "
                f"{len(libres)} extremos libres sin terminal)."
            )
        raiz = libres[0]

    # Orientar desde el equipo (árbol) y detectar ciclos.
    padre: dict[int, int | None] = {raiz: None}
    orden = [raiz]
    for n in orden:
        for m in sorted(g.ady[n]):
            if m == padre[n]:
                continue
            if m in padre:
                raise TopologiaInvalida(
                    "Los ejes forman un anillo: una red de conductos de este paso tiene que ser "
                    "un árbol desde el equipo."
                )
            padre[m] = n
            orden.append(m)
    sueltos = len(g.ady) - len(padre)
    if sueltos:
        avisos.append(f"{sueltos} punto(s) de ejes no conectados con el equipo: no se calculan.")
    hijos: dict[int, list[int]] = defaultdict(list)
    for n, p in padre.items():
        if p is not None:
            hijos[p].append(n)

    # Tramos: de un nodo «de corte» (equipo, derivación) al siguiente.
    def es_corte(n: int) -> bool:
        return n == raiz or len(hijos[n]) != 1 or n in en_nodo

    crudos = []  # (nodo inicial, lista de nodos, terminal)
    for inicio in [n for n in orden if es_corte(n)]:
        for primero in sorted(hijos[inicio]):
            camino = [inicio, primero]
            while not es_corte(camino[-1]):
                camino.append(hijos[camino[-1]][0])
            crudos.append(camino)

    # Caudales: suma de terminales aguas abajo.
    caudal_nodo: dict[int, float] = defaultdict(float)
    for n in reversed(orden):
        if n in en_nodo:
            caudal_nodo[n] += en_nodo[n].caudal_m3s
        if padre[n] is not None:
            caudal_nodo[padre[n]] += caudal_nodo[n]

    # Tronco: desde el equipo, siempre por el hijo de más caudal.
    tronco = set()
    n = raiz
    while hijos[n]:
        siguiente = max(hijos[n], key=lambda k: caudal_nodo[k])
        tronco.add((n, siguiente))
        n = siguiente

    ids: dict[tuple[int, int], str] = {}
    for k, camino in enumerate(crudos, start=1):
        ids[(camino[0], camino[1])] = f"T{k:02d}"
    final_de: dict[int, str] = {camino[-1]: ids[(camino[0], camino[1])] for camino in crudos}

    resultado = []
    for camino in crudos:
        puntos = tuple(g.nodos[i] for i in camino)
        largo = sum(_dist(a, b) for a, b in zip(puntos, puntos[1:], strict=False))
        caudal = caudal_nodo[camino[-1]]
        tid = ids[(camino[0], camino[1])]
        if caudal <= 0:
            avisos.append(f"{tid}: no lleva caudal (no acaba en ningún terminal); no se calcula.")
            continue
        # Un difusor montado sobre un conducto que sigue (no en su extremo) no cierra el
        # tramo como terminal: va en su propio ramal de longitud 0 (abajo). Si no, su
        # pérdida se sumaba a los caminos de aguas abajo.
        terminal = en_nodo.get(camino[-1]) if not hijos[camino[-1]] else None
        clase = (
            "terminal" if terminal else "principal" if (camino[0], camino[1]) in tronco else "ramal"
        )
        padre_id = final_de.get(camino[0])
        es_paso = True
        if padre_id is not None:
            anterior = next(c for c in crudos if c[-1] == camino[0])
            dir_padre = _direccion_final([g.nodos[i] for i in anterior])
            dir_hijo = _direccion_inicial(list(puntos))
            angulos = {
                tuple(c): _angulo(dir_padre, _direccion_inicial([g.nodos[i] for i in c]))
                for c in crudos
                if c[0] == camino[0]
            }
            recto = min(angulos, key=angulos.get)
            es_paso = tuple(camino) == recto and _angulo(dir_padre, dir_hijo) < PASO_MAX_GRADOS
        resultado.append(
            TramoGeometrico(
                Tramo(
                    tid,
                    padre_id,
                    largo,
                    caudal,
                    clase,
                    es_paso,
                    _codos(list(puntos)),
                    terminal.codigo if terminal else None,
                ),
                puntos,
            )
        )
    n_tramos = len(crudos)
    for n in orden:
        if n in en_nodo and hijos[n]:
            n_tramos += 1
            term = en_nodo[n]
            resultado.append(
                TramoGeometrico(
                    Tramo(
                        f"T{n_tramos:02d}",
                        final_de.get(n),
                        0.0,
                        term.caudal_m3s,
                        "terminal",
                        False,
                        (),
                        term.codigo,
                    ),
                    (g.nodos[n], g.nodos[n]),
                )
            )
    return Topologia(tuple(resultado), g.nodos[raiz], tuple(avisos))


def _lados_largos(puntos: list[Punto]) -> list[Punto]:
    dirs = []
    for a, b in zip(puntos, puntos[1:], strict=False):
        if _dist(a, b) >= LADO_LARGO_M:
            dirs.append((b[0] - a[0], b[1] - a[1]))
    return dirs


def _direccion_inicial(puntos: list[Punto]) -> Punto:
    largos = _lados_largos(puntos)
    if largos:
        return largos[0]
    return (puntos[-1][0] - puntos[0][0], puntos[-1][1] - puntos[0][1])


def _direccion_final(puntos: list[Punto]) -> Punto:
    largos = _lados_largos(puntos)
    if largos:
        return largos[-1]
    return (puntos[-1][0] - puntos[0][0], puntos[-1][1] - puntos[0][1])


def _codos(puntos: list[Punto]) -> tuple[float, ...]:
    dirs = _lados_largos(puntos)
    codos = []
    for u, v in zip(dirs, dirs[1:], strict=False):
        a = _angulo(u, v)
        if a >= CODO_MIN_GRADOS:
            codos.append(round(a, 1))
    return tuple(codos)
