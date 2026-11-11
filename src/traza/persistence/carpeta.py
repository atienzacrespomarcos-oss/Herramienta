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
from datetime import UTC, datetime
from pathlib import Path

from traza.persistence.bd import conectar, migrar, version
from traza.persistence.esquema import VERSION_ACTUAL

EXTENSION = ".traza"
BD = "proyecto.db"
DOCUMENTOS = "documentos"
EXPORTACIONES = "exportaciones"
COPIAS = "copias"
# Solo se podan las copias automáticas de apertura. Las manuales, las de antes de
# restaurar y las de antes de migrar no se borran nunca solas: son las que alguien quiso
# conservar o las únicas que guardan un estado anterior a una operación delicada.
COPIAS_APERTURA_CONSERVADAS = 30
ETIQUETA_APERTURA = "apertura"


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
        v = version(con)
        if 0 < v < VERSION_ACTUAL:
            # La copia se hace ANTES de migrar: si la migración transforma datos y algo
            # sale mal, el proyecto tal como estaba sigue existiendo.
            copia_de_seguridad(c, con, etiqueta=f"antes-de-migrar-v{v}")
        migrar(con)
    except BaseException:
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
    """Copia coherente de la base de datos con la API de backup de SQLite.

    Se escribe con otro nombre y se renombra al terminar: una copia a medias nunca aparece
    en la lista de copias restaurables. Sello en UTC: el cambio de hora no altera el orden.
    """
    sello = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    sufijo = f"-{etiqueta}" if etiqueta else ""
    destino = c.copias / f"proyecto-{sello}{sufijo}.db"
    temporal = destino.with_suffix(".parcial")
    try:
        dst = sqlite3.connect(temporal)
        try:
            con.backup(dst)
        finally:
            dst.close()
        os.replace(temporal, destino)
    except BaseException:
        temporal.unlink(missing_ok=True)
        raise
    _podar_copias(c)
    return destino


def copias(c: Carpeta) -> list[Path]:
    return sorted(c.copias.glob("proyecto-*.db"))


def _podar_copias(c: Carpeta) -> None:
    apertura = [p for p in copias(c) if p.stem.endswith(f"-{ETIQUETA_APERTURA}")]
    for vieja in apertura[: max(0, len(apertura) - COPIAS_APERTURA_CONSERVADAS)]:
        vieja.unlink()


def restaurar(c: Carpeta, copia: Path) -> None:
    """Sustituye proyecto.db por una copia. El proyecto debe estar cerrado.

    Antes se guarda el estado actual: restaurar tampoco destruye nada. Si la base de datos
    actual está dañada y no admite copia (el caso para el que sirve restaurar), se aparta
    tal cual a copias/ con la etiqueta «danada» y se restaura igualmente.
    """
    if copia.parent != c.copias or not copia.is_file():
        raise CarpetaNoValida("La copia a restaurar debe estar en la carpeta copias/ del proyecto.")
    temporal = c.bd.with_suffix(".restaurando")
    shutil.copyfile(copia, temporal)
    try:
        try:
            con = conectar(c.bd)
            try:
                copia_de_seguridad(c, con, etiqueta="antes-de-restaurar")
            finally:
                con.close()
        except sqlite3.DatabaseError:
            sello = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            os.replace(c.bd, c.copias / f"proyecto-{sello}-danada.db")
        os.replace(temporal, c.bd)
    except BaseException:
        temporal.unlink(missing_ok=True)
        raise


# --- Revisiones del proyecto (RF-009, docs/modules/revisiones.md) -----------------------

REVISIONES = "revisiones"


@dataclass(frozen=True)
class Revision:
    numero: int
    nombre: str
    nota: str
    fecha: str  # ISO, UTC
    fichero: Path
    huella: str  # SHA-256 del .db congelado
    version_esquema: int


def _carpeta_revisiones(c: Carpeta) -> Path:
    return c.raiz / REVISIONES


