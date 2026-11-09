"""Nombres de fichero válidos en Windows (el equipo del usuario)."""

from __future__ import annotations

RESERVADOS_WINDOWS = {"CON", "PRN", "AUX", "NUL"} | {
    f"{base}{n}" for base in ("COM", "LPT") for n in range(1, 10)
}


def nombre_valido(texto: str, prefijo: str = "red") -> str:
    """Nombre válido en Windows (revisión 08-11-2026): sin < > : " / \\ | ? * ni caracteres
    de control, sin punto ni espacio al final (Windows los quita sin avisar) y sin nombres
    reservados (CON, NUL, COM1…), a los que se antepone `prefijo`."""
    limpio = "".join("-" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in texto)
    limpio = " ".join(limpio.split()).rstrip(". ")
    if limpio.split(".")[0].strip().upper() in RESERVADOS_WINDOWS:
        limpio = f"{prefijo} {limpio}"
    return limpio or prefijo
