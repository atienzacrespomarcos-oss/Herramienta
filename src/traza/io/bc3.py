"""Lector de ficheros BC3 (formato FIEBDC-3).

Fuente: «Formato FIEBDC-3/2024», Asociación FIEBDC,
https://www.fiebdc.es/web2/datos/uploads/Formato-FIEBDC-3-2024.pdf (consultado 06-11-2026).
Cada regla aplicada cita su página. Lo que la especificación permite y este lector aún no
interpreta se declara como aviso; nunca se rellena con un valor supuesto.

El lector es puro (no toca la base de datos ni la interfaz): devuelve lo leído y los avisos.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

LECTOR = "bc3"
VERSION_LECTOR = "1.0.0"

# Pág. 4: «850 ó 437» (D.O.S.) o «ANSI» (Windows); vacío = 850 por compatibilidad.
_JUEGOS = {"850": "cp850", "437": "cp437", "ANSI": "cp1252", "": "cp850"}
_BLANCOS = " \t\r\n"  # pág. 2: blancos (32), tabuladores (9) y fines de línea (13 y 10)


class Bc3Error(ValueError):
    """El fichero no se puede leer como BC3 según la especificación."""


@dataclass
class Concepto:
    codigo: str  # sin «#»/«##» (pág. 8: con y sin # es el mismo concepto)
    sinonimos: list[str] = field(default_factory=list)
    unidad: str | None = None
    resumen: str | None = None
    precios: list[float] = field(default_factory=list)
    tipo: str | None = None
    texto: str | None = None
    es_raiz: bool = False
    es_capitulo: bool = False


@dataclass
class LineaD:
    hijo: str
    factor: float  # pág. 9: por defecto 1.0
    rendimiento: float  # pág. 9: por defecto 1.0
    es_porcentaje: bool  # pág. 9: código con «%» o «&»
    numero: int  # orden en la descomposición, desde 1


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
    cantidad: float | None
    precio: float | None
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
    descomposiciones: dict[str, list[LineaD]] = field(default_factory=dict)
    mediciones: dict[tuple[str | None, str], MedicionM] = field(default_factory=dict)
    no_interpretados: Counter = field(default_factory=Counter)
    avisos: list[str] = field(default_factory=list)


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
    texto = crudo.decode(_JUEGOS[juego])
    return leer_bc3_texto(texto, juego)


def leer_bc3_texto(texto: str, juego: str = "") -> Bc3:
    b = Bc3(juego_caracteres=juego)
    registros = texto.split("~")[1:]  # pág. 2: lo anterior al primer «~» se ignora
    if not registros:
        raise Bc3Error("No hay ningún registro «~»: no es un fichero BC3.")
    for n, reg in enumerate(registros, start=1):
        campos = _campos(reg)
        if not campos or not campos[0]:
            continue
        cab = campos[0]
        donde = f"registro {n} (~{cab})"
        if cab == "V":
            _leer_v(b, campos)
        elif cab == "C":
            _leer_c(b, campos, donde)
        elif cab == "D":
            _leer_d(b, campos, donde)
        elif cab == "M":
            _leer_m(b, campos, donde)
        elif cab == "T":
            _leer_t(b, campos)
        else:
            b.no_interpretados[cab] += 1
    raices = [c for c in b.conceptos.values() if c.es_raiz]
    if len(raices) > 1:
        # Pág. 8: «Únicamente puede haber un concepto raíz».
        raise Bc3Error(f"Hay {len(raices)} conceptos raíz («##»); la especificación admite uno.")
    b.raiz = raices[0].codigo if raices else None
    if b.no_interpretados:
        tipos = ", ".join(f"~{k} ({v})" for k, v in sorted(b.no_interpretados.items()))
        b.avisos.append(f"Registros conservados sin interpretar: {tipos}.")
    return b


def _leer_v(b: Bc3, c: list[str]) -> None:
    # Pág. 4: ~V | PROPIEDAD | VERSION[\fecha] | PROGRAMA | CABECERA\{ROTULO\} | JUEGO |
    #            COMENTARIO | TIPO INFORMACIÓN | ...
    def campo(i: int) -> str | None:
        return c[i].strip() or None if len(c) > i else None

    version = campo(2)
    b.version_formato = _sub(version)[0] if version else None
    b.programa = campo(3)
    b.tipo_informacion = campo(7)


def _leer_c(b: Bc3, c: list[str], donde: str) -> None:
    # Pág. 7: ~C | CODIGO{\CODIGO} | UNIDAD | RESUMEN | {PRECIO\} | {FECHA\} | TIPO |
    if len(c) < 2 or not c[1].strip():
        raise Bc3Error(f"{donde}: ~C sin código.")
    codigos = [_codigo(x) for x in _sub(c[1])]
    cod, raiz, capitulo = codigos[0]
    actual = b.conceptos.get(cod) or Concepto(codigo=cod)
    actual.sinonimos = [x[0] for x in codigos[1:]] or actual.sinonimos
    actual.es_raiz = actual.es_raiz or raiz
    actual.es_capitulo = actual.es_capitulo or capitulo
    # Pág. 2: un campo vacío es SIN INFORMACIÓN: no borra lo leído antes del mismo concepto.
    if len(c) > 2 and c[2].strip():
        actual.unidad = c[2].strip()
    if len(c) > 3 and c[3].strip():
        actual.resumen = c[3].strip()
    if len(c) > 4 and c[4].strip():
        actual.precios = [p for p in (_numero(x, donde) for x in _sub(c[4])) if p is not None]
    if len(c) > 6 and c[6].strip():
        actual.tipo = c[6].strip()
    b.conceptos[cod] = actual


def _leer_d(b: Bc3, c: list[str], donde: str) -> None:
    # Pág. 9: campo 2 = HIJO\FACTOR\RENDIMIENTO; campo 3 (más completo) = además
    # CODIGO_PORCENTAJE. «Los programas deben leer el campo 3 ... y en su defecto el 2».
    if len(c) < 3:
        raise Bc3Error(f"{donde}: ~D sin descomposición.")
    padre = _codigo(c[1])[0]
    usar3 = len(c) > 3 and c[3].strip()
    subs = _sub(c[3] if usar3 else c[2])
    paso = 4 if usar3 else 3
    if len(subs) % paso and not (usar3 and len(subs) % paso == paso - 1):
        b.avisos.append(f"{donde}: descomposición de «{padre}» con subcampos incompletos.")
    lineas = []
    for i in range(0, len(subs), paso):
        grupo = subs[i : i + paso] + [""] * paso
        hijo = _codigo(grupo[0])[0]
        if not hijo:
            continue
        factor = _numero(grupo[1], donde)
        rend = _numero(grupo[2], donde)
        lineas.append(
            LineaD(
                hijo=hijo,
                factor=1.0 if factor is None else factor,
                rendimiento=1.0 if rend is None else rend,
                es_porcentaje="%" in hijo or "&" in hijo,
                numero=len(lineas) + 1,
            )
        )
    b.descomposiciones[padre] = lineas  # pág. 10: ~D cambia la descomposición completa


def _leer_m(b: Bc3, c: list[str], donde: str) -> None:
    # Pág. 21: ~M | [PADRE\]HIJO | {POSICION\} | MEDICION_TOTAL | {líneas} | [ETIQUETA] |
    if len(c) < 2:
        raise Bc3Error(f"{donde}: ~M sin código.")
    cods = [_codigo(x)[0] for x in _sub(c[1])]
    padre, hijo = (cods[0], cods[1]) if len(cods) > 1 else (None, cods[0])
    posicion = []
    for p in _sub(c[2]) if len(c) > 2 else []:
        v = _numero(p, donde)
        if v is not None:
            posicion.append(int(v))
    total = _numero(c[3], donde) if len(c) > 3 else None
    lineas = len(_sub(c[4])) // 6 if len(c) > 4 else 0
    etiqueta = c[5].strip() or None if len(c) > 5 else None
    b.mediciones[(padre, hijo)] = MedicionM(padre, hijo, posicion, total, etiqueta, lineas)


def _leer_t(b: Bc3, c: list[str]) -> None:
    # Pág. 15: ~T | CODIGO_CONCEPTO | TEXTO_DESCRIPTIVO |
    if len(c) < 3:
        return
    cod = _codigo(c[1])[0]
    actual = b.conceptos.get(cod) or Concepto(codigo=cod)
    actual.texto = c[2].strip() or actual.texto
    b.conceptos[cod] = actual


# --- Presupuesto: capítulos y partidas ----------------------------------------------


def partidas(b: Bc3) -> tuple[list[PartidaLeida], list[str]]:
    """Recorre el presupuesto desde la raíz por los ~D. Devuelve partidas y avisos."""
    avisos: list[str] = []
    salida: list[PartidaLeida] = []
    if b.raiz is None:
        # Pág. 21: mediciones no estructuradas, sin raíz ni ~D.
        for (_padre, hijo), m in b.mediciones.items():
            con = b.conceptos.get(hijo, Concepto(codigo=hijo))
            salida.append(
                PartidaLeida(
                    [],
                    hijo,
                    con.unidad,
                    con.resumen,
                    con.texto,
                    m.total,
                    con.precios[0] if con.precios else None,
                    m.etiqueta,
                    f"~M {hijo}",
                )
            )
        if salida:
            avisos.append("Fichero sin concepto raíz: mediciones no estructuradas, sin capítulos.")
        return salida, avisos

    visitados: set[str] = set()

    def recorrer(codigo: str, ruta: list[tuple[str, str]]) -> None:
        if codigo in visitados:
            avisos.append(f"Descomposición circular en «{codigo}»: se corta ahí.")
            return
        visitados.add(codigo)
        for linea in b.descomposiciones.get(codigo, []):
            hijo = b.conceptos.get(linea.hijo)
            if hijo is None:
                avisos.append(f"«{codigo}» cita «{linea.hijo}», que no tiene ~C.")
                continue
            if hijo.es_capitulo:
                recorrer(hijo.codigo, ruta + [(hijo.codigo, hijo.resumen or "")])
                continue
            # Partida: la cantidad es su rendimiento en el ~D del capítulo (pág. 9).
            cantidad = linea.factor * linea.rendimiento
            med = b.mediciones.get((codigo, hijo.codigo)) or b.mediciones.get((None, hijo.codigo))
            if med and med.total is not None and abs(med.total - cantidad) > 1e-9:
                # Pág. 22: MEDICION_TOTAL «debe coincidir con el rendimiento del ~D».
                avisos.append(
                    f"«{hijo.codigo}»: la medición (~M) suma {med.total} y la cantidad del "
                    f"~D es {cantidad}. Se usa la del ~D; revísalo en el programa de origen."
                )
            precio = hijo.precios[0] if hijo.precios else None
            _comprobar_precio(b, hijo, precio, avisos)
            salida.append(
                PartidaLeida(
                    capitulos=ruta,
                    codigo=hijo.codigo,
                    unidad=hijo.unidad,
                    resumen=hijo.resumen,
                    texto=hijo.texto,
                    cantidad=cantidad,
                    precio=precio,
                    etiqueta=med.etiqueta if med else None,
                    localizador=f"~D {codigo}#, línea {linea.numero}; ~C {hijo.codigo}",
                )
            )
        visitados.discard(codigo)

    recorrer(b.raiz, [])
    return salida, avisos


def _comprobar_precio(b: Bc3, con: Concepto, precio: float | None, avisos: list[str]) -> None:
    """Pág. 10: si el precio sale de ~C y de ~D, prima ~D. Aquí se comprueba y se avisa."""
    lineas = b.descomposiciones.get(con.codigo)
    if not lineas:
        return
    if any(x.es_porcentaje for x in lineas):
        avisos.append(
            f"«{con.codigo}»: su descomposición tiene porcentajes; esta versión no la "
            "recalcula. Se usa el precio del ~C."
        )
        return
    suma = 0.0
    for x in lineas:
        h = b.conceptos.get(x.hijo)
        if h is None or not h.precios:
            avisos.append(f"«{con.codigo}»: falta el precio de «{x.hijo}»; no se comprueba.")
            return
        suma += x.factor * x.rendimiento * h.precios[0]
    if precio is None or abs(suma - precio) > 0.005:
        avisos.append(
            f"«{con.codigo}»: el precio del ~C es {precio} y su descomposición suma "
            f"{round(suma, 6)}. La especificación da prioridad a la descomposición (pág. 10)."
        )
