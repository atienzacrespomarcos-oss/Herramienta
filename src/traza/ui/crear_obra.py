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
    por_huella = {d["sha256"]: d["id"] for d in p.documentos()}
    ids, fallos = [], []
    for ruta in rutas:
        ruta = Path(ruta)
        try:
            ya = por_huella.get(_huella(ruta))
            # Un documento que ya está (se canceló, falló o quedó como documentación) no se
            # incorpora otra vez, pero entra en la tabla para poder leerlo (revisión
            # 10-11-2026: daba «ya está incorporado» y no había forma de leerlo).
            ids.append(ya or p.incorporar_documento(ruta))
        except (OrdenRechazada, OSError) as exc:
            fallos.append(f"{ruta.name}: {exc}")
    v.refrescar()
    elegidos = set(ids)
    docs = [d for d in p.documentos() if d["id"] in elegidos]
    if not docs:
        v.preguntas.aviso(
            "Documentos de la obra", "No se ha incorporado ningún documento.\n" + "\n".join(fallos)
        )
        return
    propuestas = clasificar.clasificar(p, docs)
    plan = _pedir_plan(v, propuestas)
    if plan is None:
        v.preguntas.informacion(
            "Documentos de la obra",
            f"{len(docs)} documento(s) en «Documentación», sin leer.",
        )
        return
    hecho: list[str] = []
    no: list[str] = list(fallos)
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


def _huella(ruta: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _pedir_plan(v, propuestas):
    """La tabla, hasta que el plan tenga sentido: un solo presupuesto por obra (usuario,
    10-11-2026) y, si la obra ya tiene venta, sustituirla se confirma."""
    while True:
        plan = v.preguntas.plan_obra(propuestas)
        if plan is None:
            return None
        presupuestos = [x for x, t in plan if t == "presupuesto"]
        if len(presupuestos) > 1:
            v.preguntas.aviso(
                "Documentos de la obra",
                "Has elegido "
                + ", ".join(f"«{x.nombre}»" for x in presupuestos)
                + " como presupuesto contratado: la obra tiene uno solo. Elige uno; los demás "
                "pueden ser mediciones u ofertas.",
            )
            continue
        venta = v.proyecto.venta_contratada()
        if (
            presupuestos
            and venta is not None
            and not v.preguntas.confirmar(
                "Documentos de la obra",
                f"La obra ya tiene presupuesto contratado («{venta['documento_nombre']}»). "
                f"¿Sustituirlo por «{presupuestos[0].nombre}»? Las certificaciones se cruzan con "
                "la venta: revísalas después.",
            )
        ):
            continue
        return plan


def _montar(v, prop: clasificar.Propuesta, tipo: str) -> bool:
    p = v.proyecto
    doc = next(d for d in p.documentos() if d["id"] == prop.documento_id)
    if tipo in clasificar.LEIDOS_CON_MEDICION:
        esperar = v._en_segundo_plano if prop.con_ia(tipo) else None
        medicion_id, _avisos = p.leer_medicion(prop.documento_id, tipo, None, esperar=esperar)
        if tipo == "presupuesto":
            try:
                p.fijar_venta_contratada(medicion_id)
            except OrdenRechazada as exc:
                raise OrdenRechazada(
                    f"se ha leído, pero no ha quedado como venta contratada: {exc}"
                ) from exc
        return True
    if tipo == "coste_objetivo":
        p.importar_coste_objetivo(prop.documento_id)
        return True
    if tipo == "certificacion":
        return v.pagina_certificaciones.accion_importar(doc, prop.numero)
    if tipo == "facturas":
        return v.pagina_coste_real.accion_erp(doc)
    return False
