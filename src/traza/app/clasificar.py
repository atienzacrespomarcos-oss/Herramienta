"""Qué es cada documento recibido: crear la obra desde sus documentos (docs/modules/obra.md,
bloque 4c).

Usuario (10-11-2026): echar **todos los documentos recibidos** («a veces habrá más otras
menos») y que TRAZA genere la obra; «habrá 1 presupuesto y mediciones, planos, etc.»; «lo
que yo te pase, sea lo que sea, te valga».

TRAZA **propone** qué es cada documento mirando su contenido (nunca su nombre), y el usuario
lo confirma o lo cambia antes de montar nada. Lo que se reconoce sin IA:

- **BC3**: con precios, presupuesto (el de mayor importe, si la obra aún no tiene venta
  contratada; los demás, mediciones); sin precios, medición.
- **Hoja de cálculo**: comparativo de costes de Presto (io/coste_presto), listado de
  facturas (io/facturas_erp), certificación (io/certificacion_excel) por sus columnas.
- **DXF**: plano.

Lo que necesitaría la IA (un PDF, o un Excel que no es nada de lo anterior) se propone como
**solo documentación**, salvo el presupuesto si no hay otro: ningún documento sale del
equipo sin que el usuario lo elija (CLAUDE.md, línea roja 7). En la tabla se dice cuáles
se leerían con la IA.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from traza.io import bc3, certificacion_excel, coste_presto, facturas_erp, hoja_calculo

TIPOS = {
    "presupuesto": "Presupuesto contratado (venta)",
    "medicion": "Medición",
    "oferta": "Oferta de proveedor",
    "coste_objetivo": "Coste objetivo (comparativo de Presto)",
    "certificacion": "Certificación",
    "facturas": "Listado de facturas del ERP",
    "plano": "Plano (DXF)",
    "documentacion": "Solo documentación",
}
#: Qué puede ser cada formato (lo que TRAZA sabe leer de él).
_POSIBLES = {
    "bc3": ("presupuesto", "medicion", "oferta", "documentacion"),
    "hoja": (
        "coste_objetivo",
        "certificacion",
        "facturas",
        "presupuesto",
        "medicion",
        "oferta",
        "documentacion",
    ),
    "pdf": ("presupuesto", "medicion", "oferta", "documentacion"),
    "dxf": ("plano", "documentacion"),
    "otro": ("documentacion",),
}
LEIDOS_CON_MEDICION = ("presupuesto", "medicion", "oferta")


@dataclass(frozen=True)
class Propuesta:
    documento_id: str
    nombre: str
    extension: str
    tipo: str  # clave de TIPOS
    motivo: str
    posibles: tuple[str, ...]
    numero: int | None = None  # certificación: el nº que dice el documento, si lo dice
    #: Lo que TRAZA ha reconocido por los títulos de una hoja (coste objetivo, certificación
    #: o facturas), o None. Elegir otro de esos tipos necesita la IA para saber qué columna
    #: es qué.
    reconocido: str | None = None
    #: Ya leído (como medición, coste objetivo, certificación o facturas): no se lee otra vez.
    uso: str | None = None

    def con_ia(self, tipo: str | None = None) -> bool:
        """Leerlo como `tipo` necesita la IA (su contenido, o sus títulos y unas filas, se
        envían a Anthropic). Revisión 10-11-2026: una hoja no reconocida elegida como
        certificación o facturas también va a la IA, y la tabla tiene que decirlo."""
        t = tipo or self.tipo
        if t in LEIDOS_CON_MEDICION:
            return self.extension != ".bc3"
        return t in ("certificacion", "facturas") and t != self.reconocido


def _formato(extension: str) -> str:
    e = extension.lower()
    if e == ".bc3":
        return "bc3"
    if hoja_calculo.es_hoja(e):
        return "hoja"
    if e == ".pdf":
        return "pdf"
    if e == ".dxf":
        return "dxf"
    return "otro"


class _Bc3Ilegible(Exception):
    pass


def _importe_bc3(ruta) -> float | None:
    """Importe total de un BC3 (cantidad × precio de sus partidas), o None si no tiene
    precios. _Bc3Ilegible si no se puede leer (se dice, no se toma por «sin precios»)."""
    try:
        partidas, _ = bc3.partidas(bc3.leer_bc3(ruta))
    except Exception as exc:  # noqa: BLE001
        raise _Bc3Ilegible(str(exc)) from exc
    con_precio = [
        p.cantidad * p.precio for p in partidas if p.cantidad is not None and p.precio is not None
    ]
    total = sum(con_precio)
    return total if con_precio and total else None


_NUMERO_CERT = re.compile(r"certificaci[oó]n\s*(?:n\s*[ºo°.]*\s*)?(\d{1,3})\b", re.IGNORECASE)


def _numero_certificacion(ruta, nombre: str) -> int | None:
    """El nº que dice la propia certificación en sus primeras filas, o su nombre."""
    try:
        texto = certificacion_excel.volcado_titulos(ruta, filas=8)
    except Exception:  # noqa: BLE001
        texto = ""
    for fuente in (texto, nombre):
        m = _NUMERO_CERT.search(fuente)
        if m:
            return int(m.group(1))
    return None


def _que_hoja(ruta) -> tuple[str, str]:
    """(tipo, motivo) de una hoja de cálculo, sin IA."""
    try:
        coste_presto.leer(ruta)
        return "coste_objetivo", "tiene las columnas del comparativo de Presto"
    except Exception:  # noqa: BLE001
        pass
    try:
        if facturas_erp.mapas(ruta):
            return "facturas", "tiene proveedor, nº, fecha e importe de facturas"
    except Exception:  # noqa: BLE001
        pass
    try:
        if certificacion_excel.mapas(ruta):
            return "certificacion", "tiene código e importe certificado"
    except Exception:  # noqa: BLE001
        pass
    return "documentacion", "no se reconoce sin la IA: si es un presupuesto o una medición, elígelo"


def usos(proyecto: Any) -> dict[str, str]:
    """documento_id → para qué se ha leído ya (un documento leído no se lee otra vez)."""
    salida: dict[str, str] = {}
    for m in proyecto.mediciones():
        salida[m["documento_id"]] = f"ya leído como {m['clase']}"
    coste = proyecto.coste_objetivo()
    if coste:
        salida[coste["documento_id"]] = "ya leído como coste objetivo"
    for c in proyecto.certificaciones():
        salida[c["documento_id"]] = f"ya leído como certificación nº {c['numero']}"
    for f in proyecto.facturas():
        if f.get("documento_id"):
            salida[f["documento_id"]] = "ya leído como listado de facturas"
    return salida


def clasificar(proyecto: Any, documentos: list[dict[str, Any]]) -> list[Propuesta]:
    """Propuesta para cada documento (no escribe nada)."""
    sin_venta = proyecto.venta_contratada() is None
    leidos = usos(proyecto)
    salida: list[Propuesta] = []
    presupuestos_bc3: list[tuple[float, int]] = []  # (importe, posición en salida)
    for d in documentos:
        formato = _formato(d["extension"])
        ruta = proyecto.ruta_documento(d["id"])
        posibles = _POSIBLES[formato]
        numero = reconocido = None
        if d["id"] in leidos:
            salida.append(
                Propuesta(
                    d["id"],
                    d["nombre_original"],
                    d["extension"],
                    "documentacion",
                    leidos[d["id"]],
                    ("documentacion",),
                    uso=leidos[d["id"]],
                )
            )
            continue
        if formato == "bc3":
            try:
                importe = _importe_bc3(ruta)
            except _Bc3Ilegible as exc:
                tipo, motivo, posibles = (
                    "documentacion",
                    f"no se puede leer como BC3: {exc}",
                    ("documentacion",),
                )
            else:
                if importe is None:
                    tipo, motivo = "medicion", "BC3 sin precios"
                else:
                    tipo, motivo = (
                        "medicion",
                        ("BC3 con precios: ¿otro presupuesto o una oferta de proveedor? elige"),
                    )
                    presupuestos_bc3.append((importe, len(salida)))
        elif formato == "hoja":
            tipo, motivo = _que_hoja(ruta)
            reconocido = tipo if tipo != "documentacion" else None
            if tipo == "certificacion":
                numero = _numero_certificacion(ruta, d["nombre_original"])
                if numero:
                    motivo += f" (dice que es la nº {numero})"
        elif formato == "dxf":
            tipo, motivo = "plano", "plano DXF: se lee en el paso Planos"
        elif formato == "pdf":
            tipo, motivo = (
                "documentacion",
                "un PDF se lee con la IA: si es el presupuesto, una medición o una oferta, elígelo",
            )
        else:
            tipo, motivo = "documentacion", "TRAZA no lee este formato: queda en Documentación"
        salida.append(
            Propuesta(
                d["id"],
                d["nombre_original"],
                d["extension"],
                tipo,
                motivo,
                posibles,
                numero,
                reconocido,
            )
        )
    # Un solo presupuesto: el BC3 con precios de mayor importe, si la obra no tiene venta.
    if presupuestos_bc3 and sin_venta:
        _imp, i = max(presupuestos_bc3)
        p = salida[i]
        otros = len(presupuestos_bc3) - 1
        salida[i] = Propuesta(
            p.documento_id,
            p.nombre,
            p.extension,
            "presupuesto",
            "BC3 con precios" + (f", el de mayor importe de {otros + 1}" if otros else ""),
            p.posibles,
        )
    return salida


def orden_de_montaje(propuestas: list[tuple[Propuesta, str]]) -> list[tuple[Propuesta, str]]:
    """El presupuesto primero (la certificación se cruza con su venta), luego mediciones y
    ofertas, el coste objetivo (las facturas van a sus paquetes), las certificaciones por su
    nº y las facturas; lo demás no se lee."""
    prioridad = {
        "presupuesto": 0,
        "medicion": 1,
        "oferta": 1,
        "coste_objetivo": 2,
        "certificacion": 3,
        "facturas": 4,
    }
    elegidas = [x for x in propuestas if x[1] in prioridad]
    return sorted(
        elegidas,
        key=lambda x: (
            prioridad[x[1]],
            x[0].numero if x[0].numero is not None else 999,
            x[0].nombre,
        ),
    )
