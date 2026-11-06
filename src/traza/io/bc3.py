"""Lector de ficheros BC3 (formato FIEBDC-3).

Fuente: «Formato FIEBDC-3/2024», Asociación FIEBDC,
https://www.fiebdc.es/web2/datos/uploads/Formato-FIEBDC-3-2024.pdf (consultado 06-11-2026).
Cada regla aplicada cita su página. Lo que la especificación permite y este lector aún no
interpreta se declara como aviso; nunca se rellena con un valor supuesto.

El lector es puro (no toca la base de datos ni la interfaz): devuelve lo leído y los avisos.

Historial de fallos corregidos (revisión del 06-11-2026), para no reintroducirlos:
- Las líneas de porcentaje de un ~D («%», «&») se importaban como partidas.
- Un concepto citado por un código sinónimo se perdía.
- Dos apariciones de la misma partida en un capítulo mezclaban sus mediciones (POSICION).
- El precio no seguía la norma: si se puede calcular por descomposición, manda la
  descomposición (págs. 8 y 10).
- La cantidad era factor × rendimiento y debía ser el rendimiento (pág. 22).
- Sin rendimiento explícito ni ~M, se daba 1 como cantidad: ahora «no consta».
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

LECTOR = "bc3"
VERSION_LECTOR = "1.1.0"

# Pág. 4: «850 ó 437» (D.O.S.) o «ANSI» (Windows); vacío = 850 por compatibilidad.
_JUEGOS = {"850": "cp850", "437": "cp437", "ANSI": "cp1252", "": "cp850"}
_BLANCOS = " \t\r\n"  # pág. 2: blancos (32), tabuladores (9) y fines de línea (13 y 10)
# Tolerancia para comparar el precio del ~C con el de su descomposición: medio céntimo
# (diferencias de redondeo al céntimo). Es criterio de TRAZA, no de la norma.
_TOLERANCIA_PRECIO = 0.005


class Bc3Error(ValueError):
    """El fichero no se puede leer como BC3 según la especificación."""


@dataclass
class Concepto:
    codigo: str  # sin «#»/«##» (pág. 8: con y sin # es el mismo concepto)
    codigo_original: str = ""  # tal como figura en el ~C (con # o ##), para localizarlo
    sinonimos: list[str] = field(default_factory=list)
    unidad: str | None = None
    resumen: str | None = None
    precios: list[float | None] = field(default_factory=list)  # posición = rótulo del ~V
    tipo: str | None = None
    texto: str | None = None
    es_raiz: bool = False
    es_capitulo: bool = False


@dataclass
class LineaD:
    hijo: str
    factor: float | None  # None = no figura (pág. 9: por defecto 1.0)
    rendimiento: float | None  # None = no figura (pág. 9: por defecto 1.0)
    es_porcentaje: bool  # pág. 9: código con «%» o «&»
    numero: int  # posición en la descomposición, desde 1, contando como en el fichero


@dataclass
class MedicionM:
    padre: str | None
    hijo: str
    posicion: list[int]
    total: float | None
    etiqueta: str | None
    lineas: int


@dataclass
class PartidaLeida:
    capitulos: list[tuple[str, str]]  # [(código, resumen)] desde el primer nivel
    codigo: str
    unidad: str | None
    resumen: str | None
    texto: str | None
    cantidad: float | None  # None = no consta
    precio: float | None  # None = no consta
    etiqueta: str | None
    localizador: str  # dónde está en el fichero, para la procedencia


@dataclass
class Bc3:
    version_formato: str | None = None
    programa: str | None = None
    juego_caracteres: str = ""
    tipo_informacion: str | None = None
    raiz: str | None = None
    conceptos: dict[str, Concepto] = field(default_factory=dict)
    alias: dict[str, str] = field(default_factory=dict)  # sinónimo → código principal
    descomposiciones: dict[str, list[LineaD]] = field(default_factory=dict)
    mediciones: list[MedicionM] = field(default_factory=list)
    no_interpretados: Counter = field(default_factory=Counter)
    avisos: list[str] = field(default_factory=list)

    def resolver(self, codigo: str) -> str:
        """Código principal de un concepto citado por cualquiera de sus códigos (pág. 7)."""
        return self.alias.get(codigo, codigo)

    def concepto(self, codigo: str) -> Concepto | None:
        return self.conceptos.get(self.resolver(codigo))


# --- Sintaxis (pág. 2) --------------------------------------------------------------


def _limpio(texto: str) -> str:
    # Pág. 2: se ignoran blancos, tabuladores y fines de línea DELANTE de los separadores.
    return texto.rstrip(_BLANCOS)


def _campos(registro: str) -> list[str]:
    # Pág. 2: se ignora lo que hay entre el último «|» y el siguiente «~».
    if "|" not in registro:
        return [registro.strip()]
    cuerpo = registro[: registro.rfind("|")]
    return [_limpio(c) for c in cuerpo.split("|")]


def _sub(campo: str) -> list[str]:
    """Subcampos separados por «\\». El separador final es opcional (pág. 2)."""
    partes = [_limpio(s) for s in campo.split("\\")]
    if partes and partes[-1] == "":
        partes.pop()
    return partes


def _numero(texto: str, donde: str) -> float | None:
    t = texto.strip()
    if not t:
        return None  # pág. 2: campo vacío = SIN INFORMACIÓN, no cero
    try:
        # Pág. 3: sin separador de miles y con punto decimal.
        return float(t)
    except ValueError:
        raise Bc3Error(f"Número no válido «{texto}» en {donde}.") from None


def _codigo(texto: str) -> tuple[str, bool, bool]:
    t = texto.strip()
    if t.endswith("##"):
        return t[:-2], True, False
    if t.endswith("#"):
        return t[:-1], False, True
    return t, False, False


# --- Lectura ------------------------------------------------------------------------


def _juego_caracteres(crudo: bytes) -> str:
    # El ~V está «al comienzo del primer archivo» (pág. 4) y es ASCII: se busca leyendo
    # como latin-1 (que nunca falla) solo para encontrar ese campo.
    provisional = crudo.decode("latin-1")
    for reg in provisional.split("~")[1:]:
        campos = _campos(reg)
        if campos and campos[0] == "V":
            return campos[5].strip().upper() if len(campos) > 5 else ""
    return ""


def leer_bc3(ruta: Path) -> Bc3:
    crudo = Path(ruta).read_bytes()
    juego = _juego_caracteres(crudo)
    if juego not in _JUEGOS:
        raise Bc3Error(
            f"Juego de caracteres «{juego}» no previsto en FIEBDC-3 (admite 850, 437 o ANSI; "
            "pág. 4). No se interpreta para no leer mal tildes y eñes."
        )
    try:
        texto = crudo.decode(_JUEGOS[juego])
    except UnicodeDecodeError as exc:
        raise Bc3Error(
            f"El fichero declara el juego «{juego or '850'}» pero contiene bytes que no "
            f"pertenecen a él (posición {exc.start}). No se interpreta para no leer mal tildes."
        ) from None
    return leer_bc3_texto(texto, juego)


def leer_bc3_texto(texto: str, juego: str = "") -> Bc3:
    b = Bc3(juego_caracteres=juego)
    registros = texto.split("~")[1:]  # pág. 2: lo anterior al primer «~» se ignora
    if not registros:
        raise Bc3Error("No hay ningún registro «~»: no es un fichero BC3.")
    pendientes_d: list[tuple[list[str], str]] = []
    pendientes_m: list[tuple[list[str], str]] = []
    pendientes_t: list[list[str]] = []
    for n, reg in enumerate(registros, start=1):
        campos = _campos(reg)
        if not campos or not campos[0]:
            continue
        cab = campos[0]
        donde = f"registro {n} (~{cab})"
        # ~C se lee primero entero: así los sinónimos se conocen antes de resolver ~D, ~M
        # y ~T (pág. 2: la disposición de registros es libre).
        if cab == "V":
            _leer_v(b, campos)
        elif cab == "C":
            _leer_c(b, campos, donde)
        elif cab == "D":
            pendientes_d.append((campos, donde))
        elif cab == "M":
            pendientes_m.append((campos, donde))
        elif cab == "T":
            pendientes_t.append(campos)
        else:
            b.no_interpretados[cab] += 1
    for campos, donde in pendientes_d:
        _leer_d(b, campos, donde)
    for campos, donde in pendientes_m:
        _leer_m(b, campos, donde)
    for campos in pendientes_t:
        _leer_t(b, campos)
    raices = [c for c in b.conceptos.values() if c.es_raiz]
    if len(raices) > 1:
        # Pág. 8: «Únicamente puede haber un concepto raíz».
        raise Bc3Error(f"Hay {len(raices)} conceptos raíz («##»); la especificación admite uno.")
    b.raiz = raices[0].codigo if raices else None
    if b.tipo_informacion == "1":
        # Pág. 4: tipo 1 = base de datos (banco de precios), no un presupuesto.
        b.avisos.append(
            "El fichero se declara «base de datos» (tipo 1), no presupuesto: sus cantidades "
            "no son mediciones de obra."
        )
    if b.no_interpretados:
        tipos = ", ".join(f"~{k} ({v})" for k, v in sorted(b.no_interpretados.items()))
        b.avisos.append(f"Registros conservados sin interpretar: {tipos}.")
    return b


def _leer_v(b: Bc3, c: list[str]) -> None:
    # Pág. 4: ~V | PROPIEDAD | VERSION[\fecha] | PROGRAMA | CABECERA\{ROTULO\} | JUEGO |
    #            COMENTARIO | TIPO INFORMACIÓN | ...
    def campo(i: int) -> str | None:
        return (c[i].strip() or None) if len(c) > i else None

    version = campo(2)
    b.version_formato = _sub(version)[0] if version else None
    b.programa = campo(3)
    b.tipo_informacion = campo(7)


def _leer_c(b: Bc3, c: list[str], donde: str) -> None:
    # Pág. 7: ~C | CODIGO{\CODIGO} | UNIDAD | RESUMEN | {PRECIO\} | {FECHA\} | TIPO |
    if len(c) < 2 or not c[1].strip():
        raise Bc3Error(f"{donde}: ~C sin código.")
    originales = _sub(c[1])
    codigos = [_codigo(x) for x in originales]
    cod, raiz, capitulo = codigos[0]
    cod = b.resolver(cod)
    actual = b.conceptos.get(cod) or Concepto(codigo=cod, codigo_original=originales[0])
    for sin, _, _ in codigos[1:]:
        # Pág. 7: varios códigos del mismo concepto actúan como sinónimos.
        b.alias[sin] = cod
        if sin not in actual.sinonimos:
            actual.sinonimos.append(sin)
    actual.es_raiz = actual.es_raiz or raiz
    actual.es_capitulo = actual.es_capitulo or capitulo
    if raiz or capitulo:
        actual.codigo_original = originales[0]
    # Pág. 2: un campo vacío es SIN INFORMACIÓN: no borra lo leído antes del mismo concepto.
    if len(c) > 2 and c[2].strip():
        actual.unidad = c[2].strip()
    if len(c) > 3 and c[3].strip():
        actual.resumen = c[3].strip()
    if len(c) > 4 and c[4].strip():
        # Se conserva la POSICIÓN de cada precio (un vacío no desplaza a los siguientes):
        # cada posición corresponde a un rótulo del ~V (pág. 8).
        actual.precios = [_numero(x, donde) for x in c[4].split("\\")]
        while actual.precios and actual.precios[-1] is None:
            actual.precios.pop()
    if len(c) > 6 and c[6].strip():
        actual.tipo = c[6].strip()
    b.conceptos[cod] = actual


def _leer_d(b: Bc3, c: list[str], donde: str) -> None:
    # Pág. 9: campo 2 = HIJO\FACTOR\RENDIMIENTO; campo 3 (más completo) = además
    # CODIGO_PORCENTAJE. «Los programas deben leer el campo 3 ... y en su defecto el 2».
    if len(c) < 3:
        b.avisos.append(f"{donde}: ~D sin descomposición; se ignora.")
        return
    padre = b.resolver(_codigo(c[1])[0])
    usar3 = len(c) > 3 and c[3].strip()
    subs = _sub(c[3] if usar3 else c[2])
    paso = 4 if usar3 else 3
    if len(subs) % paso and not (usar3 and len(subs) % paso == paso - 1):
        b.avisos.append(f"{donde}: descomposición de «{padre}» con subcampos incompletos.")
    lineas = []
    for i in range(0, len(subs), paso):
        grupo = subs[i : i + paso] + [""] * paso
        hijo_texto = _codigo(grupo[0])[0]
        if not hijo_texto:
            continue
        lineas.append(
            LineaD(
                hijo=b.resolver(hijo_texto),
                factor=_numero(grupo[1], donde),
                rendimiento=_numero(grupo[2], donde),
                es_porcentaje="%" in hijo_texto or "&" in hijo_texto,
                numero=i // paso + 1,
            )
        )
    b.descomposiciones[padre] = lineas  # pág. 10: ~D cambia la descomposición completa


def _leer_m(b: Bc3, c: list[str], donde: str) -> None:
    # Pág. 21: ~M | [PADRE\]HIJO | {POSICION\} | MEDICION_TOTAL | {líneas} | [ETIQUETA] |
    if len(c) < 2:
        raise Bc3Error(f"{donde}: ~M sin código.")
    cods = [b.resolver(_codigo(x)[0]) for x in _sub(c[1])]
    padre, hijo = (cods[0], cods[1]) if len(cods) > 1 else (None, cods[0])
    posicion = []
    for p in _sub(c[2]) if len(c) > 2 else []:
        v = _numero(p, donde)
        if v is not None:
            posicion.append(int(v))
    total = _numero(c[3], donde) if len(c) > 3 else None
    lineas = len(_sub(c[4])) // 6 if len(c) > 4 else 0
    etiqueta = (c[5].strip() or None) if len(c) > 5 else None
    b.mediciones.append(MedicionM(padre, hijo, posicion, total, etiqueta, lineas))


def _leer_t(b: Bc3, c: list[str]) -> None:
    # Pág. 15: ~T | CODIGO_CONCEPTO | TEXTO_DESCRIPTIVO |
    if len(c) < 3:
        return
    cod = b.resolver(_codigo(c[1])[0])
    actual = b.conceptos.get(cod) or Concepto(codigo=cod, codigo_original=c[1].strip())
    actual.texto = c[2].strip() or actual.texto
    b.conceptos[cod] = actual


# --- Presupuesto: capítulos y partidas ----------------------------------------------


@dataclass
class _Resultado:
    partidas: list[PartidaLeida] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    omitidas: int = 0  # líneas que no se han podido convertir en partida


def partidas(b: Bc3) -> tuple[list[PartidaLeida], list[str]]:
    """Recorre el presupuesto desde la raíz por los ~D. Devuelve partidas y avisos."""
    r = leer_partidas(b)
    return r.partidas, r.avisos


def leer_partidas(b: Bc3) -> _Resultado:
    r = _Resultado()
    if b.raiz is None:
        _no_estructuradas(b, r)
        return r

    visitados: set[str] = set()

    def recorrer(codigo: str, ruta: list[tuple[str, str]]) -> None:
        if codigo in visitados:
            r.avisos.append(f"Descomposición circular en «{codigo}»: se corta ahí.")
            return
        visitados.add(codigo)
        padre = b.conceptos.get(codigo)
        padre_txt = padre.codigo_original if padre else codigo
        for linea in b.descomposiciones.get(codigo, []):
            if linea.es_porcentaje:
                # Pág. 9-10: un «%»/«&» es un porcentaje sobre las líneas anteriores, no una
                # partida. Esta versión no lo aplica a los importes del capítulo.
                r.avisos.append(
                    f"«{codigo}» aplica el porcentaje «{linea.hijo}» "
                    f"({linea.rendimiento}) sobre sus líneas: no se incluye en los importes."
                )
                r.omitidas += 1
                continue
            hijo = b.conceptos.get(linea.hijo)
            if hijo is None:
                r.avisos.append(f"«{codigo}» cita «{linea.hijo}», que no tiene ~C: se omite.")
                r.omitidas += 1
                continue
            if hijo.es_capitulo:
                recorrer(hijo.codigo, ruta + [(hijo.codigo, hijo.resumen or "")])
                continue
            r.partidas.append(_partida(b, codigo, padre_txt, linea, hijo, ruta, r))
        visitados.discard(codigo)

    recorrer(b.raiz, [])
    return r


def _medicion_de(b: Bc3, padre: str, linea: LineaD, r: _Resultado) -> MedicionM | None:
    candidatas = [m for m in b.mediciones if m.padre == padre and m.hijo == linea.hijo]
    if len(candidatas) <= 1:
        return candidatas[0] if candidatas else None
    # Pág. 22: POSICION identifica la medición cuando un hijo se repite en la
    # descomposición; su último valor es la posición dentro de este padre.
    exactas = [m for m in candidatas if m.posicion and m.posicion[-1] == linea.numero]
    if len(exactas) == 1:
        return exactas[0]
    r.avisos.append(
        f"«{linea.hijo}» aparece varias veces en «{padre}» y sus mediciones no indican "
        "posición: no se puede saber cuál es cuál; se usa solo la cantidad del ~D."
    )
    return None


def _partida(
    b: Bc3,
    codigo: str,
    padre_txt: str,
    linea: LineaD,
    hijo: Concepto,
    ruta: list[tuple[str, str]],
    r: _Resultado,
) -> PartidaLeida:
    med = _medicion_de(b, codigo, linea, r)
    # Pág. 22: MEDICION_TOTAL «debe coincidir con el rendimiento del ~D».
    cantidad = linea.rendimiento
    if cantidad is None:
        if med is not None and med.total is not None:
            cantidad = med.total
        else:
            # El 1.0 por defecto de la pág. 9 no es una medición: sin rendimiento explícito
            # ni ~M, la cantidad no consta.
            r.avisos.append(f"«{hijo.codigo}» en «{codigo}»: sin cantidad (ni ~D ni ~M).")
    elif med is not None and med.total is not None and abs(med.total - cantidad) > 1e-9:
        r.avisos.append(
            f"«{hijo.codigo}»: la medición (~M) suma {med.total} y el rendimiento del ~D es "
            f"{cantidad}. Se usa el del ~D; revísalo en el programa de origen."
        )
    if cantidad == 0:
        # Pág. 2: un 0 explícito anula un campo numérico.
        r.avisos.append(f"«{hijo.codigo}» en «{codigo}»: cantidad 0 (campo anulado).")
        cantidad = None
    if linea.factor not in (None, 1.0):
        r.avisos.append(
            f"«{hijo.codigo}» en «{codigo}»: factor {linea.factor} en una línea de capítulo; "
            "la cantidad es el rendimiento (pág. 22) y el factor no se aplica."
        )
    if b.descomposiciones.get(hijo.codigo) and any(m.padre == hijo.codigo for m in b.mediciones):
        r.avisos.append(
            f"«{hijo.codigo}» tiene mediciones de sus componentes: parece un capítulo sin «#» "
            "en su ~C (pág. 8). Revisa el fichero."
        )
    precio = _precio(b, hijo, r)
    return PartidaLeida(
        capitulos=ruta,
        codigo=hijo.codigo,
        unidad=hijo.unidad,
        resumen=hijo.resumen,
        texto=hijo.texto,
        cantidad=cantidad,
        precio=precio,
        etiqueta=med.etiqueta if med else None,
        localizador=f"~D {padre_txt}, línea {linea.numero}; ~C {hijo.codigo}",
    )


def _precio(b: Bc3, con: Concepto, r: _Resultado) -> float | None:
    """Precio de la partida según la norma.

    Pág. 8 y 10: si el precio sale del ~C y de su descomposición (~D), prima la
    descomposición. Cuando la descomposición se puede calcular (sin porcentajes y con todos
    los precios), se usa la descomposición; si no, el del ~C, diciéndolo.
    """
    declarado = con.precios[0] if con.precios else None
    if len([p for p in con.precios if p is not None]) > 1:
        r.avisos.append(f"«{con.codigo}» tiene varios precios (rótulos del ~V); se usa el primero.")
    calculado, motivo = _precio_descomposicion(b, con)
    if calculado is not None:
        if declarado is None or abs(calculado - declarado) > _TOLERANCIA_PRECIO:
            r.avisos.append(
                f"«{con.codigo}»: el precio del ~C es {declarado} y su descomposición suma "
                f"{round(calculado, 6)}. Se usa el de la descomposición, como manda la "
                "especificación (pág. 10)."
            )
        precio = calculado
    else:
        if motivo:
            r.avisos.append(f"«{con.codigo}»: {motivo} Se usa el precio del ~C.")
        precio = declarado
    if precio == 0:
        r.avisos.append(f"«{con.codigo}»: precio 0 (campo anulado, pág. 2).")
        return None
    return precio


def _precio_descomposicion(b: Bc3, con: Concepto) -> tuple[float | None, str | None]:
    lineas = b.descomposiciones.get(con.codigo)
    if not lineas:
        return None, None
    if any(x.es_porcentaje for x in lineas):
        return None, "su descomposición tiene porcentajes, que esta versión no recalcula."
    suma = 0.0
    for x in lineas:
        h = b.conceptos.get(x.hijo)
        if h is None or not h.precios or h.precios[0] is None:
            return None, f"falta el precio de «{x.hijo}» en su descomposición."
        factor = 1.0 if x.factor is None else x.factor  # pág. 9: por defecto 1.0
        rend = 1.0 if x.rendimiento is None else x.rendimiento
        suma += factor * rend * h.precios[0]
    return suma, None


def _no_estructuradas(b: Bc3, r: _Resultado) -> None:
    # Pág. 21: mediciones no estructuradas, sin raíz ni ~D complementarios.
    if b.descomposiciones:
        r.avisos.append(
            "El fichero tiene descomposiciones (~D) pero ningún concepto raíz («##»): no se "
            "puede reconstruir el presupuesto; se leen solo las mediciones (~M)."
        )
    for m in b.mediciones:
        con = b.conceptos.get(m.hijo, Concepto(codigo=m.hijo))
        if con.es_capitulo or con.es_raiz:
            continue  # pág. 23: las ~M de capítulos llevan su etiqueta, no son partidas
        precio = _precio(b, con, r)
        cantidad = None if m.total in (None, 0) else m.total
        r.partidas.append(
            PartidaLeida(
                [],
                con.codigo,
                con.unidad,
                con.resumen,
                con.texto,
                cantidad,
                precio,
                m.etiqueta,
                f"~M {m.padre + chr(92) if m.padre else ''}{m.hijo}",
            )
        )
    if r.partidas:
        r.avisos.append("Fichero sin concepto raíz: mediciones no estructuradas, sin capítulos.")
