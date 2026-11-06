"""Ciclo de vida de un elemento (DATA_MODEL §7.3).

Distingue lo propuesto, lo calculado, lo comprobado y lo aprobado. Lo aprobado queda
bloqueado: cambiarlo exige reabrirlo con una decisión registrada (línea roja 5).
"""

from __future__ import annotations

from enum import StrEnum


class Estado(StrEnum):
    BORRADOR = "borrador"
    PROPUESTO = "propuesto"
    CALCULADO = "calculado"
    COMPROBADO = "comprobado"
    APROBADO = "aprobado"


# Transiciones que se hacen por avance normal. Aprobar y reabrir tienen orden propia
# porque exigen comprobaciones y dejan una decisión escrita.
_AVANCE: dict[Estado, frozenset[Estado]] = {
    Estado.BORRADOR: frozenset({Estado.PROPUESTO, Estado.CALCULADO}),
    Estado.PROPUESTO: frozenset({Estado.BORRADOR, Estado.CALCULADO}),
    Estado.CALCULADO: frozenset({Estado.BORRADOR, Estado.COMPROBADO}),
    Estado.COMPROBADO: frozenset({Estado.BORRADOR, Estado.CALCULADO}),
    Estado.APROBADO: frozenset(),
}


def transicion_permitida(desde: Estado, hacia: Estado) -> bool:
    return hacia in _AVANCE[desde]
