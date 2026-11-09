"""Proyecto abierto: punto de entrada de la interfaz, los scripts y (en su día) la IA."""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from traza.ai import claude_code
from traza.app import cargas as calculo_cargas
from traza.app import flujo, lectura_ia
from traza.app import hidronica as calculo_hidronica
from traza.app import modificados as calculo_mod
from traza.app import obra as calculo_obra
from traza.app import planos as calculo_planos
from traza.app import redes as calculo_redes
from traza.app import subcuadros as calculo_subcuadros
from traza.app.ordenes import (
    ENCARGOS,
    BorrarRed,
    BorrarSistemaHidraulico,
    BorrarSubcuadro,
    CambiarEstado,
    CambiarPlano,
    CerrarPaquete,
    ConfirmarContorno,
    CrearPendiente,
    DarPorRevisado,
    DefinirRed,
    DefinirSistemaHidraulico,
    DefinirSubcuadro,
    DescartarPropuesta,
    FijarCargasEspacio,
    FijarCargasProyecto,
    FijarPrevision,
    FijarPropiedad,
    FijarVentaContratada,
    ImportarCosteObjetivo,
    ImportarMedicion,
    LeerPlano,
    Orden,
    OrdenRechazada,
    PartidaNueva,
    QuitarFactura,
    QuitarVentaContratada,
    RegistrarDocumento,
    RegistrarFactura,
    RevisarPlano,
    ahora,
    nuevo_id,
)
from traza.core.estados import Estado
from traza.core.ficheros import nombre_valido
from traza.core.geometria import Contorno, Vertice
from traza.core.procedencia import Origen, Procedencia
from traza.io import (
    bc3,
    bc3_modificar,
    clima_idae,
    coste_presto,
    dxf,
    esquema_hidraulico_dxf,
    informe_cargas,
    informe_hidronica,
    informe_redes,
    memoria,
    salida_autocad,
    unifilar_dxf,
)
from traza.io.bc3_escritura import Bc3EscrituraError, CapituloBc3, PartidaBc3, codigo_valido
from traza.io.bc3_escritura import escribir as escribir_bc3
from traza.io.excel import exportar_modificado, exportar_partidas, exportar_plano
from traza.io.pdf import contar_paginas, renderizar_pagina
from traza.persistence import carpeta as fs
from traza.persistence.filas import Conflicto, Delta, a_json, aplicar, leer

AUTORES = ("usuario", "motor", "ia", "importacion")


class ElementoBloqueado(OrdenRechazada):
    """Se intentó modificar un elemento aprobado sin reabrirlo."""


@dataclass(frozen=True)
class _Paso:
    orden_id: str
    nombre: str
    deltas: tuple[Delta, ...]


