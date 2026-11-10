"""Crear una obra desde sus documentos, o añadirle documentos (docs/modules/obra.md, 4c).

Usuario (10-11-2026): echar todos los documentos recibidos y que TRAZA genere la obra. Aquí
solo se orquesta lo que ya hace cada paso: TRAZA propone qué es cada documento
(app/clasificar), el usuario lo confirma en una tabla, y se monta en orden (presupuesto,
mediciones y ofertas, coste objetivo, certificaciones por su nº, facturas). Lo que pide
datos (nº y fecha de una certificación, el paquete de cada factura) se pregunta como en su
paso. Un documento que falla no para los demás; al final se dice qué se ha hecho y qué no.
"""

from __future__ import annotations

from pathlib import Path

from traza.app import clasificar
from traza.app.ordenes import OrdenRechazada
from traza.app.proyecto import Proyecto


def nueva_obra(v) -> None:
    """Archivo → Nueva obra desde documentos…"""
    r = v.preguntas.nueva_obra()
    if r is None:
        return
    destino, nombre = r
    rutas = v.preguntas.ficheros("Documentos de la obra (todos los que tengas)")
    if not rutas:
        return
    try:
        p = Proyecto.crear(destino, nombre, "obra")
    except Exception as exc:  # noqa: BLE001 — se dice, como en «Nuevo proyecto»
        v.preguntas.aviso("No se ha creado la obra", str(exc))
        return
    v._usar_proyecto(p)
    anadir_documentos(v, rutas)


def anadir_documentos(v, rutas: list[Path] | None = None) -> None:
    """Obra → Añadir documentos a la obra… (y el final de «Nueva obra desde documentos»)."""
    if rutas is None:
        rutas = v.preguntas.ficheros("Documentos que añadir a la obra")
        if not rutas:
            return
    p = v.proyecto
    nuevos, ya, fallos = [], [], []
    for ruta in rutas:
        try:
            nuevos.append(p.incorporar_documento(Path(ruta)))
        except OrdenRechazada as exc:
            (ya if "ya está incorporado" in str(exc) else fallos).append(
                f"{Path(ruta).name}: {exc}"
            )
        except OSError as exc:
            fallos.append(f"{Path(ruta).name}: {exc}")
    v.refrescar()
    docs = [d for d in p.documentos() if d["id"] in nuevos]
    if not docs:
        v.preguntas.aviso(
            "Documentos de la obra",
            "No se ha incorporado ningún documento nuevo.\n" + "\n".join([*ya, *fallos]),
        )
        return
    propuestas = clasificar.clasificar(p, docs)
    plan = v.preguntas.plan_obra(propuestas)
    if plan is None:
        v.preguntas.informacion(
            "Documentos de la obra",
            f"{len(docs)} documento(s) incorporado(s) a «Documentación», sin leer.",
        )
        return
    hecho: list[str] = []
    no: list[str] = [*(f"{x} (no se incorpora otra vez)" for x in ya), *fallos]
    for prop, tipo in clasificar.orden_de_montaje(plan):
        etiqueta = f"{prop.nombre}: {clasificar.TIPOS[tipo].lower()}"
        try:
            if _montar(v, prop, tipo):
                hecho.append(etiqueta)
            else:
                no.append(f"{etiqueta} (cancelado)")
        except OrdenRechazada as exc:
            no.append(f"{etiqueta}: {exc}")
        except Exception as exc:  # noqa: BLE001 — un documento no tumba los demás; se dice
            no.append(f"{etiqueta}: {type(exc).__name__}: {exc}")
    sin_leer = [
        f"{prop.nombre}: {clasificar.TIPOS[tipo].lower()}"
        for prop, tipo in plan
        if tipo in ("plano", "documentacion")
    ]
    v.refrescar()
    texto = []
    if hecho:
        texto.append("Hecho:\n" + "\n".join(f"✓ {x}" for x in hecho))
    if sin_leer:
        texto.append("En Documentación (los planos se leen en «Planos y espacios»):\n"
                     + "\n".join(f"· {x}" for x in sin_leer))  # fmt: skip
    if no:
        texto.append("No hecho:\n" + "\n".join(f"✗ {x}" for x in no))
    v.preguntas.informacion("Documentos de la obra", "\n\n".join(texto))
    if p.venta_contratada() is not None:
        v.ir_a_paso("venta")


def _montar(v, prop: clasificar.Propuesta, tipo: str) -> bool:
    p = v.proyecto
    doc = next(d for d in p.documentos() if d["id"] == prop.documento_id)
    if tipo in clasificar.LEIDOS_CON_MEDICION:
        esperar = v._en_segundo_plano if prop.con_ia(tipo) else None
        medicion_id, _avisos = p.leer_medicion(prop.documento_id, tipo, None, esperar=esperar)
        if tipo == "presupuesto":
            p.fijar_venta_contratada(medicion_id)
        return True
    if tipo == "coste_objetivo":
        p.importar_coste_objetivo(prop.documento_id)
        return True
    if tipo == "certificacion":
        return v.pagina_certificaciones.accion_importar(doc, prop.numero)
    if tipo == "facturas":
        return v.pagina_coste_real.accion_erp(doc)
    return False
