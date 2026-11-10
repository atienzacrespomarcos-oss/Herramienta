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
    que no casa, también sin código, se lista con su importe: nunca se descarta en silencio
    (revisión 09-11-2026)."""
    venta: dict[str, float | None] = {}
    sin_codigo_venta = 0
    for p in partidas_venta:
        clave = _clave(p["codigo"])
        if not clave:
            sin_codigo_venta += 1
            continue
        # Un código repetido en la venta: su importe es la suma de todas sus líneas.
        previo = venta.get(clave)
        imp = p["importe"]
        venta[clave] = None if imp is None and previo is None else (previo or 0.0) + (imp or 0.0)
    capitulos = {
        _clave(c[0]) for p in partidas_venta for c in (p.get("capitulo") or []) if c and c[0]
    }
    r = ResultadoCertificacion(total_excel=leido.total_excel, avisos=list(leido.avisos))
    for f in leido.filas:
        clave = _clave(f.codigo)
        if clave and clave in venta:
            if clave in r.por_partida:
                r.avisos.append(f"{f.codigo} (fila {f.fila}) está dos veces: se suman las dos.")
            previo = r.por_partida.get(clave, (f.codigo, f.resumen, 0.0))[2]
            r.por_partida[clave] = (f.codigo, f.resumen, previo + (f.importe_origen or 0.0))
        elif clave and (clave in capitulos or f.naturaleza.lower().startswith("cap")):
            r.capitulos += 1
        elif f.importe_origen:
            r.no_casan.append((f.fila, f.codigo or f"«{f.resumen}»", f.resumen, f.importe_origen))
    if not r.por_partida:
        raise ValueError(
            "Ningún código del Excel coincide con las partidas del presupuesto contratado: "
            "¿es la certificación de esta obra?"
        )
    if not any(v[2] for v in r.por_partida.values()):
        raise ValueError(
            "Las partidas de la venta están todas a 0 € en el Excel: ¿son fórmulas sin el "
            "resultado guardado? Ábrelo en Excel y guárdalo."
        )
    if sin_codigo_venta:
        r.avisos.append(
            f"{sin_codigo_venta} partida(s) de la venta sin código: no se pueden certificar "
            "desde el Excel (se enlaza por código)."
        )
    for clave, (codigo, _r, origen) in r.por_partida.items():
        imp = venta[clave]
        if imp is not None and round(origen - imp, 2) > 0.01:
            r.avisos.append(
                f"{codigo}: certificado a origen por encima de su venta (más del 100 %)."
            )
    if r.no_casan:
        r.avisos.append(
            f"{len(r.no_casan)} línea(s) con importe que no son partidas de la venta (no suman, "
            f"{sum(x[3] for x in r.no_casan):.2f} €): ".replace(".", ",")
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


# --- Bloque 3: futuribles (escenarios sí/no) ----------------------------------------------
#
# Usuario (09-11-2026): «previsiones y parte de futuribles (si aprueban tal o no oferta)»;
# escenarios sí/no, sin probabilidades. «Venta real y previsión (no confundir con
# ampliaciones y demás)»: los futuribles nunca entran en tu previsión; se suman aparte.


@dataclass(frozen=True)
class Futurible:
    id: str
    titulo: str
    venta: float | None  # None: la del modificado no se puede calcular entera
    coste: float
    marcado: bool
    origen: str  # «escrita por ti» o «modificado nº N …»
    nota: str | None = None
    avisos: tuple[str, ...] = ()
    modificado_id: str | None = None  # None: la venta la escribió el usuario

    @property
    def margen(self) -> float | None:
        return None if self.venta is None else self.venta - self.coste


@dataclass
class Escenario:
    """Tu previsión sin futuribles y con los marcados (sus ventas y costes sumados)."""

    prevision: dict[str, Any] | None
    futuribles: list[Futurible]

    @property
    def marcados(self) -> list[Futurible]:
        return [f for f in self.futuribles if f.marcado]

    @property
    def venta_marcados(self) -> float | None:
        """None si alguno marcado no tiene venta: no se suma una cifra a medias."""
        ventas = [f.venta for f in self.marcados]
        return None if any(v is None for v in ventas) else round(sum(ventas), 2)

    @property
    def coste_marcados(self) -> float:
        return round(sum(f.coste for f in self.marcados), 2)

    @property
    def venta(self) -> float | None:
        v, p = self.venta_marcados, self.prevision
        return None if p is None or v is None else round(p["venta_total"] + v, 2)

    @property
    def coste(self) -> float | None:
        p = self.prevision
        return None if p is None else round(p["coste_total"] + self.coste_marcados, 2)

    @property
    def margen(self) -> float | None:
        return None if self.venta is None or self.coste is None else self.venta - self.coste

    @property
    def margen_pct(self) -> float | None:
        m = self.margen
        return None if m is None or not self.venta else 100 * m / self.venta


def venta_por_codigo(
    partidas_venta: list[dict[str, Any]],
) -> dict[str, tuple[str, str, float | None]]:
    """clave → (código, resumen, venta), en el orden del presupuesto; como en el cruce de
    las certificaciones (un código repetido suma sus líneas, cada una al céntimo). Las
    partidas sin código no se pueden enlazar y no salen."""
    salida: dict[str, tuple[str, str, float | None]] = {}
    for p in partidas_venta:
        clave = _clave(p["codigo"])
        if not clave:
            continue
        imp = None if p["importe"] is None else round(p["importe"], 2)
        if clave in salida:
            codigo, texto, previo = salida[clave]
            imp = None if imp is None and previo is None else (previo or 0.0) + (imp or 0.0)
            salida[clave] = (codigo, texto, imp)
        else:
            salida[clave] = (p["codigo"].strip(), p["resumen"] or "", imp)
    return salida


# --- Bloque 4b: facturas desde el listado del ERP -------------------------------------------


def clave_factura(proveedor: str, numero: str) -> tuple[str, str]:
    """La misma que RegistrarFactura: «ACME» y «Acme», o con espacios de más, son la misma."""
    return " ".join(proveedor.split()).casefold(), " ".join(numero.split()).casefold()


@dataclass(frozen=True)
class FacturaPropuesta:
    leida: Any  # io/facturas_erp.FacturaLeida
    #: «nueva», «apuntada» (ya está, igual) o «distinta» (ya está con otro importe o fecha:
    #: no se sobrescribe; se avisa).
    estado: str
    paquete: str | None  # el que propone TRAZA (None: lo elige el usuario)
    motivo: str  # por qué ese paquete, o por qué ninguno


def proponer_facturas(
    leidas: list[Any],
    existentes: list[dict[str, Any]],
    paquetes: list[str],
    cerrados: set[str],
) -> list[FacturaPropuesta]:
    """Qué facturas del listado son nuevas y a qué paquete irían. El paquete se propone,
    nunca se impone (lo confirma el usuario):
    1. Si el listado trae en «obra» o «concepto» exactamente el nombre de un paquete.
    2. Si no, el paquete donde están las demás facturas de ese proveedor en esta obra
       (si están todas en uno).
    Un paquete cerrado no se propone (no admite facturas)."""
    por_clave = {clave_factura(f["proveedor"], f["numero"]): f for f in existentes}
    historial: dict[str, set[str]] = {}
    for f in existentes:
        historial.setdefault(clave_factura(f["proveedor"], "")[0], set()).add(f["paquete"])
    nombres = {p.casefold(): p for p in paquetes}
    salida = []
    for x in leidas:
        previa = por_clave.get(clave_factura(x.proveedor, x.numero))
        if previa is not None:
            igual = (
                round(previa["importe"], 2) == round(x.importe, 2) and previa["fecha"] == x.fecha
            )
            salida.append(
                FacturaPropuesta(
                    x,
                    "apuntada" if igual else "distinta",
                    previa["paquete"],
                    "ya está apuntada"
                    if igual
                    else (
                        f"ya está apuntada con {previa['importe']:.2f} € del "
                        f"{previa['fecha']}: no se cambia (corrígela a mano si hace falta)"
                    ).replace(".", ",", 1),
                )
            )
            continue
        paquete, motivo = None, "elige el paquete"
        for texto in (x.obra, x.concepto):
            candidato = nombres.get(" ".join(texto.split()).casefold())
            if candidato:
                paquete, motivo = candidato, "el listado lo dice"
                break
        if paquete is None:
            usados = historial.get(clave_factura(x.proveedor, "")[0], set())
            if len(usados) == 1:
                paquete, motivo = next(iter(usados)), "sus otras facturas van ahí"
            elif len(usados) > 1:
                motivo = "el proveedor tiene facturas en varios paquetes: elige"
        if paquete is not None and paquete in cerrados:
            paquete, motivo = None, f"«{paquete}» está cerrado: elige otro o reábrelo"
        salida.append(FacturaPropuesta(x, "nueva", paquete, motivo))
    return salida