def revisiones(c: Carpeta) -> list[Revision]:
    """Las emitidas, por número. Una ficha sin su .db, o con otra huella, no se lista: una
    revisión que no es la que se emitió no se compara (se dice en `revision_danada`)."""
    import json

    salida = []
    carpeta = _carpeta_revisiones(c)
    if not carpeta.is_dir():
        return salida
    for ficha in sorted(carpeta.glob("Rev *.json")):
        try:
            d = json.loads(ficha.read_text(encoding="utf-8"))
            r = Revision(
                int(d["numero"]),
                str(d["nombre"]),
                str(d.get("nota", "")),
                str(d["fecha"]),
                carpeta / str(d["fichero"]),
                str(d["huella"]),
                int(d["version_esquema"]),
            )
        except (OSError, ValueError, KeyError, TypeError):
            continue
        salida.append(r)
    return sorted(salida, key=lambda r: r.numero)


def revision_danada(r: Revision) -> str | None:
    """Por qué no vale una revisión (el .db falta o no es el emitido), o None."""
    if not r.fichero.is_file():
        return f"Falta el fichero de la revisión {r.numero} («{r.fichero.name}»)."
    if sha256_de(r.fichero) != r.huella:
        return f"La revisión {r.numero} ha cambiado desde que se emitió: no se usa."
    return None


def emitir_revision(c: Carpeta, con: sqlite3.Connection, nombre: str, nota: str) -> Revision:
    """Congela el proyecto tal como está: copia coherente de la base de datos (API de backup
    de SQLite), de solo lectura, con su ficha. Nunca se sobrescribe ni se modifica."""
    import json

    carpeta = _carpeta_revisiones(c)
    carpeta.mkdir(exist_ok=True)
    existentes = revisiones(c)
    # El número sigue al mayor que haya, también de fichas dañadas o sueltas: nunca se
    # reutiliza un número.
    usados = [r.numero for r in existentes]
    for f in carpeta.glob("Rev *"):
        trozo = f.stem.removeprefix("Rev ").split(" ")[0]
        if trozo.isdigit():
            usados.append(int(trozo))
    numero = max(usados, default=-1) + 1
    base = f"Rev {numero}"
    db = carpeta / f"{base}.db"
    temporal = db.with_suffix(".parcial")
    try:
        dst = sqlite3.connect(temporal)
        try:
            con.backup(dst)
        finally:
            dst.close()
        os.replace(temporal, db)
    except BaseException:
        temporal.unlink(missing_ok=True)
        raise
    db.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    r = Revision(
        numero,
        nombre,
        nota,
        datetime.now(UTC).isoformat(timespec="seconds"),
        db,
        sha256_de(db),
        version(con),
    )
    ficha = carpeta / f"{base}.json"
    ficha.write_text(
        json.dumps(
            {
                "numero": r.numero,
                "nombre": r.nombre,
                "nota": r.nota,
                "fecha": r.fecha,
                "fichero": db.name,
                "huella": r.huella,
                "version_esquema": r.version_esquema,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    ficha.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    return r


def abrir_revision(r: Revision) -> sqlite3.Connection:
    """La revisión en memoria, migrada al esquema actual si es de uno anterior: se puede
    calcular sobre ella sin tocar el fichero congelado."""
    problema = revision_danada(r)
    if problema:
        raise CarpetaNoValida(problema)
    from urllib.request import pathname2url

    # URI de solo lectura, con la ruta codificada (una carpeta con «#» o «?» la rompería).
    origen = sqlite3.connect(f"file:{pathname2url(str(r.fichero))}?mode=ro", uri=True)
    memoria = sqlite3.connect(":memory:", isolation_level=None)
    try:
        origen.backup(memoria)
    finally:
        origen.close()
    memoria.row_factory = sqlite3.Row
    memoria.execute("PRAGMA foreign_keys = ON")
    migrar(memoria)
    return memoria
