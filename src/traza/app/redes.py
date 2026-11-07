"""Redes de aire del proyecto (Etapa 5, docs/modules/redes_aire.md).

Junta el dibujo (ejes y bloques del DXF), los espacios confirmados y sus cargas, y llama a
los motores de topología y de conductos. Cada caudal dice de dónde sale: atributo CAUDAL
del bloque (manda) o las cargas del espacio repartidas entre sus terminales.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from traza.app import planos as calculo_planos
from traza.core.numeros import leer_numero
from traza.engines import conductos as cd
from traza.engines import topologia_conductos as topo
from traza.io.dxf import PlanoDxf

PREFIJO = {"impulsion": "D", "retorno": "R", "extraccion": "E"}
ATRIBUTO_CAUDAL = "CAUDAL"  # m³/h
#: ASHRAE Fundamentals, cap. 18: q_s = 1,23·Q·ΔT (W; Q en L/s) con aire normal; con la
#: densidad de la obra se escala por p/101 325.
CALOR_SENSIBLE_AIRE = 1230.0  # W/(m³/s·K)


def _distancia_segmento(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    largo2 = dx * dx + dy * dy
    s = (
        0.0
        if largo2 == 0
        else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / largo2))
    )
    return ((p[0] - a[0] - s * dx) ** 2 + (p[1] - a[1] - s * dy) ** 2) ** 0.5


@dataclass(frozen=True)
class TerminalRed:
    codigo: str
    bloque: str
    x: float
    y: float
    espacio: str | None  # «ESP-001 Oficinas»
    caudal_m3h: float
    origen_caudal: str


@dataclass(frozen=True)
class FilaMedicion:
    seccion: str
    longitud_m: float
    superficie_m2: float  # chapa o panel: perímetro × longitud


@dataclass(frozen=True)
class ResultadoRedAire:
    red: dict[str, Any]
    terminales: tuple[TerminalRed, ...]
    topologia: topo.Topologia | None
    calculo: cd.ResultadoRed | None
    avisos: tuple[str, ...] = ()
    medicion: tuple[FilaMedicion, ...] = field(default=())

    @property
    def caudal_total_m3h(self) -> float:
        """El de los terminales que de verdad cuelgan de la red (uno suelto no lleva aire
        por ella; revisión 07-11-2026)."""
        if self.topologia is None:
            return 0.0
        conectados = {t.tramo.terminal for t in self.topologia.tramos if t.tramo.terminal}
        return sum(t.caudal_m3h for t in self.terminales if t.codigo in conectados)

    @property
    def terminales_conectados(self) -> int:
        if self.topologia is None:
            return 0
        return len({t.tramo.terminal for t in self.topologia.tramos if t.tramo.terminal})

    @property
    def sfp_exigida(self) -> int:
        return cd.SFP_EXIGIDA[(self.red["tipo"], bool(self.red["climatizacion"]))]

    @property
    def rendimiento_minimo(self) -> float | None:
        """Rendimiento mínimo del grupo motoventilador para no pasar de la SFP exigida,
        solo con la presión de la red (sin el equipo): una cota inferior."""
        if self.calculo is None:
            return None
        return cd.rendimiento_minimo(self.calculo.presion_necesaria_pa, self.sfp_exigida)


def _atributo(bloque, nombre: str) -> str | None:
    for etiqueta, valor in bloque.atributos:
        if etiqueta.strip().upper() == nombre:
            return valor
    return None


def caudal_espacio_m3h(tipo: str, carga, salto_k: float, presion_pa: float) -> tuple[float, str]:
    """Caudal de un espacio según el tipo de red, con su explicación."""
    exterior = carga.aire_exterior_m3h
    if tipo == "extraccion":
        return exterior, "aire exterior del espacio (cargas)"
    # La carga del LOCAL: sin la del aire exterior de ventilación, que se trata en el equipo
    # (sí con la infiltración, que entra al local; revisión 07-11-2026).
    sensible = max(
        sum(p.sensible_w for p in carga.verano.partidas if p.concepto != "Ventilación"), 0.0
    )
    por_carga = sensible / (CALOR_SENSIBLE_AIRE * presion_pa / 101_325 * salto_k) * 3600
    impulsion = max(exterior, por_carga)
    if tipo == "impulsion":
        motivo = (
            f"carga sensible de verano con ΔT {salto_k:g} K"
            if por_carga >= exterior
            else "aire exterior (mayor que el de la carga)"
        )
        return impulsion, motivo
    return max(impulsion - exterior, 0.0), "impulsión menos aire exterior del espacio"


def calcular(
    red: dict[str, Any],
    plano: PlanoDxf,
    unidad: str,
    espacios: list[dict[str, Any]],
    cargas,  # ResultadoCargas | None
) -> ResultadoRedAire:
    f = calculo_planos.factor(unidad)
    avisos: list[str] = []
    tipo = red["tipo"]
    capa = red["capa_ejes"].casefold()
    polilineas = [
        [(x * f, y * f) for x, y in pts] for c, pts in plano.trazos if c.casefold() == capa
    ]
    nombres = {b.casefold() for b in red["bloques_terminales"]}
    bloques = sorted(
        (b for b in plano.bloques if b.nombre.casefold() in nombres), key=lambda b: (b.x, b.y)
    )
    equipo = None
    if red["bloque_equipo"]:
        eq = [b for b in plano.bloques if b.nombre.casefold() == red["bloque_equipo"].casefold()]
        if eq:
            # Con varios equipos iguales (varias UTA), el de esta red es el que está junto a
            # sus ejes, no el primero del fichero (revisión 07-11-2026).
            segmentos = [s for pl in polilineas for s in zip(pl, pl[1:], strict=False)]

            def lejania(b) -> float:
                # Distancia al EJE (no a sus vértices): un tramo recto largo solo tiene
                # vértices en los extremos (segunda revisión, 07-11-2026).
                x, y = b.x * f, b.y * f
                return min((_distancia_segmento((x, y), a, c) for a, c in segmentos), default=0.0)

            elegido = min(eq, key=lejania)
            equipo = (elegido.x * f, elegido.y * f)
            if len(eq) > 1:
                avisos.append(
                    f"Hay {len(eq)} bloques «{red['bloque_equipo']}»: se toma el más cercano a "
                    "los ejes de esta red."
                )
        else:
            avisos.append(f"No hay ningún bloque «{red['bloque_equipo']}» en el plano.")

    del_nivel = [
        e
        for e in espacios
        if e["plano_id"] == red["plano_id"]
        and (red["nivel_id"] is None or e["padre_id"] == red["nivel_id"])
    ]
    por_espacio: dict[str | None, list] = defaultdict(list)
    for b in bloques:
        x, y = b.x * f, b.y * f
        dentro = [e for e in del_nivel if e["contorno"].contiene(x, y)]
        e = min(dentro, key=lambda e: e["contorno"].area) if dentro else None
        por_espacio[e["id"] if e else None].append((b, e))

    cargas_por_id = {c.espacio_id: c for c in cargas.espacios} if cargas else {}
    presion = cargas.condiciones["normal"].presion_pa if cargas else 101_325.0
    terminales: list[TerminalRed] = []
    usados: set[str] = set()
    for _id, lista in sorted(
        por_espacio.items(),
        key=lambda kv: (kv[1][0][1] is None, kv[1][0][1] and kv[1][0][1]["codigo"]),
    ):
        _b0, e = lista[0]
        q_esp, motivo = None, ""
        if e is not None and e["id"] in cargas_por_id:
            q_esp, motivo = caudal_espacio_m3h(
                tipo, cargas_por_id[e["id"]], red["salto_impulsion"], presion
            )
        for b, _e in lista:
            n = len(terminales) + 1
            codigo = _atributo(b, "REF") or f"{PREFIJO[tipo]}{n:02d}"
            if codigo in usados:  # dos bloques con la misma REF: se distinguen
                avisos.append(f"Referencia «{codigo}» repetida: el segundo pasa a {codigo}-{n}.")
                codigo = f"{codigo}-{n}"
            usados.add(codigo)
            texto = _atributo(b, ATRIBUTO_CAUDAL)
            donde = f"{e['codigo']} {e['nombre'] or ''}".strip() if e else None
            if texto:
                try:
                    caudal = float(leer_numero(texto))
                    origen = "atributo CAUDAL del bloque (m³/h)"
                except ValueError:
                    avisos.append(f"{codigo}: CAUDAL «{texto}» no es un número; no se usa.")
                    caudal, origen = None, ""
            else:
                caudal, origen = None, ""
            if caudal is None and q_esp is not None:
                caudal = q_esp / len(lista)
                origen = f"{motivo}, entre {len(lista)} terminal(es) de {donde}"
            if caudal is None:
                razon = "fuera de todo espacio" if e is None else "su espacio no tiene cargas"
                avisos.append(f"{codigo}: sin caudal ({razon}); ponle un atributo CAUDAL.")
                caudal, origen = 0.0, "sin caudal"
            terminales.append(
                TerminalRed(codigo, b.nombre, b.x * f, b.y * f, donde, caudal, origen)
            )

    # Espacios con caudal y sin ningún terminal de esta red: su aire no entra en el cálculo
    # (p. ej. retorno por plenum). Se dice, para que no parezca completo (revisión 07-11-2026).
    if cargas is not None:
        for e in del_nivel:
            c = cargas_por_id.get(e["id"])
            if c is None or e["id"] in por_espacio:
                continue
            q, _ = caudal_espacio_m3h(tipo, c, red["salto_impulsion"], presion)
            if q > 0:
                avisos.append(
                    f"{e['codigo']} {e['nombre'] or ''}: necesita {q:.0f} m³/h y no tiene "
                    "terminales de esta red."
                )
    con_caudal = [t for t in terminales if t.caudal_m3h > 0]
    try:
        topologia = topo.leer(
            polilineas,
            [topo.Terminal(t.codigo, t.x, t.y, t.caudal_m3h / 3600) for t in con_caudal],
            equipo,
        )
    except topo.TopologiaInvalida as exc:
        return ResultadoRedAire(red, tuple(terminales), None, None, (*avisos, str(exc)))
    avisos.extend(topologia.avisos)
    if not topologia.tramos:
        avisos.append("La red no tiene ningún tramo con caudal.")
        return ResultadoRedAire(red, tuple(terminales), topologia, None, tuple(avisos))
    calculo = cd.calcular_red(
        [t.tramo for t in topologia.tramos],
        tipo,
        red["friccion_objetivo"],
        red["alto_maximo"],
        red["forma"],
        cd.aire(20.0, presion),
    )
    for t in calculo.tramos:
        for a in t.avisos:
            avisos.append(f"{t.tramo.id}: {a}")
    medicion: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for t in calculo.tramos:
        m = medicion[t.seccion.texto()]
        m[0] += t.tramo.longitud_m
        m[1] += t.tramo.longitud_m * t.seccion.perimetro_m
    filas = tuple(FilaMedicion(s, v[0], v[1]) for s, v in sorted(medicion.items()) if v[0] > 0)
    return ResultadoRedAire(red, tuple(terminales), topologia, calculo, tuple(avisos), filas)
