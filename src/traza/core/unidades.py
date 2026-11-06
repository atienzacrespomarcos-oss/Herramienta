"""Unidades (ADR-0004).

El valor se guarda tal como lo da su fuente («2 400 m³/h» si así figura en la oferta),
porque reescribirlo en otra unidad ya es una transformación que la trazabilidad debe
poder ver. La compatibilidad dimensional se comprueba al escribir; la conversión a SI se
hace al leer, cuando un motor la necesita.
"""

from __future__ import annotations

from functools import cache

import pint

_SUPERINDICES = str.maketrans({"²": "**2", "³": "**3", "·": "*"})


class UnidadInvalida(ValueError):
    pass


@cache
def registro() -> pint.UnitRegistry:
    return pint.UnitRegistry()


def normalizar(unidad: str) -> str:
    """Admite la notación habitual en documentos técnicos españoles (m³/h, W/m²·K).

    En esa notación todo lo que sigue a la barra es denominador: «W/m²·K» es W/(m²·K).
    pint lee de izquierda a derecha y lo tomaría como (W/m²)·K, que es otra magnitud
    (fallo detectado en revisión el 06-11-2026). Por eso el denominador se encierra entre
    paréntesis, y una expresión con dos barras y sin paréntesis se rechaza por ambigua.
    """
    u = unidad.strip().translate(_SUPERINDICES)
    if "(" in u or "/" not in u:
        return u
    if u.count("/") > 1:
        raise UnidadInvalida(f"«{unidad}» es ambigua (dos barras); usa paréntesis.")
    num, den = u.split("/")
    return f"{num or '1'}/({den})"


def comprobar_compatible(unidad: str, referencia: str) -> None:
    """Falla si `unidad` no mide la misma magnitud que `referencia`."""
    ureg = registro()
    normalizada = normalizar(unidad)  # fuera del try: su error «ambigua» debe llegar tal cual
    try:
        u = ureg.Unit(normalizada)
    except Exception as exc:  # pint lanza varias clases según el fallo
        raise UnidadInvalida(f"Unidad no reconocida: «{unidad}».") from exc
    ref = ureg.Unit(normalizar(referencia))
    if u.dimensionality != ref.dimensionality:
        raise UnidadInvalida(
            f"«{unidad}» no es compatible con «{referencia}» "
            f"({u.dimensionality} frente a {ref.dimensionality})."
        )


def a_si(valor: float, unidad: str, referencia: str) -> float:
    """Convierte a la unidad de referencia (SI) del tipo de propiedad."""
    comprobar_compatible(unidad, referencia)
    ureg = registro()
    return float(ureg.Quantity(valor, normalizar(unidad)).to(normalizar(referencia)).magnitude)
