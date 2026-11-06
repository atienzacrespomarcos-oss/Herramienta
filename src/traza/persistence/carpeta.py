"""Proyecto = carpeta (ADR-0002).

Nave Ejemplo.traza/
    proyecto.db         base de datos SQLite
    documentos/         originales incorporados, nombrados por su SHA-256
    exportaciones/      DXF, LISP, XLSX, DOCX generados
    copias/             copias de seguridad de proyecto.db
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from traza.persistence.bd import conectar, migrar

EXTENSION = ".traza"
BD = "proyecto.db"
DOCUMENTOS = "documentos"
EXPORTACIONES = "exportaciones"
COPIAS = "copias"
COPIAS_CONSERVADAS = 30


class CarpetaNoValida(RuntimeError):
    pass


@dataclass(frozen=True)
class Carpeta:
    raiz: Path

    @property
    def bd(self) -> Path:
        return self.raiz / BD

    @property
    def documentos(self) -> Path:
        return self.raiz / DOCUMENTOS

    @property
    def copias(self) -> Path:
        return self.raiz / COPIAS

    @property
    def exportaciones(self) -> Path:
        return self.raiz / EXPORTACIONES


def crear(destino: Path) -> Carpeta:
    """Crea la carpeta del proyecto. `destino` puede llevar o no la extensión .traza."""
    raiz = destino if destino.suffix == EXTENSION else destino.with_name(destino.name + EXTENSION)
    if raiz.exists():
        raise CarpetaNoValida(f"Ya existe «{raiz}». No se sobrescribe un proyecto.")
    raiz.mkdir(parents=True)
    c = Carpeta(raiz)
    for sub in (c.documentos, c.copias, c.exportaciones):
        sub.mkdir()
    con = conectar(c.bd)
    try:
        migrar(con)
    finally:
        con.close()
    return c


def abrir(raiz: Path) -> tuple[Carpeta, sqlite3.Connection]:
    c = Carpeta(raiz)
    if not c.bd.is_file():
        raise CarpetaNoValida(f"«{raiz}» no es un proyecto TRAZA (falta {BD}).")
    for sub in (c.documentos, c.copias, c.exportaciones):
        sub.mkdir(exist_ok=True)
    con = conectar(c.bd)
    try:
        migrar(con)
    except Exception:
        con.close()
        raise
    return c, con


# --- Documentos ---------------------------------------------------------------------


def sha256_de(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def guardar_documento(c: Carpeta, origen: Path) -> tuple[str, Path]:
    """Copia el original al almacén del proyecto, sin modificarlo, y lo deja de solo lectura.

    Devuelve (sha256, ruta en el almacén). Si ya estaba, no se copia otra vez.
    """
    sha = sha256_de(origen)
    destino = c.documentos / f"{sha}{origen.suffix.lower()}"
    if not destino.exists():
        temporal = destino.with_suffix(destino.suffix + ".parcial")
        shutil.copyfile(origen, temporal)
        # Se comprueba la copia antes de darla por buena: un original que cambia mientras
        # se copia dejaría en el almacén algo distinto de lo que dice su huella.
        if sha256_de(temporal) != sha:
            temporal.unlink()
            raise OSError(f"La copia de «{origen.name}» no coincide con el original.")
        os.replace(temporal, destino)
        destino.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    return sha, destino


def ruta_documento(c: Carpeta, sha: str, extension: str) -> Path:
    return c.documentos / f"{sha}{extension}"


# --- Copias de seguridad -------------------------------------------------------------


def copia_de_seguridad(c: Carpeta, con: sqlite3.Connection, etiqueta: str = "") -> Path:
    """Copia coherente de la base de datos con la API de backup de SQLite."""
    sello = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    sufijo = f"-{etiqueta}" if etiqueta else ""
    destino = c.copias / f"proyecto-{sello}{sufijo}.db"
    dst = sqlite3.connect(destino)
    try:
        con.backup(dst)
    finally:
        dst.close()
    _podar_copias(c)
    return destino


def copias(c: Carpeta) -> list[Path]:
    return sorted(c.copias.glob("proyecto-*.db"))


def _podar_copias(c: Carpeta) -> None:
    existentes = copias(c)
    for vieja in existentes[: max(0, len(existentes) - COPIAS_CONSERVADAS)]:
        vieja.unlink()


def restaurar(c: Carpeta, copia: Path) -> None:
    """Sustituye proyecto.db por una copia. El proyecto debe estar cerrado.

    Antes se guarda una copia del estado actual: restaurar tampoco destruye nada.
    """
    if copia.parent != c.copias or not copia.is_file():
        raise CarpetaNoValida("La copia a restaurar debe estar en la carpeta copias/ del proyecto.")
    # Primero se aparta la copia elegida: la copia de seguridad previa poda las más
    # antiguas y, si la elegida era la más vieja, la borraría antes de restaurarla.
    temporal = c.bd.with_suffix(".restaurando")
    shutil.copyfile(copia, temporal)
    con = conectar(c.bd)
    try:
        copia_de_seguridad(c, con, etiqueta="antes-de-restaurar")
    finally:
        con.close()
    os.replace(temporal, c.bd)
