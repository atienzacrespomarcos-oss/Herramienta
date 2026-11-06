"""Operaciones genéricas por fila, base del deshacer y del registro de cambios.

Cada orden se traduce en una lista de `Delta`: la fila antes y después del cambio
(None = no existía / deja de existir). Aplicar el delta al revés es deshacer. Así el
deshacer y el registro de cambios no dependen de que cada orden programe su inversa,
que es donde suelen esconderse los errores.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

Fila = dict[str, Any]

# Tabla → columnas de clave primaria. Solo estas tablas se modifican mediante órdenes.
CLAVES: dict[str, tuple[str, ...]] = {
    "elemento": ("id",),
    "propiedad": ("elemento_id", "clave"),
    "documento": ("id",),
    "decision": ("id",),
    "pendiente": ("id",),
}


class Conflicto(RuntimeError):
    """La fila no está como la orden esperaba: no se aplica nada."""


@dataclass(frozen=True)
class Delta:
    tabla: str
    antes: Fila | None
    despues: Fila | None

    def __post_init__(self) -> None:
        if self.tabla not in CLAVES:
            raise ValueError(f"Tabla no modificable por órdenes: {self.tabla}")
        if self.antes is None and self.despues is None:
            raise ValueError("Delta vacío.")

    def invertido(self) -> Delta:
        return Delta(self.tabla, self.despues, self.antes)

    @property
    def clave(self) -> dict[str, Any]:
        fila = self.despues if self.despues is not None else self.antes
        assert fila is not None
        return {c: fila[c] for c in CLAVES[self.tabla]}

    @property
    def id_legible(self) -> str:
        return "/".join(str(v) for v in self.clave.values())

    def campos_cambiados(self) -> list[str]:
        if self.antes is None or self.despues is None:
            return []
        return sorted(k for k in self.despues if self.antes.get(k) != self.despues.get(k))


def leer(con: sqlite3.Connection, tabla: str, clave: dict[str, Any]) -> Fila | None:
    cond = " AND ".join(f"{c} = ?" for c in clave)
    fila = con.execute(f"SELECT * FROM {tabla} WHERE {cond}", tuple(clave.values())).fetchone()
    return dict(fila) if fila is not None else None


def aplicar(con: sqlite3.Connection, d: Delta) -> None:
    """Aplica un delta comprobando que la base está en el estado `antes` esperado."""
    actual = leer(con, d.tabla, d.clave)
    if actual != d.antes:
        raise Conflicto(
            f"Conflicto en {d.tabla} {d.id_legible}: el estado no es el esperado; "
            "no se aplica el cambio."
        )
    if d.despues is None:
        cond = " AND ".join(f"{c} = ?" for c in d.clave)
        con.execute(f"DELETE FROM {d.tabla} WHERE {cond}", tuple(d.clave.values()))
    elif d.antes is None:
        cols = list(d.despues)
        con.execute(
            f"INSERT INTO {d.tabla} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            tuple(d.despues[c] for c in cols),
        )
    else:
        cols = [c for c in d.despues if c not in CLAVES[d.tabla]]
        cond = " AND ".join(f"{c} = ?" for c in d.clave)
        con.execute(
            f"UPDATE {d.tabla} SET {', '.join(f'{c} = ?' for c in cols)} WHERE {cond}",
            tuple(d.despues[c] for c in cols) + tuple(d.clave.values()),
        )


def a_json(fila: Fila | None) -> str | None:
    return None if fila is None else json.dumps(fila, ensure_ascii=False, sort_keys=True)
