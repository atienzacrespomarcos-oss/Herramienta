"""Conexión SQLite y migraciones."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from traza.persistence.esquema import MIGRACIONES, VERSION_ACTUAL


class ProyectoDeVersionFutura(RuntimeError):
    """El proyecto lo guardó una versión más nueva del programa."""


def conectar(ruta: Path) -> sqlite3.Connection:
    # isolation_level=None: las transacciones se abren a mano (BEGIN IMMEDIATE) para que
    # una orden se aplique entera o no se aplique.
    con = sqlite3.connect(ruta, isolation_level=None)
    try:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        # Diario clásico (no WAL): el proyecto queda en UN fichero, sin -wal/-shm sueltos
        # que se pierden al copiar la carpeta. FULL: la orden confirmada sobrevive a un corte.
        con.execute("PRAGMA journal_mode = DELETE")
        con.execute("PRAGMA synchronous = FULL")
    except BaseException:
        # Con un fichero dañado, `connect` funciona y el primer PRAGMA falla. Si no se
        # cierra aquí, Windows mantiene el fichero bloqueado y no se puede apartar para
        # restaurar una copia (fallo visto en CI de Windows, 06-11-2026).
        con.close()
        raise
    return con


def version(con: sqlite3.Connection) -> int:
    return int(con.execute("PRAGMA user_version").fetchone()[0])


def migrar(con: sqlite3.Connection) -> None:
    actual = version(con)
    if actual > VERSION_ACTUAL:
        raise ProyectoDeVersionFutura(
            f"El proyecto es de la versión de esquema {actual} y este programa solo conoce "
            f"hasta la {VERSION_ACTUAL}. No se abre para no estropearlo."
        )
    for n in range(actual, VERSION_ACTUAL):
        con.execute("BEGIN IMMEDIATE")
        try:
            for sentencia in _sentencias(MIGRACIONES[n]):
                con.execute(sentencia)
            con.execute(f"PRAGMA user_version = {n + 1}")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise


def _sentencias(script: str) -> list[str]:
    """Divide un script en sentencias respetando los cuerpos BEGIN…END de los triggers.

    No se usa `executescript` porque hace COMMIT implícito y rompería la atomicidad de
    la migración.
    """
    sentencias: list[str] = []
    actual: list[str] = []
    dentro_trigger = False
    for linea in script.splitlines():
        limpia = linea.strip()
        if not limpia or limpia.startswith("--"):
            continue
        actual.append(linea)
        mayus = limpia.upper()
        if mayus.startswith("CREATE TRIGGER"):
            dentro_trigger = True
        if dentro_trigger:
            if mayus.endswith("END;"):
                dentro_trigger = False
                sentencias.append("\n".join(actual))
                actual = []
        elif limpia.endswith(";"):
            sentencias.append("\n".join(actual))
            actual = []
    if actual:
        raise ValueError("Script de migración con una sentencia sin terminar.")
    return sentencias
