"""Pruebas de los fallos encontrados en la revisión del núcleo (06-11-2026).

Cada prueba nombra el fallo que impide reintroducir.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pytest

from traza.app.ordenes import (
    Aprobar,
    ConfirmarPropuesta,
    CrearElemento,
    CrearPendiente,
    FijarPropiedad,
    Orden,
    OrdenRechazada,
    Reabrir,
)
from traza.app.proyecto import ElementoBloqueado, Proyecto
from traza.core.procedencia import Origen, Procedencia
from traza.core.unidades import UnidadInvalida, a_si
from traza.persistence import bd
from traza.persistence import carpeta as fs
from traza.persistence.filas import Delta, leer

USUARIO = Procedencia(Origen.USUARIO)
IA = Procedencia(Origen.IA_PROPUESTA)


def _equipo(p: Proyecto, codigo="EQ-1") -> str:
    o = CrearElemento("equipo", codigo)
    p.ejecutar(o)
    p.ejecutar(FijarPropiedad(o.id, "fabricante", "F", None, USUARIO))
    p.ejecutar(FijarPropiedad(o.id, "modelo", "M", None, USUARIO))
    return o.id


# --- La IA solo propone (línea roja 7) ---------------------------------------------------


def test_la_ia_no_confirma_ni_aprueba_ni_escribe_como_usuario(proyecto):
    el = _equipo(proyecto)
    proyecto.ejecutar(FijarPropiedad(el, "tension", 400, "V", IA), autor="ia")
    for orden in (
        ConfirmarPropuesta(el, "tension"),
        Aprobar(el, "ok"),
        FijarPropiedad(el, "masa", 10, "kg", USUARIO),
    ):
        with pytest.raises(OrdenRechazada, match="La IA solo puede proponer"):
            proyecto.ejecutar(orden, autor="ia")
    proyecto.ejecutar(CrearPendiente("Falta la masa", el), autor="ia")


def test_el_usuario_no_fabrica_propuestas_de_ia(proyecto):
    el = _equipo(proyecto)
    with pytest.raises(OrdenRechazada, match="Solo la IA"):
        proyecto.ejecutar(FijarPropiedad(el, "tension", 400, "V", IA))


# --- Bloqueo de lo aprobado ---------------------------------------------------------------


def test_un_conjunto_aprobado_no_admite_componentes_nuevos(proyecto):
    padre = _equipo(proyecto, "UTA-01")
    proyecto.ejecutar(Aprobar(padre, "ok"))
    with pytest.raises(ElementoBloqueado):
        proyecto.ejecutar(CrearElemento("equipo", "VENT-01", padre_id=padre))


# --- Atomicidad ---------------------------------------------------------------------------


@dataclass
class _DosDeltasSegundoEnConflicto(Orden):
    elemento_id: str

    def planificar(self, con):
        el = leer(con, "elemento", {"id": self.elemento_id})
        bueno = Delta("elemento", el, {**el, "codigo": "CAMBIADO"})
        # «antes» falso: aplicar() lo detecta como conflicto a mitad de transacción.
        falso = {**el, "codigo": "NO-ES-ASI"}
        malo = Delta("elemento", falso, {**falso, "estado": "propuesto"})
        return [bueno, malo]


def test_una_orden_falla_a_mitad_y_no_queda_nada_aplicado(proyecto):
    el = _equipo(proyecto)
    cambios = len(proyecto.cambios())
    pila = proyecto._deshacer[:]
    with pytest.raises(OrdenRechazada, match="Conflicto"):
        proyecto.ejecutar(_DosDeltasSegundoEnConflicto(el))
    assert proyecto.elemento(el)["codigo"] == "EQ-1"
    assert len(proyecto.cambios()) == cambios
    assert proyecto._deshacer == pila


def test_reejecutar_la_misma_orden_se_rechaza_limpiamente(proyecto):
    el = _equipo(proyecto)
    aprobar = Aprobar(el, "ok")
    proyecto.ejecutar(aprobar)
    proyecto.ejecutar(Reabrir(el, "cambio"))
    with pytest.raises(OrdenRechazada):
        proyecto.ejecutar(aprobar)  # mismo id de decisión: antes daba IntegrityError


# --- Copias de seguridad ------------------------------------------------------------------


def test_copia_antes_de_migrar_conserva_el_esquema_anterior(tmp_path, monkeypatch):
    p = Proyecto.crear(tmp_path / "N", "N")
    raiz = p.carpeta.raiz
    p.cerrar()
    v = bd.VERSION_ACTUAL
    siguiente = "CREATE TABLE prueba_siguiente (x INTEGER);"
    monkeypatch.setattr(bd, "MIGRACIONES", (*bd.MIGRACIONES, siguiente))
    monkeypatch.setattr(bd, "VERSION_ACTUAL", v + 1)
    monkeypatch.setattr(fs, "VERSION_ACTUAL", v + 1)
    Proyecto.abrir(raiz).cerrar()
    previas = [c for c in fs.copias(fs.Carpeta(raiz)) if f"antes-de-migrar-v{v}" in c.name]
    assert len(previas) == 1
    con = sqlite3.connect(previas[0])
    try:
        assert con.execute("PRAGMA user_version").fetchone()[0] == v
        assert not con.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'prueba_siguiente'"
        ).fetchone()
    finally:
        con.close()


def test_un_proyecto_v1_se_actualiza_a_la_version_actual(tmp_path):
    """Un proyecto creado antes de existir las mediciones (esquema V1) se abre y se migra."""
    from traza.persistence.esquema import MIGRACIONES, VERSION_ACTUAL

    raiz = tmp_path / "Antiguo.traza"
    for sub in ("documentos", "copias", "exportaciones"):
        (raiz / sub).mkdir(parents=True)
    con = bd.conectar(raiz / fs.BD)
    con.execute("BEGIN IMMEDIATE")
    for s in bd._sentencias(MIGRACIONES[0]):
        con.execute(s)
    con.execute("PRAGMA user_version = 1")
    con.execute("INSERT INTO meta VALUES ('nombre', 'Antiguo')")
    con.execute("COMMIT")
    con.close()
    p = Proyecto.abrir(raiz)
    try:
        assert bd.version(p._con) == VERSION_ACTUAL
        assert p.mediciones() == []
        assert p.encargo == "diseno"  # sin tipo de encargo: se muestran todos los pasos
    finally:
        p.cerrar()


def test_se_restaura_aunque_la_base_de_datos_este_danada(tmp_path):
    p = Proyecto.crear(tmp_path / "N", "N")
    el = _equipo(p)
    copia = p.copia_de_seguridad()
    raiz = p.carpeta.raiz
    p.cerrar()
    (raiz / fs.BD).write_bytes(b"esto no es una base de datos" * 100)
    fs.restaurar(fs.Carpeta(raiz), copia)
    p2 = Proyecto.abrir(raiz)
    try:
        assert p2.elemento(el) is not None
        assert any(c.name.endswith("-danada.db") for c in fs.copias(p2.carpeta))
        assert not list(raiz.glob("*.restaurando"))
    finally:
        p2.cerrar()


def test_la_poda_solo_afecta_a_las_copias_de_apertura(tmp_path, monkeypatch):
    monkeypatch.setattr(fs, "COPIAS_APERTURA_CONSERVADAS", 2)
    p = Proyecto.crear(tmp_path / "N", "N")
    manual = p.copia_de_seguridad()
    raiz = p.carpeta.raiz
    p.cerrar()
    for _ in range(4):
        Proyecto.abrir(raiz).cerrar()
    todas = fs.copias(fs.Carpeta(raiz))
    assert manual in todas
    assert sum(c.stem.endswith("-apertura") for c in todas) == 2


def test_proyecto_a_medio_crear_no_deja_carpeta(tmp_path, monkeypatch):
    def falla(_raiz):
        raise OSError("disco lleno")

    monkeypatch.setattr(fs, "abrir", falla)
    with pytest.raises(OSError):
        Proyecto.crear(tmp_path / "N", "N")
    assert not (tmp_path / "N.traza").exists()


def test_copia_de_documento_que_no_coincide_se_descarta(tmp_path, monkeypatch, pdf_3_paginas):
    p = Proyecto.crear(tmp_path / "N", "N")
    try:
        huellas = iter(["a" * 64, "b" * 64])
        monkeypatch.setattr(fs, "sha256_de", lambda _ruta: next(huellas))
        with pytest.raises(OSError, match="no coincide"):
            p.incorporar_documento(pdf_3_paginas)
        assert list(p.carpeta.documentos.iterdir()) == []
        assert p.documentos() == []
    finally:
        p.cerrar()


# --- Unidades -----------------------------------------------------------------------------


def test_notacion_espanola_de_transmitancia():
    # W/m²·K es W/(m²·K); antes se interpretaba como (W/m²)·K.
    assert a_si(0.5, "W/m²·K", "W/(m**2*K)") == pytest.approx(0.5)
    assert a_si(1, "kg·m/s²", "N") == pytest.approx(1)
    with pytest.raises(UnidadInvalida, match="ambigua"):
        a_si(1, "m/s/s", "m/s**2")


# --- Revisión de la interfaz (06-11-2026) -------------------------------------------------


def test_no_se_admiten_valores_negativos_sin_sentido_fisico(proyecto):
    el = _equipo(proyecto)
    with pytest.raises(OrdenRechazada, match="no admite valores negativos"):
        proyecto.ejecutar(FijarPropiedad(el, "potencia_frigorifica", -3, "kW", USUARIO))


@pytest.mark.parametrize("nombre", ["../fuera", "a/b", "nave:1", "nave?"])
def test_nombre_de_proyecto_que_saldria_de_la_carpeta(tmp_path, nombre):
    with pytest.raises(OrdenRechazada):
        Proyecto.crear(tmp_path / nombre, nombre)


def test_historial_completo_sin_corte(proyecto):
    for i in range(260):
        proyecto.ejecutar(CrearPendiente(f"dato {i}"))
    assert len(proyecto.cambios()) == 260 * 1
    for _ in range(260):
        proyecto.deshacer()
    assert len(proyecto.cambios()) == 520
