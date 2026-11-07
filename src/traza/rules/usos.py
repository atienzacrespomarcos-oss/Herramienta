"""Catálogo de usos de los espacios: valores propuestos por uso (decisión del usuario,
07-11-2026: «propuesta por uso», ocupación de diseño ASHRAE). El usuario los cambia por
espacio; aquí está lo típico y de dónde sale.

Fuentes (docs/modules/cargas.md):
- Ocupación, calor de las personas, iluminación y equipos: valores por defecto por tipo de
  espacio de ASHRAE, tal como los reproduce Autodesk en la ayuda de Revit («Space Type Data»
  y «People Heat Gain», basados en ASHRAE Handbook – Fundamentals, tabla 1 de ganancias de
  las personas). Se guardan en sus unidades de origen (personas/100 m², Btu/h, W/ft²) y se
  convierten aquí, para que se puedan cotejar con la fuente sin reconvertir.
- Temperaturas interiores de cálculo: RITE IT 1.1.4.1.2 (21 °C invierno, 25 °C verano) y,
  en lugares de trabajo industriales, RD 486/1997 anexo III (trabajo ligero 14–25 °C).
- Ventilación: RITE IT 1.1.4.2 (categorías IDA, tablas 1.4.2.1 y 1.4.2.4, piscinas), RD
  486/1997 anexo III (50 m³/h por trabajador en trabajo no sedentario), UNE 100713 para
  quirófanos (a través de la NTP 859 del INSST).
- Congelados: RD 1109/1991 (productos ultracongelados a −18 °C o menos); cámara a −20 °C.
- Salas limpias: renovaciones de impulsión por clase ISO (tabla de referencia de Mecart),
  punto medio del intervalo.
- Cobertura climática «alta» (percentiles extremos): IDAE, apartado 5.2.
"""

from __future__ import annotations

from dataclasses import dataclass

BTU_H_A_W = 0.29307107
W_FT2_A_W_M2 = 10.7639104

URL_ASHRAE_ESPACIOS = (
    "https://help.autodesk.com/cloudhelp/2014/ENU/Revit/files/"
    "GUID-151D513A-09C1-418C-BCF7-005F51A1D111.htm"
)
URL_RITE = "https://www.boe.es/buscar/act.php?id=BOE-A-2007-15820"
URL_RD486 = "https://www.boe.es/buscar/act.php?id=BOE-A-1997-8669"
URL_NTP859 = (
    "https://www.insst.es/documentacion/colecciones-tecnicas/ntp-notas-tecnicas-de-prevencion/"
    "25-serie-ntp-numeros-856-a-890-ano-2011/nota-tecnica-de-prevencion-ntp-859"
)
URL_SALAS_LIMPIAS = "https://www.mecart-cleanrooms.com/?p=2824"

F_ASHRAE = "ASHRAE, valores por defecto por tipo de espacio (Autodesk Revit, «Space Type Data»)"
F_RITE_T = "RITE IT 1.1.4.1.2, tabla 1.4.1.1"
F_RD486_T = "RD 486/1997, anexo III.3.a (trabajo ligero 14–25 °C)"

#: Caudal de aire exterior por persona según IDA (RITE tabla 1.4.2.1), dm³/s.
IDA_PERSONA = {1: 20.0, 2: 12.5, 3: 8.0, 4: 5.0}
#: Por superficie, locales sin ocupación permanente (RITE tabla 1.4.2.4), dm³/(s·m²).
IDA_SUPERFICIE = {2: 0.83, 3: 0.55, 4: 0.28}


@dataclass(frozen=True)
class Ventilacion:
    """Cómo se calcula el aire exterior mínimo del espacio."""

    metodo: str  # persona_ida | superficie_ida | trabajador | fijo | lamina | ninguna
    valor: float  # IDA (1–4), m³/h por trabajador, m³/h fijos o dm³/(s·m²) de lámina
    fuente: str


