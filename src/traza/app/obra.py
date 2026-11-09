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
    if total_doc is not None and r.venta is not None and abs(total_doc - r.venta) > 0.01:
        a.append(
            f"La suma de partidas no coincide con el total que declara el documento "
            f"({total_doc:.2f} €)."
        )
