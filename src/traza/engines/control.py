"""Propuesta de control de la instalación (motor puro; docs/modules/control.md).

A partir de lo diseñado (espacios con su uso, redes de aire, servicios hidráulicos) propone
las categorías de control del RITE de cada espacio, el listado de puntos (entradas y salidas)
de cada equipo y las comprobaciones de la IT 1.2.4.3. Todo es propuesta: lo que exige el
RITE lleva su artículo; lo demás, «Propuesta (práctica habitual)».
"""

from __future__ import annotations

from dataclasses import dataclass, field

from traza.core.numeros import escribir_numero
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
    caudal_unidad_m3h: float
    kv: float  # el de la válvula de control de cada unidad (sistema hidráulico)
    perdida_unidad_pa: float


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


CUMPLE, NO_CUMPLE = "CUMPLE", "NO CUMPLE"
INCLUIDA, NO_APLICA = "Incluida en la propuesta", "No aplica"


@dataclass(frozen=True)
class Comprobacion:
    requisito: str
    norma: str
    resultado: str  # CUMPLE | NO CUMPLE | Incluida en la propuesta | No aplica
    detalle: str


@dataclass
class ResultadoControl:
    categorias: list[Categoria] = field(default_factory=list)
    puntos: list[Punto] = field(default_factory=list)
    comprobaciones: list[Comprobacion] = field(default_factory=list)
    #: Secuencia de funcionamiento de cada sistema («el cómo»; parte 2 del control), con
    #: el mismo nombre de sistema que sus puntos.
    secuencias: dict[str, list[str]] = field(default_factory=dict)

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
    # El .6 solo obliga en generadores de calor estándar, de baja temperatura y de
    # condensación; TRAZA no sabe el tipo (suele ser bomba de calor): en calor es propuesta.
    citas = []
    if s.frio:
        citas.append("RITE IT 1.2.4.3.1.7 (impulsión de frío constante)")
    if s.calor:
        citas.append(
            rc.PROPUESTA + ": agua de calor según el exterior (con calderas lo exige el RITE "
            "IT 1.2.4.3.1.6)"
        )
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
    _secuencias(r, redes, servicios)
    if r.puntos:
        r.puntos.append(
            Punto(
                "General",
                "Exterior",
                "Temperatura exterior",
                "EA",
                1,
                rc.PROPUESTA + ": curvas de calor y secuencias",
            )
        )
    _comprobar(r, servicios, grandes, estabilizados)
    return r


