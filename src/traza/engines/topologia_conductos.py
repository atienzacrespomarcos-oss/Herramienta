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


#: Lado de la celda de la rejilla espacial (m). Sin rejilla, 2000 segmentos tardaban
#: 97 s (todas las búsquedas recorrían el dibujo entero; revisión 07-11-2026).
CELDA_M = 1.0
MAX_CELDAS_ARISTA = 10_000


def _celda(p: Punto) -> tuple[int, int]:
    return (math.floor(p[0] / CELDA_M), math.floor(p[1] / CELDA_M))


class _Grafo:
    def __init__(self) -> None:
        self.nodos: list[Punto] = []
        self.ady: dict[int, set[int]] = defaultdict(set)
        self._nodos_celda: dict[tuple[int, int], list[int]] = defaultdict(list)
        self._aristas_celda: dict[tuple[int, int], set[tuple[int, int]]] = defaultdict(set)
        #: Aristas cuya caja ocupa demasiadas celdas (una diagonal enorme, p. ej. con la
        #: unidad mal elegida): se miran siempre, en vez de llenar millones de celdas.
        self._aristas_grandes: set[tuple[int, int]] = set()

    def nodo(self, p: Punto) -> int:
        cx, cy = _celda(p)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for i in self._nodos_celda.get((cx + dx, cy + dy), ()):
                    if _dist(p, self.nodos[i]) <= UNION_M:
                        return i
        self.nodos.append(p)
        k = len(self.nodos) - 1
        self._nodos_celda[(cx, cy)].append(k)
        return k

    def _celdas_arista(self, i: int, j: int, margen: float):
        (x0, y0), (x1, y1) = self.nodos[i], self.nodos[j]
        cx0, cy0 = _celda((min(x0, x1) - margen, min(y0, y1) - margen))
        cx1, cy1 = _celda((max(x0, x1) + margen, max(y0, y1) + margen))
        if (cx1 - cx0 + 1) * (cy1 - cy0 + 1) > MAX_CELDAS_ARISTA:
            return None
        return [(cx, cy) for cx in range(cx0, cx1 + 1) for cy in range(cy0, cy1 + 1)]

    def unir(self, i: int, j: int) -> None:
        if i != j and j not in self.ady[i]:
            self.ady[i].add(j)
            self.ady[j].add(i)
            arista = (min(i, j), max(i, j))
            celdas = self._celdas_arista(i, j, 0.0)
            if celdas is None:
                self._aristas_grandes.add(arista)
            else:
                for c in celdas:
                    self._aristas_celda[c].add(arista)

    def aristas(self) -> list[tuple[int, int]]:
        return [(i, j) for i in self.ady for j in self.ady[i] if i < j]

    def cerca(self, p: Punto, radio: float) -> set[tuple[int, int]]:
        """Aristas cuya caja está a menos de `radio` de p (candidatas)."""
        cx0, cy0 = _celda((p[0] - radio, p[1] - radio))
        cx1, cy1 = _celda((p[0] + radio, p[1] + radio))
        encontradas: set[tuple[int, int]] = set(self._aristas_grandes)
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                encontradas |= self._aristas_celda.get((cx, cy), set())
        return encontradas

    def nodos_cerca(self, p: Punto, radio: float) -> list[int]:
        cx0, cy0 = _celda((p[0] - radio, p[1] - radio))
        cx1, cy1 = _celda((p[0] + radio, p[1] + radio))
        return [
            i
            for cx in range(cx0, cx1 + 1)
            for cy in range(cy0, cy1 + 1)
            for i in self._nodos_celda.get((cx, cy), ())
            if _dist(p, self.nodos[i]) <= radio
        ]

    def partir(self, i: int, j: int, k: int) -> None:
        """Inserta el nodo k en la arista i–j."""
        self.ady[i].discard(j)
        self.ady[j].discard(i)
        arista = (min(i, j), max(i, j))
        self._aristas_grandes.discard(arista)
        for c in self._celdas_arista(i, j, 0.0) or ():
            self._aristas_celda[c].discard(arista)
        self.unir(i, k)
        self.unir(k, j)

    def punto_en_eje(self, p: Punto, tolerancia: float) -> int | None:
        """Nodo en el punto de un eje más cercano a p (lo crea partiendo la arista)."""
        mejor = None
        for i, j in sorted(self.cerca(p, tolerancia)):
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
    for n in [n for n in list(g.ady) if len(g.ady[n]) == 1]:
        for i, j in sorted(g.cerca(g.nodos[n], UNION_M)):
            if n in (i, j):
                continue
            t, q = _proyeccion(g.nodos[n], g.nodos[i], g.nodos[j])
            if 0 < t < 1 and _dist(g.nodos[n], q) <= UNION_M:
                g.partir(i, j, n)
                break

    avisos: list[str] = []
    # Varios terminales pueden caer en el mismo punto (dos difusores juntos, o junto a un
    # vértice): antes el segundo se descartaba con un aviso falso (revisión 07-11-2026).
    en_nodo: dict[int, list[Terminal]] = defaultdict(list)
    for term in terminales:
        p = (term.x, term.y)
        libres = [
            n
            for n in g.nodos_cerca(p, TERMINAL_M)
            if len(g.ady.get(n, ())) == 1 and n not in en_nodo
        ]
        if libres:
            n = min(libres, key=lambda k: _dist(g.nodos[k], p))
        else:
            n = g.punto_en_eje(p, TERMINAL_M)
        if n is None:
            avisos.append(f"Terminal {term.codigo}: no está junto a ningún eje; no se calcula.")
            continue
        en_nodo[n].append(term)

    if equipo is not None:
        # El punto de eje más cercano (un extremo o un punto intermedio), con el mismo
        # criterio que los terminales: antes se tomaba el vértice más cercano aunque el eje
        # pasara mucho más cerca de otro punto (revisión 07-11-2026).
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
            caudal_nodo[n] += sum(x.caudal_m3s for x in en_nodo[n])
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
        fin = camino[-1]
        terminal = en_nodo[fin][0] if not hijos[fin] and len(en_nodo.get(fin, ())) == 1 else None
        clase = (
            "terminal" if terminal else "principal" if (camino[0], camino[1]) in tronco else "ramal"
        )
        padre_id = final_de.get(camino[0])
        es_paso = True
        if padre_id is not None:
            anterior = next(c for c in crudos if c[-1] == camino[0])
            dir_padre = _direccion_final([g.nodos[i] for i in anterior])
            dir_hijo = _direccion_inicial(list(puntos))
            # Solo entre hermanos con caudal: uno vacío (que no se calcula) no puede quitarle
            # el «paso recto» al que sí lleva aire (revisión 07-11-2026).
            angulos = {
                tuple(c): _angulo(dir_padre, _direccion_inicial([g.nodos[i] for i in c]))
                for c in crudos
                if c[0] == camino[0] and caudal_nodo[c[-1]] > 0
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
        if n not in en_nodo or (not hijos[n] and len(en_nodo[n]) == 1):
            continue
        for term in en_nodo[n]:
            n_tramos += 1
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