@dataclass(frozen=True)
class Uso:
    clave: str
    nombre: str
    grupo: str
    tipo_ashrae: str
    personas_100m2: float
    sensible_btuh: float
    latente_btuh: float
    iluminacion_w_ft2: float
    equipos_w_ft2: float
    t_invierno: float | None  # °C de cálculo; None = sin calefacción (cámaras)
    t_verano: float
    fuente_temperaturas: str
    ventilacion: Ventilacion
    cobertura: str = "normal"
    impulsion_renovaciones: float | None = None  # salas limpias (recirculación)
    nota: str | None = None
    #: Calor por persona (W sensible, W latente) cuando el de confort de ASHRAE no vale (frío).
    calor_persona_w: tuple[float, float] | None = None
    fuente_calor_persona: str | None = None

    @property
    def m2_persona(self) -> float | None:
        return 100.0 / self.personas_100m2 if self.personas_100m2 else None

    @property
    def sensible_w(self) -> float:
        if self.calor_persona_w is not None:
            return self.calor_persona_w[0]
        return self.sensible_btuh * BTU_H_A_W

    @property
    def latente_w(self) -> float:
        if self.calor_persona_w is not None:
            return self.calor_persona_w[1]
        return self.latente_btuh * BTU_H_A_W

    @property
    def iluminacion_w_m2(self) -> float:
        return self.iluminacion_w_ft2 * W_FT2_A_W_M2

    @property
    def equipos_w_m2(self) -> float:
        return self.equipos_w_ft2 * W_FT2_A_W_M2


def _ida(n: int) -> Ventilacion:
    return Ventilacion("persona_ida", n, f"RITE IT 1.1.4.2.2 (IDA {n}) y tabla 1.4.2.1")


def _sup(n: int) -> Ventilacion:
    return Ventilacion("superficie_ida", n, f"RITE IT 1.1.4.2.3.D, tabla 1.4.2.4 (IDA {n})")


_TRABAJO = Ventilacion("trabajador", 50.0, "RD 486/1997, anexo III.3.d (50 m³/h por trabajador)")
#: Cámaras: la tabla 1.4.2.4 del RITE es de calidad de aire en locales de personas, no de
#: cámaras; las entradas de aire por puertas se cuentan aparte (revisión 07-11-2026).
_SIN_VENTILACION = Ventilacion(
    "ninguna",
    0.0,
    "Cámara frigorífica: sin aire exterior de ventilación; las infiltraciones "
    "por apertura de puertas se añaden como proceso (ASHRAE Refrigeration, cap. 24)",
)


def _persona_frio(t: float) -> dict:
    """Calor de una persona en una cámara: q = 272 − 6·t W (ASHRAE Handbook – Refrigeration,
    cap. 24, carga de personas), tomado como sensible."""
    return {
        "calor_persona_w": (272.0 - 6.0 * t, 0.0),
        "fuente_calor_persona": f"ASHRAE Refrigeration, cap. 24: 272 − 6·t = {272 - 6 * t:g} W "
        f"por persona a {t:g} °C",
    }


F_DESPIECE = (
    "Reglamento (CE) 853/2004, anexo III, sección I, cap. V: salas de despiece a 12 °C como máximo"
)


def _u(clave, nombre, grupo, tipo, p, s, lat, luz, eq, ti, tv, ft, vent, **kw) -> Uso:
    return Uso(clave, nombre, grupo, tipo, p, s, lat, luz, eq, ti, tv, ft, vent, **kw)


