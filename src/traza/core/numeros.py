"""Lectura y escritura de números con la convención española.

Riesgo que se evita: «2.400» en un documento español es dos mil cuatrocientos, pero
leído con la convención anglosajona es dos coma cuatro. Un error de mil veces en un
caudal no da ningún aviso. Por eso un número con punto seguido de exactamente tres cifras
y sin coma se rechaza por ambiguo: hay que escribir «2400» o «2,4».
"""

from __future__ import annotations

import re


class NumeroAmbiguo(ValueError):
    pass


_MILES_CON_PUNTO = re.compile(r"^[+-]?\d{1,3}(\.\d{3})+$")


def leer_numero(texto: str) -> int | float:
    t = texto.strip().replace(" ", "").replace(" ", "")
    if not t:
        raise ValueError("Escribe un número.")
    if "," in t and "." in t:
        raise NumeroAmbiguo(
            f"«{texto}» mezcla punto y coma. Escribe el número sin separador de miles "
            "(p. ej. 2400,5)."
        )
    if _MILES_CON_PUNTO.match(t):
        raise NumeroAmbiguo(
            f"«{texto}» es ambiguo: ¿{t.replace('.', '')} o {t.replace('.', ',')}? "
            "Escríbelo sin punto de miles."
        )
    t = t.replace(",", ".")
    try:
        if re.fullmatch(r"[+-]?\d+", t):
            return int(t)
        valor = float(t)
    except ValueError:
        raise ValueError(f"«{texto}» no es un número.") from None
    if valor != valor or valor in (float("inf"), float("-inf")):
        raise ValueError(f"«{texto}» no es un número finito.")
    return valor


def escribir_numero(valor: int | float) -> str:
    """Formato para mostrar: coma decimal, sin separador de miles (no se reinterpreta)."""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).replace(".", ",")
