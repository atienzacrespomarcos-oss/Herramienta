"""Propuesta de control de la instalación (motor puro; docs/modules/control.md).

A partir de lo diseñado (espacios con su uso, redes de aire, servicios hidráulicos) propone
las categorías de control del RITE de cada espacio, el listado de puntos (entradas y salidas)
de cada equipo y las comprobaciones de la IT 1.2.4.3. Todo es propuesta: lo que exige el
RITE lleva su artículo; lo demás, «Propuesta (práctica habitual)».
"""

from __future__ import annotations

from dataclasses import dataclass, field

from traza.rules import control as rc


@dataclass(frozen=True)
class EspacioControl:
    nombre: str
    uso_clave: str
    uso_nombre: str
    calefaccion: bool  # False: cámaras frigoríficas (uso sin temperatura de invierno)
    metodo_ventilacion: str  # el del catálogo de usos (rules/usos): persona_ida, trabajador…


@dataclass(frozen=True)
class RedControl:
    nombre: str
    tipo: str  # impulsion | retorno | extraccion
    caudal_m3h: float
    climatizacion: bool


@dataclass(frozen=True)
class CircuitoControl:
    nombre: str
    unidades: int


@dataclass(frozen=True)
class ServicioControl:
    sistema: str  # nombre del sistema hidráulico
    servicio: str  # «Frío», «Calor», «Frío y calor»
    frio: bool
    calor: bool
    #: Potencia de generación total del sistema (con 4 tubos, frío + calor): la que cuenta
    #: para el umbral de 70 kW del RITE, como en el esquema hidráulico.
    potencia_instalacion_kw: float
    circuitos: tuple[CircuitoControl, ...]


@dataclass(frozen=True)
class Categoria:
    espacio: str
    uso: str
    thm: str | None
    thm_motivo: str
    ida: str | None
    ida_motivo: str
    ocupacion: str  # variable | permanente | no_permanente | ninguna (RITE IT 1.2.4.3.3)


@dataclass(frozen=True)
class Punto:
    sistema: str
    equipo: str
    senal: str
    tipo: str  # ED | SD | EA | SA
    cantidad: int
    motivo: str


@dataclass(frozen=True)
class Comprobacion:
    requisito: str
    norma: str
    cumple: bool | None  # None: no aplica en este proyecto
    detalle: str


@dataclass
class ResultadoControl:
    categorias: list[Categoria] = field(default_factory=list)
    puntos: list[Punto] = field(default_factory=list)
    comprobaciones: list[Comprobacion] = field(default_factory=list)

    @property
    def resumen(self) -> dict[str, int]:
        """Puntos por tipo (lo que necesita el integrador para presupuestar)."""
        salida = dict.fromkeys(rc.TIPOS_PUNTO, 0)
        for p in self.puntos:
            salida[p.tipo] += p.cantidad
        return salida


def categoria(e: EspacioControl, refrigeracion: bool) -> Categoria:
    """THM-C e IDA-C del espacio (RITE IT 1.2.4.3.2 y 1.2.4.3.3)."""
    if e.metodo_ventilacion == "ninguna" or not e.calefaccion:
        return Categoria(
            e.nombre,
            e.uso_nombre,
            None,
            "Cámara frigorífica: la regula su equipo frigorífico, no la climatización",
            None,
            "Sin ventilación de calidad de aire (uso sin ocupación)",
            "ninguna",
        )
    if e.uso_clave in rc.HUMEDAD_POR_NORMA:
        thm, thm_m = "THM-C5", "Humedad en el local por norma: " + rc.HUMEDAD_POR_NORMA[e.uso_clave]
    elif refrigeracion:
        thm, thm_m = (
            "THM-C3",
            "Calefacción y refrigeración, humedad sin controlar (RITE tabla 2.4.3.1). Si el "
            "proceso exige humedad, THM-C4 o C5",
        )
    else:
        thm, thm_m = "THM-C1", "Solo calefacción (RITE tabla 2.4.3.1)"
    ocupacion = "permanente"
    if e.uso_clave in rc.OCUPACION_VARIABLE:
        ocupacion = "variable"
        ida, ida_m = (
            "IDA-C6",
            "Ocupación variable: control directo obligatorio (RITE IT 1.2.4.3.3.4)",
        )
    elif e.metodo_ventilacion == "superficie_ida":
        ocupacion = "no_permanente"
        ida, ida_m = (
            "IDA-C3",
            "Local sin ocupación permanente: IDA-C2, C3 o C4 (RITE IT 1.2.4.3.3.3); se "
            "propone por horario",
        )
    elif e.metodo_ventilacion == "persona_ida":
        ida, ida_m = (
            "IDA-C6",
            "Ocupación permanente: C2, C3 y C4 no valen (RITE IT 1.2.4.3.3.3). Se propone "
            "por CO₂, que ajusta el aire exterior a la ocupación real (C1 o C5 también valen)",
        )
    else:
        ida, ida_m = (
            "IDA-C1",
            "Ocupación permanente: C2, C3 y C4 no valen (RITE IT 1.2.4.3.3.3). Se propone "
            "continuo durante la actividad (C5 o C6 también valen)",
        )
    return Categoria(e.nombre, e.uso_nombre, thm, thm_m, ida, ida_m, ocupacion)