USOS: tuple[Uso, ...] = (
    # --- Oficinas y zonas comunes ---------------------------------------------------------
    _u("despacho", "Despacho", "Oficinas", "Office - Enclosed", 5.0, 250, 200, 1.0, 1.5,
       21, 25, F_RITE_T, _ida(2)),
    _u("oficina_abierta", "Oficina abierta", "Oficinas", "Office - Open Plan", 5.0, 250, 200,
       1.1, 1.5, 21, 25, F_RITE_T, _ida(2)),
    _u("reuniones", "Sala de reuniones", "Oficinas", "Conference/Meeting/Multipurpose", 50.0,
       250, 200, 1.3, 1.0, 21, 25, F_RITE_T, _ida(2)),
    _u("vestibulo", "Vestíbulo / recepción", "Oficinas", "Lobby", 150.0, 250, 155, 1.3, 0.54,
       21, 25, F_RITE_T, _ida(2)),
    _u("pasillo", "Pasillo / circulaciones", "Oficinas", "Corridor/Transition", 10.0, 250, 200,
       0.5, 0.3, 21, 25, F_RITE_T, _sup(2)),
    _u("aseos", "Aseos", "Oficinas", "Restrooms", 10.0, 250, 200, 0.9, 0.3, 21, 25, F_RITE_T,
       _sup(3)),
    _u("vestuarios", "Vestuarios", "Oficinas", "Dressing/Locker/Fitting Room - Exercise Center",
       20.0, 250, 200, 0.56, 0.54, 21, 25, F_RITE_T, _ida(3)),
    _u("comedor", "Comedor de personal", "Oficinas", "Dining Area", 70.0, 275, 275, 0.9, 0.54,
       21, 25, F_RITE_T, _ida(3)),
    _u("cocina", "Cocina", "Oficinas", "Food Preparation", 20.0, 250, 200, 1.2, 1.5, 21, 25,
       F_RITE_T, _ida(3), nota="La extracción de campanas se calcula aparte."),
    _u("sala_tecnica", "Sala técnica / instalaciones", "Oficinas", "Electrical/Mechanical", 3.0,
       250, 200, 1.5, 0.3, 21, 25, F_RITE_T, _sup(4)),
    # --- Hotel ----------------------------------------------------------------------------
    _u("habitacion_hotel", "Habitación de hotel", "Hotel", "Living Quarters - Hotel", 10.0,
       250, 155, 1.1, 0.54, 21, 25, F_RITE_T, _ida(3)),
    _u("recepcion_hotel", "Recepción / zonas comunes de hotel", "Hotel", "Lobby - Hotel",
       150.0, 250, 200, 1.1, 0.54, 21, 25, F_RITE_T, _ida(2)),
    _u("restaurante_hotel", "Restaurante", "Hotel", "Dining Area - Hotel", 70.0, 275, 275, 1.3,
       0.54, 21, 25, F_RITE_T, _ida(3)),
    _u("salon_eventos", "Salón de eventos / congresos", "Hotel",
       "Hotel/Conference Center - Conference/Meeting", 50.0, 225, 105, 1.3, 1.0, 21, 25,
       F_RITE_T, _ida(3)),
    _u("gimnasio", "Gimnasio", "Hotel", "Exercise Area - Exercise Center", 30.0, 710, 1090,
       0.93, 0.54, 21, 25, F_RITE_T, _ida(3)),
    # --- Sanitario ------------------------------------------------------------------------
    _u("habitacion_hospital", "Habitación de hospitalización", "Sanitario",
       "Patient Room - Hospital/Healthcare", 10.0, 250, 200, 0.7, 1.5, 21, 25, F_RITE_T, _ida(1),
       cobertura="alta"),
    _u("consulta", "Consulta / exploración", "Sanitario", "Exam/Treatment - Hospital/Healthcare",
       20.0, 250, 200, 1.5, 1.5, 21, 25, F_RITE_T, _ida(1), cobertura="alta"),
    _u("espera_hospital", "Sala de espera / circulación sanitaria", "Sanitario",
       "Corridor w/Patient Waiting Exam - Hospital/Healthcare", 10.0, 250, 200, 1.0, 0.3, 21, 25,
       F_RITE_T, _ida(1), cobertura="alta"),
    _u("reanimacion", "Reanimación / UCI", "Sanitario", "Recovery - Hospital/Healthcare", 20.0,
       250, 200, 0.8, 1.5, 21, 25, F_RITE_T, _ida(1), cobertura="alta"),
    _u("quirofano", "Quirófano", "Sanitario", "Operating Room - Hospital/Healthcare", 20.0, 250,
       200, 2.2, 1.5, 21, 25, F_RITE_T,
       Ventilacion("fijo", 1200.0, "UNE 100713:2005 (NTP 859 INSST): aire exterior mínimo "
                   "1200 m³/h por quirófano; caudal de referencia 2400 m³/h"),
       cobertura="alta", nota="Impulsión de referencia 2400 m³/h; se recomienda 100 % exterior."),
    _u("laboratorio", "Laboratorio", "Sanitario", "Laboratory - Office", 5.0, 250, 200, 1.4, 1.5,
       21, 25, F_RITE_T, _ida(1)),
    # --- Comercial ------------------------------------------------------------------------
    _u("tienda", "Tienda / área de ventas", "Comercial", "Department Store Sales - Retail",
       15.0, 250, 200, 2.14, 1.0, 21, 25, F_RITE_T, _ida(3)),
    _u("supermercado", "Supermercado (sala de ventas)", "Comercial",
       "Supermarket Sales Area - Retail", 8.0, 250, 200, 2.1, 1.0, 21, 25, F_RITE_T, _ida(3),
       nota="Los muebles frigoríficos abiertos restan carga: se meten como equipo con signo."),
    _u("gran_superficie", "Gran superficie / hipermercado", "Comercial",
       "Mass Merchandising Sales Area - Retail", 15.0, 250, 200, 1.11, 0.1, 21, 25, F_RITE_T,
       _ida(3)),
    # --- Logística e industria ------------------------------------------------------------
    _u("almacen", "Almacén / logística (picking)", "Logística", "Active Storage", 3.0, 250, 200,
       0.8, 0.3, 14, 25, F_RD486_T, _TRABAJO),
    _u("almacen_voluminoso", "Almacén de mercancía voluminosa", "Logística",
       "Medium/Bulky Material - Warehouse", 10.0, 250, 200, 0.9, 0.3, 14, 25, F_RD486_T,
       _TRABAJO),
    _u("almacen_sin_personal", "Almacén sin presencia permanente", "Logística",
       "Inactive Storage", 3.0, 250, 200, 0.3, 0.3, 14, 25, F_RD486_T, _sup(4)),
    _u("produccion_nave_alta", "Producción, nave alta", "Industria",
       "General High Bay - Manufacturing Facility", 10.0, 250, 200, 1.7, 1.0, 14, 25, F_RD486_T,
       _TRABAJO, nota="Las cargas de proceso (máquinas, hornos…) se añaden como equipos."),
    _u("produccion_nave_baja", "Producción, nave baja", "Industria",
       "General Low Bay - Manufacturing Facility", 10.0, 250, 200, 1.2, 1.0, 14, 25, F_RD486_T,
       _TRABAJO),
    _u("produccion_precision", "Producción de precisión / montaje", "Industria",
       "Detailed - Manufacturing Facility", 10.0, 250, 200, 2.1, 1.0, 21, 25, F_RITE_T, _TRABAJO),
    _u("sala_maquinas", "Sala de máquinas / compresores", "Industria",
       "Equipment Room - Manufacturing Facility", 3.0, 250, 200, 1.2, 1.0, 14, 25, F_RD486_T,
       _sup(4)),
    # --- Frío -----------------------------------------------------------------------------
    _u("camara_refrigeracion", "Cámara de refrigeración (0–4 °C)", "Frío", "Active Storage",
       3.0, 250, 200, 0.8, 0.3, None, 2, "Producto fresco refrigerado, 0–4 °C",
       _SIN_VENTILACION, **_persona_frio(2),
       nota="La carga de producto (kg/día y su enfriamiento) se añade como proceso."),
    _u("camara_congelacion", "Cámara de congelación (−20 °C)", "Frío", "Active Storage", 3.0,
       250, 200, 0.8, 0.3, None, -20,
       "RD 1109/1991: ultracongelados a −18 °C o menos; cámara a −20 °C", _SIN_VENTILACION,
       **_persona_frio(-20),
       nota="La carga de producto (kg/día y su congelación) se añade como proceso."),
    _u("sala_manipulacion", "Sala de manipulación refrigerada (12 °C)", "Frío",
       "Detailed - Manufacturing Facility", 10.0, 250, 200, 2.1, 1.0, None, 12,
       F_DESPIECE, _TRABAJO, **_persona_frio(12)),
    # --- Salas limpias --------------------------------------------------------------------
    _u("sala_limpia_iso8", "Sala limpia ISO 8", "Salas limpias", "Laboratory - Office", 5.0,
       250, 200, 1.4, 1.5, 21, 25, F_RITE_T, _ida(1), impulsion_renovaciones=17.5,
       nota="Impulsión 10–25 renovaciones/h (punto medio)."),
    _u("sala_limpia_iso7", "Sala limpia ISO 7", "Salas limpias", "Laboratory - Office", 5.0,
       250, 200, 1.4, 1.5, 21, 25, F_RITE_T, _ida(1), impulsion_renovaciones=45.0,
       nota="Impulsión 30–60 renovaciones/h (punto medio)."),
    _u("sala_limpia_iso6", "Sala limpia ISO 6", "Salas limpias", "Laboratory - Office", 5.0,
       250, 200, 1.4, 1.5, 21, 25, F_RITE_T, _ida(1), impulsion_renovaciones=135.0,
       nota="Impulsión 90–180 renovaciones/h (punto medio)."),
    # --- Otros ----------------------------------------------------------------------------
    _u("piscina", "Piscina climatizada", "Otros", "Exercise Area - Exercise Center", 30.0, 710,
       1090, 0.93, 0.54, 28, 30,
       "RITE IT 1.1.4.1.2.3: aire 1–2 °C por encima del agua, máximo 30 °C",
       Ventilacion("lamina", 2.5, "RITE IT 1.1.4.2.3.2: 2,5 dm³/s por m² de lámina y playa"),
       nota="Falta la carga de evaporación del vaso: se añade como proceso latente."),
    _u("centro_calculo", "Centro de cálculo / sala de servidores", "Otros",
       "Electrical/Mechanical", 3.0, 250, 200, 1.5, 0.3, 21, 25, F_RITE_T, _ida(3),
       cobertura="alta", nota="La carga de los equipos informáticos se añade como equipo."),
)  # fmt: skip

