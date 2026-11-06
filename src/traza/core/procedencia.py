"""Procedencia de cada valor del modelo (ADR-0005).

La promesa central del programa es que ninguna cifra aparece sin saber de dónde sale.
Por eso la procedencia no es un comentario opcional: es parte del valor, y una
procedencia incompleta es un error que impide guardar el dato.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Origen(StrEnum):
    USUARIO = "usuario"  # lo introduce el ingeniero
    DOCUMENTO = "documento"  # sale de un documento incorporado (página/celda)
    CALCULO = "calculo"  # resultado de un motor, con su registro de cálculo
    CATALOGO = "catalogo"  # dato de fabricante tomado de un catálogo con origen
    HIPOTESIS = "hipotesis"  # hipótesis de diseño declarada y justificada
    IA_PROPUESTA = "ia_propuesta"  # propuesta de la IA, pendiente de confirmar


class ProcedenciaInvalida(ValueError):
    """La procedencia no permite saber de dónde sale el valor."""


@dataclass(frozen=True, slots=True)
class Procedencia:
    origen: Origen
    documento_id: str | None = None
    localizador: str | None = None  # «p. 14», «hoja Mediciones!C12»…
    registro_calculo_id: str | None = None
    nota: str | None = None

    def __post_init__(self) -> None:
        o = self.origen
        cita = bool(self.documento_id) or bool(self.localizador)
        if o in (Origen.DOCUMENTO, Origen.CATALOGO) or (o is Origen.IA_PROPUESTA and cita):
            # La IA puede proponer citando un documento (es lo normal al leer una oferta);
            # si cita, la cita tiene que estar completa como cualquier otra.
            if not self.documento_id:
                raise ProcedenciaInvalida(f"Un valor con origen «{o}» debe citar el documento.")
            if not (self.localizador and self.localizador.strip()):
                raise ProcedenciaInvalida(
                    f"Un valor con origen «{o}» debe indicar dónde está en el documento "
                    "(página, hoja, celda…)."
                )
        elif cita:
            # Evita procedencias contradictorias («lo escribió el usuario» + «página 14»).
            raise ProcedenciaInvalida(
                f"Un valor con origen «{o}» no puede citar documento; usa origen «documento»."
            )
        if o is Origen.CALCULO and not self.registro_calculo_id:
            raise ProcedenciaInvalida(
                "Un resultado de cálculo debe enlazar su registro de cálculo."
            )
        if o is not Origen.CALCULO and self.registro_calculo_id:
            raise ProcedenciaInvalida(
                "Solo un valor con origen «calculo» enlaza registro de cálculo."
            )
        if o is Origen.HIPOTESIS and not (self.nota and self.nota.strip()):
            raise ProcedenciaInvalida("Una hipótesis de diseño debe llevar su justificación.")

    @property
    def requiere_confirmacion(self) -> bool:
        """Lo que propone la IA nunca cuenta como dato hasta que el usuario lo confirma."""
        return self.origen is Origen.IA_PROPUESTA
