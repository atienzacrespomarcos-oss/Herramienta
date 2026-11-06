"""Esquemas de propiedades por tipo de elemento (ADR-0005).

Aquí se define QUÉ propiedades tiene un tipo y en qué magnitud se miden; nunca qué
valor tienen. Los valores solo entran por una orden y con procedencia.

Cada tipo lleva versión: si cambia su esquema, los proyectos antiguos se migran de forma
explícita en lugar de reinterpretarse en silencio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from traza.core.unidades import comprobar_compatible


class Disciplina(StrEnum):
    CLIMATIZACION = "climatizacion"
    VENTILACION = "ventilacion"
    ELECTRICIDAD = "electricidad"
    FONTANERIA = "fontaneria"
    SANEAMIENTO = "saneamiento"
    PCI = "pci"
    CONTROL = "control"
    ESTRUCTURA = "estructura"
    GENERAL = "general"


class Clase(StrEnum):
    NUMERO = "numero"
    TEXTO = "texto"


@dataclass(frozen=True, slots=True)
class DefPropiedad:
    clave: str
    etiqueta: str
    clase: Clase
    unidad_si: str | None = None  # solo números: magnitud de referencia en SI
    obligatoria_para_aprobar: bool = False

    def __post_init__(self) -> None:
        if self.clase is Clase.NUMERO and self.unidad_si is None:
            raise ValueError(f"{self.clave}: una propiedad numérica declara su magnitud.")
        if self.clase is Clase.TEXTO and self.unidad_si is not None:
            raise ValueError(f"{self.clave}: una propiedad de texto no lleva unidad.")


@dataclass(frozen=True, slots=True)
class TipoElemento:
    nombre: str
    etiqueta: str
    disciplina: Disciplina
    version: int
    propiedades: tuple[DefPropiedad, ...] = field(default_factory=tuple)

    def propiedad(self, clave: str) -> DefPropiedad:
        for p in self.propiedades:
            if p.clave == clave:
                return p
        raise KeyError(f"El tipo «{self.nombre}» no tiene la propiedad «{clave}».")


class ValorInvalido(ValueError):
    pass


def validar_valor(defn: DefPropiedad, valor: object, unidad: str | None) -> None:
    if defn.clase is Clase.TEXTO:
        if not isinstance(valor, str) or not valor.strip():
            raise ValorInvalido(f"«{defn.etiqueta}» espera un texto no vacío.")
        if unidad:
            raise ValorInvalido(f"«{defn.etiqueta}» no lleva unidad.")
        return
    # bool es subclase de int en Python: se excluye a propósito.
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        raise ValorInvalido(f"«{defn.etiqueta}» espera un número.")
    if valor != valor or valor in (float("inf"), float("-inf")):
        raise ValorInvalido(f"«{defn.etiqueta}»: valor no finito.")
    if unidad is None:
        raise ValorInvalido(f"«{defn.etiqueta}» necesita unidad (magnitud {defn.unidad_si}).")
    assert defn.unidad_si is not None
    comprobar_compatible(unidad, defn.unidad_si)


_REGISTRO: dict[str, TipoElemento] = {}


def registrar(tipo: TipoElemento) -> TipoElemento:
    if tipo.nombre in _REGISTRO:
        raise ValueError(f"Tipo duplicado: {tipo.nombre}")
    claves = [p.clave for p in tipo.propiedades]
    if len(claves) != len(set(claves)):
        raise ValueError(f"{tipo.nombre}: propiedades duplicadas.")
    _REGISTRO[tipo.nombre] = tipo
    return tipo


def tipo(nombre: str) -> TipoElemento:
    try:
        return _REGISTRO[nombre]
    except KeyError:
        raise KeyError(f"Tipo de elemento desconocido: «{nombre}».") from None


def tipos() -> tuple[TipoElemento, ...]:
    return tuple(_REGISTRO.values())


# --- Tipos disponibles en la Etapa 1 -------------------------------------------------
# Solo un tipo genérico de equipo, suficiente para ejercitar el núcleo (procedencia,
# estados, aprobación). Los tipos de cada disciplina llegan con su etapa y su ficha de
# método en docs/modules/.

EQUIPO = registrar(
    TipoElemento(
        nombre="equipo",
        etiqueta="Equipo",
        disciplina=Disciplina.GENERAL,
        version=1,
        propiedades=(
            DefPropiedad("fabricante", "Fabricante", Clase.TEXTO, obligatoria_para_aprobar=True),
            DefPropiedad("modelo", "Modelo", Clase.TEXTO, obligatoria_para_aprobar=True),
            DefPropiedad("descripcion", "Descripción", Clase.TEXTO),
            DefPropiedad("potencia_frigorifica", "Potencia frigorífica", Clase.NUMERO, "W"),
            DefPropiedad("potencia_calorifica", "Potencia calorífica", Clase.NUMERO, "W"),
            DefPropiedad("potencia_electrica", "Potencia eléctrica absorbida", Clase.NUMERO, "W"),
            DefPropiedad("caudal_aire", "Caudal de aire", Clase.NUMERO, "m**3/s"),
            DefPropiedad("tension", "Tensión de alimentación", Clase.NUMERO, "V"),
            DefPropiedad("masa", "Masa en servicio", Clase.NUMERO, "kg"),
        ),
    )
)
