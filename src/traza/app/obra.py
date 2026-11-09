"""Control de la obra: venta frente a coste objetivo (docs/modules/obra.md, bloque 1).

Puro sobre lo leído: las partidas del presupuesto contratado (una medición) y el coste
objetivo del Excel de Presto del usuario. No escribe nada; lo usan la pantalla y el Excel.

- Venta = suma de las partidas del presupuesto contratado (cantidad × precio).
- Objetivo = suma de las partidas del coste objetivo (con las líneas añadidas a mano).
- Margen previsto = venta − objetivo (y su % sobre la venta).
- Las partidas de venta y de coste se enlazan por **código** (sin espacios a los lados, sin
  distinguir mayúsculas); las que no casan se listan, no se descartan en silencio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LineaComparada:
    codigo: str
    resumen: str
    venta: float | None  # None: la partida no está en el presupuesto contratado
    objetivo: float | None  # None: la partida no está en el coste objetivo

    @property
    def margen(self) -> float | None:
        if self.venta is None or self.objetivo is None:
            return None
        return self.venta - self.objetivo


@dataclass
class ResumenObra:
    venta: float | None  # None: sin presupuesto contratado
    objetivo: float | None  # None: sin coste objetivo
    paquetes: dict[str, float] = field(default_factory=dict)  # objetivo por paquete
    lineas: list[LineaComparada] = field(default_factory=list)
    venta_sin_importe: int = 0  # partidas de venta sin cantidad o sin precio
    venta_sin_codigo: int = 0  # partidas de venta que no se pueden enlazar con el coste
    avisos_venta: list[str] = field(default_factory=list)
    avisos_coste: list[str] = field(default_factory=list)

    @property
    def avisos(self) -> list[str]:
        return [*self.avisos_venta, *self.avisos_coste]

    @property
    def margen(self) -> float | None:
        if self.venta is None or self.objetivo is None:
            return None
        return self.venta - self.objetivo

    @property
    def margen_pct(self) -> float | None:
        m = self.margen
        return None if m is None or not self.venta else 100 * m / self.venta

    @property
    def solo_en_venta(self) -> list[LineaComparada]:
        return [x for x in self.lineas if x.objetivo is None]

    @property
    def solo_en_coste(self) -> list[LineaComparada]:
        return [x for x in self.lineas if x.venta is None]


def _clave(codigo: str | None) -> str:
    return (codigo or "").strip().casefold()


def resumir(
    partidas_venta: list[dict[str, Any]] | None,
    coste: dict[str, Any] | None,
    medicion: dict[str, Any] | None = None,
) -> ResumenObra:
    """`partidas_venta`: filas de `Proyecto.partidas` (None si no hay presupuesto
    contratado); `medicion`, su fila (para avisar de lo que el lector no convirtió).
    `coste`: `Proyecto.coste_objetivo()` (None si no se ha importado)."""
    r = ResumenObra(None, None)
    venta: dict[str, tuple[str, float]] = {}
    if partidas_venta is not None:
        con_importe = [p for p in partidas_venta if p["importe"] is not None]
        # Cada línea redondeada al céntimo, como Presto y el Excel de costes (revisión
        # 09-11-2026: sin redondear, cientos de líneas desviaban el margen).
        r.venta = sum(round(p["importe"], 2) for p in con_importe) if con_importe else None
        for p in partidas_venta:
            if p["importe"] is None:
                r.venta_sin_importe += 1
            clave = _clave(p["codigo"])
            if not clave:
                r.venta_sin_codigo += 1
                continue
            previo = venta.get(clave, ("", 0.0))[1]
            venta[clave] = (p["resumen"] or "", previo + round(p["importe"] or 0.0, 2))
        _avisos_venta(r, partidas_venta, medicion)
    objetivo: dict[str, tuple[str, float]] = {}
    if coste is not None:
        r.objetivo = sum(p["importe"] for p in coste["partidas"])
        r.paquetes = dict.fromkeys(coste["paquetes"], 0.0)
        for p in coste["partidas"]:
            for nombre, importe in p["paquetes"].items():
                r.paquetes[nombre] = r.paquetes.get(nombre, 0.0) + importe
            clave = _clave(p["codigo"]) or f"«{p['resumen']}»"  # añadida a mano: sin código
            previo = objetivo.get(clave, ("", 0.0))[1]
            objetivo[clave] = (p["resumen"], previo + p["importe"])
        r.avisos_coste += coste["avisos"]
    if partidas_venta is not None and coste is not None:
        for clave in [*venta, *(k for k in objetivo if k not in venta)]:
            v, o = venta.get(clave), objetivo.get(clave)
            r.lineas.append(
                LineaComparada(
                    clave if not clave.startswith("«") else "",
                    (v or o)[0],
                    v[1] if v else None,
                    o[1] if o else None,
                )
            )
    return r


def _avisos_venta(r: ResumenObra, partidas: list[dict[str, Any]], medicion) -> None:
    """Lo que puede dejar la venta corta o sin comprobar, dicho (nunca en silencio)."""
    a = r.avisos_venta
    if r.venta is None and partidas:
        a.append("Ninguna partida del presupuesto contratado tiene importe: la venta no consta.")
    elif r.venta_sin_importe:
        a.append(
            f"{r.venta_sin_importe} partida(s) del presupuesto contratado sin cantidad o sin "
            "precio: no suman en la venta (revísalas en «Mediciones y ofertas»)."
        )
    a_revisar = sum(1 for p in partidas if p.get("estado") == "a_revisar")
    if a_revisar:
        a.append(
            f"{a_revisar} partida(s) «a revisar» (leídas sin comprobar del todo) suman en la "
            "venta: confírmalas en «Mediciones y ofertas»."
        )
    if r.venta_sin_codigo:
        a.append(
            f"{r.venta_sin_codigo} partida(s) de venta sin código: suman en la venta pero no "
            "se pueden enlazar con el coste."
        )
    if medicion is None:
        return
    if medicion.get("omitidas"):
        a.append(
            f"{medicion['omitidas']} línea(s) del documento no se convirtieron en partida: la "
            "venta puede quedarse corta."
        )
    total_doc = medicion.get("total_documento")
    diferencia = None if total_doc is None or r.venta is None else total_doc - r.venta
    if diferencia is not None and round(abs(diferencia), 2) > 0.01:
        a.append(
            f"La suma de partidas no coincide con el total que declara el documento "
            f"({total_doc:.2f} €)."
        )


# --- Bloque 2a: coste real, foto de lo real y previsión del usuario ---------------------
#
# Usuario (09-11-2026): «Quiero una foto de lo real (coste − venta hasta que yo actualice) y
# una previsión que yo haga»; «lo quiero como un número total. El tema de hacerlo por
# paquetes a mí me sirve para ver qué partidas se me está descuadrando».


@dataclass(frozen=True)
class EstadoPaquete:
    nombre: str
    objetivo: float
    facturado: float
    facturas: int
    cerrado: bool
    #: False: sus facturas son de un paquete que ya no está en el coste objetivo (se
    #: reimportó con otros nombres). Sale en la lista para poder corregirlas o quitarlas.
    en_objetivo: bool = True

    @property
    def diferencia(self) -> float:
        """Objetivo − facturado: positiva, queda margen; negativa, se ha pasado."""
        return self.objetivo - self.facturado


@dataclass
class Foto:
    paquetes: list[EstadoPaquete]
    facturado: float
    certificado: float | None  # a origen; None sin certificaciones
    prevision: dict[str, Any] | None
    venta: float | None
    objetivo: float | None
    #: Facturas de paquetes que ya no están en el coste objetivo (se reimportó con otros).
    huerfanas: dict[str, float] = field(default_factory=dict)

    @property
    def margen_real(self) -> float | None:
        """Lo certificado menos lo facturado, a la fecha de la última actualización."""
        return None if self.certificado is None else self.certificado - self.facturado

    @property
    def margen_previsto(self) -> float | None:
        p = self.prevision
        return None if p is None else p["venta_total"] - p["coste_total"]

    @property
    def margen_previsto_pct(self) -> float | None:
        p, m = self.prevision, self.margen_previsto
        return None if p is None or not p["venta_total"] else 100 * m / p["venta_total"]

    @property
    def descuadrados(self) -> list[EstadoPaquete]:
        """Paquetes que ya se han pasado de su objetivo (más de un céntimo)."""
        return [x for x in self.paquetes if round(x.diferencia, 2) < -0.01]


def foto(
    resumen: ResumenObra,
    facturas: list[dict[str, Any]],
    cerrados: set[str],
    certificado: float | None,
    prevision: dict[str, Any] | None,
) -> Foto:
    por_paquete: dict[str, list[float]] = {}
    for f in facturas:
        por_paquete.setdefault(f["paquete"], []).append(f["importe"])
    paquetes = [
        EstadoPaquete(
            nombre,
            objetivo,
            round(sum(por_paquete.get(nombre, [])), 2),
            len(por_paquete.get(nombre, [])),
            nombre in cerrados,
        )
        for nombre, objetivo in resumen.paquetes.items()
    ]
    huerfanas = {n: round(sum(v), 2) for n, v in por_paquete.items() if n not in resumen.paquetes}
    paquetes += [
        EstadoPaquete(n, 0.0, v, len(por_paquete[n]), n in cerrados, en_objetivo=False)
        for n, v in huerfanas.items()
    ]
    return Foto(
        paquetes,
        round(sum(f["importe"] for f in facturas), 2),
        certificado,
        prevision,
        resumen.venta,
        resumen.objetivo,
        huerfanas,
    )


# --- Bloque 2b: certificaciones (las hace el usuario; TRAZA las lee y las suma) ----------


@dataclass
class ResultadoCertificacion:
    """Lo leído de un Excel de certificación, cruzado con la venta por código."""

    #: clave del código → (código, resumen, importe a origen)
    por_partida: dict[str, tuple[str, str, float]] = field(default_factory=dict)
    no_casan: list[tuple[int, str, str, float]] = field(default_factory=list)  # fila, cód…
    capitulos: int = 0  # filas de capítulo o subtotal, que no suman (ya suman sus partidas)
    total_excel: tuple[int, float] | None = None
    avisos: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return round(sum(round(v[2], 2) for v in self.por_partida.values()), 2)


def cruzar_certificacion(
    leido: Any, partidas_venta: list[dict[str, Any]]
) -> ResultadoCertificacion:
    """Solo suman las filas cuyo código es una partida de la venta: un capítulo o un
    subtotal (su código es de capítulo, o su naturaleza lo dice) no se suma dos veces. Lo
    que no casa se lista con su importe, nunca se descarta en silencio."""
    venta = {_clave(p["codigo"]): p for p in partidas_venta if _clave(p["codigo"])}
    capitulos = {
        _clave(c[0]) for p in partidas_venta for c in (p.get("capitulo") or []) if c and c[0]
    }
    r = ResultadoCertificacion(total_excel=leido.total_excel, avisos=list(leido.avisos))
    for f in leido.filas:
        clave = _clave(f.codigo)
        if clave in venta:
            if clave in r.por_partida:
                r.avisos.append(f"{f.codigo} (fila {f.fila}) está dos veces: se suman las dos.")
            previo = r.por_partida.get(clave, (f.codigo, f.resumen, 0.0))[2]
            r.por_partida[clave] = (f.codigo, f.resumen, previo + (f.importe_origen or 0.0))
        elif clave in capitulos or "cap" in f.naturaleza.lower():
            r.capitulos += 1
        elif f.importe_origen:
            r.no_casan.append((f.fila, f.codigo, f.resumen, f.importe_origen))
    if not r.por_partida:
        raise ValueError(
            "Ningún código del Excel coincide con las partidas del presupuesto contratado: "
            "¿es la certificación de esta obra?"
        )
    for clave, (codigo, _r, origen) in r.por_partida.items():
        imp = venta[clave]["importe"]
        if imp is not None and round(origen - imp, 2) > 0.01:
            r.avisos.append(
                f"{codigo}: certificado a origen por encima de su venta (más del 100 %)."
            )
    if r.no_casan:
        r.avisos.append(
            f"{len(r.no_casan)} línea(s) con importe que no son partidas de la venta (no suman): "
            + ", ".join(f"{c} (fila {n})" for n, c, _r, _i in r.no_casan[:8])
            + ("…" if len(r.no_casan) > 8 else "")
        )
    if r.total_excel is not None and round(abs(r.total_excel[1] - r.total), 2) > 0.01:
        r.avisos.append(
            f"La suma de las partidas ({r.total:.2f} €) no coincide con el TOTAL del Excel "
            f"({r.total_excel[1]:.2f} €, fila {r.total_excel[0]})".replace(".", ",")
            + ": revisa las líneas que no casan."
        )
    return r
