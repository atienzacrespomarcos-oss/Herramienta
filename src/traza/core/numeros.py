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


_MILES_CON_PUNTO = re.compile(r"^[+-]?[0-9]{1,3}(\.[0-9]{3})+$")
# Solo cifras ASCII, una coma o punto decimal y exponente opcional. Rechaza espacios
# internos («2 4» no es 24), guiones bajos («1_000», que float() aceptaría) y cifras de
# otros alfabetos.
_NUMERO = re.compile(r"^[+-]?[0-9]+([.,][0-9]+)?([eE][+-]?[0-9]+)?$")


def leer_numero(texto: str) -> int | float:
    t = texto.strip()  # strip() también quita el espacio duro (NBSP) de los PDF
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
    if not _NUMERO.match(t):
        raise ValueError(f"«{texto}» no es un número (sin espacios ni separador de miles).")
    t = t.replace(",", ".")
    if re.fullmatch(r"[+-]?[0-9]+", t):
        return int(t)
    valor = float(t)
    if valor != valor or valor in (float("inf"), float("-inf")):
        raise ValueError(f"«{texto}» no es un número finito.")
    return valor


def escribir_numero(valor: int | float) -> str:
    """Formato para mostrar: coma decimal, sin separador de miles (no se reinterpreta)."""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).replace(".", ",")


# --- Números tal como aparecen en documentos ajenos -----------------------------------

_SOBRANTE = re.compile(r"[€$%\s ]|EUR|eur|ud\.?$|uds\.?$")


def interpretaciones_documento(texto: str) -> list[float]:
    """Valores posibles de un número escrito en una oferta, medición o presupuesto.

    A diferencia de lo que teclea el usuario (`leer_numero`, estricto), en un documento
    ajeno el formato no se puede elegir. Se devuelven TODAS las lecturas razonables:
    - «1.234,56» → [1234.56]  (miles con punto y coma decimal, uso español)
    - «1,234.56» → [1234.56]  (formato anglosajón)
    - «2.400»    → [2400.0, 2.4]   ambiguo: lo resuelve otra comprobación o el usuario
    - «12,5»     → [12.5]
    Lista vacía si no es un número. Quien llama decide qué hacer con la ambigüedad.
    """
    t = texto.strip().replace(" ", " ")
    # Un espacio solo vale como separador de miles en grupos de tres («2 400»); «12 5» son
    # dos números distintos (p. ej. dos celdas contiguas), no 125 (revisión 06-11-2026).
    if " " in re.sub(r"\s*(€|EUR|eur|%|\$|uds?\.?)\s*$", "", t).strip():
        nucleo = re.sub(r"\s*(€|EUR|eur|%|\$|uds?\.?)\s*$", "", t).strip()
        if not re.fullmatch(r"[+-]?[0-9]{1,3}( [0-9]{3})+([.,][0-9]+)?", nucleo):
            return []
    t = _SOBRANTE.sub("", t)
    if not t or not re.fullmatch(r"[+-]?[0-9.,]+", t) or not re.search(r"[0-9]", t):
        return []
    signo = -1.0 if t.startswith("-") else 1.0
    t = t.lstrip("+-")
    punto, coma = "." in t, "," in t
    try:
        if punto and coma:
            if t.rfind(",") > t.rfind("."):  # 1.234,56
                return [signo * float(t.replace(".", "").replace(",", "."))]
            return [signo * float(t.replace(",", ""))]  # 1,234.56
        sep = "." if punto else "," if coma else None
        if sep is None:
            return [signo * float(t)]
        partes = t.split(sep)
        # Un primer grupo «0» nunca es un millar: «0,500» es medio, no quinientos.
        miles = (
            len(partes) > 1
            and all(len(p) == 3 for p in partes[1:])
            and 1 <= len(partes[0]) <= 3
            and not partes[0].startswith("0")
        )
        if len(partes) > 2:  # 1.250.000: solo miles
            return [signo * float("".join(partes))] if miles else []
        decimal = signo * float(t.replace(sep, "."))
        if miles:
            entero = signo * float("".join(partes))
            return [entero, decimal]  # «2.400»: ¿2400 o 2,4?
        return [decimal]
    except ValueError:
        return []
