"""Escenario de aceptación de la Etapa 1 (DEVELOPMENT_ROADMAP) sobre el núcleo, sin interfaz.

Crear proyecto → incorporar PDF → crear elemento → fijar valor citando página →
aprobar → intento de modificar bloqueado → reabrir con motivo → deshacer/rehacer →
cerrar y reabrir sin pérdidas → copia de seguridad restaurable.
"""

from __future__ import annotations

import sqlite3
import stat

import pytest

from traza.app.ordenes import (
    Aprobar,
    BorrarPropiedad,
    CambiarEstado,
    ConfirmarPropuesta,
    CrearElemento,
    CrearPendiente,
    FijarPropiedad,
    OrdenRechazada,
    Reabrir,
    ResolverPendiente,
)
from traza.app.proyecto import ElementoBloqueado, Proyecto
from traza.core.estados import Estado
from traza.core.procedencia import Origen, Procedencia
from traza.persistence import carpeta as fs

USUARIO = Procedencia(Origen.USUARIO)


def _doc(doc_id: str, pagina: str = "p. 2") -> Procedencia:
    return Procedencia(Origen.DOCUMENTO, documento_id=doc_id, localizador=pagina)


def _equipo_completo(p: Proyecto, codigo: str = "UTA-01") -> str:
    orden = CrearElemento("equipo", codigo)
    p.ejecutar(orden)
    p.ejecutar(FijarPropiedad(orden.id, "fabricante", "Fabricante X", None, USUARIO))
    p.ejecutar(FijarPropiedad(orden.id, "modelo", "Modelo Y", None, USUARIO))
    return orden.id


def test_escenario_aceptacion_etapa_1(tmp_path, pdf_3_paginas):
    p = Proyecto.crear(tmp_path / "Nave A", "Nave A")
    assert p.carpeta.raiz.name == "Nave A.traza"

    doc_id = p.incorporar_documento(pdf_3_paginas, clasificacion="oferta")
    assert p.documentos()[0]["paginas"] == 3

    el = _equipo_completo(p)
    p.ejecutar(FijarPropiedad(el, "caudal_aire", 2400, "m³/h", _doc(doc_id, "p. 2, tabla 1")))
    caudal = {r["clave"]: r for r in p.propiedades(el)}["caudal_aire"]
    assert caudal["valor"] == 2400 and caudal["unidad"] == "m³/h"
    assert caudal["origen"] == "documento" and caudal["localizador"] == "p. 2, tabla 1"
    assert caudal["documento_nombre"] == "oferta.pdf"
    assert p.usos_de_documento(doc_id) == [
        {"codigo": "UTA-01", "clave": "caudal_aire", "localizador": "p. 2, tabla 1"}
    ]

    p.ejecutar(Aprobar(el, "Equipo seleccionado según oferta"))
    assert p.elemento(el)["estado"] == Estado.APROBADO
    with pytest.raises(ElementoBloqueado):
        p.ejecutar(FijarPropiedad(el, "caudal_aire", 2600, "m³/h", USUARIO))
    with pytest.raises(ElementoBloqueado):
        p.ejecutar(BorrarPropiedad(el, "caudal_aire"))

    # Deshacer la aprobación es la inversa inmediata: permitido. Rehacer la vuelve a poner.
    assert p.deshacer() == "Aprobar"
    assert p.elemento(el)["estado"] == Estado.BORRADOR
    assert p.decisiones(el) == []
    assert p.rehacer() == "Aprobar"
    assert p.elemento(el)["estado"] == Estado.APROBADO

    with pytest.raises(OrdenRechazada):
        p.ejecutar(Reabrir(el, "   "))
    p.ejecutar(Reabrir(el, "El cliente cambia el caudal en la revisión B"))
    p.ejecutar(FijarPropiedad(el, "caudal_aire", 2600, "m³/h", USUARIO))
    assert [d["tipo"] for d in p.decisiones(el)] == ["aprobar", "reabrir"]

    raiz = p.carpeta.raiz
    p.cerrar()

    p2 = Proyecto.abrir(raiz)
    try:
        assert p2.nombre == "Nave A"
        props = {r["clave"]: r for r in p2.propiedades(el)}
        assert props["caudal_aire"]["valor"] == 2600 and props["caudal_aire"]["origen"] == "usuario"
        assert len(p2.decisiones(el)) == 2
        assert fs.copias(p2.carpeta), "al abrir se hace copia de seguridad"
    finally:
        p2.cerrar()