def _comprobar(r: ResultadoControl, servicios, grandes, estabilizados) -> None:
    """Revisiones del 11-11-2026: todas salían CUMPLE y no podían fallar, porque comprobaban
    la propia propuesta. Ahora:
    - «Incluida en la propuesta»: exigencias del RITE que la propuesta ya recoge (la sonda,
      la categoría, el punto o el Kv que piden). Sirven para justificar; no son CUMPLE.
    - NO CUMPLE: un dato del proyecto impide la exigencia (unidad sin pérdida: la válvula
      no se puede dimensionar). Se calcula con el Kv: Δp = 10⁵·(q/Kv)².
    CUMPLE queda para cuando haya un dato independiente que verificar (un Kv comercial).
    """

    def fila(requisito, norma, resultado, detalle):
        r.comprobaciones.append(Comprobacion(requisito, norma, resultado, detalle))

    con_thm = [c for c in r.categorias if c.thm is not None]
    req, norma = "Regulación de la temperatura en cada espacio", "RITE IT 1.2.4.3.1.1"
    if con_thm:
        fila(
            req,
            norma,
            INCLUIDA,
            f"Sonda de temperatura en los {len(con_thm)} espacios climatizados",
        )
    else:
        fila(req, norma, NO_APLICA, "Sin espacios climatizados")

    variables = [c.espacio for c in r.categorias if c.ocupacion == "variable"]
    req, norma = "Control directo (IDA-C6) en locales de ocupación variable", "RITE IT 1.2.4.3.3.4"
    if variables:
        fila(req, norma, INCLUIDA, "IDA-C6 con sonda de CO₂ en: " + ", ".join(variables))
    else:
        fila(req, norma, NO_APLICA, "Ningún local de ocupación variable")

    permanentes = [c for c in r.categorias if c.ocupacion == "permanente"]
    req, norma = "IDA-C2, C3 y C4 solo en locales sin ocupación permanente", "RITE IT 1.2.4.3.3.3"
    if permanentes:
        fila(
            req,
            norma,
            INCLUIDA,
            f"{len(permanentes)} espacios de ocupación permanente con IDA-C1 o C6",
        )
    else:
        fila(req, norma, NO_APLICA, "Ningún espacio de ocupación permanente")

    req = "Válvulas de control entre 0,6 y 1,3 veces la pérdida del elemento controlado"
    norma = "RITE IT 1.2.4.3.1.5"
    circuitos = [(s, c) for s in servicios for c in s.circuitos]
    if circuitos:
        malos, relaciones = [], []
        for s, c in circuitos:
            x = relacion_valvula(c)
            nombre = f"{s.sistema} · {s.servicio} · {c.nombre}"
            if x is None or not rc.RELACION_VALVULA[0] <= x <= rc.RELACION_VALVULA[1]:
                malos.append(
                    f"{nombre} ("
                    + ("sin pérdida de la unidad: ponla en el sistema" if x is None else _dos(x))
                    + ")"
                )
            else:
                relaciones.append(x)
        if malos:
            fila(req, norma, NO_CUMPLE, "Sin dato o fuera de 0,6–1,3: " + "; ".join(malos))
        else:
            # El Kv sale de la pérdida de la unidad (sistema hidráulico): la relación es 1
            # por construcción, no una verificación (segunda revisión 11-11-2026).
            menor, mayor = _dos(min(relaciones)), _dos(max(relaciones))
            fila(
                req,
                norma,
                INCLUIDA,
                "Kv dimensionado para perder lo mismo que la unidad (relación "
                + (menor if menor == mayor else f"{menor} a {mayor}")
                + f" en {len(relaciones)} circuitos)",
            )
    else:
        fila(req, norma, NO_APLICA, "Sin sistema hidráulico")

    req = "Presión diferencial estabilizada sobre la válvula (caudal variable y más de 70 kW)"
    if estabilizados:
        fila(
            req,
            norma,
            INCLUIDA,
            "Válvulas independientes de la presión (PICV) en: " + ", ".join(estabilizados),
        )
    else:
        fila(req, norma, NO_APLICA, "Ningún sistema pasa de 70 kW")

    req = "Medición y control del caudal en ventiladores de más de 5 m³/s"
    if grandes:
        fila(req, "RITE IT 1.2.4.3.1.10", INCLUIDA, "Medición de caudal en: " + ", ".join(grandes))
    else:
        fila(req, "RITE IT 1.2.4.3.1.10", NO_APLICA, "Ningún ventilador pasa de 5 m³/s")


def _dos(x: float) -> str:
    return escribir_numero(round(x, 2))


def relacion_valvula(c: CircuitoControl) -> float | None:
    """Pérdida de la válvula abierta al caudal de proyecto, Δp = 10⁵·(q/Kv)² (Pa, q en m³/h:
    definición del Kv), entre la pérdida de la unidad. None si no se puede calcular (sin
    pérdida de la unidad, el sistema hidráulico deja el Kv en 0)."""
    if c.kv <= 0 or c.perdida_unidad_pa <= 0:
        return None
    return 1e5 * (c.caudal_unidad_m3h / c.kv) ** 2 / c.perdida_unidad_pa


# --- Secuencias de funcionamiento (parte 2: «hay el qué pero no el cómo») -----------------

P = " (propuesta)"