class Proyecto:
    def __init__(self, c: fs.Carpeta, con: sqlite3.Connection) -> None:
        self.carpeta = c
        self._con = con
        self._deshacer: list[_Paso] = []
        #: Quién lee PDF y Excel. Por defecto Claude Code (ADR-0013); las pruebas lo sustituyen.
        self.extractor_ia = claude_code.extraer
        self._rehacer: list[_Paso] = []
        #: DXF ya leídos en esta sesión (el documento no cambia).
        self._planos_dxf: dict[str, dxf.PlanoDxf] = {}
        #: Lector de la guía del IDAE (las pruebas lo sustituyen: la guía no se reproduce).
        self.lector_guia = clima_idae.leer_guia
        self._guias: dict[str, list[clima_idae.EstacionIdae]] = {}

    # --- Ciclo de vida -----------------------------------------------------------------

    @classmethod
    def crear(cls, destino: Path, nombre: str, encargo: str = "diseno") -> Proyecto:
        if not nombre.strip():
            raise OrdenRechazada("El proyecto necesita un nombre.")
        if set('<>:"/\\|?*') & set(nombre) or ".." in nombre:
            # Con «/» o «..» el proyecto acabaría fuera de la carpeta elegida.
            raise OrdenRechazada('El nombre no puede contener < > : " / \\ | ? * ni «..».')
        c = fs.crear(destino)
        con = None
        try:
            _, con = fs.abrir(c.raiz)
            con.execute("BEGIN IMMEDIATE")
            con.execute("INSERT INTO meta VALUES ('nombre', ?)", (nombre.strip(),))
            con.execute("INSERT INTO meta VALUES ('creado', ?)", (ahora(),))
            if encargo not in ENCARGOS:
                raise OrdenRechazada(f"Tipo de encargo desconocido: «{encargo}».")
            con.execute("INSERT INTO meta VALUES ('encargo', ?)", (encargo,))
            con.execute("COMMIT")
        except BaseException:
            # Un proyecto a medio crear dejaría ocupado el nombre («ya existe») sin servir
            # para nada. La carpeta la acabamos de crear nosotros: se puede retirar.
            if con is not None:
                con.close()
            shutil.rmtree(c.raiz, ignore_errors=True)
            raise
        return cls(c, con)

    @classmethod
    def abrir(cls, raiz: Path) -> Proyecto:
        # La copia «antes de migrar», si hace falta, la hace fs.abrir antes de tocar nada.
        c, con = fs.abrir(raiz)
        try:
            # Copia al abrir: si algo sale mal durante la sesión, el estado de partida existe.
            fs.copia_de_seguridad(c, con, etiqueta=fs.ETIQUETA_APERTURA)
        except BaseException:
            con.close()
            raise
        return cls(c, con)

    def cerrar(self) -> None:
        self._con.close()

    @property
    def nombre(self) -> str:
        return self._con.execute("SELECT valor FROM meta WHERE clave='nombre'").fetchone()[0]

    @property
    def encargo(self) -> str:
        fila = self._con.execute("SELECT valor FROM meta WHERE clave='encargo'").fetchone()
        # Proyectos creados antes de existir el tipo de encargo: se tratan como diseño.
        return fila[0] if fila else "diseno"

    def copia_de_seguridad(self) -> Path:
        return fs.copia_de_seguridad(self.carpeta, self._con, etiqueta="manual")

    def copias(self) -> list[Path]:
        return fs.copias(self.carpeta)

    @staticmethod
    def restaurar_copia(raiz: Path, copia: Path) -> None:
        """Restaura una copia. El proyecto debe estar cerrado (lo exige la interfaz)."""
        fs.restaurar(fs.Carpeta(raiz), copia)

    # --- Órdenes -----------------------------------------------------------------------

    def ejecutar(self, orden: Orden, autor: str = "usuario") -> str:
        """Aplica una orden entera o nada. Devuelve el id de la orden."""
        if autor not in AUTORES:
            raise ValueError(f"Autor no válido: {autor}")
        self._comprobar_autor(orden, autor)
        try:
            paso = self._transaccion(orden.nombre, autor, lambda: self._planificar(orden))
        except (sqlite3.IntegrityError, Conflicto) as exc:
            # Segunda barrera (CHECK, claves únicas, estado inesperado): la orden no entra y
            # la transacción ya se ha deshecho entera.
            raise OrdenRechazada(f"No se aplica el cambio: {exc}") from exc
        self._deshacer.append(paso)
        self._rehacer.clear()
        return paso.orden_id

    def deshacer(self) -> str | None:
        if not self._deshacer:
            return None
        paso = self._deshacer[-1]
        inverso = tuple(d.invertido() for d in reversed(paso.deltas))
        self._transaccion(paso.nombre, "deshacer", lambda: inverso, orden_id=paso.orden_id)
        self._rehacer.append(self._deshacer.pop())
        return paso.nombre

    def rehacer(self) -> str | None:
        if not self._rehacer:
            return None
        paso = self._rehacer[-1]
        self._transaccion(paso.nombre, "rehacer", lambda: paso.deltas, orden_id=paso.orden_id)
        self._deshacer.append(self._rehacer.pop())
        return paso.nombre

    @property
    def puede_deshacer(self) -> bool:
        return bool(self._deshacer)

    @property
    def puede_rehacer(self) -> bool:
        return bool(self._rehacer)

    @staticmethod
    def _comprobar_autor(orden: Orden, autor: str) -> None:
        """Quién puede hacer qué.

        - La IA solo propone (línea roja 7): valores con origen «ia_propuesta» y avisos de
          información pendiente. No confirma, no aprueba, no reabre.
        - «Calculado» y «comprobado» solo los fija un motor: marcarlos a mano sería mostrar
          un indicador de cumplimiento sin haber ejecutado la comprobación.
        """
        if autor == "ia":
            propone = (
                isinstance(orden, FijarPropiedad)
                and orden.procedencia.origen is Origen.IA_PROPUESTA
            )
            if not (propone or isinstance(orden, CrearPendiente)):
                raise OrdenRechazada(
                    "La IA solo puede proponer valores (origen «propuesta de IA») o señalar "
                    "información pendiente; lo demás lo decide el usuario."
                )
        elif isinstance(orden, FijarPropiedad) and orden.procedencia.origen is Origen.IA_PROPUESTA:
            raise OrdenRechazada("Solo la IA genera propuestas de IA.")
        if (
            isinstance(orden, CambiarEstado)
            and orden.estado in (Estado.CALCULADO, Estado.COMPROBADO)
            and autor != "motor"
        ):
            raise OrdenRechazada(
                f"El estado «{orden.estado}» lo fija un motor de cálculo al ejecutarse, no a mano."
            )

    def _planificar(self, orden: Orden) -> tuple[Delta, ...]:
        deltas = tuple(orden.planificar(self._con))
        if not deltas:
            raise OrdenRechazada("La orden no cambia nada.")
        if not orden.puede_tocar_aprobado:
            for d in deltas:
                self._comprobar_bloqueo(d)
        return deltas

    def _comprobar_bloqueo(self, d: Delta) -> None:
        """Línea roja 5: lo aprobado no se toca sin reabrirlo con una decisión escrita."""
        afectados: list[dict | None] = []
        if d.tabla == "elemento":
            afectados.append(d.antes)
            fila = d.despues if d.antes is None else (d.antes if d.despues is None else None)
            if fila is not None and fila["padre_id"]:
                # Añadir un componente a un conjunto aprobado, o quitárselo, también lo
                # modifica (revisión 07-11-2026: quitar un espacio de un nivel aprobado pasaba).
                afectados.append(leer(self._con, "elemento", {"id": fila["padre_id"]}))
        elif d.tabla in ("propiedad", "decision", "cargas_espacio"):
            fila = d.antes or d.despues
            assert fila is not None
            el = leer(self._con, "elemento", {"id": fila["elemento_id"]})
            afectados.append(el)
            if d.tabla == "propiedad" and el is not None and el["tipo"] == "nivel":
                # Los espacios y obstáculos heredan la altura del nivel (y su nombre y cota
                # salen con ellos): cambiarlo cambia los aprobados en silencio (revisión
                # 07-11-2026).
                aprobados = self._filas(
                    "SELECT codigo FROM elemento WHERE padre_id = ? AND estado = ?",
                    (el["id"], str(Estado.APROBADO)),
                )
                if aprobados:
                    raise ElementoBloqueado(
                        f"El nivel «{el['codigo']}» tiene elementos aprobados que dependen de "
                        f"él ({', '.join(a['codigo'] for a in aprobados)}): reábrelos antes "
                        "de cambiarlo."
                    )
        else:
            return
        for el in afectados:
            if el is not None and el["estado"] == Estado.APROBADO:
                raise ElementoBloqueado(
                    f"«{el['codigo']}» está aprobado. Para cambiarlo hay que reabrirlo "
                    "indicando el motivo."
                )

    def _transaccion(self, nombre, autor, obtener_deltas, orden_id: str | None = None) -> _Paso:
        orden_id = orden_id or nuevo_id()
        con = self._con
        con.execute("BEGIN IMMEDIATE")
        try:
            deltas = tuple(obtener_deltas())
            fecha = ahora()
            for d in deltas:
                aplicar(con, d)
                con.execute(
                    "INSERT INTO cambio (orden_id, orden, autor, fecha, entidad, entidad_id,"
                    " campo, antes, despues) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        orden_id,
                        nombre,
                        autor,
                        fecha,
                        d.tabla,
                        d.id_legible,
                        ",".join(d.campos_cambiados()) or None,
                        a_json(d.antes),
                        a_json(d.despues),
                    ),
                )
            con.execute("COMMIT")
        except BaseException:
            # BaseException: también una interrupción (Ctrl+C) deshace la transacción.
            con.execute("ROLLBACK")
            raise
        return _Paso(orden_id, nombre, deltas)

    # --- Documentos --------------------------------------------------------------------

    def incorporar_documento(self, origen: Path, clasificacion: str | None = None) -> str:
        """Copia el original al almacén (sin modificarlo) y lo registra. Devuelve su id.

        La copia física no se deshace: el almacén es de solo-añadir y un fichero sin
        registro no aparece en ningún sitio. Deshacer quita el registro.
        """
        origen = Path(origen)
        if not origen.is_file():
            raise OrdenRechazada(f"No se encuentra el fichero «{origen}».")
        extension = origen.suffix.lower()
        sha, almacenado = fs.guardar_documento(self.carpeta, origen)
        # Páginas y tamaño se leen de la copia verificada, no del original: si el original
        # cambiara entre medias, el registro describiría otro fichero.
        paginas = None
        if extension == ".pdf":
            try:
                paginas = contar_paginas(almacenado)
            except Exception as exc:
                raise OrdenRechazada(f"«{origen.name}» no se puede leer como PDF: {exc}") from exc
        orden = RegistrarDocumento(
            sha256=sha,
            nombre_original=origen.name,
            extension=extension,
            tamano=almacenado.stat().st_size,
            paginas=paginas,
            clasificacion=clasificacion,
        )
        self.ejecutar(orden)
        return orden.id

    def ruta_documento(self, documento_id: str) -> Path:
        doc = leer(self._con, "documento", {"id": documento_id})
        if doc is None:
            raise OrdenRechazada("Documento no incorporado.")
        return fs.ruta_documento(self.carpeta, doc["sha256"], doc["extension"])

    # --- Consultas (solo lectura) ------------------------------------------------------

    def _filas(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [dict(r) for r in self._con.execute(sql, params)]

    def elementos(self) -> list[dict[str, Any]]:
        return self._filas("SELECT * FROM elemento ORDER BY codigo")

    def elemento(self, elemento_id: str) -> dict[str, Any] | None:
        return leer(self._con, "elemento", {"id": elemento_id})

    def propiedades(self, elemento_id: str) -> list[dict[str, Any]]:
        filas = self._filas(
            "SELECT p.*, d.nombre_original AS documento_nombre FROM propiedad p"
            " LEFT JOIN documento d ON d.id = p.documento_id"
            " WHERE p.elemento_id = ? ORDER BY p.clave",
            (elemento_id,),
        )
        for f in filas:
            f["valor"] = json.loads(f["valor"])
        return filas

    def documentos(self) -> list[dict[str, Any]]:
        return self._filas("SELECT * FROM documento ORDER BY incorporado, nombre_original")

    def decisiones(self, elemento_id: str | None = None) -> list[dict[str, Any]]:
        if elemento_id is None:
            return self._filas("SELECT * FROM decision ORDER BY fecha, rowid")
        # rowid desempata decisiones del mismo segundo (aprobar y reabrir seguidos).
        return self._filas(
            "SELECT * FROM decision WHERE elemento_id = ? ORDER BY fecha, rowid", (elemento_id,)
        )

    def pendientes(self, solo_abiertos: bool = True) -> list[dict[str, Any]]:
        sql = "SELECT * FROM pendiente"
        if solo_abiertos:
            sql += " WHERE estado = 'abierto'"
        return self._filas(sql + " ORDER BY creado")

    def cambios(self, limite: int | None = None) -> list[dict[str, Any]]:
        """Registro de cambios, el más reciente primero. Sin límite: se muestra entero."""
        if limite is None:
            return self._filas("SELECT * FROM cambio ORDER BY n DESC")
        return self._filas("SELECT * FROM cambio ORDER BY n DESC LIMIT ?", (limite,))

    def usos_de_documento(self, documento_id: str) -> list[dict[str, Any]]:
        """Qué valores del modelo citan este documento (trazabilidad inversa)."""
        return self._filas(
            "SELECT e.codigo, p.clave, p.localizador FROM propiedad p"
            " JOIN elemento e ON e.id = p.elemento_id WHERE p.documento_id = ?"
            " ORDER BY e.codigo, p.clave",
            (documento_id,),
        )

    # --- Mediciones, ofertas y presupuestos ---------------------------------------------

    #: Formatos que se pueden leer como medición. Se amplía con cada lector (Excel, PDF).
    #: BC3 se lee sin IA (exacto). PDF y Excel se leen con IA + comprobaciones (ADR-0013).
    FORMATOS_MEDICION = (".bc3", ".pdf", ".xlsx", ".xlsm")
    FORMATOS_CON_IA = (".pdf", ".xlsx", ".xlsm")

    def leer_medicion(
        self,
        documento_id: str,
        clase: str,
        proveedor: str | None = None,
        esperar: Callable[[Callable[[], Any]], Any] | None = None,
    ) -> tuple[str, list[str]]:
        """Lee un documento incorporado como medición/oferta/presupuesto y guarda sus partidas.

        Se lee la copia del almacén (la verificada por su huella), no el original.
        Devuelve (id de la medición, avisos del lector).

        `esperar` ejecuta la parte lenta (la llamada a la IA, que no toca la base de datos)
        mientras la interfaz sigue respondiendo; por defecto se ejecuta sin más.
        """
        doc = leer(self._con, "documento", {"id": documento_id})
        if doc is None:
            raise OrdenRechazada("Documento no incorporado.")
        if doc["extension"] not in self.FORMATOS_MEDICION:
            raise OrdenRechazada(
                f"Todavía no se pueden leer mediciones en formato «{doc['extension']}». "
                f"Formatos disponibles: {', '.join(self.FORMATOS_MEDICION)}."
            )
        previa = self._con.execute(
            "SELECT nombre FROM medicion WHERE documento_id = ?", (documento_id,)
        ).fetchone()
        if previa:
            # Antes de leer: así no se envía a la IA (ni se gasta suscripción) en balde.
            raise OrdenRechazada(
                f"«{previa['nombre']}» ya está leído. Quita esa medición si quieres volver a "
                "leerlo."
            )
        ruta = self.ruta_documento(documento_id)
        if doc["extension"] in self.FORMATOS_CON_IA:
            return self._leer_con_ia(doc, ruta, clase, proveedor, esperar or (lambda f: f()))
        try:
            leido = bc3.leer_bc3(ruta)
        except bc3.Bc3Error as exc:
            raise OrdenRechazada(f"«{doc['nombre_original']}»: {exc}") from exc
        resultado = bc3.leer_partidas(leido)
        ps = resultado.partidas
        avisos = leido.avisos + resultado.avisos
        orden = ImportarMedicion(
            documento_id=documento_id,
            titulo=doc["nombre_original"],
            clase=clase,
            proveedor=proveedor,
            lector=bc3.LECTOR,
            version_lector=bc3.VERSION_LECTOR,
            partidas=[
                PartidaNueva(
                    capitulo=[list(c) for c in p.capitulos],
                    codigo=p.codigo,
                    etiqueta=p.etiqueta,
                    unidad=p.unidad,
                    resumen=p.resumen,
                    texto=p.texto,
                    cantidad=p.cantidad,
                    precio=p.precio,
                    localizador=p.localizador,
                )
                for p in ps
            ],
            avisos=avisos,
            omitidas=resultado.omitidas,
        )
        self.ejecutar(orden)
        return orden.id, avisos

    def _leer_con_ia(
        self,
        doc: dict[str, Any],
        ruta: Path,
        clase: str,
        proveedor: str | None,
        esperar: Callable[[Callable[[], Any]], Any],
    ) -> tuple[str, list[str]]:
        avisos: list[str] = []
        imagenes: dict[int, Path] = {}
        temporal: Path | None = None
        if doc["extension"] == ".pdf":
            fuente: lectura_ia.Fuente = lectura_ia.FuentePdf(ruta)
            sin_texto = fuente.paginas_sin_texto
            if sin_texto:
                # Páginas escaneadas (todas o algunas): la IA las lee como imagen, pero no hay
                # texto con que comprobarlas: sus líneas quedan «a revisar».
                avisos.append(
                    f"Páginas sin texto (escaneadas): {', '.join(map(str, sin_texto))}. La IA "
                    "las lee como imagen; sus líneas no se pueden comprobar y quedan «a revisar»."
                )
                temporal = Path(tempfile.mkdtemp(prefix="traza-pdf-"))
                imagenes = {
                    n: renderizar_pagina(ruta, n, temporal / f"pagina_{n:03d}.png")
                    for n in sin_texto
                }
        else:
            fuente = lectura_ia.FuenteExcel(ruta)
            avisos += fuente.avisos
        texto = fuente.texto_para_ia()
        try:
            extraido = esperar(lambda: self.extractor_ia(texto, imagenes or None))
        except (claude_code.IaNoDisponible, claude_code.IaError) as exc:
            raise OrdenRechazada(f"«{doc['nombre_original']}»: {exc}") from exc
        finally:
            if temporal is not None:
                shutil.rmtree(temporal, ignore_errors=True)
        r = lectura_ia.comprobar(extraido, fuente)
        if r.proveedor and not proveedor:
            # Leído por la IA y no comprobado: se dice, no se guarda como dato.
            avisos.append(f"La IA identifica el proveedor como «{r.proveedor}» (sin comprobar).")
        avisos += r.avisos
        orden = ImportarMedicion(
            documento_id=doc["id"],
            titulo=doc["nombre_original"],
            clase=clase,
            proveedor=proveedor,
            lector=claude_code.PROVEEDOR,
            version_lector=claude_code.VERSION,
            partidas=r.partidas,
            avisos=avisos,
            total_documento=r.total_documento,
        )
        self.ejecutar(orden, autor="importacion")
        return orden.id, avisos

    # --- Obra: venta y coste objetivo (docs/modules/obra.md) -----------------------------

    def venta_contratada(self) -> dict[str, Any] | None:
        """La medición que es el presupuesto contratado de la obra (o None)."""
        fila = leer(self._con, "meta", {"clave": "venta_medicion"})
        if fila is None:
            return None
        return next((m for m in self.mediciones() if m["id"] == fila["valor"]), None)

    def fijar_venta_contratada(self, medicion_id: str) -> None:
        self.ejecutar(FijarVentaContratada(medicion_id))

    def importar_coste_objetivo(self, documento_id: str) -> coste_presto.CosteObjetivo:
        """Lee el Excel de coste objetivo de Presto (incorporado como documento) y lo guarda
        tal cual (orden ImportarCosteObjetivo; sustituye al anterior)."""
        doc = leer(self._con, "documento", {"id": documento_id})
        if doc is None:
            raise OrdenRechazada("Documento no incorporado.")
        if doc["extension"].lower() not in (".xlsx", ".xlsm"):
            raise OrdenRechazada(
                f"«{doc['nombre_original']}» no es un Excel (.xlsx): guárdalo desde Excel."
            )
        try:
            r = coste_presto.leer(self.ruta_documento(documento_id))
        except coste_presto.CosteNoReconocido as exc:
            raise OrdenRechazada(f"«{doc['nombre_original']}»: {exc}") from exc
        self.ejecutar(
            ImportarCosteObjetivo(
                documento_id,
                r.hoja,
                r.paquetes,
                [
                    {
                        "codigo": p.codigo,
                        "resumen": p.resumen,
                        "unidad": p.unidad,
                        "capitulo": p.capitulo,
                        "cantidad": p.cantidad,
                        "precio": p.precio,
                        "importe": p.importe,
                        "paquetes": p.paquetes,
                        "nota": p.nota,
                        "fila": p.fila,
                    }
                    for p in r.partidas
                ],
                r.avisos,
                coste_presto.LECTOR,
                coste_presto.VERSION,
            )
        )
        return r

    def coste_objetivo(self) -> dict[str, Any] | None:
        fila = leer(self._con, "coste_objetivo", {"id": 1})
        if fila is None:
            return None
        for clave in ("paquetes", "partidas", "avisos"):
            fila[clave] = json.loads(fila[clave])
        doc = leer(self._con, "documento", {"id": fila["documento_id"]})
        fila["documento_nombre"] = doc["nombre_original"] if doc else ""
        return fila

    def resumen_obra(self) -> calculo_obra.ResumenObra:
        venta = self.venta_contratada()
        return calculo_obra.resumir(
            self.partidas(venta["id"]) if venta is not None else None,
            self.coste_objetivo(),
            venta,
        )

    def quitar_venta_contratada(self) -> None:
        self.ejecutar(QuitarVentaContratada())

    # --- Obra, bloque 2a: coste real y previsión ----------------------------------------

    def facturas(self) -> list[dict[str, Any]]:
        return self._filas("SELECT * FROM factura ORDER BY paquete, fecha, proveedor, numero")

    def registrar_factura(self, **datos: Any) -> str:
        orden = RegistrarFactura(**datos)
        self.ejecutar(orden)
        return orden.id

    def quitar_factura(self, factura_id: str) -> None:
        self.ejecutar(QuitarFactura(factura_id))

    def paquetes_cerrados(self) -> set[str]:
        return {f["paquete"] for f in self._filas("SELECT paquete FROM paquete_cerrado")}

    def cerrar_paquete(self, paquete: str, cerrar: bool = True) -> None:
        self.ejecutar(CerrarPaquete(paquete, cerrar))

    def prevision(self) -> dict[str, Any] | None:
        return leer(self._con, "prevision", {"id": 1})

    def fijar_prevision(
        self, coste_total: float, certificacion_total: float, nota: str = ""
    ) -> None:
        self.ejecutar(FijarPrevision(coste_total, certificacion_total, nota))

    def certificado_a_origen(self) -> float | None:
        """Lo certificado a origen (bloque 2b: certificaciones). Hasta entonces, no consta."""
        return None

    def foto_obra(self) -> calculo_obra.Foto:
        return calculo_obra.foto(
            self.resumen_obra(),
            self.facturas(),
            self.paquetes_cerrados(),
            self.certificado_a_origen(),
            self.prevision(),
        )

    def mediciones(self) -> list[dict[str, Any]]:
        filas = self._filas(
            "SELECT m.*, d.nombre_original AS documento_nombre,"
            " (SELECT count(*) FROM partida p WHERE p.medicion_id = m.id) AS n_partidas"
            " FROM medicion m JOIN documento d ON d.id = m.documento_id ORDER BY m.leido"
        )
        for f in filas:
            f["avisos"] = json.loads(f["avisos"])
        return filas

    def partidas(self, medicion_id: str) -> list[dict[str, Any]]:
        filas = self._filas(
            "SELECT * FROM partida WHERE medicion_id = ? ORDER BY orden", (medicion_id,)
        )
        for f in filas:
            f["capitulo"] = json.loads(f["capitulo"])
            f["motivos"] = json.loads(f["motivos"])
            f["importe"] = (
                f["cantidad"] * f["precio"]
                if f["cantidad"] is not None and f["precio"] is not None
                else None
            )
        return filas

    def exportar_excel(self, destino: Path, medicion_ids: list[str] | None = None) -> Path:
        """El «Excel con todo» para hacer los pedidos en el ERP del usuario."""
        meds = [m for m in self.mediciones() if medicion_ids is None or m["id"] in medicion_ids]
        if not meds:
            raise OrdenRechazada("No hay mediciones leídas que exportar.")
        bloques = [(m, self.partidas(m["id"])) for m in meds]
        return exportar_partidas(Path(destino), self.nombre, bloques)

    # --- Ampliaciones y modificaciones ---------------------------------------------------

    def modificados(self, medicion_id: str | None = None) -> list[dict[str, Any]]:
        sql = (
            "SELECT o.*, d.nombre_original AS base_nombre,"
            " (SELECT count(*) FROM cambio_modificado c WHERE c.modificado_id = o.id)"
            " AS n_cambios"
            " FROM modificado o JOIN medicion m ON m.id = o.medicion_id"
            " JOIN documento d ON d.id = m.documento_id"
        )
        if medicion_id is None:
            return self._filas(sql + " ORDER BY o.creado, o.numero")
        return self._filas(sql + " WHERE o.medicion_id = ? ORDER BY o.numero", (medicion_id,))

    def modificado(self, modificado_id: str) -> dict[str, Any] | None:
        return next((m for m in self.modificados() if m["id"] == modificado_id), None)

    def ofertas_utilizables(self) -> list[dict[str, Any]]:
        """Líneas de ofertas leídas que pueden ser partida nueva: fiables y con precio."""
        filas = self._filas(
            "SELECT p.*, d.nombre_original AS documento_nombre, m.proveedor"
            " FROM partida p JOIN medicion m ON m.id = p.medicion_id"
            " JOIN documento d ON d.id = m.documento_id"
            " WHERE m.clase = 'oferta' AND p.precio IS NOT NULL"
            " AND p.estado IN ('exacta','comprobada','confirmada')"
            " ORDER BY d.nombre_original, p.orden"
        )
        for f in filas:
            f["capitulo"] = json.loads(f["capitulo"])
        return filas

    def resumen_modificado(self, modificado_id: str) -> calculo_mod.Resumen:
        mod = leer(self._con, "modificado", {"id": modificado_id})
        if mod is None:
            raise OrdenRechazada("Ese modificado no existe.")
        cambios = self._filas(
            "SELECT * FROM cambio_modificado WHERE modificado_id = ? ORDER BY orden",
            (modificado_id,),
        )
        nuevas = {}
        for c in cambios:
            if c["tipo"] == "nueva":
                p = leer(self._con, "partida", {"id": c["partida_id"]})
                nuevas[c["partida_id"]] = p
        meds = self.mediciones()
        nombres = {m["id"]: m["documento_nombre"] for m in meds}
        base = next(m for m in meds if m["id"] == mod["medicion_id"])
        return calculo_mod.calcular(
            self.partidas(mod["medicion_id"]), cambios, nuevas, nombres, base["omitidas"]
        )

    def exportar_modificado_excel(self, modificado_id: str, destino: Path) -> Path:
        mod = self.modificado(modificado_id)
        if mod is None:
            raise OrdenRechazada("Ese modificado no existe.")
        r = self.resumen_modificado(modificado_id)
        if not r.cambios:
            raise OrdenRechazada("El modificado no tiene cambios que exportar.")
        return exportar_modificado(Path(destino), self.nombre, mod, r)

    def exportar_modificado_bc3(self, modificado_id: str, destino: Path) -> tuple[Path, list[str]]:
        """BC3 del presupuesto completo actualizado (decisión del usuario, 06-11-2026).

        Base leída de un BC3: se parte del fichero original (conserva descompuestos, textos y
        todo lo que TRAZA no interpreta). Base leída de PDF o Excel: se genera con lo leído.
        En ambos casos el fichero se relee y se compara antes de guardarlo.
        """
        mod = self.modificado(modificado_id)
        if mod is None:
            raise OrdenRechazada("Ese modificado no existe.")
        r = self.resumen_modificado(modificado_id)
        if not r.cambios:
            raise OrdenRechazada("El modificado no tiene cambios que exportar.")
        base = next(m for m in self.mediciones() if m["id"] == mod["medicion_id"])
        destino = Path(destino)
        if destino.suffix.lower() != ".bc3":
            destino = destino.with_name(destino.name + ".bc3")
        nuevas = [
            PartidaBc3(x.codigo or "", x.unidad, x.resumen, None, x.cantidad_modificada, x.precio)
            for x in r.cambios
            if x.tipo == "nueva"
        ]
        try:
            if base["lector"] == bc3.LECTOR:
                partidas = {p["id"]: p for p in self.partidas(base["id"])}
                variaciones = [
                    bc3_modificar.Variacion(
                        localizador=partidas[x.partida_id]["localizador"],
                        codigo=x.codigo or "",
                        cantidad_contrato=x.cantidad_contrato,
                        cantidad_nueva=x.cantidad_modificada,
                        precio=x.precio,
                        capitulos=[c[0] for c in x.capitulo],
                        comentario=f"{x.motivo}. {x.justificacion}",
                    )
                    for x in r.cambios
                    if x.tipo != "nueva"
                ]
                ruta, avisos = bc3_modificar.actualizar(
                    self.ruta_documento(base["documento_id"]),
                    destino,
                    mod["numero"],
                    variaciones,
                    nuevas,
                )
            else:
                ruta, avisos = self._bc3_generado(mod, r, destino, nuevas)
                if r.omitidas_base:
                    # Partiendo del original, lo omitido sigue en el fichero; generándolo, no.
                    avisos.append(
                        f"El BC3 generado NO incluye {r.omitidas_base} línea(s) de la base que "
                        "el lector no pudo convertir en partida."
                    )
        except (bc3_modificar.Bc3ModificarError, Bc3EscrituraError, bc3.Bc3Error) as exc:
            raise OrdenRechazada(str(exc)) from exc
        if r.a_revisar_base:
            avisos.append(
                f"{r.a_revisar_base} partida(s) de la base están «a revisar»: se escriben con "
                "lo leído, sin comprobar."
            )
        return ruta, avisos

    def _bc3_generado(self, mod, r, destino: Path, nuevas) -> tuple[Path, list[str]]:
        """Base que no es BC3 (leída de PDF o Excel): presupuesto generado con lo leído."""
        numero = mod["numero"]
        base = [
            PartidaBc3(x.codigo or "", x.unidad, x.resumen, None, x.cantidad_modificada, x.precio)
            for x in r.lineas
            if x.tipo != "nueva"
        ]
        # Códigos: primero se reservan los que ya son válidos y únicos; después se dan códigos
        # nuevos a los demás (sin código, repetidos, de más de 20 caracteres o con caracteres
        # reservados), y por último a capítulos y raíz, sin chocar con ninguno. Cada cambio de
        # un código que sí existía se avisa (revisión 06-11-2026: antes era en silencio y un
        # código «C01» de la base chocaba con el del capítulo).
        usados: set[str] = set()
        pendientes: list[tuple[PartidaBc3, str]] = []
        for i, p in enumerate(base, start=1):
            pendientes.append((p, f"P{i:04d}"))
        for k, p in enumerate(nuevas, start=1):
            pendientes.append((p, f"MOD{numero}.{k}"))
        sin_codigo = 0
        cambiados: list[str] = []
        validos: set[int] = set()
        for i, (p, _) in enumerate(pendientes):
            if codigo_valido(p.codigo) and p.codigo not in usados:
                usados.add(p.codigo)
                validos.add(i)
        for i, (p, alternativa) in enumerate(pendientes):
            if i in validos:
                continue
            nuevo = _codigo_libre(alternativa, usados)
            if p.codigo.strip():
                cambiados.append(f"«{p.codigo}» → «{nuevo}»")
            else:
                sin_codigo += 1
            p.codigo = nuevo
        avisos_codigos = []
        if cambiados:
            avisos_codigos.append(
                "Códigos repetidos o no válidos en BC3 que se escriben con otro código: "
                + ", ".join(cambiados)
                + "."
            )
        if sin_codigo:
            avisos_codigos.append(f"{sin_codigo} partida(s) sin código reciben P0001, P0002…")

        raiz = CapituloBc3(_codigo_libre("OBRA", usados), f"{self.nombre} - modificado nº {numero}")
        capitulos: dict[str, CapituloBc3] = {}
        lineas_base = [x for x in r.lineas if x.tipo != "nueva"]
        for x, p in zip(lineas_base, base, strict=True):
            nombre = " / ".join(c[0] for c in x.capitulo) or "Sin capítulo"
            if nombre not in capitulos:
                codigo = _codigo_libre(f"C{len(capitulos) + 1:02d}", usados)
                capitulos[nombre] = CapituloBc3(codigo, nombre)
                raiz.capitulos.append(capitulos[nombre])
            capitulos[nombre].partidas.append(p)
        if nuevas:
            cap = CapituloBc3(
                _codigo_libre(f"MOD{numero}", usados),
                f"Modificado nº {numero} - partidas nuevas",
            )
            cap.partidas.extend(nuevas)
            raiz.capitulos.append(cap)
        ruta, avisos = escribir_bc3(
            destino, raiz, propiedad=self.nombre, comentario=f"Modificado nº {numero}"
        )
        avisos[:0] = [
            "La base se leyó de PDF o Excel: el BC3 se ha generado con lo leído (capítulos con "
            "códigos C01, C02…; sin descompuestos ni textos originales).",
            *avisos_codigos,
        ]
        return ruta, avisos

    # --- Planos: niveles, espacios y obstáculos (Etapa 3) --------------------------------

    def plano_dxf(
        self, documento_id: str, esperar: Callable[[Callable], Any] | None = None
    ) -> dxf.PlanoDxf:
        """Lo leído de un DXF del proyecto. El documento no cambia (almacén de solo lectura),
        así que se lee una vez por sesión.

        `esperar` permite a la interfaz leer el fichero en otro hilo (un DXF grande tarda):
        solo la lectura del fichero, que no toca la base de datos (SQLite no admite usar la
        conexión desde otro hilo)."""
        if documento_id not in self._planos_dxf:
            doc = leer(self._con, "documento", {"id": documento_id})
            if doc is None:
                raise OrdenRechazada("Documento no incorporado.")
            if doc["extension"].lower() != ".dxf":
                raise OrdenRechazada(f"«{doc['nombre_original']}» no es un DXF.")
            ruta = self.ruta_documento(documento_id)
            esperar = esperar or (lambda f: f())
            try:
                self._planos_dxf[documento_id] = esperar(lambda: dxf.leer_dxf(ruta))
            except dxf.DxfError as exc:
                raise OrdenRechazada(f"«{doc['nombre_original']}»: {exc}") from exc
        return self._planos_dxf[documento_id]

    def leer_plano(
        self,
        documento_id: str,
        unidad: str,
        capas_espacios: list[str],
        capas_obstaculos: list[str],
        capas_textos: list[str] | None = None,
    ) -> str:
        """Registra cómo se lee un DXF. Las capas tienen que existir en el dibujo."""
        plano = self.plano_dxf(documento_id)
        _capas_existen(plano, [*capas_espacios, *capas_obstaculos, *(capas_textos or [])])
        orden = LeerPlano(
            documento_id,
            unidad,
            _nombres_del_dxf(plano, capas_espacios),
            _nombres_del_dxf(plano, capas_obstaculos),
            _nombres_del_dxf(plano, capas_textos),
            dxf.LECTOR,
            dxf.VERSION,
        )
        self.ejecutar(orden)
        return orden.id

    def cambiar_plano(
        self,
        plano_id: str,
        unidad: str,
        capas_espacios: list[str],
        capas_obstaculos: list[str],
        capas_textos: list[str] | None = None,
    ) -> None:
        fila = self.plano(plano_id)
        dibujo = self.plano_dxf(fila["documento_id"])
        _capas_existen(dibujo, [*capas_espacios, *capas_obstaculos, *(capas_textos or [])])
        self.ejecutar(
            CambiarPlano(
                plano_id,
                unidad,
                _nombres_del_dxf(dibujo, capas_espacios),
                _nombres_del_dxf(dibujo, capas_obstaculos),
                _nombres_del_dxf(dibujo, capas_textos),
            )
        )

    def planos(self, sustituidos: bool = False) -> list[dict[str, Any]]:
        filas = self._filas(
            "SELECT p.*, d.nombre_original AS documento_nombre FROM plano p"
            " JOIN documento d ON d.id = p.documento_id"
            # Un plano sustituido por su revisión ya no se trabaja (sus elementos y redes
            # pasaron al revisado); sigue en la base por la historia (V10).
            + ("" if sustituidos else " WHERE p.sustituido_por IS NULL")
            + " ORDER BY p.leido"
        )
        for f in filas:
            for clave in ("capas_espacios", "capas_obstaculos", "capas_textos", "descartados"):
                f[clave] = json.loads(f[clave])
        return filas

    def plano(self, plano_id: str) -> dict[str, Any]:
        fila = next((p for p in self.planos() if p["id"] == plano_id), None)
        if fila is None:
            raise OrdenRechazada("Ese plano no está leído en el proyecto.")
        return fila

    def propuestas(self, plano_id: str) -> list[calculo_planos.Propuesta]:
        p = self.plano(plano_id)
        confirmados = {
            r["handle"]
            for r in self._filas("SELECT handle FROM geometria WHERE plano_id = ?", (plano_id,))
        }
        return calculo_planos.propuestas(
            self.plano_dxf(p["documento_id"]),
            p["unidad"],
            p["capas_espacios"],
            p["capas_obstaculos"],
            p["capas_textos"],
            confirmados,
            set(p["descartados"]),
        )

    def confirmar_contorno(
        self,
        plano_id: str,
        handle: str,
        nivel_id: str,
        nombre: str | None = None,
        texto_handle: str | None = None,
        altura: float | None = None,
        cota_inferior: float | None = None,
    ) -> str:
        """Confirma una propuesta como espacio u obstáculo (según su capa). Con
        `texto_handle`, el nombre es ese texto del plano y lo cita."""
        p = self.plano(plano_id)
        propuesta = next((x for x in self.propuestas(plano_id) if x.handle == handle), None)
        if propuesta is None:
            raise OrdenRechazada(
                "Ese contorno no está entre las propuestas (ya confirmado, descartado o fuera "
                "de las capas elegidas)."
            )
        procedencia = None
        if texto_handle is not None:
            texto = next((t for t in propuesta.textos if t.handle == texto_handle), None)
            if texto is None:
                raise OrdenRechazada("Ese texto no está dentro del contorno.")
            nombre = texto.texto
            procedencia = Procedencia(
                Origen.DOCUMENTO,
                documento_id=p["documento_id"],
                localizador=f"texto {texto.handle} (capa «{texto.capa}»)",
            )
        orden = ConfirmarContorno(
            propuesta.rol,
            plano_id,
            handle,
            propuesta.capa,
            nivel_id,
            tuple((v.x, v.y, v.bulge) for v in propuesta.contorno.vertices),
            nombre,
            procedencia,
            altura,
            cota_inferior,
        )
        self.ejecutar(orden)
        return orden.id

    def descartar_propuesta(self, plano_id: str, handle: str) -> None:
        """Descarta una propuesta que existe (la orden sola no conoce el DXF)."""
        if handle not in {x.handle for x in self.propuestas(plano_id)}:
            raise OrdenRechazada("Ese contorno no está entre las propuestas del plano.")
        self.ejecutar(DescartarPropuesta(plano_id, handle))

    def comparar_plano_revisado(
        self, plano_id: str, documento_id: str
    ) -> tuple[calculo_planos.Emparejamiento, list[str]]:
        """Qué pasa con cada espacio u obstáculo si el plano se sustituye por el revisado
        (no escribe nada). Devuelve el emparejamiento y los descartes que se conservan."""
        p = self.plano(plano_id)
        revisado = self.plano_dxf(documento_id)
        _capas_existen(revisado, [*p["capas_espacios"], *p["capas_obstaculos"], *p["capas_textos"]])
        nuevas = calculo_planos.propuestas(
            revisado,
            p["unidad"],
            p["capas_espacios"],
            p["capas_obstaculos"],
            p["capas_textos"],
            set(),
            set(),
        )
        confirmados = [
            calculo_planos.Confirmado(
                f["id"],
                f["codigo"],
                f["nombre"] or "",
                tipo_elemento,
                f["contorno"],
                f["estado"] == Estado.APROBADO,
            )
            for tipo_elemento in ("espacio", "obstaculo")
            for f in self.contornos_confirmados(tipo_elemento)
            if f["plano_id"] == plano_id
        ]
        r = calculo_planos.emparejar(confirmados, nuevas)
        # Los descartes (contornos que el usuario no quiere, p. ej. pilares) se buscan igual
        # en el revisado, para no tener que descartarlos otra vez.
        anterior = calculo_planos.propuestas(
            self.plano_dxf(p["documento_id"]),
            p["unidad"],
            p["capas_espacios"],
            p["capas_obstaculos"],
            p["capas_textos"],
            set(),
            set(),
        )
        descartes = [
            calculo_planos.Confirmado(x.handle, "", "", x.rol, x.contorno)
            for x in anterior
            if x.handle in set(p["descartados"])
        ]
        d = calculo_planos.emparejar(descartes, r.nuevas)
        siguen = sorted(x.despues.handle for x in [*d.iguales, *d.cambiados])
        r.nuevas = [x for x in r.nuevas if x.handle not in set(siguen)]
        # Las redes de aire pasan al plano revisado: se avisa antes si les falta algo.
        capas = {c.casefold() for c in revisado.capas}
        bloques = {b.nombre.casefold() for b in revisado.bloques}
        for red in self.redes():
            if red["plano_id"] != plano_id:
                continue
            faltan = [f"la capa «{red['capa_ejes']}»"] * (red["capa_ejes"].casefold() not in capas)
            faltan += [
                f"el bloque «{b}»"
                for b in [*red["bloques_terminales"], red["bloque_equipo"] or ""]
                if b and b.casefold() not in bloques
            ]
            if faltan:
                r.avisos.append(
                    f"La red «{red['nombre']}» no se podrá calcular: el revisado no tiene "
                    + ", ".join(faltan)
                    + "."
                )
        return r, siguen

    def revisar_plano(self, plano_id: str, documento_id: str) -> calculo_planos.Emparejamiento:
        """Sustituye el plano por el revisado (orden RevisarPlano): lo que depende se
        recalcula y queda marcado para revisar."""
        r, descartes = self.comparar_plano_revisado(plano_id, documento_id)
        if r.aprobados_que_cambian:
            raise OrdenRechazada(
                "Están aprobados y cambian o desaparecen en el plano revisado: "
                + ", ".join(f"«{c.rotulo}»" for c in r.aprobados_que_cambian)
                + ". Reábrelos indicando el motivo antes de revisar el plano."
            )
        if r.desaparecidos and not (r.iguales or r.cambiados):
            raise OrdenRechazada(
                "Ningún espacio u obstáculo del plano anterior coincide con el revisado: "
                "¿está el dibujo desplazado (otro punto base) o en otra unidad?"
            )
        self.ejecutar(
            RevisarPlano(
                plano_id,
                documento_id,
                tuple(
                    (
                        x.antes.elemento_id,
                        x.despues.handle,
                        x.despues.capa,
                        tuple((v.x, v.y, v.bulge) for v in x.despues.contorno.vertices),
                    )
                    for x in [*r.iguales, *r.cambiados]
                ),
                tuple(c.elemento_id for c in r.desaparecidos),
                tuple(descartes),
                dxf.LECTOR,
                dxf.VERSION,
            )
        )
        return r

    def _valores(self, tipos_elemento: tuple[str, ...]) -> dict[str, dict[str, Any]]:
        marcas = ",".join("?" * len(tipos_elemento))
        valores: dict[str, dict[str, Any]] = {}
        for r in self._filas(
            "SELECT p.elemento_id, p.clave, p.valor FROM propiedad p"
            f" JOIN elemento e ON e.id = p.elemento_id WHERE e.tipo IN ({marcas})",
            tipos_elemento,
        ):
            valores.setdefault(r["elemento_id"], {})[r["clave"]] = json.loads(r["valor"])
        return valores

    def niveles(self) -> list[dict[str, Any]]:
        v = self._valores(("nivel",))
        filas = self._filas("SELECT * FROM elemento WHERE tipo = 'nivel' ORDER BY codigo")
        for f in filas:
            f.update({k: v.get(f["id"], {}).get(k) for k in ("nombre", "cota", "altura_libre")})
        return sorted(filas, key=lambda f: (f["cota"] is None, f["cota"], f["codigo"]))

    def contornos_confirmados(self, tipo_elemento: str) -> list[dict[str, Any]]:
        """Espacios u obstáculos con su nivel, geometría y alturas.

        Altura de un espacio (decisión del usuario): la suya si consta; si no, la del nivel
        («heredada»). Con altura mínima y máxima (cubierta inclinada), las dos.
        """
        v = self._valores((tipo_elemento, "nivel"))
        filas = self._filas(
            "SELECT e.*, g.plano_id, g.handle, g.capa, g.contorno, n.codigo AS nivel_codigo"
            " FROM elemento e JOIN geometria g ON g.elemento_id = e.id"
            " LEFT JOIN elemento n ON n.id = e.padre_id"
            " WHERE e.tipo = ? ORDER BY e.codigo",
            (tipo_elemento,),
        )
        for f in filas:
            propias = v.get(f["id"], {})
            nivel = v.get(f["padre_id"], {})
            f["nivel_nombre"] = nivel.get("nombre")
            f["contorno"] = Contorno(tuple(Vertice(*xyb) for xyb in json.loads(f["contorno"])))
            for k in (
                "nombre",
                "superficie",
                "perimetro",
                "altura_minima",
                "altura_maxima",
                "cota_inferior",
            ):
                f[k] = propias.get(k)
            clave = "altura_libre" if tipo_elemento == "espacio" else "altura"
            inclinada = f["altura_minima"] is not None or f["altura_maxima"] is not None
            if propias.get(clave) is not None:
                f["altura"], f["altura_origen"] = propias[clave], "propia"
            elif inclinada:
                # Cubierta inclinada: no hay UNA altura; mínima y máxima van en sus columnas
                # (revisión 07-11-2026: salía la del nivel junto a la mínima y la máxima).
                f["altura"], f["altura_origen"] = None, "inclinada"
            elif tipo_elemento == "obstaculo" and (f["cota_inferior"] or 0) > 0:
                # Un obstáculo que no arranca del suelo no ocupa toda la altura del nivel:
                # heredarla daría una cara superior por encima del techo. No consta.
                f["altura"], f["altura_origen"] = None, None
            elif nivel.get("altura_libre") is not None:
                f["altura"], f["altura_origen"] = nivel["altura_libre"], "del nivel"
            else:
                f["altura"], f["altura_origen"] = None, None
        return filas

    def espacios(self) -> list[dict[str, Any]]:
        return self.contornos_confirmados("espacio")

    def obstaculos(self) -> list[dict[str, Any]]:
        return self.contornos_confirmados("obstaculo")

    def bloques_por_espacio(self, plano_id: str) -> calculo_planos.Bloques:
        p = self.plano(plano_id)
        espacios = [
            calculo_planos.EspacioConfirmado(e["id"], e["codigo"], e["nombre"] or "", e["contorno"])
            for e in self.espacios()
            if e["plano_id"] == plano_id
        ]
        return calculo_planos.bloques_por_espacio(
            self.plano_dxf(p["documento_id"]), p["unidad"], espacios
        )

    def longitudes_por_capa(self, plano_id: str) -> list[calculo_planos.FilaLongitud]:
        p = self.plano(plano_id)
        return calculo_planos.longitudes_por_capa(self.plano_dxf(p["documento_id"]), p["unidad"])

    def exportar_plano_excel(self, plano_id: str, destino: Path) -> Path:
        p = self.plano(plano_id)
        dxf_leido = self.plano_dxf(p["documento_id"])
        return exportar_plano(
            Path(destino),
            self.nombre,
            p,
            [e for e in self.espacios() if e["plano_id"] == plano_id],
            [o for o in self.obstaculos() if o["plano_id"] == plano_id],
            self.bloques_por_espacio(plano_id),
            self.longitudes_por_capa(plano_id),
            dxf_leido.avisos,
        )

    # --- Cargas y ventilación ----------------------------------------------------------

    def estaciones(
        self, documento_id: str, esperar: Callable[[Callable], Any] | None = None
    ) -> list[clima_idae.EstacionIdae]:
        """Estaciones de la guía del IDAE incorporada como documento (se lee una vez por
        sesión). `esperar`: como en `plano_dxf`, para leer el PDF en otro hilo."""
        if documento_id not in self._guias:
            ruta = self.ruta_documento(documento_id)
            if ruta.suffix.lower() != ".pdf":
                raise OrdenRechazada("La guía del IDAE es un PDF.")
            esperar = esperar or (lambda f: f())
            try:
                self._guias[documento_id] = esperar(lambda: self.lector_guia(ruta))
            except clima_idae.GuiaNoReconocida as exc:
                raise OrdenRechazada(str(exc)) from exc
            if not self._guias[documento_id]:
                del self._guias[documento_id]
                raise OrdenRechazada(
                    "Ese PDF no contiene fichas de estación de la guía del IDAE «Condiciones "
                    "climáticas exteriores de proyecto»."
                )
        return self._guias[documento_id]

    def guia_leida(self, documento_id: str) -> bool:
        """Si la guía ya se ha leído en esta sesión (leerla tarda unos segundos)."""
        return documento_id in self._guias

    def estacion(self, documento_id: str, pagina: int) -> clima_idae.EstacionIdae:
        for e in self.estaciones(documento_id):
            if e.pagina == pagina:
                return e
        raise OrdenRechazada(f"La página {pagina} de la guía no es la ficha de una estación.")

    def cargas_config(self) -> dict[str, Any] | None:
        return leer(self._con, "cargas_proyecto", {"id": 1})

    def fijar_cargas(self, **datos: Any) -> None:
        """Clima y obra (ver FijarCargasProyecto). Comprueba antes que la página es una
        estación de la guía."""
        self.estacion(datos["guia_documento_id"], datos["estacion_pagina"])
        self.ejecutar(FijarCargasProyecto(**datos))

    def datos_cargas_espacios(self) -> dict[str, dict[str, Any]]:
        filas = self._filas("SELECT * FROM cargas_espacio")
        return {
            f["elemento_id"]: {
                "uso": f["uso"],
                "ajustes": json.loads(f["ajustes"]),
                "fachadas": json.loads(f["fachadas"]),
            }
            for f in filas
        }

    def fijar_cargas_espacio(
        self,
        espacio_id: str,
        uso: str,
        ajustes: dict[str, Any] | None = None,
        fachadas: dict[str, bool] | None = None,
    ) -> None:
        self.ejecutar(FijarCargasEspacio(espacio_id, uso, ajustes or {}, fachadas or {}))

    def calcular_cargas(self) -> calculo_cargas.ResultadoCargas:
        config = self.cargas_config()
        if config is None:
            raise OrdenRechazada(
                "Faltan el clima y la obra: elige la guía del IDAE, la estación, la provincia "
                "y la altitud de la obra."
            )
        return calculo_cargas.calcular(
            config,
            self.estacion(config["guia_documento_id"], config["estacion_pagina"]),
            self.espacios(),
            self.niveles(),
            self.datos_cargas_espacios(),
        )

    def exportar_cargas_excel(self, destino: Path) -> Path:
        return informe_cargas.exportar_excel(Path(destino), self.nombre, self.calcular_cargas())

    def exportar_cargas_pdf(self, destino: Path) -> Path:
        return informe_cargas.exportar_pdf(Path(destino), self.nombre, self.calcular_cargas())

    # --- Redes de aire -------------------------------------------------------------------

    def redes(self) -> list[dict[str, Any]]:
        filas = self._filas("SELECT * FROM red_aire ORDER BY nombre")
        for f in filas:
            f["bloques_terminales"] = json.loads(f["bloques_terminales"])
        return filas

    def red(self, red_id: str) -> dict[str, Any]:
        for r in self.redes():
            if r["id"] == red_id:
                return r
        raise OrdenRechazada("Esa red no existe.")

    def definir_red(self, **datos: Any) -> str:
        """Crea o cambia una red (`id` para cambiarla). Comprueba antes contra el DXF que la
        capa de ejes y los bloques existen (la orden no lee ficheros)."""
        p = self.plano(datos["plano_id"])
        leido = self.plano_dxf(p["documento_id"])
        capas = {c.casefold(): c for c in leido.capas}
        if datos["capa_ejes"].casefold() not in capas:
            raise OrdenRechazada(f"El plano no tiene la capa «{datos['capa_ejes']}».")
        nombres = {b.nombre.casefold() for b in leido.bloques}
        for b in [*datos["bloques_terminales"], datos.get("bloque_equipo") or ""]:
            if b and b.casefold() not in nombres:
                raise OrdenRechazada(f"El plano no tiene ningún bloque «{b}».")
        orden = DefinirRed(**datos)
        self.ejecutar(orden)
        return orden.id

    def borrar_red(self, red_id: str) -> None:
        self.ejecutar(BorrarRed(red_id))

    def calcular_red(self, red_id: str) -> calculo_redes.ResultadoRedAire:
        red = self.red(red_id)
        p = self.plano(red["plano_id"])
        cargas, aviso = None, None
        try:
            cargas = self.calcular_cargas()
        except OrdenRechazada as exc:
            aviso = f"Sin cargas ({exc}): solo valen los caudales del atributo CAUDAL."
        r = calculo_redes.calcular(
            red, self.plano_dxf(p["documento_id"]), p["unidad"], self.espacios(), cargas
        )
        if aviso:
            r = calculo_redes.ResultadoRedAire(
                r.red, r.terminales, r.topologia, r.calculo, (aviso, *r.avisos), r.medicion
            )
        return r

    def exportar_red_autocad(self, red_id: str, destino: Path) -> tuple[Path, Path]:
        """DXF R2013 y LISP de la red, en las unidades y coordenadas de su plano: el DXF para
        abrirlo o superponerlo; el LISP para dibujarla dentro del plano abierto."""
        r = self.calcular_red(red_id)
        if r.calculo is None:
            raise OrdenRechazada(
                "La red no se ha podido calcular: revisa los avisos antes de exportarla."
            )
        unidad = self.plano(r.red["plano_id"])["unidad"]
        destino = Path(destino)
        try:
            dxf_ruta = salida_autocad.escribir_dxf(destino, r, unidad)
            lsp_ruta = salida_autocad.escribir_lisp(dxf_ruta.with_suffix(".lsp"), r, unidad)
        except PermissionError as exc:
            # En Windows, un fichero abierto en AutoCAD no se puede sobrescribir.
            raise OrdenRechazada(
                f"No se puede escribir «{Path(exc.filename or destino).name}»: ¿está abierto en "
                "AutoCAD? Ciérralo o elige otro nombre."
            ) from exc
        return dxf_ruta, lsp_ruta

    def exportar_red_excel(self, red_id: str, destino: Path) -> Path:
        return informe_redes.exportar_excel(Path(destino), self.nombre, self.calcular_red(red_id))

    # --- Sistemas hidráulicos (Etapa 7, docs/modules/hidronica.md) ----------------------
    def sistemas_hidraulicos(self) -> list[dict[str, Any]]:
        filas = self._filas("SELECT * FROM sistema_hidraulico ORDER BY nombre")
        for f in filas:
            f["circuitos"] = json.loads(f["circuitos"])
        return filas

    def sistema_hidraulico(self, sistema_id: str) -> dict[str, Any]:
        for s in self.sistemas_hidraulicos():
            if s["id"] == sistema_id:
                return s
        raise OrdenRechazada("Ese sistema no existe.")

    def definir_sistema_hidraulico(self, **datos: Any) -> str:
        orden = DefinirSistemaHidraulico(**datos)
        self.ejecutar(orden)
        return orden.id

    def borrar_sistema_hidraulico(self, sistema_id: str) -> None:
        self.ejecutar(BorrarSistemaHidraulico(sistema_id))

    def calcular_sistema_hidraulico(self, sistema_id: str) -> calculo_hidronica.ResultadoSistema:
        """Las potencias salen de las cargas: sin cargas no hay sistema que dimensionar."""
        sistema = self.sistema_hidraulico(sistema_id)
        cargas = self.calcular_cargas()
        try:
            return calculo_hidronica.calcular(sistema, cargas)
        except ValueError as exc:
            raise OrdenRechazada(str(exc)) from exc

    # --- Estado de los pasos (docs/modules/flujo.md) ------------------------------------
    def estado_paso(self, paso: str) -> flujo.EstadoPaso:
        return flujo.estado(self, paso)

    def dar_por_revisado(self, paso: str) -> None:
        self.ejecutar(DarPorRevisado(paso))

    # --- Subcuadros de clima (Etapa 8, docs/modules/electricidad.md) -------------------
    def subcuadros(self) -> list[dict[str, Any]]:
        filas = self._filas("SELECT * FROM subcuadro ORDER BY nombre")
        for f in filas:
            f["salidas"] = json.loads(f["salidas"])
        return filas

    def subcuadro(self, subcuadro_id: str) -> dict[str, Any]:
        for s in self.subcuadros():
            if s["id"] == subcuadro_id:
                return s
        raise OrdenRechazada("Ese subcuadro no existe.")

    def definir_subcuadro(self, **datos: Any) -> str:
        orden = DefinirSubcuadro(**datos)
        self.ejecutar(orden)
        return orden.id

    def borrar_subcuadro(self, subcuadro_id: str) -> None:
        self.ejecutar(BorrarSubcuadro(subcuadro_id))

    def calcular_subcuadro(self, subcuadro_id: str):
        try:
            return calculo_subcuadros.calcular(self.subcuadro(subcuadro_id))
        except ValueError as exc:
            raise OrdenRechazada(str(exc)) from exc

    def salidas_propuestas(self) -> list[dict[str, Any]]:
        """Salidas de los equipos ya dimensionados (sistemas hidráulicos y redes de aire)
        que se pueden calcular; los que no, se omiten."""
        sistemas, redes = [], []
        for s in self.sistemas_hidraulicos():
            try:
                sistemas.append(self.calcular_sistema_hidraulico(s["id"]))
            except OrdenRechazada:
                continue
        for r in self.redes():
            try:
                redes.append(self.calcular_red(r["id"]))
            except OrdenRechazada:
                continue
        return calculo_subcuadros.propuestas(sistemas, redes)

    def exportar_unifilar(self, subcuadro_id: str, destino: Path) -> Path:
        r = self.calcular_subcuadro(subcuadro_id)
        try:
            return unifilar_dxf.escribir_unifilar(
                Path(destino), self.nombre, r, f"{subcuadro_id}:unifilar"
            )
        except PermissionError as exc:
            raise OrdenRechazada(
                f"No se puede escribir «{exc.filename or destino}»: ¿está abierto en AutoCAD? "
                "Ciérralo o elige otro nombre."
            ) from exc

    def exportar_esquema_hidraulico(self, sistema_id: str, destino: Path) -> Path:
        """Esquema de principio en DXF R2013 (docs/modules/hidronica.md)."""
        r = self.calcular_sistema_hidraulico(sistema_id)
        try:
            return esquema_hidraulico_dxf.escribir_esquema(Path(destino), self.nombre, r)
        except ValueError as exc:
            raise OrdenRechazada(str(exc)) from exc
        except PermissionError as exc:
            raise OrdenRechazada(
                f"No se puede escribir «{exc.filename or destino}»: ¿está abierto en AutoCAD? "
                "Ciérralo o elige otro nombre."
            ) from exc

    def exportar_sistema_hidraulico_excel(self, sistema_id: str, destino: Path) -> Path:
        r = self.calcular_sistema_hidraulico(sistema_id)
        try:
            return informe_hidronica.exportar_excel(Path(destino), self.nombre, r)
        except PermissionError as exc:
            raise OrdenRechazada(
                f"No se puede escribir «{exc.filename or destino}»: ¿está abierto en Excel? "
                "Ciérralo o elige otro nombre."
            ) from exc

    # --- Entregables (docs/modules/flujo.md, bloque 2) ---------------------------------

    def datos_memoria(self) -> memoria.DatosMemoria:
        """Lo que entra en la justificación de cálculos: cada cálculo que se puede hacer; lo
        que no, se dice (nunca se omite en silencio). Cualquier error de un cálculo, no solo
        un rechazo, se apunta y no impide el resto (revisión 09-11-2026)."""
        d = memoria.DatosMemoria(
            self.nombre, ENCARGOS.get(self.encargo, self.encargo), date.today()
        )

        def intentar(rotulo: str, funcion):
            try:
                return funcion()
            except OrdenRechazada as exc:
                d.sin_calcular.append(f"{rotulo}: {exc}")
            except Exception as exc:  # noqa: BLE001 — se dice en el documento
                d.sin_calcular.append(f"{rotulo}: {type(exc).__name__}: {exc}")
            return None

        hay_algo = bool(self.redes() or self.sistemas_hidraulicos() or self.subcuadros())
        if self.cargas_config() is not None and self.espacios():
            d.cargas = intentar("Cargas", self.calcular_cargas)
        elif self.espacios() or hay_algo:
            falta = "el clima y la obra" if self.espacios() else "espacios confirmados"
            d.sin_calcular.append(f"Cargas: falta {falta}")
        for f in self.redes():
            r = intentar(f"Red «{f['nombre']}»", lambda f=f: self.calcular_red(f["id"]))
            if r is not None:
                d.redes.append(r)
                if r.calculo is None:
                    d.sin_calcular.append(f"Red «{f['nombre']}»: no se ha podido dimensionar")
        for f in self.sistemas_hidraulicos():
            r = intentar(
                f"Sistema «{f['nombre']}»", lambda f=f: self.calcular_sistema_hidraulico(f["id"])
            )
            if r is not None:
                d.sistemas.append(r)
        for f in self.subcuadros():
            r = intentar(f"Subcuadro «{f['nombre']}»", lambda f=f: self.calcular_subcuadro(f["id"]))
            if r is not None:
                d.subcuadros.append((f["nombre"], r))
        for paso in flujo.DEPENDE:
            e = self.estado_paso(paso)
            if e.estado == flujo.DESACTUALIZADO:
                d.pasos_no_hechos.append((flujo.NOMBRES[paso], "desactualizado", e.texto))
        return d

    def exportar_memoria(self, destino: Path, plantilla: Path | None = None) -> Path:
        try:
            return memoria.escribir(Path(destino), self.datos_memoria(), plantilla)
        except memoria.PlantillaNoValida as exc:
            raise OrdenRechazada(str(exc)) from exc
        except PermissionError as exc:
            raise OrdenRechazada(
                f"No se puede escribir «{exc.filename or destino}»: ¿está abierto en Word? "
                "Ciérralo o elige otro nombre."
            ) from exc

    def generar_entregables(
        self, carpeta: Path, plantilla: Path | None = None
    ) -> tuple[Path, list[tuple[str, list[Path], str | None]]]:
        """Todo lo del diseño a una carpeta nueva dentro de `carpeta` (nunca sobrescribe):
        planos (Excel), cargas (Excel y PDF), redes (DXF, LISP y Excel), hidráulica (Excel y
        esquema DXF), subcuadros (unifilar DXF) y la justificación en Word. Devuelve la
        carpeta y, por entregable, sus ficheros o el motivo por el que no se ha generado.
        Un error en uno (de cualquier tipo) se apunta y se sigue con el resto."""
        base = Path(carpeta) / nombre_valido(
            f"{self.nombre} - Entregables {datetime.now():%Y-%m-%d %H%M}", "TRAZA"
        )
        sub, n = base, 1
        while sub.exists():
            n += 1
            sub = base.with_name(f"{base.name} ({n})")
        try:
            sub.mkdir(parents=True)
        except OSError as exc:
            raise OrdenRechazada(f"No se puede crear la carpeta «{sub}»: {exc}") from exc
        hechos: list[tuple[str, list[Path], str | None]] = []

        def hacer(nombre: str, funcion) -> None:
            try:
                r = funcion()
            except OrdenRechazada as exc:
                hechos.append((nombre, [], str(exc)))
                return
            except PermissionError as exc:
                cual = Path(exc.filename).name if exc.filename else "el fichero"
                hechos.append((nombre, [], f"no se puede escribir «{cual}»: ¿está abierto?"))
                return
            except Exception as exc:  # noqa: BLE001 — se dice al usuario, no se corta
                hechos.append((nombre, [], f"{type(exc).__name__}: {exc}"))
                return
            rutas = list(r) if isinstance(r, tuple) else [r]
            hechos.append((nombre, rutas, None))

        # Un nombre por entregable, sin repetir (sin distinguir mayúsculas, como Windows):
        # dos planos «Planta.dxf» de carpetas distintas, o redes «A/B» y «A:B», daban el
        # mismo fichero y el segundo pisaba al primero (revisión 09-11-2026).
        usados: set[str] = set()

        def unico(texto: str) -> Path:
            nombre = nombre_valido(texto, "TRAZA")
            final, k = nombre, 1
            while final.casefold() in usados:
                k += 1
                final = f"{nombre} ({k})"
            usados.add(final.casefold())
            return sub / final

        for pl in self.planos():
            ruta = unico(f"Plano {Path(pl['documento_nombre']).stem}")
            hacer(
                f"Plano «{pl['documento_nombre']}» (Excel)",
                lambda pl=pl, ruta=ruta: self.exportar_plano_excel(pl["id"], ruta),
            )
        if self.cargas_config() is not None and self.espacios():
            ruta = unico("Cargas")
            hacer("Cargas (Excel)", lambda ruta=ruta: self.exportar_cargas_excel(ruta))
            hacer("Cargas (PDF)", lambda ruta=ruta: self.exportar_cargas_pdf(ruta))
        for red in self.redes():
            ruta = unico(f"Red {red['nombre']}")
            hacer(
                f"Red «{red['nombre']}» (DXF y LISP)",
                lambda red=red, ruta=ruta: self.exportar_red_autocad(red["id"], ruta),
            )
            hacer(
                f"Red «{red['nombre']}» (Excel)",
                lambda red=red, ruta=ruta: self.exportar_red_excel(red["id"], ruta),
            )
        for s in self.sistemas_hidraulicos():
            ruta = unico(f"Hidráulica {s['nombre']}")
            esquema = unico(f"Esquema hidráulico {s['nombre']}")
            hacer(
                f"Sistema «{s['nombre']}» (Excel)",
                lambda s=s, ruta=ruta: self.exportar_sistema_hidraulico_excel(s["id"], ruta),
            )
            hacer(
                f"Sistema «{s['nombre']}» (esquema DXF)",
                lambda s=s, esquema=esquema: self.exportar_esquema_hidraulico(s["id"], esquema),
            )
        for c in self.subcuadros():
            ruta = unico(f"Unifilar {c['nombre']}")
            hacer(
                f"Subcuadro «{c['nombre']}» (unifilar DXF)",
                lambda c=c, ruta=ruta: self.exportar_unifilar(c["id"], ruta),
            )
        ruta = unico("Justificación de cálculos")
        hacer(
            "Justificación de cálculos (Word)",
            lambda: self.exportar_memoria(ruta, plantilla),
        )
        return sub, hechos


def _codigo_libre(propuesto: str, usados: set[str]) -> str:
    """Código BC3 libre a partir de `propuesto` (que ya es válido): si está usado, se le
    añade «.1», «.2»… Lo reserva en `usados`."""
    codigo, n = propuesto, 0
    while codigo in usados:
        n += 1
        codigo = f"{propuesto}.{n}"
    usados.add(codigo)
    return codigo


def _capas_existen(plano: dxf.PlanoDxf, capas: list[str]) -> None:
    existentes = {c.casefold() for c in plano.capas}
    faltan = sorted({c for c in capas if c.strip().casefold() not in existentes})
    if faltan:
        raise OrdenRechazada(f"El plano no tiene la capa «{faltan[0]}».")


def _nombres_del_dxf(plano: dxf.PlanoDxf, capas: list[str] | None) -> list[str]:
    """Las capas con el nombre que tienen en el DXF (el usuario puede escribirlas con otras
    mayúsculas): así el Excel y la pantalla dicen lo mismo que el plano."""
    reales = {c.casefold(): c for c in plano.capas}
    return [reales.get(c.strip().casefold(), c) for c in (capas or [])]
