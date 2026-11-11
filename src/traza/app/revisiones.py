"""Revisiones del diseño y su comparación (RF-009, docs/modules/revisiones.md).

Una revisión es el proyecto congelado (persistence/carpeta.emitir_revision). Comparar dos
estados (una revisión y lo actual, o dos revisiones) es comparar su **resumen**: los datos y
los resultados que deciden, cada uno con su unidad y redondeado a la precisión con que se
muestra (una diferencia de coma flotante no es un cambio).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Precisión con que se compara y se muestra cada unidad.
DECIMALES = {"m²": 2, "m": 2, "m³": 1, "kW": 2, "m³/h": 0, "Pa": 0, "m c.a.": 2, "A": 1, "%": 2}
MCA = 9806.65


@dataclass(frozen=True)
class Dato:
    apartado: str  # Espacios, Cargas, Redes de aire, Sistema hidráulico, Subcuadros
    elemento: str
    dato: str
    valor: Any  # número (redondeado) o texto
    unidad: str = ""


@dataclass(frozen=True)
class Cambio:
    apartado: str
    elemento: str
    dato: str
    antes: Any  # None: no existía
    ahora: Any  # None: ya no existe
    unidad: str

    @property
    def diferencia(self):
        if isinstance(self.antes, int | float) and isinstance(self.ahora, int | float):
            return round(self.ahora - self.antes, DECIMALES.get(self.unidad, 2))
        return None


def _r(valor: float, unidad: str) -> float:
    return round(float(valor), DECIMALES.get(unidad, 2))


def resumen(p) -> list[Dato]:
    """Lo que decide del proyecto `p` (actual o revisión). Lo que no se calcula entra como
    texto con el motivo: que deje de calcular también es un cambio."""
    from traza.app.ordenes import OrdenRechazada
    from traza.engines.hidraulica import SERVICIOS
    from traza.io.unifilar_dxf import cable

    datos: list[Dato] = []

    def add(apartado, elemento, dato, valor, unidad=""):
        if isinstance(valor, int | float) and not isinstance(valor, bool):
            valor = _r(valor, unidad)
        datos.append(Dato(apartado, elemento, dato, valor, unidad))

    def nombre_espacio(e) -> str:
        return " ".join(x for x in (e["codigo"], e["nombre"]) if x)

    for e in p.espacios():
        n = nombre_espacio(e)
        add("Espacios", n, "Superficie", e["superficie"] or 0.0, "m²")
        for clave, texto in (
            ("altura", "Altura"),
            ("altura_minima", "Altura mínima"),
            ("altura_maxima", "Altura máxima"),
        ):
            if e.get(clave) is not None:
                add("Espacios", n, texto, e[clave], "m")
    if p.espacios() and p.cargas_config() is not None:
        try:
            cargas = p.calcular_cargas()
        except OrdenRechazada as exc:
            add("Cargas", "Proyecto", "Cálculo", f"No se calcula: {exc}")
        else:
            for c in cargas.espacios:
                n = " ".join(x for x in (c.codigo, c.nombre) if x)
                add("Cargas", n, "Uso", c.uso.nombre)
                add("Cargas", n, "Calefacción", c.invierno.total_w / 1000, "kW")
                add("Cargas", n, "Refrigeración", c.verano.total_w / 1000, "kW")
                add("Cargas", n, "Aire exterior", c.aire_exterior_m3h, "m³/h")
            add("Cargas", "Proyecto", "Calefacción total", cargas.invierno_total_w / 1000, "kW")
            add(
                "Cargas",
                "Proyecto",
                "Refrigeración simultánea",
                cargas.verano_simultaneo_w / 1000,
                "kW",
            )
    for red in p.redes():
        n = red["nombre"]
        try:
            r = p.calcular_red(red["id"])
        except OrdenRechazada as exc:
            add("Redes de aire", n, "Cálculo", f"No se calcula: {exc}")
            continue
        add("Redes de aire", n, "Caudal", r.caudal_total_m3h, "m³/h")
        add("Redes de aire", n, "Terminales conectados", r.terminales_conectados)
        if r.calculo is not None:
            add("Redes de aire", n, "Presión necesaria", r.calculo.presion_necesaria_pa, "Pa")
    for s in p.sistemas_hidraulicos():
        try:
            r = p.calcular_sistema_hidraulico(s["id"])
        except OrdenRechazada as exc:
            add("Sistema hidráulico", s["nombre"], "Cálculo", f"No se calcula: {exc}")
            continue
        for sv in r.servicios:
            n = f"{s['nombre']} · {SERVICIOS[sv.clave]}"
            add("Sistema hidráulico", n, "Potencia del generador", sv.potencia_kw, "kW")
            add("Sistema hidráulico", n, "Caudal", sv.caudal_m3s * 3600, "m³/h")
            add("Sistema hidráulico", n, "Tubería del primario", sv.primario.tubo.nombre)
            add("Sistema hidráulico", n, "Bomba de primario", sv.altura_primario_pa / MCA, "m c.a.")
            for c in sv.circuitos:
                nc = f"{n} · {c.datos.nombre}"
                add("Sistema hidráulico", nc, "Unidades", c.datos.unidades)
                add("Sistema hidráulico", nc, "Caudal", c.caudal_m3s * 3600, "m³/h")
                add("Sistema hidráulico", nc, "Tubería", c.tubo.tubo.nombre)
                add("Sistema hidráulico", nc, "Bomba", c.altura_bomba_pa / MCA, "m c.a.")
    for sub in p.subcuadros():
        n = sub["nombre"]
        try:
            r = p.calcular_subcuadro(sub["id"])
        except OrdenRechazada as exc:
            add("Subcuadros", n, "Cálculo", f"No se calcula: {exc}")
            continue
        a = r.alimentacion
        add("Subcuadros", n, "Alimentación", cable(a))
        add("Subcuadros", n, "Interruptor general", f"{a.calibre_a or '>160'} A")
        add("Subcuadros", n, "Cumple", "CUMPLE" if r.cumple else "NO CUMPLE")
        for s in r.salidas:
            ns = f"{n} · {s.nombre}"
            add("Subcuadros", ns, "Potencia", s.potencia_kw, "kW")
            add("Subcuadros", ns, "Cable", cable(s))
            add("Subcuadros", ns, "Caída de tensión total", s.caida_total_pct, "%")
    return datos


def comparar(antes: list[Dato], ahora: list[Dato]) -> list[Cambio]:
    """Lo que cambia, lo nuevo y lo que ya no está, en el orden del resumen de `ahora` y
    después lo desaparecido."""
    clave = lambda d: (d.apartado, d.elemento, d.dato)  # noqa: E731
    a = {clave(d): d for d in antes}
    b = {clave(d): d for d in ahora}
    cambios = []
    for k, d in b.items():
        previo = a.get(k)
        if previo is None:
            cambios.append(Cambio(*k, None, d.valor, d.unidad))
        elif previo.valor != d.valor:
            cambios.append(Cambio(*k, previo.valor, d.valor, d.unidad or previo.unidad))
    for k, d in a.items():
        if k not in b:
            cambios.append(Cambio(*k, d.valor, None, d.unidad))
    return cambios
