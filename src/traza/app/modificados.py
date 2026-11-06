"""Cálculo de un modificado: contrato frente a modificado, por partida y en total.

Puro (recibe filas, devuelve el resultado): lo usan la pantalla, el Excel y el BC3, de modo
que las tres salidas dan siempre las mismas cifras.

Reglas:
- Una variación cambia la cantidad de una partida de la base; el precio es el de la base.
- Una partida nueva toma su precio de la oferta leída (y se cita ese origen); su cantidad de
  contrato es 0.
- Un importe solo existe si constan cantidad y precio. Lo que no consta no se suma: el total
  se marca «parcial» y se dice cuántas partidas faltan. Nunca se suma un 0 inventado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from traza.app.ordenes import MOTIVOS


@dataclass
class LineaModificado:
    tipo: str  # sin_cambio | aumento | disminucion | anulacion | nueva
    capitulo: list[list[str]]
    codigo: str | None
    resumen: str | None
    unidad: str | None
    cantidad_contrato: float | None
    cantidad_modificada: float | None
    precio: float | None
    motivo: str | None = None
    justificacion: str | None = None
    origen_precio: str | None = None
    partida_id: str | None = None
    cambio_id: str | None = None

    @property
    def diferencia_cantidad(self) -> float | None:
        if self.cantidad_contrato is None or self.cantidad_modificada is None:
            return None
        return self.cantidad_modificada - self.cantidad_contrato

    def _importe(self, cantidad: float | None) -> float | None:
        if cantidad is None or self.precio is None:
            return None
        return cantidad * self.precio

    @property
    def importe_contrato(self) -> float | None:
        return self._importe(self.cantidad_contrato)

    @property
    def importe_modificado(self) -> float | None:
        return self._importe(self.cantidad_modificada)

    @property
    def diferencia_importe(self) -> float | None:
        a, b = self.importe_contrato, self.importe_modificado
        return None if a is None or b is None else b - a


TIPOS = {
    "sin_cambio": "Sin cambio",
    "aumento": "Aumento",
    "disminucion": "Disminución",
    "anulacion": "Anulación",
    "nueva": "Partida nueva",
}


@dataclass
class Resumen:
    lineas: list[LineaModificado] = field(default_factory=list)
    total_contrato: float = 0.0
    total_modificado: float = 0.0
    sin_importe_contrato: int = 0
    sin_importe_modificado: int = 0

    @property
    def cambios(self) -> list[LineaModificado]:
        return [x for x in self.lineas if x.tipo != "sin_cambio"]

    @property
    def diferencia(self) -> float:
        return self.total_modificado - self.total_contrato

    @property
    def parcial(self) -> bool:
        return bool(self.sin_importe_contrato or self.sin_importe_modificado)


def calcular(
    base: list[dict[str, Any]],
    cambios: list[dict[str, Any]],
    nuevas: dict[str, dict[str, Any]],
    nombres_documentos: dict[str, str],
) -> Resumen:
    """base: partidas de la medición de base; cambios: filas de cambio_modificado;
    nuevas: partidas de oferta citadas por los cambios «nueva», por id;
    nombres_documentos: medicion_id → nombre del documento (para citar el origen)."""
    variaciones = {c["partida_id"]: c for c in cambios if c["tipo"] == "variacion"}
    r = Resumen()
    for p in base:
        c = variaciones.get(p["id"])
        linea = LineaModificado(
            tipo="sin_cambio",
            capitulo=p["capitulo"],
            codigo=p["codigo"],
            resumen=p["resumen"],
            unidad=p["unidad"],
            cantidad_contrato=p["cantidad"],
            cantidad_modificada=p["cantidad"],
            precio=p["precio"],
            partida_id=p["id"],
        )
        if c is not None:
            linea.cantidad_modificada = c["cantidad"]
            linea.tipo = (
                "anulacion"
                if c["cantidad"] == 0
                else "aumento"
                if c["cantidad"] > (p["cantidad"] or 0)
                else "disminucion"
            )
            linea.motivo = MOTIVOS[c["motivo"]]
            linea.justificacion = c["justificacion"]
            linea.cambio_id = c["id"]
        r.lineas.append(linea)
    for c in sorted((c for c in cambios if c["tipo"] == "nueva"), key=lambda c: c["orden"]):
        o = nuevas[c["partida_id"]]
        r.lineas.append(
            LineaModificado(
                tipo="nueva",
                capitulo=[],
                codigo=o["codigo"],
                resumen=o["resumen"],
                unidad=o["unidad"],
                cantidad_contrato=0.0,
                cantidad_modificada=c["cantidad"],
                precio=o["precio"],
                motivo=MOTIVOS[c["motivo"]],
                justificacion=c["justificacion"],
                origen_precio=(
                    f"{nombres_documentos.get(o['medicion_id'], '¿?')} · {o['localizador']}"
                ),
                partida_id=o["id"],
                cambio_id=c["id"],
            )
        )
    for x in r.lineas:
        if x.importe_contrato is None:
            r.sin_importe_contrato += 1
        else:
            r.total_contrato += x.importe_contrato
        if x.importe_modificado is None:
            r.sin_importe_modificado += 1
        else:
            r.total_modificado += x.importe_modificado
    return r