POR_CLAVE = {u.clave: u for u in USOS}
GRUPOS = tuple(dict.fromkeys(u.grupo for u in USOS))


def caudal_exterior_m3h(uso: Uso, area_m2: float, personas: float) -> float:
    """Aire exterior mínimo del espacio (m³/h) según el método de ventilación de su uso.

    - persona_ida: RITE tabla 1.4.2.1 (dm³/s por persona);
    - superficie_ida: RITE tabla 1.4.2.4 (dm³/s·m²);
    - trabajador: RD 486/1997 (m³/h por trabajador);
    - fijo: caudal del local (quirófano, UNE 100713);
    - lamina: RITE, piscinas, por m² de lámina y playa; se toma la superficie del espacio
      (sin zona de espectadores);
    - ninguna: cámaras frigoríficas.
    """
    v = uso.ventilacion
    if v.metodo == "persona_ida":
        return personas * IDA_PERSONA[int(v.valor)] * 3.6
    if v.metodo == "superficie_ida":
        return area_m2 * IDA_SUPERFICIE[int(v.valor)] * 3.6
    if v.metodo == "trabajador":
        return personas * v.valor
    if v.metodo == "fijo":
        return v.valor
    if v.metodo == "lamina":
        return area_m2 * v.valor * 3.6
    if v.metodo == "ninguna":
        return 0.0
    raise ValueError(f"Método de ventilación no previsto: «{v.metodo}».")


