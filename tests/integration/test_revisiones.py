"""Revisiones del diseño y su comparación (RF-009, docs/modules/revisiones.md).

Proyecto de tests/integration/test_redes_proyecto.py (ALMACÉN y OFICINAS con cargas y una
red de impulsión).
"""

from __future__ import annotations

import os
import stat

import pytest
from openpyxl import load_workbook
from tests.integration.test_hidronica_proyecto import _circuitos
from tests.integration.test_redes_proyecto import red  # noqa: F401 (fixture)

from traza.app.ordenes import OrdenRechazada


def test_emitir_congela_el_proyecto_y_numera(red):  # noqa: F811
    p, *_ = red
    r0 = p.emitir_revision("Para oferta", "Primera entrega")
    r1 = p.emitir_revision("Planos rev. B")
    assert [(r.numero, r.nombre) for r in p.revisiones()] == [
        (0, "Para oferta"),
        (1, "Planos rev. B"),
    ]
    assert r0.nota == "Primera entrega" and r0.fichero.name == "Rev 0.db"
    # Congelada: solo lectura y con su huella.
    assert not os.stat(r0.fichero).st_mode & stat.S_IWUSR
    assert r1.huella and r1.huella != ""
    with pytest.raises(OrdenRechazada, match="necesita un nombre"):
        p.emitir_revision("  ")


def test_una_revision_abierta_no_admite_ordenes(red):  # noqa: F811
    p, *_ = red
    p.emitir_revision("Para oferta")
    rev = p.abrir_revision(0)
    try:
        assert [e["nombre"] for e in rev.espacios()] == [e["nombre"] for e in p.espacios()]
        with pytest.raises(OrdenRechazada, match="está emitida"):
            rev.definir_sistema_hidraulico(titulo="X", tipo="2_tubos", circuitos=_circuitos(p))
    finally:
        rev.cerrar()
    # El fichero congelado sigue siendo el mismo.
    (r,) = p.revisiones()
    from traza.persistence.carpeta import revision_danada

    assert revision_danada(r) is None


def test_revision_alterada_no_se_usa(red):  # noqa: F811
    p, *_ = red
    r = p.emitir_revision("Para oferta")
    r.fichero.chmod(stat.S_IREAD | stat.S_IWRITE)
    with r.fichero.open("ab") as f:
        f.write(b"\0")
    with pytest.raises(OrdenRechazada, match="ha cambiado desde que se emitió"):
        p.abrir_revision(0)
    # Y el número no se reutiliza.
    assert p.emitir_revision("Otra").numero == 1


def test_comparar_con_lo_actual_datos_y_resultados(red, tmp_path):  # noqa: F811
    p, *_ = red
    p.emitir_revision("Sin hidráulica")
    assert p.comparar_revisiones(0) == []  # nada ha cambiado todavía
    p.definir_sistema_hidraulico(titulo="Clima", tipo="2_tubos", circuitos=_circuitos(p))
    ofi = next(e for e in p.espacios() if e["nombre"] == "OFICINAS")
    p.fijar_cargas_espacio(ofi["id"], "reuniones")
    cambios = p.comparar_revisiones(0)
    por = {(c.apartado, c.elemento, c.dato): c for c in cambios}
    # Lo nuevo: el sistema hidráulico, con su potencia calculada.
    nuevo = por[("Sistema hidráulico", "Clima · Frío / calor (2 tubos)", "Potencia del generador")]
    assert nuevo.antes is None and nuevo.ahora > 0
    # Lo que cambia: el uso de OFICINAS y, con él, su carga (resultado, no solo dato).
    nombre = next(c.elemento for c in cambios if c.dato == "Uso")
    from traza.rules.usos import POR_CLAVE

    assert por[("Cargas", nombre, "Uso")].ahora == POR_CLAVE["reuniones"].nombre
    refri = por[("Cargas", nombre, "Refrigeración")]
    assert refri.antes != refri.ahora and refri.diferencia == round(refri.ahora - refri.antes, 2)
    # Excel con todo.
    x = p.exportar_comparacion(0, None, tmp_path / "Comparación")
    wb = load_workbook(x)
    assert wb.sheetnames == ["Resumen", "Cambios"]
    filas = list(wb["Cambios"].iter_rows(min_row=2, values_only=True))
    assert len(filas) == len(cambios)
    assert ("Nuevo" in {f[3] for f in filas}) and ("Cambia" in {f[3] for f in filas})
    # Entre dos revisiones: lo mismo, sin mirar lo actual.
    p.emitir_revision("Con hidráulica")
    entre = p.comparar_revisiones(0, 1)
    assert {(c.apartado, c.dato) for c in entre} == {(c.apartado, c.dato) for c in cambios}


# --- Revisión del 11-11-2026 ------------------------------------------------------------


def test_un_error_del_motor_no_tumba_la_comparacion(red, monkeypatch):  # noqa: F811
    """Una red que no calcula (ValueError del motor, p. ej. un ciclo) entra con su motivo; el
    resto se compara igual."""
    p, *_ = red
    p.emitir_revision("Base")

    def falla(_red_id):
        raise ValueError("la red tiene un ciclo")

    monkeypatch.setattr(p, "calcular_red", falla)
    cambios = p.comparar_revisiones(0)
    red_cambios = [c for c in cambios if c.apartado == "Redes de aire"]
    assert any(c.dato == "Cálculo" and "ciclo" in str(c.ahora) for c in red_cambios)
    assert not any(c.apartado == "Cargas" for c in cambios)  # lo demás, igual


def test_revision_de_un_traza_mas_nuevo_se_avisa(red):  # noqa: F811
    p, *_ = red
    r = p.emitir_revision("Base")
    # Simula una revisión emitida con un esquema futuro (y su huella coherente).
    import json
    import sqlite3

    from traza.persistence.carpeta import sha256_de

    r.fichero.chmod(stat.S_IREAD | stat.S_IWRITE)
    con = sqlite3.connect(r.fichero)
    con.execute("PRAGMA user_version = 9999")
    con.close()
    ficha = r.fichero.with_suffix(".json")
    ficha.chmod(stat.S_IREAD | stat.S_IWRITE)
    d = json.loads(ficha.read_text(encoding="utf-8"))
    d["huella"] = sha256_de(r.fichero)
    ficha.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(OrdenRechazada, match="No se puede abrir la revisión 0"):
        p.abrir_revision(0)


def test_la_revision_abierta_no_cambia_ni_hace_copias(red):  # noqa: F811
    p, *_ = red
    r = p.emitir_revision("Base")
    rev = p.abrir_revision(0)
    try:
        from traza.app.revisiones import resumen

        assert resumen(rev)  # calcula sobre ella
        with pytest.raises(OrdenRechazada, match="no hace copias"):
            rev.copia_de_seguridad()
    finally:
        rev.cerrar()
    from traza.persistence.carpeta import sha256_de

    assert sha256_de(r.fichero) == r.huella
