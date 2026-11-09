"""Justificación de cálculos en Word (docs/modules/flujo.md, bloque 2).

Decisión del usuario (09-11-2026): «Es de soporte en caso de que me hagan justificar algo.
Con plantilla de Aliter. Nada oficial», y sin membrete propio de TRAZA. Por eso:
- No es la memoria del proyecto: recoge, por cálculo, el método, los datos de partida con
  su fuente, los resultados y la norma de cada criterio, para justificarlo si se pide.
- Se escribe sobre la plantilla .docx (o .dotx) que elige el usuario: se conservan sus
  estilos, encabezado y pie y se vacía su cuerpo. Sin plantilla, el documento por defecto.
- Los criterios son los mismos textos que las hojas «Hipótesis» de los Excel (una sola
  fuente: lo que dice el Excel y lo que dice el Word no pueden divergir).
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.exceptions import PackageNotFoundError
from docx.shared import Pt

from traza.engines.hidraulica import SERVICIOS
from traza.io import informe_cargas, informe_hidronica, informe_redes
from traza.io.informe_hidronica import MCA
from traza.rules import electricidad as elec

TIPOS_PLANTILLA = (".docx", ".dotx")


@dataclass
class DatosMemoria:
    """Lo que entra en la justificación (lo junta Proyecto; aquí no se calcula nada)."""

    proyecto: str
    encargo: str  # el texto del tipo de encargo
    fecha: date
    cargas: Any = None  # ResultadoCargas
    redes: list[Any] = field(default_factory=list)  # ResultadoRedAire
    sistemas: list[Any] = field(default_factory=list)  # ResultadoSistema (hidráulica)
    subcuadros: list[tuple[str, Any]] = field(default_factory=list)  # (nombre, resultado)
    #: Lo que no se ha podido calcular, para decirlo en el documento (nunca se omite).
    sin_calcular: list[str] = field(default_factory=list)
    #: Pasos desactualizados al generar (paso, estado, texto): los pendientes no se listan
    #: aquí, porque lo que les falta ya sale en «Sin calcular».
    pasos_no_hechos: list[tuple[str, str, str]] = field(default_factory=list)


class PlantillaNoValida(ValueError):
    pass


# --- Formato --------------------------------------------------------------------------


def _n(v: Any, dec: int = 1) -> str:
    """Coma decimal, sin separador de miles (como el resto de la herramienta).

    Un número con hasta 3 decimales (un dato de partida: 0,25; 2,75 m; 0,37 kW) se escribe
    entero, tal cual se usó; uno con más (un resultado), redondeado a `dec`. Revisión
    09-11-2026: redondear todo a 1 decimal escribía «0,2» para un dato de 0,25 en la
    tabla de procedencia, una cifra que no es la que se usó."""
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "Sí" if v else "No"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if abs(v - round(v, 3)) < 1e-9:
            texto = f"{round(v, 3):.3f}".rstrip("0").rstrip(".")
        else:
            texto = f"{v:.{dec}f}"
        return texto.replace(".", ",")
    return str(v)


def _abrir(plantilla: Path | None):
    if plantilla is None:
        return Document()
    plantilla = Path(plantilla)
    if plantilla.suffix.lower() not in TIPOS_PLANTILLA:
        raise PlantillaNoValida("La plantilla tiene que ser un documento de Word (.docx o .dotx).")
    try:
        try:
            doc = Document(str(plantilla))
        except ValueError:
            # Una plantilla (.dotx), aunque se llame .docx: python-docx solo abre documentos.
            doc = _abrir_dotx(plantilla)
    except (zipfile.BadZipFile, PackageNotFoundError, KeyError, ValueError, OSError) as exc:
        raise PlantillaNoValida(
            f"No se puede abrir la plantilla «{plantilla.name}»: {exc}"
        ) from exc
    # Se vacía el cuerpo (el texto de ejemplo de la plantilla) y se conservan los estilos,
    # el encabezado, el pie y la configuración de página (el último sectPr del cuerpo).
    cuerpo = doc.element.body
    for hijo in list(cuerpo):
        if not hijo.tag.endswith("}sectPr"):
            cuerpo.remove(hijo)
    return doc


def _abrir_dotx(plantilla: Path):
    """python-docx solo abre documentos: una plantilla (.dotx) es el mismo paquete con otro
    tipo de contenido en la parte principal; se cambia en una copia temporal."""
    tipo_dotx = "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"
    tipo_docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
    with TemporaryDirectory() as tmp:
        copia = Path(tmp) / "plantilla.docx"
        with zipfile.ZipFile(plantilla) as zin, zipfile.ZipFile(copia, "w") as zout:
            for item in zin.infolist():
                datos = zin.read(item.filename)
                if item.filename == "[Content_Types].xml":
                    datos = datos.replace(tipo_dotx.encode(), tipo_docx.encode())
                zout.writestr(item, datos)
        return Document(str(copia))


class _Escritor:
    """Párrafos, títulos y tablas con los estilos de la plantilla; si la plantilla no
    trae alguno (Word solo guarda los que se han usado), se imita con formato directo."""

    def __init__(self, doc) -> None:
        self.doc = doc
        self._estilos = {s.name for s in doc.styles}

    def _estilo(self, *nombres: str) -> str | None:
        return next((n for n in nombres if n in self._estilos), None)

    def titulo(self, texto: str, nivel: int) -> None:
        estilo = self._estilo("Title" if nivel == 0 else f"Heading {nivel}")
        if estilo:
            self.doc.add_paragraph(texto, style=estilo)
            return
        p = self.doc.add_paragraph()
        r = p.add_run(texto)
        r.bold = True
        r.font.size = Pt({0: 20, 1: 14, 2: 12}.get(nivel, 11))

    def parrafo(self, texto: str, cursiva: bool = False) -> None:
        p = self.doc.add_paragraph()
        r = p.add_run(texto)
        r.italic = cursiva

    def vinetas(self, lineas: list[str]) -> None:
        estilo = self._estilo("List Bullet")
        for linea in lineas:
            if estilo:
                self.doc.add_paragraph(linea, style=estilo)
            else:
                self.doc.add_paragraph(f"• {linea}")

    def tabla(self, cabecera: list[str], filas: list[list[Any]], numericas=()) -> None:
        if not filas:
            self.parrafo("(Sin filas.)", cursiva=True)
            return
        t = self.doc.add_table(rows=1, cols=len(cabecera))
        estilo = self._estilo("Table Grid")
        if estilo:
            t.style = estilo
        for celda, texto in zip(t.rows[0].cells, cabecera, strict=True):
            celda.text = ""
            run = celda.paragraphs[0].add_run(texto)
            run.bold = True
        for fila in filas:
            celdas = t.add_row().cells
            for j, (celda, valor) in enumerate(zip(celdas, fila, strict=True)):
                celda.text = valor if isinstance(valor, str) else _n(valor)
                if j in numericas:
                    celda.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        self.doc.add_paragraph()


# --- Documento --------------------------------------------------------------------------


def escribir(destino: Path, d: DatosMemoria, plantilla: Path | None = None) -> Path:
    destino = Path(destino)
    if destino.suffix.lower() != ".docx":
        destino = destino.with_name(destino.name + ".docx")
    doc = _abrir(plantilla)
    # Propiedades del documento: las suyas, no las de la plantilla (o «python-docx», 2013).
    props = doc.core_properties
    props.title = f"Justificación de cálculos — {d.proyecto}"
    props.subject = "Documento de apoyo"
    props.author = props.last_modified_by = ""
    props.created = props.modified = datetime.now()
    props.revision = 1
    w = _Escritor(doc)
    w.titulo("Justificación de cálculos", 0)
    w.parrafo(f"Proyecto: {d.proyecto}")
    w.parrafo(f"Encargo: {d.encargo}")
    w.parrafo(f"Fecha: {d.fecha:%d-%m-%Y}")
    w.parrafo(
        "Documento de apoyo: recoge cómo se ha calculado cada parte de la instalación, con "
        "los datos de partida, su procedencia y la norma o fuente de cada criterio, para "
        "justificarlo si se pide. No es la memoria del proyecto.",
        cursiva=True,
    )
    if d.pasos_no_hechos or d.sin_calcular:
        w.titulo("Estado al generar este documento", 1)
        w.vinetas(
            [
                f"{paso}: {estado}" + (f" ({texto})" if texto else "")
                for paso, estado, texto in d.pasos_no_hechos
            ]
            + [f"Sin calcular: {x}" for x in d.sin_calcular]
        )
    n = 0
    if d.cargas is not None:
        n += 1
        _cargas(w, n, d.proyecto, d.cargas)
    if d.redes:
        n += 1
        _redes(w, n, d.redes)
    if d.sistemas:
        n += 1
        _hidraulica(w, n, d.sistemas)
    if d.subcuadros:
        n += 1
        _subcuadros(w, n, d.subcuadros)
    if n == 0:
        w.parrafo("No hay ningún cálculo hecho en el proyecto.", cursiva=True)
    # Se escribe aparte y se sustituye: un fallo a medias no deja un .docx roto.
    temporal = destino.with_name(destino.name + ".parcial")
    doc.save(str(temporal))
    temporal.replace(destino)
    return destino


def _cargas(w: _Escritor, n: int, proyecto: str, r: Any) -> None:
    w.titulo(f"{n}. Cargas térmicas y ventilación", 1)
    w.titulo(f"{n}.1. Datos de partida", 2)
    w.tabla(
        ["Concepto", "Valor", "Unidad"],
        [[c, v, u] for c, v, u in informe_cargas._resumen(proyecto, r)],
        numericas=(1,),
    )
    w.titulo(f"{n}.2. Método y criterios", 2)
    w.vinetas(informe_cargas.hipotesis(r))
    w.titulo(f"{n}.3. Resultados por espacio", 2)
    w.tabla(
        [
            "Espacio",
            "Uso",
            "Superficie (m²)",
            "Calefacción (kW)",
            "Refrigeración (kW)",
            "Hora punta",
            "Refrig. (W/m²)",
            "Aire exterior (m³/h)",
        ],
        [
            [
                f"{x.codigo} {x.nombre}",
                x.uso.nombre,
                x.superficie_m2,
                x.invierno.total_w / 1000,
                x.verano.total_w / 1000,
                x.verano.hora_solar,
                x.verano.total_w / x.superficie_m2 if x.superficie_m2 else None,
                round(x.aire_exterior_m3h),
            ]
            for x in r.espacios
        ],
        numericas=(2, 3, 4, 5, 6, 7),
    )
    w.titulo(f"{n}.4. Desglose y procedencia de los datos de cada espacio", 2)
    for x in r.espacios:
        w.titulo(f"{x.codigo} {x.nombre}", 3)
        w.tabla(
            ["Dato", "Valor", "Unidad", "Origen", "Fuente"],
            [[dt.concepto, dt.valor, dt.unidad, dt.origen, dt.fuente] for dt in x.datos],
            numericas=(1,),
        )
        w.tabla(
            ["Estación", "Concepto", "Sensible (W)", "Latente (W)"],
            [
                [estacion, p.concepto, p.sensible_w, p.latente_w]
                for estacion, res in (("Invierno", x.invierno), ("Verano", x.verano))
                for p in res.partidas
            ],
            numericas=(2, 3),
        )


def _redes(w: _Escritor, n: int, redes: list[Any]) -> None:
    w.titulo(f"{n}. Redes de aire", 1)
    for i, r in enumerate(redes, start=1):
        red, c = r.red, r.calculo
        w.titulo(f"{n}.{i}. {red['nombre']} ({informe_redes.TIPOS[red['tipo']].lower()})", 2)
        filas: list[list[Any]] = [["Caudal total", r.caudal_total_m3h, "m³/h"]]
        if c is not None:
            filas += [
                ["Presión necesaria en la red (camino crítico)", c.presion_necesaria_pa, "Pa"],
                ["Terminal del camino crítico", c.terminal_critico, ""],
                ["Potencia específica exigida (RITE IT 1.2.4.2.5)", f"SFP {r.sfp_exigida}", ""],
                ["Potencia eléctrica máxima del ventilador", r.potencia_maxima_w, "W"],
            ]
        w.tabla(["Concepto", "Valor", "Unidad"], filas, numericas=(1,))
        if c is None:
            # Sin dimensionar, los criterios de dimensionado no se han aplicado: se dice por
            # qué (sus avisos), no se describe un método que no se ha usado.
            w.parrafo("No se ha podido dimensionar la red:", cursiva=True)
            w.vinetas([f"Aviso: {a}" for a in r.avisos] or ["sin más detalle"])
            continue
        w.vinetas(informe_redes.hipotesis(r))
        if c is not None:
            w.tabla(
                [
                    "Tramo",
                    "Caudal (m³/h)",
                    "Sección (mm)",
                    "Velocidad (m/s)",
                    "Rozamiento (Pa/m)",
                    "Pérdida (Pa)",
                ],
                [
                    [
                        t.tramo.id,
                        t.tramo.caudal_m3s * 3600,
                        t.seccion.texto(),
                        t.velocidad_m_s,
                        t.friccion_pa_m,
                        t.perdida_pa,
                    ]
                    for t in c.tramos
                ],
                numericas=(1, 3, 4, 5),
            )


def _hidraulica(w: _Escritor, n: int, sistemas: list[Any]) -> None:
    w.titulo(f"{n}. Sistema hidráulico", 1)
    for i, r in enumerate(sistemas, start=1):
        w.titulo(f"{n}.{i}. {r.sistema['nombre']}", 2)
        filas: list[list[Any]] = []
        for s in r.servicios:
            nombre = SERVICIOS[s.clave]
            p = s.presiones
            filas += [
                [f"{nombre} · potencia del generador", s.potencia_kw, "kW"],
                [f"{nombre} · caudal", s.caudal_m3s * 3600, "m³/h"],
                [f"{nombre} · tubería del primario", s.primario.tubo.nombre, ""],
                [f"{nombre} · bomba de primario", s.altura_primario_pa / MCA, "m c.a."],
                [f"{nombre} · colectores", s.colector.tubo.nombre, ""],
                [f"{nombre} · depósito de inercia (mínimo)", s.inercia_l, "l"],
                [f"{nombre} · vaso de expansión (mínimo)", s.vaso_l, "l"],
                [
                    f"{nombre} · llenado / máxima",
                    f"{_n(p.llenado)} / {_n(p.maxima_servicio)}",
                    "bar",
                ],
                [f"{nombre} · seguridad / prueba", f"{_n(p.seguridad)} / {_n(p.prueba)}", "bar"],
            ]
        w.tabla(["Concepto", "Valor", "Unidad"], filas, numericas=(1,))
        w.vinetas(informe_hidronica.hipotesis(r))
        w.tabla(
            [
                "Circuito",
                "Frío (kW)",
                "Calor (kW)",
                "Caudal (m³/h)",
                "Tubería",
                "v (m/s)",
                "R (Pa/m)",
                "Bomba (m c.a.)",
            ],
            [
                [
                    f"{c.datos.nombre} ({SERVICIOS[s.clave].lower()})",
                    c.datos.potencia_frio_w / 1000,
                    c.datos.potencia_calor_w / 1000,
                    c.caudal_m3s * 3600,
                    c.tubo.tubo.nombre,
                    c.tubo.velocidad_m_s,
                    c.tubo.friccion_pa_m,
                    c.altura_bomba_pa / MCA,
                ]
                for s in r.servicios
                for c in s.circuitos
            ],
            numericas=(1, 2, 3, 5, 6, 7),
        )
        w.parrafo("Elementos y la norma o fuente que los exige:")
        w.tabla(
            ["Zona", "Elemento", "Especificación", "Cantidad", "Norma o fuente"],
            [[e.zona, e.elemento, e.especificacion, e.cantidad, e.norma] for e in r.elementos],
            numericas=(3,),
        )


def hipotesis_subcuadro(r: Any) -> list[str]:
    """Criterios de los subcuadros: los de docs/modules/electricidad.md («Criterios
    elegidos») y los que aplica engines/subcuadro.py."""
    return [
        f"{elec.REBT} y guías técnicas de aplicación del Ministerio. Cable de cobre RZ1-K "
        "0,6/1 kV (XLPE, 90 °C).",
        "Intensidad admisible Iz: GUÍA-BT-19, tabla A (UNE 20460-5-523 tabla A.52-1 bis) por "
        "método de instalación, con el factor de agrupamiento de la tabla E por el número de "
        "líneas.",
        "Motores: intensidad de diseño al 125 % (ITC-BT-47). Alimentación del subcuadro: "
        "suma de las salidas (las monofásicas cuentan 1/3, repartidas entre las tres fases) "
        "más el 25 % del motor mayor.",
        f"Caída de tensión: GUÍA-BT Anexo 2 (γ del cobre a 90 °C); límite del "
        f"{_n(r.limite_pct)} % sumando la línea que alimenta el subcuadro (ITC-BT-19 2.2.2).",
        "Protección: magnetotérmico con I diseño ≤ In ≤ Iz (GUÍA-BT-22; en motores, I diseño "
        "= 125 % de Ib); curva D en motores de arranque directo y C en el resto; por encima "
        "de 160 A, caja moldeada a definir.",
        "Diferencial por salida (GUÍA-BT-24): 30 mA en monofásicas hasta 32 A y 300 mA en el "
        "resto; tipo B con variador trifásico, F con convertidor monofásico, A en el resto; "
        "en esquema TT, RA·Ia ≤ 50 V.",
        "Conductor de protección: ITC-BT-19 tabla 2.",
        f"Factor de potencia a falta de dato: {_n(elec.COS_PHI_DEFECTO, 2)} (GUÍA-BT Anexo 2).",
        *(f"Aviso: {a}" for a in r.avisos),
    ]


def comprobacion(x: Any, limite_pct: float) -> bool:
    """CUMPLE se calcula aquí con los valores de la línea, no se lee de un indicador: I
    diseño ≤ In ≤ Iz (sin calibre, caja moldeada: I diseño ≤ Iz) y caída total ≤ límite."""
    protegida = (
        x.intensidad_diseno_a <= x.calibre_a <= x.admisible_a
        if x.calibre_a
        else x.intensidad_diseno_a <= x.admisible_a
    )
    return protegida and x.caida_total_pct <= limite_pct + 1e-9


def _subcuadros(w: _Escritor, n: int, subcuadros: list[tuple[str, Any]]) -> None:
    w.titulo(f"{n}. Subcuadros eléctricos de clima", 1)
    for i, (nombre, r) in enumerate(subcuadros, start=1):
        w.titulo(f"{n}.{i}. {nombre}", 2)
        w.vinetas(hipotesis_subcuadro(r))
        w.tabla(
            [
                "Línea",
                "Método",
                "L (m)",
                "P (kW)",
                "Ib (A)",
                "I diseño (A)",
                "Sección / PE (mm²)",
                "Iz (A)",
                "Protección",
                "Diferencial",
                "ΔU (%)",
                "ΔU total (%)",
                "Comprobación",
            ],
            [
                [
                    x.nombre,
                    x.metodo,
                    x.longitud_m,
                    x.potencia_kw,
                    x.intensidad_a,
                    x.intensidad_diseno_a,
                    f"{_n(x.seccion, 1)} / {_n(x.seccion_pe, 1)}",
                    x.admisible_a,
                    f"{x.calibre_a} A curva {x.curva}" if x.calibre_a else "Caja moldeada",
                    f"{x.diferencial_ma} mA tipo {x.diferencial_tipo}" if x.diferencial_ma else "—",
                    x.caida_pct,
                    x.caida_total_pct,
                    "CUMPLE" if comprobacion(x, r.limite_pct) else "NO CUMPLE",
                ]
                for x in (r.alimentacion, *r.salidas)
            ],
            numericas=(2, 3, 4, 5, 7, 10, 11),
        )