def _marcha(
    sistema: str, equipo: str, alarma: str = "Fallo / disparo de protecciones"
) -> list[Punto]:
    return [
        Punto(sistema, equipo, "Orden de marcha", "SD", 1, rc.PROPUESTA),
        Punto(sistema, equipo, "Estado (en marcha)", "ED", 1, rc.PROPUESTA),
        Punto(sistema, equipo, alarma, "ED", 1, rc.PROPUESTA),
    ]


def _zonas(r: ResultadoControl, espacios: list[EspacioControl], refrigeracion: bool) -> None:
    for e in espacios:
        c = categoria(e, refrigeracion)
        r.categorias.append(c)
        if c.thm is None:
            continue
        zona = f"Zona {e.nombre}"
        r.puntos.append(
            Punto(
                "Zonas",
                zona,
                "Temperatura ambiente",
                "EA",
                1,
                "RITE IT 1.2.4.3.1.1 (regulación de la temperatura en cada espacio)",
            )
        )
        if c.thm in rc.CON_HUMEDAD:
            r.puntos.append(
                Punto(
                    "Zonas",
                    zona,
                    "Humedad relativa ambiente",
                    "EA",
                    1,
                    f"{c.thm} (RITE IT 1.2.4.3.2.3)",
                )
            )
        if c.ida == "IDA-C6":
            r.puntos.append(
                Punto("Zonas", zona, "Concentración de CO₂", "EA", 1, "IDA-C6 (RITE tabla 2.4.3.2)")
            )


def _aire(r: ResultadoControl, redes: list[RedControl]) -> list[str]:
    grandes = []
    for red in redes:
        sistema = f"Red {red.nombre}"
        equipo = "Ventilador de " + {"impulsion": "impulsión", "retorno": "retorno"}.get(
            red.tipo, "extracción"
        )
        r.puntos += _marcha(sistema, equipo)
        r.puntos.append(Punto(sistema, equipo, "Velocidad (variador)", "SA", 1, rc.PROPUESTA))
        if red.tipo == "impulsion":
            r.puntos.append(
                Punto(
                    sistema,
                    "Filtros",
                    "Colmatación (presostato diferencial)",
                    "ED",
                    1,
                    rc.PROPUESTA + ": aviso de mantenimiento",
                )
            )
            if red.climatizacion:
                r.puntos.append(
                    Punto(sistema, "Impulsión", "Temperatura de impulsión", "EA", 1, rc.PROPUESTA)
                )
        if red.caudal_m3h > rc.CAUDAL_MEDICION_M3H:
            grandes.append(red.nombre)
            r.puntos.append(
                Punto(
                    sistema,
                    equipo,
                    "Medición del caudal de aire",
                    "EA",
                    1,
                    "RITE IT 1.2.4.3.1.10 (ventiladores de más de 5 m³/s)",
                )
            )
    return grandes


def _consigna(s: ServicioControl) -> str:
    citas = []
    if s.frio:
        citas.append("RITE IT 1.2.4.3.1.7 (impulsión de frío constante)")
    if s.calor:
        citas.append("RITE IT 1.2.4.3.1.6 (temperatura del agua de calor según el exterior)")
    return "; ".join(citas)


def _agua(r: ResultadoControl, servicios: list[ServicioControl]) -> list[str]:
    estabilizados = []
    for s in servicios:
        sistema = f"{s.sistema} · {s.servicio}"
        r.puntos += _marcha(sistema, "Generador", alarma="Alarma general")
        r.puntos += [
            Punto(
                sistema, "Generador", "Consigna de temperatura de impulsión", "SA", 1, _consigna(s)
            ),
            Punto(sistema, "Generador", "Temperatura de impulsión", "EA", 1, rc.PROPUESTA),
            Punto(sistema, "Generador", "Temperatura de retorno", "EA", 1, rc.PROPUESTA),
        ]
        r.puntos += _marcha(sistema, "Bomba de primario")
        picv = s.potencia_instalacion_kw > rc.POTENCIA_PRESION_DIFERENCIAL_KW
        for c in s.circuitos:
            bomba = f"Bomba del circuito {c.nombre}"
            r.puntos += _marcha(sistema, bomba)
            r.puntos += [
                Punto(
                    sistema,
                    bomba,
                    "Velocidad (variador)",
                    "SA",
                    1,
                    "Secundario de caudal variable (válvulas de 2 vías en las unidades)",
                ),
                Punto(
                    sistema,
                    f"Circuito {c.nombre}",
                    "Presión diferencial (mando de la bomba)",
                    "EA",
                    1,
                    rc.PROPUESTA,
                ),
                Punto(
                    sistema,
                    f"Circuito {c.nombre}",
                    "Temperatura de impulsión",
                    "EA",
                    1,
                    rc.PROPUESTA,
                ),
                Punto(
                    sistema,
                    f"Unidades de {c.nombre}",
                    "Válvula de control proporcional"
                    + (" independiente de la presión (PICV)" if picv else " de 2 vías"),
                    "SA",
                    c.unidades,
                    "RITE IT 1.2.4.3.1.5"
                    + (" (más de 70 kW: presión diferencial estabilizada)" if picv else ""),
                ),
            ]
            if picv:
                estabilizados.append(f"{s.sistema} · {c.nombre}")
    return estabilizados


