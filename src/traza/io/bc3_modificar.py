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

Antes de guardarlo, el resultado se vuelve a leer con el lector de TRAZA y se compara con lo
esperado (todas las partidas originales, con las cantidades nuevas, más las nuevas). Si no
coincide, no se guarda.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from traza.io import bc3
from traza.io.bc3_escritura import PartidaBc3, _num

_RESERVADOS = re.compile(r"[|\\~]")
_LOCALIZADOR = re.compile(r"^~D (?P<padre>[^,]+), línea (?P<n>\d+); ~C (?P<cod>.+)$")
_CODIFICACION = {"850": "cp850", "437": "cp437", "ANSI": "cp1252", "": "cp850"}


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


def _limpio(t: str) -> str:
    return _RESERVADOS.sub("/", t.replace("\r", " ").replace("\n", " ")).strip()


class _Registro:
    """Un registro BC3 editable que conserva intacto lo que no se toca."""

    def __init__(self, crudo: str) -> None:
        self.crudo = crudo
        if "|" in crudo:
            corte = crudo.rfind("|")
            self.campos = crudo[:corte].split("|")
            self.cola = crudo[corte + 1 :]
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
    esperado_original = bc3.leer_partidas(modelo).partidas

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
        _variar_m(registros, padre, n, v, numero, resolver, avisos)
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

    for cap, delta in deltas_capitulo.items():
        _ajustar_precio(registros, cap, delta, resolver, avisos)

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
        _verificar(temporal, esperado_original, variaciones, nuevas)
    except Bc3ModificarError:
        temporal.unlink(missing_ok=True)
        raise
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
        if len(subs) <= inicio + 2 or resolver(subs[inicio].strip()) != v.codigo:
            raise Bc3ModificarError(
                f"La línea {n} de la descomposición de «{padre}» no es «{v.codigo}»: el fichero "
                "no coincide con lo leído."
            )
        subs[inicio + 2] = _num(v.cantidad_nueva)
        reg.poner(i, "\\".join(subs))
        cambiado = True
    if not cambiado:
        raise Bc3ModificarError(f"La descomposición de «{padre}» está vacía.")


def _variar_m(registros, padre, n, v, numero, resolver, avisos) -> None:
    candidatos = []
    for r in registros:
        if r.tipo != "M":
            continue
        cods = [resolver(x) for x in r.campo(1).split("\\") if x.strip()]
        if len(cods) == 2 and cods == [padre, v.codigo]:
            candidatos.append(r)
    if len(candidatos) > 1:
        candidatos = [
            r
            for r in candidatos
            if [x for x in r.campo(2).split("\\") if x.strip()][-1:] == [str(n)]
        ]
    if not candidatos:
        avisos.append(f"«{v.codigo}» no tiene medición (~M) en el original: se cambia solo el ~D.")
        return
    r = candidatos[-1]
    r.poner(3, _num(v.cantidad_nueva))
    lineas = r.campo(4)
    if lineas.strip():
        base = lineas.rstrip(" \t\r\n")
        if not base.endswith("\\"):
            base += "\\"
        diferencia = v.cantidad_nueva - v.cantidad_contrato
        comentario = _limpio(f"Modificado nº {numero}: {v.comentario}")
        # Línea: TIPO \ COMENTARIO \ UNIDADES \ LONGITUD \ LATITUD \ ALTURA \ (pág. 21)
        r.poner(4, base + "\\".join(["", comentario, _num(diferencia), "", "", ""]) + "\\")


def _ajustar_precio(registros, codigo, delta, resolver, avisos) -> None:
    candidatos = [
        r
        for r in registros
        if r.tipo == "C" and resolver(r.campo(1).split("\\")[0]) == codigo and r.campo(4).strip()
    ]
    if not candidatos:
        avisos.append(f"El capítulo «{codigo}» no declara precio: no se corrige.")
        return
    r = candidatos[-1]
    precios = r.campo(4).split("\\")
    try:
        actual = float(precios[0].strip())
    except ValueError:
        avisos.append(f"El precio del capítulo «{codigo}» no es un número: no se corrige.")
        return
    precios[0] = _num(round(actual + delta, 6))
    r.poner(4, "\\".join(precios))


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
        cod = _limpio(p.codigo or "").rstrip("#")
        if not cod or cod in existentes or len(cod) > 20:
            nuevo = f"{cap}.{k}"
            if cod:
                avisos.append(
                    f"La partida nueva «{cod}» se renombra «{nuevo}» (código ya usado o no válido)."
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


def _verificar(ruta: Path, originales, variaciones, nuevas) -> None:
    leido = bc3.leer_partidas(bc3.leer_bc3(ruta)).partidas
    # Una partida anulada se escribe con cantidad 0, y el lector de TRAZA lee un 0 explícito
    # como campo anulado («no consta», pág. 2): eso es lo esperado al releer.
    cambios = {v.localizador: (v.cantidad_nueva or None) for v in variaciones}
    esperado = [
        (p.codigo, cambios.get(p.localizador, p.cantidad), p.precio) for p in originales
    ] + [(p.codigo, p.cantidad, p.precio) for p in nuevas]
    obtenido = [(p.codigo, p.cantidad, p.precio) for p in leido]
    if obtenido != esperado:
        distintos = [(e, o) for e, o in zip(esperado, obtenido, strict=False) if e != o][:3]
        raise Bc3ModificarError(
            "El BC3 actualizado no se relee igual que lo esperado; no se guarda. "
            f"Diferencias (esperado, leído): {distintos or (len(esperado), len(obtenido))}"
        )
