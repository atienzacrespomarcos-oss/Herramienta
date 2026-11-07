"""Cargas y ventilación de los espacios del proyecto (Etapa 4, docs/modules/cargas.md).

Junta el clima (guía del IDAE del usuario), la geometría confirmada (contornos, alturas,
niveles), el uso de cada espacio y los cerramientos típicos del tipo de construcción, y
llama a los motores. Lo propuesto se calcula cada vez desde el catálogo con su fuente; lo
que el usuario cambia manda. Cada dato del resultado dice de dónde sale (línea roja 2).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any

from traza.engines import cargas as cg
from traza.engines import clima as motor_clima
from traza.engines import envolvente as env
from traza.io.clima_idae import EstacionIdae
from traza.rules import cerramientos as tc
from traza.rules import usos as catalogo

#: Origen de cada dato del informe.
PROPUESTA, USUARIO, PLANO, CALCULO = "propuesta", "usuario", "plano", "cálculo"


@dataclass(frozen=True)
class Dato:
    concepto: str
    valor: Any
    unidad: str
    origen: str
    fuente: str


@dataclass(frozen=True)
class CargaEspacio:
    espacio_id: str
    codigo: str
    nombre: str
    nivel: str
    uso: catalogo.Uso
    uso_origen: str  # usuario | propuesta (por el nombre del espacio)
    superficie_m2: float
    altura_m: float
    volumen_m3: float
    datos: tuple[Dato, ...]
    fachadas_m: dict[str, float]  # sector → longitud de fachada (tras las correcciones)
    tramos: tuple[env.Tramo, ...]  # los mismos, dibujables (m, coordenadas del plano)
    cerramientos: tuple[cg.Cerramiento, ...]
    aire_exterior_m3h: float
    infiltracion_m3h: float
    impulsion_m3h: float | None
    invierno: cg.Resultado
    verano: cg.Resultado


@dataclass(frozen=True)
class ResultadoCargas:
    estacion: EstacionIdae
    zona: str
    provincia: str
    altitud_obra_m: float
    tipo_construccion: str
    envolvente: tc.Envolvente
    mes: int
    condiciones: dict[str, motor_clima.CondicionesProyecto]
    espacios: tuple[CargaEspacio, ...]
    hora_simultanea: int
    verano_simultaneo_w: float
    avisos: tuple[str, ...] = field(default=())

    @property
    def invierno_total_w(self) -> float:
        return sum(e.invierno.total_w for e in self.espacios)


# --- Uso propuesto por el nombre del espacio ------------------------------------------
# Se recorre en orden y compara por «contiene»: lo específico antes que lo general, o el
# término largo queda inalcanzable («cámara de congelación» antes que «cámara»). Sin
# palabras ambiguas en logística: «rack» o «cuadro» daban «Almacén de racks» → CPD
# (revisión 07-11-2026).
PALABRAS_USO = (
    ("quirofano", "quirofano"),
    ("reanimacion", "reanimacion"),
    ("uci", "reanimacion"),
    ("hospitalizacion", "habitacion_hospital"),
    ("consulta", "consulta"),
    ("laboratorio", "laboratorio"),
    ("sala limpia", "sala_limpia_iso8"),
    ("sala blanca", "sala_limpia_iso8"),
    ("congelacion", "camara_congelacion"),
    ("congelado", "camara_congelacion"),
    ("camara", "camara_refrigeracion"),
    ("manipulacion", "sala_manipulacion"),
    ("cpd", "centro_calculo"),
    ("servidores", "centro_calculo"),
    ("sala tecnica", "sala_tecnica"),
    ("instalaciones", "sala_tecnica"),
    ("compresores", "sala_maquinas"),
    ("sala de maquinas", "sala_maquinas"),
    ("despacho", "despacho"),
    ("reunion", "reuniones"),
    ("juntas", "reuniones"),
    ("formacion", "reuniones"),
    ("oficina", "oficina_abierta"),
    ("administracion", "oficina_abierta"),
    ("recepcion", "vestibulo"),
    ("vestibulo", "vestibulo"),
    ("hall", "vestibulo"),
    ("pasillo", "pasillo"),
    ("distribuidor", "pasillo"),
    ("vestuario", "vestuarios"),
    ("aseo", "aseos"),
    ("bano", "aseos"),
    ("wc", "aseos"),
    ("comedor", "comedor"),
    ("cocina", "cocina"),
    ("restaurante", "restaurante_hotel"),
    ("habitacion", "habitacion_hotel"),
    ("gimnasio", "gimnasio"),
    ("piscina", "piscina"),
    ("salon", "salon_eventos"),
    ("supermercado", "supermercado"),
    ("sala de ventas", "supermercado"),
    ("tienda", "tienda"),
    ("produccion", "produccion_nave_alta"),
    ("fabricacion", "produccion_nave_alta"),
    ("montaje", "produccion_precision"),
    ("taller", "produccion_nave_baja"),
    ("almacen", "almacen"),
    ("muelle", "almacen"),
    ("expedicion", "almacen"),
    ("logistica", "almacen"),
)


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.casefold().split())


def uso_por_nombre(nombre: str) -> str | None:
    n = _normalizar(nombre)
    for palabra, clave in PALABRAS_USO:
        if palabra in n:
            return clave
    return None


# --- Cálculo ----------------------------------------------------------------------------


def _datos_estacion(e: EstacionIdae) -> motor_clima.DatosEstacion:
    return motor_clima.DatosEstacion(
        e.altitud_m, e.ts_996, e.ts_99, e.hum_coin, e.ts_04, e.thc_04, e.ts_1, e.thc_1
    )


def _clase_ventana(tipo: str, letra: str) -> int:
    """Clase de permeabilidad de las ventanas (UNE-EN 12207) supuesta por tipo: la que
    exige el CTE (tabla 3.1.3.a-HE1) en obra nueva; clase 2 en naves de panel; clase 1
    (la peor) en chapa y edificios antiguos."""
    if tipo == "cte":
        return 3 if letra in ("C", "D", "E") else 2
    return 2 if tipo == "nave_panel" else 1


def calcular(
    config: dict[str, Any],
    estacion: EstacionIdae,
    espacios: list[dict[str, Any]],
    niveles: list[dict[str, Any]],
    datos_espacios: dict[str, dict[str, Any]],
) -> ResultadoCargas:
    """`espacios`: los de Proyecto.espacios(); `datos_espacios`: filas de cargas_espacio
    por id, con `ajustes` y `fachadas` ya decodificados."""
    zona = tc.zona_climatica(config["provincia"], config["altitud_obra"])
    tipo = config["tipo_construccion"]
    contexto = _Contexto(
        config,
        tc.envolvente(tipo, zona),
        zona,
        tipo,
        cg.ALFA_HO[config["color"]],
        {
            c: motor_clima.condiciones(_datos_estacion(estacion), c, config["altitud_obra"])
            for c in motor_clima.COBERTURAS
        },
        estacion,
    )
    nivel_cota = {n["id"]: n["cota"] for n in niveles}
    avisos: list[str] = []
    por_nivel: dict[str, list[env.Planta]] = {}
    for e in espacios:
        por_nivel.setdefault(e["padre_id"], []).append(
            env.Planta(e["id"], tuple(e["contorno"].aplanado()))
        )
    automaticas: dict[str, list[env.Tramo]] = {}
    for plantas in por_nivel.values():
        automaticas.update(env.tramos(plantas, config["norte"]))

    # 1.ª pasada: lo que cada espacio necesita y lo que impide calcularlo (con aviso).
    validos: list[_Candidato] = []
    for e in espacios:
        nombre = e["nombre"] or e["codigo"]
        fila = datos_espacios.get(e["id"])
        if fila is not None:
            clave_uso, uso_origen = fila["uso"], USUARIO
        else:
            clave_uso, uso_origen = uso_por_nombre(nombre), PROPUESTA
        motivo = None
        altura = e["altura"]
        if altura is None and e["altura_minima"] is not None and e["altura_maxima"] is not None:
            altura = (e["altura_minima"] + e["altura_maxima"]) / 2
        cota = nivel_cota.get(e["padre_id"])
        if clave_uso is None:
            motivo = "sin uso; elige uno para calcularlo"
        elif clave_uso not in catalogo.POR_CLAVE:
            motivo = f"uso «{clave_uso}» que ya no está en el catálogo; elige otro"
        elif not e["superficie"] or e["superficie"] <= 0:
            motivo = "sin superficie; revisa su contorno en el paso Planos"
        elif altura is None:
            motivo = "sin altura; ponla en el paso Planos"
        elif cota is None:
            motivo = "su nivel no tiene cota; ponla en el paso Planos"
        if motivo:
            avisos.append(f"{e['codigo']} «{nombre}»: {motivo}.")
            continue
        correcciones = fila["fachadas"] if fila else {}
        # «Es fachada» toma todos los lados del sector (como si no tuviera vecinos); «no
        # es fachada» los quita.
        solo = env.tramos([env.Planta(e["id"], tuple(e["contorno"].aplanado()))], config["norte"])
        tramos = [t for t in automaticas[e["id"]] if t.sector not in correcciones]
        tramos += [t for t in solo[e["id"]] if correcciones.get(t.sector)]
        techo = cota + (e["altura_maxima"] or altura)
        validos.append(
            _Candidato(
                e,
                nombre,
                catalogo.POR_CLAVE[clave_uso],
                uso_origen,
                altura,
                cota,
                techo,
                fila["ajustes"] if fila else {},
                tuple(tramos),
            )
        )

    # Solera: los espacios de la cota más baja. Su U, con la losa entera (UNE-EN ISO 13370:
    # B' = A/(0,5·P) de toda la planta en contacto con el terreno, no de cada local).
    cota_baja = min((c.cota for c in validos), default=None)
    en_terreno = [c for c in validos if c.cota == cota_baja]
    if contexto.envolvente.u_terreno is not None:
        u_terreno = contexto.envolvente.u_terreno
    else:
        area_losa = sum(c.e["superficie"] for c in en_terreno)
        perimetro = sum(t.largo for c in en_terreno for t in c.tramos)
        u_terreno = tc.u_solera(area_losa, perimetro) if area_losa and perimetro else 0.0

    resultados = []
    for c in validos:
        encima = [
            o.e["contorno"]
            for o in validos
            if o is not c
            and (
                o.cota >= c.techo - TOLERANCIA_FORJADO_M
                or (o.cota < c.cota and o.techo > c.techo + TOLERANCIA_FORJADO_M)
            )
        ]
        cubierta = c.e["superficie"] * _fraccion_descubierta(c.e["contorno"], encima)
        solera = u_terreno if c.cota == cota_baja else None
        resultados.append(_espacio(c, contexto, cubierta, solera))

    # Simultánea de la climatización: sin las cámaras (su frío es otra instalación).
    climatizados = [r for r in resultados if r.uso.grupo not in GRUPOS_FUERA_SIMULTANEA]
    hora, total = 0, 0.0
    if climatizados:
        suma = [sum(r.verano.perfil_w[k] for r in climatizados) for k in range(24)]
        k = max(range(24), key=lambda i: suma[i])
        hora, total = k + 1, suma[k]
    return ResultadoCargas(
        estacion,
        zona,
        config["provincia"],
        config["altitud_obra"],
        tipo,
        contexto.envolvente,
        config["mes"],
        contexto.condiciones,
        tuple(resultados),
        hora,
        total,
        tuple(avisos),
    )


#: Un espacio de un nivel cuya cota está a menos de esto del techo de otro lo cubre (forjado).
TOLERANCIA_FORJADO_M = 0.5
#: Fuera de la simultánea de climatización: las cámaras tienen su propia instalación de frío.
GRUPOS_FUERA_SIMULTANEA = ("Frío",)
#: Rejilla para medir qué parte de la planta queda bajo otro espacio (aproximación declarada).
REJILLA = 30


@dataclass(frozen=True)
class _Contexto:
    config: dict[str, Any]
    envolvente: tc.Envolvente
    zona: str
    tipo: str
    alfa: float
    condiciones: dict[str, motor_clima.CondicionesProyecto]
    estacion: EstacionIdae


@dataclass(frozen=True)
class _Candidato:
    e: dict[str, Any]
    nombre: str
    uso: catalogo.Uso
    uso_origen: str
    altura: float
    cota: float
    techo: float
    ajustes: dict[str, Any]
    tramos: tuple[env.Tramo, ...]


def _fraccion_descubierta(contorno, encima: list) -> float:
    """Fracción de la planta sin otro espacio encima, por muestreo en una rejilla de
    REJILLA × REJILLA puntos (aproximación declarada en el informe)."""
    pts = contorno.aplanado()
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    candidatos = []
    for o in encima:
        q = o.aplanado()
        if not (
            max(p[0] for p in q) < x0
            or min(p[0] for p in q) > x1
            or max(p[1] for p in q) < y0
            or min(p[1] for p in q) > y1
        ):
            candidatos.append(o)
    if not candidatos:
        return 1.0
    dentro = cubiertos = 0
    for i in range(REJILLA):
        x = x0 + (i + 0.5) * (x1 - x0) / REJILLA
        for j in range(REJILLA):
            y = y0 + (j + 0.5) * (y1 - y0) / REJILLA
            if contorno.contiene(x, y):
                dentro += 1
                if any(o.contiene(x, y) for o in candidatos):
                    cubiertos += 1
    return 1.0 - cubiertos / dentro if dentro else 1.0


def _dato(concepto, propuesto, fuente, unidad, ajustes, clave):
    if clave in ajustes:
        return Dato(concepto, ajustes[clave], unidad, USUARIO, "Cambiado por el usuario"), ajustes[
            clave
        ]
    return Dato(concepto, propuesto, unidad, PROPUESTA, fuente), propuesto


def propuestas(uso: catalogo.Uso, area_m2: float, personas: float | None = None):
    """Lo propuesto para un uso y una superficie: clave de ajuste → (concepto, valor, unidad,
    fuente). Las claves son las de `ordenes.AJUSTES_CARGAS` (lo comprueba una prueba). El
    aire exterior se propone con `personas` si el usuario ha cambiado la ocupación."""
    ocupacion = round(uso.personas_100m2 * area_m2 / 100, 1)
    f_personas = uso.fuente_calor_persona or (
        f"{catalogo.F_ASHRAE} ({uso.tipo_ashrae}); 1 Btu/h = 0,29307 W"
    )
    f_dens = f"{catalogo.F_ASHRAE} ({uso.tipo_ashrae}); 1 W/ft² = 10,764 W/m²"
    sin_proceso = "Sin proceso salvo que se indique"
    wwr, f_wwr = catalogo.huecos(uso)
    f_inv = uso.fuente_temperaturas if uso.t_invierno is not None else "Sin calefacción"
    aire = catalogo.caudal_exterior_m3h(uso, area_m2, ocupacion if personas is None else personas)
    return {
        "personas": (
            "Ocupación",
            ocupacion,
            "personas",
            f"{catalogo.F_ASHRAE} ({uso.tipo_ashrae}): {uso.personas_100m2:g} personas/100 m²",
        ),
        "sensible_persona_w": ("Calor sensible por persona", uso.sensible_w, "W", f_personas),
        "latente_persona_w": ("Calor latente por persona", uso.latente_w, "W", f_personas),
        "iluminacion_w_m2": ("Iluminación", uso.iluminacion_w_m2, "W/m²", f_dens),
        "equipos_w_m2": ("Equipos", uso.equipos_w_m2, "W/m²", f_dens),
        "proceso_sensible_w": ("Proceso, sensible", 0.0, "W", sin_proceso),
        "proceso_latente_w": ("Proceso, latente", 0.0, "W", sin_proceso),
        "t_invierno_c": ("Temperatura de invierno", uso.t_invierno, "°C", f_inv),
        "t_verano_c": ("Temperatura de verano", uso.t_verano, "°C", uso.fuente_temperaturas),
        "aire_exterior_m3h": ("Aire exterior", aire, "m³/h", uso.ventilacion.fuente),
        "huecos": ("Huecos en fachada", wwr, "fracción", f_wwr),
    }


def _espacio(
    c: _Candidato, ctx: _Contexto, area_cubierta: float, u_solera: float | None
) -> CargaEspacio:
    e, nombre, uso, uso_origen, altura = c.e, c.nombre, c.uso, c.uso_origen, c.altura
    ajustes, cota, tramos = c.ajustes, c.cota, list(c.tramos)
    config, envolvente, zona, tipo, alfa = ctx.config, ctx.envolvente, ctx.zona, ctx.tipo, ctx.alfa
    condiciones, estacion, mes = ctx.condiciones, ctx.estacion, ctx.config["mes"]
    area = e["superficie"]
    volumen = area * altura
    datos: list[Dato] = [
        Dato("Superficie", area, "m²", PLANO, "Contorno confirmado del plano"),
        Dato("Altura", altura, "m", PLANO, f"Altura {e['altura_origen'] or 'media'}"),
        Dato(
            "Uso",
            uso.nombre,
            "",
            uso_origen,
            "Elegido por el usuario" if uso_origen == USUARIO else "Propuesto por el nombre",
        ),
    ]

    personas_propuestas = propuestas(uso, area)["personas"][1]
    props = propuestas(uso, area, ajustes.get("personas", personas_propuestas))
    v: dict[str, Any] = {}
    for clave, (concepto, valor, unidad, fuente) in props.items():
        if clave == "t_invierno_c" and ajustes.get("sin_calefaccion"):
            datos.append(Dato(concepto, None, unidad, USUARIO, "Sin calefacción"))
            v[clave] = None
            continue
        d, v[clave] = _dato(concepto, valor, fuente, unidad, ajustes, clave)
        datos.append(d)
    personas, sens, lat = v["personas"], v["sensible_persona_w"], v["latente_persona_w"]
    luz, equipos = v["iluminacion_w_m2"], v["equipos_w_m2"]
    proc_s, proc_l = v["proceso_sensible_w"], v["proceso_latente_w"]
    t_inv, t_ver, aire = v["t_invierno_c"], v["t_verano_c"], v["aire_exterior_m3h"]
    frac_huecos = v["huecos"]

    fachadas = env.longitudes(tramos)

    cerr: list[cg.Cerramiento] = []
    area_opaca = area_huecos = 0.0
    for s in env.SECTORES:
        largo = fachadas.get(s)
        if not largo:
            continue
        bruta = largo * altura
        huecos = bruta * frac_huecos
        az = env.AZIMUT_SECTOR[s]
        cerr.append(
            cg.Cerramiento(
                f"Fachada {s}", "opaco", bruta - huecos, envolvente.u_muro, azimut=az, alfa_ho=alfa
            )
        )
        if huecos > 0:
            cerr.append(
                cg.Cerramiento(
                    f"Huecos {s}",
                    "hueco",
                    huecos,
                    envolvente.hueco.u,
                    azimut=az,
                    factor_solar=envolvente.hueco.factor_solar,
                )
            )
        area_opaca += bruta - huecos
        area_huecos += huecos
    if area_cubierta > 1e-6:
        cerr.append(
            cg.Cerramiento(
                "Cubierta",
                "opaco",
                area_cubierta,
                envolvente.u_cubierta,
                azimut=0,
                inclinacion=0,
                alfa_ho=alfa,
            )
        )
        area_opaca += area_cubierta
    if u_solera:
        cerr.append(cg.Cerramiento("Solera", "terreno", area, u_solera, inclinacion=180))

    letra = tc.letra_invierno(zona)
    co = cg.CO_OPACO["nuevo" if tipo in ("cte", "nave_panel") else "existente"]
    ch = cg.CH_CLASE[_clase_ventana(tipo, letra)]
    infil = 0.0
    if area_opaca + area_huecos > 0:
        n50 = cg.n50(volumen, area_opaca, area_huecos, co, ch)
        infil = cg.infiltracion_m3h(volumen, n50, len(fachadas), cota + altura / 2)
    datos.append(
        Dato(
            "Infiltración",
            infil,
            "m³/h",
            CALCULO,
            f"UNE-EN 12831 con n50 del CTE DB HE, Anejo H (Co {co:g}, Ch {ch:g})",
        )
    )
    impulsion = None
    if uso.impulsion_renovaciones:
        impulsion = uso.impulsion_renovaciones * volumen
        datos.append(
            Dato(
                "Impulsión (sala limpia)",
                impulsion,
                "m³/h",
                PROPUESTA,
                f"{uso.impulsion_renovaciones:g} renovaciones/h ({uso.nota})",
            )
        )

    cond = condiciones[uso.cobertura]
    clima = cg.Clima(
        latitud=estacion.latitud,
        presion_pa=cond.presion_pa,
        invierno_ts_c=cond.invierno_ts,
        verano_ts_c=cond.verano_ts,
        verano_w=cond.verano_w,
        oscilacion_c=estacion.omdr,
        mes=mes,
    )
    espacio = cg.Espacio(
        nombre=nombre,
        area_m2=area,
        volumen_m3=volumen,
        t_invierno_c=t_inv,
        t_verano_c=t_ver,
        personas=personas,
        sensible_persona_w=sens,
        latente_persona_w=lat,
        iluminacion_w=luz * area,
        equipos_w=equipos * area,
        proceso_sensible_w=proc_s,
        proceso_latente_w=proc_l,
        aire_exterior_m3h=aire,
        infiltracion_m3h=infil,
        recuperacion=config["recuperacion"],
        cerramientos=tuple(cerr),
    )
    return CargaEspacio(
        e["id"],
        e["codigo"],
        nombre,
        e["nivel_nombre"] or "",
        uso,
        uso_origen,
        area,
        altura,
        volumen,
        tuple(datos),
        fachadas,
        tuple(tramos),
        tuple(cerr),
        aire,
        infil,
        impulsion,
        cg.invierno(espacio, clima),
        cg.verano(espacio, clima),
    )