def _secuencias(r: ResultadoControl, redes: list[RedControl], servicios: list[ServicioControl]):
    """Lo que el RITE exige lleva su artículo y solo eso se le atribuye; el medio con que se
    consigue termina en «(propuesta)» (revisión 11-11-2026: dos frases le atribuían al RITE
    el mecanismo, PICV y humectación, que el artículo no fija)."""
    fuera_de_servicio = (
        "puede quedar fuera de servicio según su horario de ocupación sin afectar al resto "
        "de la instalación (RITE IT 1.2.4.3.1.4)"
    )
    con_thm = [c for c in r.categorias if c.thm is not None]
    if con_thm:
        z = [
            "Cada espacio regula su temperatura con su sonda (RITE IT 1.2.4.3.1.1), que actúa "
            "sobre la válvula de su unidad terminal" + P + ".",
            "Cada zona " + fuera_de_servicio + ".",
        ]
        co2 = [c.espacio for c in con_thm if c.ida == "IDA-C6"]
        if co2:
            z.append(
                "IDA-C6 en " + ", ".join(co2) + ": control directo por sensores de calidad del "
                "aire, CO₂ o COV (RITE tabla 2.4.3.2); la sonda de CO₂ ajusta el caudal de aire "
                "exterior" + P + "."
            )
        hr = [c for c in con_thm if c.thm in rc.CON_HUMEDAD]
        if hr:
            z.append(
                "Humedad relativa controlada en "
                + ", ".join(f"{c.espacio} ({c.thm})" for c in hr)
                + ": equipamiento mínimo de su categoría (RITE IT 1.2.4.3.2.3); la sonda actúa "
                "sobre la humectación y la deshumectación del equipo" + P + "."
            )
        r.secuencias["Zonas"] = z
    for red in redes:
        s = [
            "La red " + fuera_de_servicio + "; el estado confirma la orden y el fallo para el "
            "ventilador y da alarma" + P + ".",
            "El variador ajusta la velocidad del ventilador al caudal de proyecto" + P + ".",
        ]
        if red.tipo == "impulsion":
            s.append("El presostato diferencial avisa de los filtros colmatados" + P + ".")
            if red.climatizacion:
                s.append(
                    "La temperatura de impulsión se mide para vigilar la climatización" + P + "."
                )
        if red.caudal_m3h > rc.CAUDAL_MEDICION_M3H:
            s.append(
                "Ventilador de más de 5 m³/s: dispositivo para la medición y el control del "
                "caudal de aire (RITE IT 1.2.4.3.1.10), que actúa sobre el variador" + P + "."
            )
        r.secuencias[f"Red {red.nombre}"] = s
    for sv in servicios:
        s = []
        if sv.frio:
            s.append(
                "La temperatura del agua fría a la salida del generador se mantiene constante, "
                "cualquiera que sea la demanda (RITE IT 1.2.4.3.1.7)."
            )
        if sv.calor:
            s.append(
                "En calor, la consigna de impulsión sigue una curva según la temperatura "
                "exterior" + P + "; con calderas lo exige el RITE IT 1.2.4.3.1.6."
            )
        if sv.frio and sv.calor:
            s.append("El cambio de frío a calor se hace por temporada" + P + ".")
        s.append(
            "La bomba de primario marcha con el generador; el generador no arranca sin la "
            "confirmación de su estado" + P + "."
        )
        s.append(
            "Cada bomba de circuito modula con su variador para mantener la presión "
            "diferencial de consigna: al cerrar las válvulas de 2 vías baja el caudal" + P + "."
        )
        if sv.potencia_instalacion_kw > rc.POTENCIA_PRESION_DIFERENCIAL_KW:
            s.append(
                "Caudal variable y más de 70 kW: presión diferencial estabilizada sobre la "
                "válvula de control (RITE IT 1.2.4.3.1.5), con válvulas independientes de la "
                "presión (PICV) en las unidades" + P + "."
            )
        s.append("Cada circuito " + fuera_de_servicio + ".")
        r.secuencias[f"{sv.sistema} · {sv.servicio}"] = s


#: Símbolo de cada señal en el esquema, por su texto y por su tipo. Se recorren en orden:
#: lo específico antes que lo general. En las entradas digitales, el fallo antes que la
#: magnitud («Alarma temperatura alta» es un fallo, no una sonda); en las salidas digitales,
#: la marcha antes que el equipo («Orden de marcha del variador»). Revisión 11-11-2026.
#: Las claves casan por inicio de palabra («cov» no casa en «recovery»).
_F = (("fallo", "alarma", "disparo", "averia"), "F")
_E = (("estado", "funcionamiento", "confirmacion"), "E")
_CO2 = (("co2", "calidad del aire", "cov"), "CO₂")
_HR = (("humedad",), "HR")
_DP = (("presion diferencial", "presostato", "colmatacion", "filtro"), "ΔP")
_Q = (("caudal",), "Q")
_P = (("presencia",), "P")
_T = (("temperatura", "sonda"), "T")
_C = (("consigna",), "C")
_VF = (("velocidad", "variador", "frecuencia"), "VF")
_V = (("valvula", "compuerta"), "V")
_M = (("marcha", "arranque", "paro"), "M")
SIMBOLOS = {
    "ED": (_F, _E, _P, _DP, _Q, _CO2, _HR, _T),
    "EA": (_CO2, _HR, _DP, _Q, _T),
    "SD": (_M, _V, _VF),
    "SA": (_C, _VF, _V),
}
#: Para la leyenda: entradas y salidas, sin repetir.
SIMBOLOS_ENTRADA = (_CO2, _HR, _DP, _Q, _P, _T, _E, _F)
SIMBOLOS_SALIDA = (_C, _VF, _V, _M)


def _normal(texto: str) -> str:
    import unicodedata

    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def simbolo(senal: str, tipo: str) -> str:
    """Rótulo del símbolo: entradas (ED/EA) en círculo, salidas (SD/SA) en cuadrado. Si el
    texto no dice qué es, el propio tipo."""
    import re

    t = _normal(senal)
    for claves, s in SIMBOLOS.get(tipo, ()):
        if any(re.search(r"\b" + re.escape(k), t) for k in claves):
            return s
    return tipo