def test_cita_de_pagina_inexistente_o_sin_pagina(proyecto, pdf_3_paginas):
    doc = proyecto.incorporar_documento(pdf_3_paginas)
    el = _equipo_completo(proyecto)
    with pytest.raises(OrdenRechazada, match="no existe la página 4"):
        proyecto.ejecutar(FijarPropiedad(el, "tension", 400, "V", _doc(doc, "p. 4")))
    with pytest.raises(OrdenRechazada, match="debe empezar por la página"):
        proyecto.ejecutar(FijarPropiedad(el, "tension", 400, "V", _doc(doc, "tabla 2")))
    with pytest.raises(OrdenRechazada, match="no está incorporado"):
        proyecto.ejecutar(FijarPropiedad(el, "tension", 400, "V", _doc("otro-id", "p. 1")))


def test_documento_original_intacto_y_sin_duplicar(proyecto, pdf_3_paginas):
    original = pdf_3_paginas.read_bytes()
    doc = proyecto.incorporar_documento(pdf_3_paginas)
    assert pdf_3_paginas.read_bytes() == original, "el original no se toca"
    copia = proyecto.ruta_documento(doc)
    assert copia.read_bytes() == original
    assert not copia.stat().st_mode & stat.S_IWUSR, "el almacén es de solo lectura"
    with pytest.raises(OrdenRechazada, match="ya está incorporado"):
        proyecto.incorporar_documento(pdf_3_paginas)
    assert len(proyecto.documentos()) == 1


def test_aprobar_exige_obligatorias_y_propuestas_confirmadas(proyecto):
    orden = CrearElemento("equipo", "BC-01")
    proyecto.ejecutar(orden)
    with pytest.raises(OrdenRechazada, match="faltan Fabricante, Modelo"):
        proyecto.ejecutar(Aprobar(orden.id, "ok"))
    proyecto.ejecutar(FijarPropiedad(orden.id, "fabricante", "X", None, USUARIO))
    proyecto.ejecutar(
        FijarPropiedad(orden.id, "modelo", "Y", None, Procedencia(Origen.IA_PROPUESTA)),
        autor="ia",
    )
    with pytest.raises(OrdenRechazada, match="propuestas sin confirmar"):
        proyecto.ejecutar(Aprobar(orden.id, "ok"))
    proyecto.ejecutar(ConfirmarPropuesta(orden.id, "modelo"))
    modelo = {r["clave"]: r for r in proyecto.propiedades(orden.id)}["modelo"]
    assert modelo["origen"] == "usuario" and modelo["confirmado"] == 1
    proyecto.ejecutar(Aprobar(orden.id, "ok"))


def test_propuesta_ia_con_cita_se_confirma_como_documento(proyecto, pdf_3_paginas):
    doc = proyecto.incorporar_documento(pdf_3_paginas)
    el = _equipo_completo(proyecto)
    ia = Procedencia(Origen.IA_PROPUESTA, documento_id=doc, localizador="p. 1")
    proyecto.ejecutar(FijarPropiedad(el, "potencia_frigorifica", 25.3, "kW", ia), autor="ia")
    proyecto.ejecutar(ConfirmarPropuesta(el, "potencia_frigorifica"))
    fila = {r["clave"]: r for r in proyecto.propiedades(el)}["potencia_frigorifica"]
    assert fila["origen"] == "documento" and fila["localizador"] == "p. 1"


def test_resultados_de_calculo_no_se_escriben_a_mano(proyecto):
    el = _equipo_completo(proyecto)
    with pytest.raises(OrdenRechazada, match="los escribe el motor"):
        proyecto.ejecutar(
            FijarPropiedad(
                el, "masa", 120, "kg", Procedencia(Origen.CALCULO, registro_calculo_id="r")
            )
        )


def test_transiciones_de_estado(proyecto):
    el = _equipo_completo(proyecto)
    proyecto.ejecutar(CambiarEstado(el, Estado.PROPUESTO))
    with pytest.raises(OrdenRechazada, match="lo fija un motor"):
        proyecto.ejecutar(CambiarEstado(el, Estado.CALCULADO))
    proyecto.ejecutar(CambiarEstado(el, Estado.CALCULADO), autor="motor")
    with pytest.raises(OrdenRechazada, match="lo fija un motor"):
        proyecto.ejecutar(CambiarEstado(el, Estado.COMPROBADO))
    with pytest.raises(OrdenRechazada):
        proyecto.ejecutar(CambiarEstado(el, Estado.PROPUESTO), autor="motor")
    with pytest.raises(OrdenRechazada, match="orden Aprobar"):
        proyecto.ejecutar(CambiarEstado(el, Estado.APROBADO))


