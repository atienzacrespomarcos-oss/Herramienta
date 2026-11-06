"""BC3 del presupuesto completo actualizado, a partir del fichero BC3 ORIGINAL.

Decisión del usuario (06-11-2026): el BC3 del modificado es el presupuesto completo
actualizado. Partir del fichero original conserva todo lo que TRAZA no interpreta
(descompuestos, pliegos, información gráfica, registros ~K…): solo se tocan los registros
imprescindibles, y el resto del texto queda **byte a byte igual**.

Qué se cambia (reglas de «Formato FIEBDC-3/2024», Asociación FIEBDC):
- Variación de una partida: su RENDIMIENTO en la línea del `~D` del capítulo (pág. 9; si el
  registro tiene campo 3 y campo 2, ambos) y el MEDICION_TOTAL de su `~M`, que debe coincidir
  con él (pág. 22). Si la `~M` tiene líneas de medición, se añade una línea con la
  diferencia y el motivo, para que la suma de líneas siga dando el total.
- Precio de los capítulos que contienen la partida y de la raíz: se corrige con la diferencia
  de importe, porque el precio de un capítulo es el resultado de su descomposición y se
  escribe para su comprobación (pág. 8).
- Partidas nuevas: un capítulo nuevo «Modificado nº N — partidas nuevas» colgado de la raíz,
  con sus `~C`, `~T`, `~D` y `~M`.
- El fichero se escribe en su mismo juego de caracteres.

Lo que NO se hace a ciegas (revisión 06-11-2026): se rechaza, explicando por qué, cuando la
medición tiene líneas de expresión (tipo 3, que TRAZA no evalúa), cuando sus líneas no suman
el total antiguo (el programa de origen recalcula el total con las líneas al leer, pág. 22),
cuando hay registros `~N` (añaden líneas a esa medición, pág. 23) y cuando la partida se
repite en el capítulo y no se puede saber qué `~M` es la suya (POSICION, pág. 22).

Antes de guardarlo, el resultado se vuelve a leer con el lector de TRAZA y se comprueba:
todas las partidas (código, cantidad y precio) son las esperadas, el lector no da ningún
aviso nuevo (p. ej. una `~M` que no cuadre con su `~D`) y los precios de los capítulos
corregidos son los calculados. Si algo no coincide, no se guarda.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from traza.io import bc3

# Una sola `_cifra` (cómo se relee una cifra escrita) para las dos verificaciones: si
# divergieran, una aceptaría lo que la otra rechaza.
from traza.io.bc3_escritura import AVISO_ANULACION, PartidaBc3, _cifra, _num, codigo_valido

# Pág. 2: «|», «\» y «~» son separadores. En el COMENTARIO de una línea de medición «#»
# separa los ID_BIM (pág. 21), así que también se sustituye.
_RESERVADOS = re.compile(r"[|\\~]")
_RESERVADOS_COMENTARIO = re.compile(r"[|\\~#]")
_LOCALIZADOR = re.compile(r"^~D (?P<padre>.+), línea (?P<n>\d+); ~C (?P<cod>.+)$")
_CODIFICACION = {"850": "cp850", "437": "cp437", "ANSI": "cp1252", "": "cp850"}
#: Tolerancia con que las líneas de una medición deben sumar su total: una centésima, la
#: misma que en las comprobaciones de lectura (los programas redondean el total).
TOL_MEDICION = 0.01


class Bc3ModificarError(RuntimeError):
    pass


@dataclass
class Variacion:
    localizador: str  # el que guardó el lector BC3 de TRAZA para la partida
    codigo: str
    cantidad_contrato: float
    cantidad_nueva: float
    precio: float | None
    capitulos: list[str]  # códigos de los capítulos que la contienen, del primer nivel abajo
    comentario: str


def _limpio(t: str, reservados: re.Pattern = _RESERVADOS) -> str:
    return reservados.sub("/", t.replace("\r", " ").replace("\n", " ")).strip()


class _Registro:
    """Un registro BC3 editable que conserva intacto lo que no se toca."""

    def __init__(self, crudo: str) -> None:
        self.crudo = crudo
        if "|" in crudo:
            corte = crudo.rfind("|")
            self.campos = crudo[:corte].split("|")
            self.cola = crudo[corte + 1 :]
            if self.cola.strip():
                # Registro sin «|» final: lo que queda también es un campo (p. ej. las líneas
                # de una ~M). Si no, se cambiaría el total y las líneas quedarían sin tocar.
                contenido = crudo.rstrip(" \t\r\n")
                self.campos = contenido.split("|")
                self.cola = crudo[len(contenido) :]
        else:
            self.campos, self.cola = [crudo], ""
        self.tocado = False

    @property
    def tipo(self) -> str:
        return self.campos[0].strip()

    def campo(self, i: int) -> str:
        return self.campos[i] if len(self.campos) > i else ""

    def poner(self, i: int, valor: str) -> None:
        while len(self.campos) <= i:
            self.campos.append("")
        self.campos[i] = valor
        self.tocado = True

    def texto(self) -> str:
        if not self.tocado:
            return self.crudo
        return "|".join(self.campos) + "|" + self.cola


def actualizar(
    original: Path,
    destino: Path,
    numero: int,
    variaciones: list[Variacion],
    nuevas: list[PartidaBc3],
) -> tuple[Path, list[str]]:
    try:
        return _actualizar(original, destino, numero, variaciones, nuevas)
    except bc3.Bc3Error as exc:
        raise Bc3ModificarError(f"El BC3 no se puede leer: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise Bc3ModificarError(
            "El BC3 original tiene caracteres que no corresponden a su juego de caracteres "
            "declarado: no se modifica."
        ) from exc


def _actualizar(original, destino, numero, variaciones, nuevas) -> tuple[Path, list[str]]:
    avisos: list[str] = []
    crudo = original.read_bytes()
    juego = bc3._juego_caracteres(crudo)
    if juego not in _CODIFICACION:
        raise Bc3ModificarError(f"Juego de caracteres «{juego}» no previsto en FIEBDC-3.")
    codificacion = _CODIFICACION[juego]
    texto = crudo.decode(codificacion)
    modelo = bc3.leer_bc3_texto(texto, juego)
    if modelo.raiz is None:
        raise Bc3ModificarError("El BC3 original no tiene concepto raíz: no es un presupuesto.")
    leido_original = bc3.leer_partidas(modelo)

    trozos = texto.split("~")
    preambulo, registros = trozos[0], [_Registro(t) for t in trozos[1:]]

    def resolver(cod: str) -> str:
        return modelo.resolver(bc3._codigo(cod)[0])

    def ultimo(tipo: str, codigo: str) -> _Registro | None:
        hallados = [
            r for r in registros if r.tipo == tipo and resolver(r.campo(1).split("\\")[0]) == codigo
        ]
        return hallados[-1] if hallados else None

    deltas_capitulo: dict[str, float] = {}
    for v in variaciones:
        m = _LOCALIZADOR.match(v.localizador)
        if not m:
            raise Bc3ModificarError(
                f"«{v.codigo}»: origen en el BC3 no reconocible ({v.localizador})."
            )
        padre, n = resolver(m["padre"].strip()), int(m["n"])
        _variar_d(ultimo("D", padre), padre, n, v, resolver)
        _variar_m(registros, modelo, padre, n, v, numero, resolver, avisos)
        if _cifra(v.cantidad_nueva) is None:
            avisos.append(AVISO_ANULACION.format(codigo=v.codigo))
        if v.precio is None:
            avisos.append(
                f"«{v.codigo}» no tiene precio: no se corrigen los precios de sus capítulos."
            )
            continue
        delta = (v.cantidad_nueva - v.cantidad_contrato) * v.precio
        for cap in [*v.capitulos, modelo.raiz]:
            deltas_capitulo[cap] = deltas_capitulo.get(cap, 0.0) + delta

    nuevos_registros: list[str] = []
    if nuevas:
        nuevos_registros = _anadir_nuevas(registros, modelo, numero, nuevas, ultimo, avisos)
        total = sum(
            p.cantidad * p.precio for p in nuevas if p.cantidad is not None and p.precio is not None
        )
        deltas_capitulo[modelo.raiz] = deltas_capitulo.get(modelo.raiz, 0.0) + total

    precios_esperados: dict[str, float] = {}
    for cap, delta in deltas_capitulo.items():
        nuevo = _ajustar_precio(registros, modelo, cap, delta, resolver, avisos)
        if nuevo is not None:
            precios_esperados[cap] = nuevo

    salida = preambulo + "".join("~" + r.texto() for r in registros)
    if nuevos_registros:
        if not salida.endswith(("\n", "\r\n")):
            salida += "\r\n"
        salida += "\r\n".join(nuevos_registros) + "\r\n"
    try:
        datos = salida.encode(codificacion)
    except UnicodeEncodeError:
        datos = salida.encode(codificacion, errors="replace")
        avisos.append(
            f"Algún carácter no existe en el juego «{juego or '850'}» del original y se "
            "ha sustituido por «?»."
        )

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".parcial")
    temporal.write_bytes(datos)
    try:
        _verificar(temporal, leido_original, variaciones, nuevas, precios_esperados)
    except (Bc3ModificarError, bc3.Bc3Error, UnicodeDecodeError) as exc:
        temporal.unlink(missing_ok=True)
        if isinstance(exc, Bc3ModificarError):
            raise
        raise Bc3ModificarError(f"El BC3 actualizado no se puede releer: {exc}") from exc
    temporal.replace(destino)
    return destino, avisos


def _variar_d(reg: _Registro | None, padre: str, n: int, v: Variacion, resolver) -> None:
    if reg is None:
        raise Bc3ModificarError(f"No se encuentra la descomposición (~D) de «{padre}».")
    cambiado = False
    for i, paso in ((2, 3), (3, 4)):
        campo = reg.campo(i)
        if not campo.strip():
            continue
        subs = campo.split("\\")
        inicio = (n - 1) * paso
        if len(subs) <= inicio or resolver(subs[inicio].strip()) != v.codigo:
            raise Bc3ModificarError(
                f"La línea {n} de la descomposición de «{padre}» no es «{v.codigo}»: el fichero "
                "no coincide con lo leído."
            )
        # La última línea puede venir sin rendimiento ni separador final (pág. 2: el
        # separador final es opcional): se completa en vez de rechazar un fichero válido.
        while len(subs) <= inicio + 2:
            subs.append("")
        subs[inicio + 2] = _num(v.cantidad_nueva)
        reg.poner(i, "\\".join(subs))
        cambiado = True
    if not cambiado:
        raise Bc3ModificarError(f"La descomposición de «{padre}» está vacía.")


def _posicion(r: _Registro) -> int | None:
    """Último valor de POSICION de una ~M (su posición dentro del padre), como número."""
    valores = [x for x in r.campo(2).split("\\") if x.strip()]
    if not valores:
        return None
    try:
        return int(float(valores[-1]))
    except ValueError:
        return None


def _variar_m(registros, modelo, padre, n, v, numero, resolver, avisos) -> None:
    def es_de(r: _Registro) -> bool:
        cods = [resolver(x) for x in r.campo(1).split("\\") if x.strip()]
        return cods == [padre, v.codigo]

    if any(r.tipo == "N" and es_de(r) for r in registros):
        raise Bc3ModificarError(
            f"«{v.codigo}» tiene líneas de medición añadidas con ~N en «{padre}» (pág. 23): "
            "TRAZA no las actualiza. Cambia esa medición en el programa de origen."
        )
    candidatos = [r for r in registros if r.tipo == "M" and es_de(r)]
    repetida = sum(1 for x in modelo.descomposiciones.get(padre, []) if x.hijo == v.codigo) > 1
    if repetida or len(candidatos) > 1:
        # Pág. 22: con el hijo repetido, la ~M se identifica por su POSICION. El mismo
        # criterio que el lector (io/bc3.py, _medicion_de).
        exactas = [r for r in candidatos if _posicion(r) == n]
        if len(exactas) > 1 or (not exactas and any(_posicion(r) is None for r in candidatos)):
            raise Bc3ModificarError(
                f"«{v.codigo}» aparece varias veces en «{padre}» y no se puede saber qué "
                f"medición (~M) es la de la línea {n} (falta POSICION, pág. 22): no se "
                "modifica a ciegas."
            )
        candidatos = exactas
    if not candidatos:
        avisos.append(f"«{v.codigo}» no tiene medición (~M) en el original: se cambia solo el ~D.")
        return
    r = candidatos[-1]
    lineas = r.campo(4)
    if lineas.strip():
        suma = _suma_lineas(lineas, v.codigo)
        try:
            total_antiguo = float(r.campo(3).strip())
        except ValueError:
            total_antiguo = None
        if total_antiguo is None:
            raise Bc3ModificarError(
                f"La medición de «{v.codigo}» tiene líneas pero su total está vacío: TRAZA no "
                "lo recalcula para no suponer cómo lo hace el programa de origen. Revisa esa "
                "medición en el programa de origen."
            )
        if abs(suma - total_antiguo) > TOL_MEDICION:
            raise Bc3ModificarError(
                f"Las líneas de medición de «{v.codigo}» suman {_num(round(suma, 6))} y su "
                f"total es {r.campo(3).strip()}: el programa de origen recalcula el total con "
                "las líneas (pág. 22), así que añadir la diferencia no daría la cantidad "
                "nueva. Revisa esa medición en el programa de origen."
            )
        if abs(total_antiguo - v.cantidad_contrato) > TOL_MEDICION:
            # La ~M y el ~D del original no coinciden (el lector ya lo avisa y usa el ~D):
            # no se sabe cuál de las dos es la buena (revisión 06-11-2026).
            raise Bc3ModificarError(
                f"En el original, la medición (~M) de «{v.codigo}» suma {r.campo(3).strip()} "
                f"y el ~D dice {_num(v.cantidad_contrato)}: no se sabe cuál es la buena. "
                "Corrígelo en el programa de origen antes de hacer el modificado."
            )
        base = lineas.rstrip(" \t\r\n")
        if not base.endswith("\\"):
            base += "\\"
        # Lo que falta para que las líneas sumen EXACTAMENTE la cantidad nueva (y no la
        # diferencia con el contrato, que deja el redondeo de la tolerancia arrastrado).
        diferencia = round(v.cantidad_nueva - suma, 6)
        comentario = _limpio(f"Modificado nº {numero}: {v.comentario}", _RESERVADOS_COMENTARIO)
        # Línea: TIPO \ COMENTARIO \ UNIDADES \ LONGITUD \ LATITUD \ ALTURA \ (pág. 21)
        r.poner(4, base + "\\".join(["", comentario, _num(diferencia), "", "", ""]) + "\\")
    r.poner(3, _num(v.cantidad_nueva))


def _suma_lineas(campo: str, codigo: str) -> float:
    """Suma de las líneas de una ~M según la pág. 22.

    Cada línea: TIPO\\COMENTARIO\\UNIDADES\\LONGITUD\\LATITUD\\ALTURA\\. Vale el producto de
    las magnitudes que existen (un campo vacío es una magnitud que no existe, pág. 23); una
    línea sin ninguna es un comentario. Las de subtotal (tipo 1 y 2) no suman. Las de
    expresión (tipo 3) no se evalúan: se rechaza.
    """
    subs = campo.rstrip(" \t\r\n").split("\\")
    if subs and subs[-1].strip() == "":
        subs.pop()
    if len(subs) % 6:
        raise Bc3ModificarError(
            f"Las líneas de medición de «{codigo}» están incompletas (cada línea tiene seis "
            "subcampos, pág. 21): no se modifican."
        )
    suma = 0.0
    for i in range(0, len(subs), 6):
        tipo = subs[i].strip()
        if tipo in ("1", "2"):
            continue
        if tipo:
            raise Bc3ModificarError(
                f"La medición de «{codigo}» tiene líneas de tipo «{tipo}» (expresiones, pág. "
                "22), que TRAZA no evalúa: no se modifica. Cámbiala en el programa de origen."
            )
        magnitudes = [bc3._numero(x, f"medición de «{codigo}»") for x in subs[i + 2 : i + 6]]
        presentes = [x for x in magnitudes if x is not None]
        if presentes:
            producto = 1.0
            for x in presentes:
                producto *= x
            suma += producto
    return suma


def _ajustar_precio(registros, modelo, codigo, delta, resolver, avisos) -> float | None:
    candidatos = [
        r
        for r in registros
        if r.tipo == "C" and resolver(r.campo(1).split("\\")[0]) == codigo and r.campo(4).strip()
    ]
    if not candidatos:
        avisos.append(f"El capítulo «{codigo}» no declara precio: no se corrige.")
        return None
    if any(x.es_porcentaje for x in modelo.descomposiciones.get(codigo, [])):
        # Pág. 9-10: el porcentaje se aplica sobre las líneas anteriores. TRAZA no lo
        # recalcula (como al leer): se declara, no se disimula.
        avisos.append(
            f"El capítulo «{codigo}» aplica porcentajes («%»/«&»): su precio se corrige solo "
            "con la diferencia de importe, sin el porcentaje. Recalcúlalo en el programa de "
            "origen."
        )
    r = candidatos[-1]
    precios = r.campo(4).split("\\")
    try:
        actual = float(precios[0].strip())
    except ValueError:
        avisos.append(f"El precio del capítulo «{codigo}» no es un número: no se corrige.")
        return None
    nuevo = round(actual + delta, 6)
    precios[0] = _num(nuevo)
    r.poner(4, "\\".join(precios))
    return nuevo


def _anadir_nuevas(registros, modelo, numero, nuevas, ultimo, avisos) -> list[str]:
    existentes = set(modelo.conceptos) | set(modelo.alias)
    cap = f"MOD{numero}"
    while cap in existentes:
        cap += "X"
    existentes.add(cap)
    raiz = ultimo("D", modelo.raiz)
    if raiz is None:
        raise Bc3ModificarError("La raíz del presupuesto no tiene descomposición (~D).")
    for i, paso in ((2, 3), (3, 4)):
        campo = raiz.campo(i)
        if not campo.strip():
            continue
        base = campo.rstrip(" \t\r\n")
        if not base.endswith("\\"):
            base += "\\"
        grupo = [f"{cap}#", "1", "1"] + ([""] if paso == 4 else [])
        raiz.poner(i, base + "\\".join(grupo) + "\\")
    posicion_cap = len(modelo.descomposiciones.get(modelo.raiz, [])) + 1
    hoy = date.today().strftime("%d%m%Y")
    codigos, lineas = [], []
    for k, p in enumerate(nuevas, start=1):
        cod = (p.codigo or "").strip()
        if not codigo_valido(cod) or cod in existentes:
            nuevo, s = f"{cap}.{k}", 0
            while nuevo in existentes:
                s += 1
                nuevo = f"{cap}.{k}.{s}"
            if cod:
                avisos.append(
                    f"La partida nueva «{cod}» se renombra «{nuevo}» (código ya usado en el "
                    "presupuesto o no válido en BC3)."
                )
            cod = nuevo
        existentes.add(cod)
        codigos.append(cod)
        lineas.append(
            f"~C|{cod}|{_limpio(p.unidad or '')}|{_limpio(p.resumen or '')}|"
            f"{_num(p.precio)}|{hoy}|0|"
        )
        if p.texto:
            lineas.append(f"~T|{cod}|{_limpio(p.texto)}|")
        lineas.append(f"~M|{cap}#\\{cod}|{posicion_cap}\\{k}\\|{_num(p.cantidad)}|||")
    total = sum(
        p.cantidad * p.precio for p in nuevas if p.cantidad is not None and p.precio is not None
    )
    cabecera = [
        f"~C|{cap}#||Modificado nº {numero} - partidas nuevas|{_num(round(total, 6))}||0|",
        f"~D|{cap}#|"
        + "".join(f"{c}\\1\\{_num(p.cantidad)}\\" for c, p in zip(codigos, nuevas, strict=True))
        + "|",
    ]
    for p, c in zip(nuevas, codigos, strict=True):
        p.codigo = c  # para la verificación
    return cabecera + lineas


def _verificar(ruta: Path, original, variaciones, nuevas, precios_capitulo) -> None:
    modelo = bc3.leer_bc3(ruta)
    leido = bc3.leer_partidas(modelo)
    cambios = {v.localizador: v.cantidad_nueva for v in variaciones}
    esperado = [
        (p.codigo, _cifra(cambios.get(p.localizador, p.cantidad)), _cifra(p.precio))
        for p in original.partidas
    ] + [(p.codigo, _cifra(p.cantidad), _cifra(p.precio)) for p in nuevas]
    obtenido = [(p.codigo, _cifra(p.cantidad), _cifra(p.precio)) for p in leido.partidas]
    if obtenido != esperado:
        distintos = [(e, o) for e, o in zip(esperado, obtenido, strict=False) if e != o][:3]
        raise Bc3ModificarError(
            "El BC3 actualizado no se relee igual que lo esperado; no se guarda. "
            f"Diferencias (esperado, leído): {distintos or (len(esperado), len(obtenido))}"
        )
    # Un aviso nuevo del lector delata algo mal actualizado aunque las cifras cuadren (p. ej.
    # una ~M que ya no coincide con su ~D). Solo se esperan los de «campo anulado» de lo que
    # se ha escrito con 0 a propósito: las anulaciones pedidas y un precio 0 de una partida
    # nueva. Cualquier otro, aunque diga «campo anulado», se considera un fallo.
    esperados = {f"«{v.codigo}» en " for v in variaciones if _cifra(v.cantidad_nueva) is None} | {
        f"«{p.codigo}»: precio 0" for p in nuevas if p.precio is not None and not _cifra(p.precio)
    }

    def esperado_aviso(a: str) -> bool:
        return "campo anulado" in a and any(a.startswith(e) for e in esperados)

    nuevos = [a for a in leido.avisos if a not in original.avisos and not esperado_aviso(a)]
    if nuevos:
        raise Bc3ModificarError(
            "El BC3 actualizado se relee con avisos que el original no tenía; no se guarda: "
            + " ".join(nuevos[:3])
        )
    for cap, precio in precios_capitulo.items():
        con = modelo.conceptos.get(cap)
        leido_precio = con.precios[0] if con and con.precios else None
        if leido_precio is None or abs(leido_precio - precio) > 1e-6:
            raise Bc3ModificarError(
                f"El precio del capítulo «{cap}» se relee {leido_precio} y debía ser {precio}; "
                "no se guarda."
            )