# --- Huecos en fachada --------------------------------------------------------------------
# Decisión del usuario (07-11-2026): «% por fachada», propuesto y modificable. Fuente:
# ASHRAE 90.1-2019, apéndice G, tabla G3.1.1-1 (huecos verticales del edificio de referencia,
# en fracción de la superficie bruta de fachada), tal como la incorpora NREL en
# openstudio-standards (ashrae_90_1_prm_2019.prm_wwr_bldg_type.json).
F_ASHRAE_901 = "ASHRAE 90.1-2019, tabla G3.1.1-1"
F_SIN_HUECOS = (
    "Local sin huecos al exterior (práctica habitual en cámaras, salas limpias, quirófanos y CPD)"
)
_WWR = {
    "Oficinas": (0.31, f"{F_ASHRAE_901}: oficina de 5000 a 50 000 ft²"),
    "Hotel": (0.34, f"{F_ASHRAE_901}: hotel de más de 75 habitaciones"),
    "Sanitario": (0.27, f"{F_ASHRAE_901}: hospital"),
    "Comercial": (0.11, f"{F_ASHRAE_901}: comercio independiente"),
    "Logística": (0.06, f"{F_ASHRAE_901}: almacén no refrigerado"),
    "Industria": (0.06, f"{F_ASHRAE_901}: almacén no refrigerado (nave)"),
    "Frío": (0.0, F_SIN_HUECOS),
    "Salas limpias": (0.0, F_SIN_HUECOS),
    "Otros": (0.40, f"{F_ASHRAE_901}: resto de usos"),
}
_WWR_USO = {
    "comedor": (0.24, f"{F_ASHRAE_901}: restaurante"),
    "cocina": (0.24, f"{F_ASHRAE_901}: restaurante"),
    "restaurante_hotel": (0.24, f"{F_ASHRAE_901}: restaurante"),
    "consulta": (0.21, f"{F_ASHRAE_901}: centro sanitario ambulatorio"),
    "supermercado": (0.07, f"{F_ASHRAE_901}: supermercado"),
    "gran_superficie": (0.07, f"{F_ASHRAE_901}: supermercado"),
    "centro_calculo": (0.0, F_SIN_HUECOS),
    "quirofano": (0.0, F_SIN_HUECOS),
}


def huecos(uso: Uso) -> tuple[float, str]:
    """Fracción de huecos en fachada propuesta para el uso, con su fuente."""
    return _WWR_USO.get(uso.clave) or _WWR[uso.grupo]