def test_codigo_duplicado(proyecto):
    proyecto.ejecutar(CrearElemento("equipo", "UTA-01"))
    with pytest.raises(OrdenRechazada, match="Ya existe"):
        proyecto.ejecutar(CrearElemento("equipo", " UTA-01 "))


def test_pendientes(proyecto):
    orden = CrearPendiente("Falta confirmar la tensión de alimentación de la UTA")
    proyecto.ejecutar(orden)
    assert len(proyecto.pendientes()) == 1
    with pytest.raises(OrdenRechazada):
        proyecto.ejecutar(ResolverPendiente(orden.id, " "))
    proyecto.ejecutar(ResolverPendiente(orden.id, "400 V según ficha técnica"))
    assert proyecto.pendientes() == []
    assert len(proyecto.pendientes(solo_abiertos=False)) == 1


def test_orden_rechazada_no_deja_rastro(proyecto):
    antes = len(proyecto.cambios())
    with pytest.raises(OrdenRechazada):
        proyecto.ejecutar(CrearElemento("tipo-que-no-existe", "X-1"))
    assert len(proyecto.cambios()) == antes
    assert not proyecto.puede_deshacer


def test_registro_de_cambios_completo_y_no_editable(proyecto):
    el = _equipo_completo(proyecto)
    proyecto.ejecutar(FijarPropiedad(el, "fabricante", "Otro", None, USUARIO))
    proyecto.deshacer()
    autores = [c["autor"] for c in reversed(proyecto.cambios())]
    assert autores == ["usuario"] * 4 + ["deshacer"]
    ultimo = proyecto.cambios()[0]
    # «modificado» solo aparece si cambió el segundo del reloj; lo que importa es «valor».
    assert "valor" in ultimo["campo"].split(",")
    con = proyecto._con
    with pytest.raises(sqlite3.IntegrityError, match="no se modifica"):
        con.execute("UPDATE cambio SET autor = 'usuario'")
    with pytest.raises(sqlite3.IntegrityError, match="no se borra"):
        con.execute("DELETE FROM cambio")


def test_la_base_de_datos_rechaza_valores_sin_procedencia(proyecto):
    """Segunda capa: aunque un error saltara las órdenes, la BD no guarda sin origen."""
    el = _equipo_completo(proyecto)
    con = proyecto._con
    malos = [
        ("documento", None, None, None, None, 1),
        ("hipotesis", None, None, None, "", 1),
        ("calculo", None, None, None, None, 1),
        ("ia_propuesta", None, None, None, None, 1),
        ("usuario", None, "p. 1", None, None, 1),
        ("usuario", None, None, "r", None, 1),
        ("usuario", None, None, None, None, 0),  # solo una propuesta de IA va sin confirmar
        ("catalogo", None, None, None, None, 1),
    ]
    for origen, doc, loc, reg, nota, conf in malos:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO propiedad VALUES (?, 'tension', '400', 'V', ?, ?, ?, ?, ?, ?, 'x')",
                (el, origen, doc, loc, reg, nota, conf),
            )


def test_copia_de_seguridad_y_restauracion(tmp_path):
    p = Proyecto.crear(tmp_path / "Nave B", "Nave B")
    el = _equipo_completo(p, "UTA-02")
    copia = p.copia_de_seguridad()
    p.ejecutar(FijarPropiedad(el, "tension", 230, "V", USUARIO))
    raiz = p.carpeta.raiz
    p.cerrar()

    fs.restaurar(fs.Carpeta(raiz), copia)
    p2 = Proyecto.abrir(raiz)
    try:
        assert "tension" not in {r["clave"] for r in p2.propiedades(el)}
        assert any("antes-de-restaurar" in c.name for c in fs.copias(p2.carpeta))
    finally:
        p2.cerrar()


def test_no_se_sobrescribe_un_proyecto_existente(tmp_path):
    Proyecto.crear(tmp_path / "Nave C", "Nave C").cerrar()
    with pytest.raises(fs.CarpetaNoValida):
        Proyecto.crear(tmp_path / "Nave C", "Otra")


def test_proyecto_de_version_futura_no_se_abre(tmp_path):
    from traza.persistence.bd import ProyectoDeVersionFutura

    p = Proyecto.crear(tmp_path / "Nave D", "Nave D")
    p._con.execute("PRAGMA user_version = 999")
    raiz = p.carpeta.raiz
    p.cerrar()
    with pytest.raises(ProyectoDeVersionFutura):
        Proyecto.abrir(raiz)