def proponer(
    espacios: list[EspacioControl],
    redes: list[RedControl],
    servicios: list[ServicioControl],
    refrigeracion: bool,
) -> ResultadoControl:
    """`refrigeracion`: si la instalación da frío (THM-C3) o solo calor (THM-C1)."""
    r = ResultadoControl()
    _zonas(r, espacios, refrigeracion)
    grandes = _aire(r, redes)
    estabilizados = _agua(r, servicios)
    if r.puntos:
        r.puntos.append(
            Punto(
                "General",
                "Exterior",
                "Temperatura exterior",
                "EA",
                1,
                "RITE IT 1.2.4.3.1.6" if any(s.calor for s in servicios) else rc.PROPUESTA,
            )
        )
    _comprobar(r, servicios, grandes, estabilizados)
    return r


def _comprobar(r: ResultadoControl, servicios, grandes, estabilizados) -> None:
    def no_aplica(requisito, norma, detalle):
        r.comprobaciones.append(Comprobacion(requisito, norma, None, detalle))

    con_thm = [c for c in r.categorias if c.thm is not None]
    sondas = {p.equipo for p in r.puntos if p.senal == "Temperatura ambiente"}
    req = "Regulación de la temperatura en cada espacio"
    if con_thm:
        faltan = [c.espacio for c in con_thm if f"Zona {c.espacio}" not in sondas]
        r.comprobaciones.append(
            Comprobacion(
                req,
                "RITE IT 1.2.4.3.1.1",
                not faltan,
                f"Sonda de temperatura en los {len(con_thm)} espacios climatizados"
                if not faltan
                else "Sin sonda: " + ", ".join(faltan),
            )
        )
    else:
        no_aplica(req, "RITE IT 1.2.4.3.1.1", "Sin espacios climatizados")

    req = "Control directo (IDA-C6) en locales de ocupación variable"
    variables = [c for c in r.categorias if c.ocupacion == "variable"]
    if variables:
        mal = [c.espacio for c in variables if c.ida != "IDA-C6"]
        r.comprobaciones.append(
            Comprobacion(
                req,
                "RITE IT 1.2.4.3.3.4",
                not mal,
                "IDA-C6 con sonda de CO₂ en: " + ", ".join(c.espacio for c in variables)
                if not mal
                else "Sin IDA-C6: " + ", ".join(mal),
            )
        )
    else:
        no_aplica(req, "RITE IT 1.2.4.3.3.4", "Ningún local de ocupación variable")

    req = "IDA-C2, C3 y C4 solo en locales sin ocupación permanente"
    con_ida = [c for c in r.categorias if c.ida is not None]
    if con_ida:
        mal = [
            c.espacio
            for c in con_ida
            if c.ida in rc.SIN_OCUPACION_PERMANENTE and c.ocupacion == "permanente"
        ]
        r.comprobaciones.append(
            Comprobacion(
                req,
                "RITE IT 1.2.4.3.3.3",
                not mal,
                "Todas las categorías IDA son válidas para su ocupación"
                if not mal
                else "Ocupación permanente con IDA-C2/C3/C4: " + ", ".join(mal),
            )
        )
    else:
        no_aplica(req, "RITE IT 1.2.4.3.3.3", "Sin espacios ventilados")

    req = "Válvulas de control entre 0,6 y 1,3 veces la pérdida del elemento controlado"
    if servicios:
        r.comprobaciones.append(
            Comprobacion(
                req,
                "RITE IT 1.2.4.3.1.5",
                True,
                "Kv de cada válvula calculado para que pierda lo mismo que su unidad "
                "(relación 1,0; paso «Sistema hidráulico»)",
            )
        )
    else:
        no_aplica(req, "RITE IT 1.2.4.3.1.5", "Sin sistema hidráulico")

    req = "Presión diferencial estabilizada sobre la válvula (caudal variable y más de 70 kW)"
    if estabilizados:
        r.comprobaciones.append(
            Comprobacion(
                req,
                "RITE IT 1.2.4.3.1.5",
                True,
                "Válvulas independientes de la presión (PICV) en: " + ", ".join(estabilizados),
            )
        )
    else:
        no_aplica(req, "RITE IT 1.2.4.3.1.5", "Ningún sistema pasa de 70 kW")

    req = "Medición y control del caudal en ventiladores de más de 5 m³/s"
    if grandes:
        r.comprobaciones.append(
            Comprobacion(
                req, "RITE IT 1.2.4.3.1.10", True, "Medición de caudal en: " + ", ".join(grandes)
            )
        )
    else:
        no_aplica(req, "RITE IT 1.2.4.3.1.10", "Ningún ventilador pasa de 5 m³/s")
