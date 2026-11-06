"""Escritura de ficheros BC3 (FIEBDC-3) a partir de capítulos y partidas.

Mismas reglas que el lector (`io/bc3.py`), de la especificación «Formato FIEBDC-3/2024»
(Asociación FIEBDC):
- Registros que empiezan por «~», campos separados por «|», subcampos por «\\» (pág. 2).
- Números con punto decimal y sin separador de miles (pág. 3).
- `~V` con JUEGO_CARACTERES «ANSI» (Windows, pág. 4) y TIPO INFORMACIÓN 2 = presupuesto.
- Raíz con «##» y capítulos con «#» en su `~C` (pág. 8).
- Cantidad de cada partida = rendimiento de su línea en el `~D` del capítulo, y la misma
  cifra como MEDICION_TOTAL en su `~M` (pág. 22). FACTOR = 1.
- El precio de un capítulo es el resultado de su descomposición y se escribe para permitir
  su comprobación (pág. 8): suma de los importes de sus líneas.

Lo que no se escribe y se declara: registro `~K` (decimales), descompuestos de las
partidas (TRAZA no los guarda), pliegos y demás registros. Una partida sin precio se
escribe sin precio (campo vacío = sin información, pág. 2), nunca con 0.

Tras escribir, el fichero se vuelve a leer con el lector de TRAZA y se comparan cantidades
y precios: un BC3 que no se lee igual que lo que se quiso escribir no se da por bueno.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from traza.io import bc3

# Pág. 2: «|», «\» y «~» son separadores; dentro de un texto se sustituyen.
_RESERVADOS = re.compile(r"[|\\~]")
VERSION_FORMATO = "FIEBDC-3/2016"  # la que el propio texto de la ed. 2024 llama «actual» (pág. 4)


class Bc3EscrituraError(RuntimeError):
    pass


@dataclass
class PartidaBc3:
    codigo: str
    unidad: str | None
    resumen: str | None
    texto: str | None
    cantidad: float | None
    precio: float | None
    etiqueta: str | None = None


@dataclass
class CapituloBc3:
    codigo: str
    resumen: str
    capitulos: list[CapituloBc3] = field(default_factory=list)
    partidas: list[PartidaBc3] = field(default_factory=list)

    def importe(self) -> float:
        total = sum(c.importe() for c in self.capitulos)
        total += sum(
            p.cantidad * p.precio
            for p in self.partidas
            if p.cantidad is not None and p.precio is not None
        )
        return total


def _texto(v: str | None, avisos: list[str], donde: str) -> str:
    if not v:
        return ""
    limpio = _RESERVADOS.sub("/", v.replace("\r", " ").replace("\n", " "))
    if limpio != v.replace("\r", " ").replace("\n", " "):
        avisos.append(f"{donde}: se han sustituido caracteres reservados (| \\ ~) por «/».")
    return limpio


#: En un código, además de los separadores: «#» marca raíz y capítulo (pág. 8) y «%»/«&»
#: convierten la línea del ~D en un porcentaje (pág. 9). Un código así no se lee como partida.
_RESERVADOS_CODIGO = re.compile(r"[|\\~#%&]")


def codigo_valido(codigo: str) -> bool:
    """Código que se puede escribir tal cual en un BC3 y se relee igual (pág. 8: hasta 20
    caracteres)."""
    c = codigo.strip()
    return bool(c) and c == codigo and len(c) <= 20 and not _RESERVADOS_CODIGO.search(c)


def _codigo_limpio(codigo: str) -> str:
    return _RESERVADOS.sub("/", codigo).strip().rstrip("#")


def _num(v: float | None) -> str:
    if v is None:
        return ""
    texto = f"{v:.6f}".rstrip("0").rstrip(".")
    return texto if texto not in ("", "-0") else "0"


def escribir(
    destino: Path, raiz: CapituloBc3, *, propiedad: str, comentario: str
) -> tuple[Path, list[str]]:
    """Escribe el presupuesto. Devuelve (ruta, avisos)."""
    avisos: list[str] = [
        "No se escriben los descompuestos de las partidas ni el registro ~K (decimales): "
        "el programa que lo importe usará los precios de las partidas tal cual."
    ]
    lineas: list[str] = []
    hoy = date.today().strftime("%d%m%Y")
    lineas.append(
        f"~V|{_texto(propiedad, avisos, '~V')}|{VERSION_FORMATO}\\{hoy}|TRAZA|\\|ANSI|"
        f"{_texto(comentario, avisos, '~V')}|2|"
    )
    codigos: set[str] = set()

    def registrar(codigo: str, donde: str) -> str:
        c = codigo
        if not c.strip():
            raise Bc3EscrituraError(f"{donde}: código vacío.")
        if not codigo_valido(c):
            # Pág. 8: hasta 20 caracteres, y sin los que el formato reserva. Quien llama
            # tiene que dar códigos válidos (y avisar si los cambia): aquí no se retocan en
            # silencio, porque entonces el fichero no diría lo que se quiso escribir.
            raise Bc3EscrituraError(
                f"{donde}: el código «{c}» no es válido en BC3 (más de 20 caracteres o con "
                "| \\ ~ # % &)."
            )
        if c in codigos:
            raise Bc3EscrituraError(f"{donde}: código «{c}» repetido.")
        codigos.add(c)
        return c

    def capitulo(cap: CapituloBc3, sufijo: str, ruta: list[int]) -> None:
        cod = registrar(cap.codigo, f"capítulo «{cap.resumen}»")
        lineas.append(
            f"~C|{cod}{sufijo}||{_texto(cap.resumen, avisos, cod)}|{_num(cap.importe())}||0|"
        )
        # El código en el ~D tiene que ser el mismo, ya saneado, que el del ~C del hijo.
        hijos = [f"{_codigo_limpio(sub.codigo)}#\\1\\1\\" for sub in cap.capitulos]
        base = len(cap.capitulos)
        for p in cap.partidas:
            hijos.append(f"{_codigo_limpio(p.codigo)}\\1\\{_num(p.cantidad)}\\")
        if hijos:
            lineas.append(f"~D|{cod}{sufijo}|{''.join(hijos)}|")
        for i, sub in enumerate(cap.capitulos, start=1):
            capitulo(sub, "#", ruta + [i])
        for j, p in enumerate(cap.partidas, start=base + 1):
            pc = registrar(p.codigo, f"partida «{p.resumen}»")
            lineas.append(
                f"~C|{pc}|{_texto(p.unidad, avisos, pc)}|{_texto(p.resumen, avisos, pc)}|"
                f"{_num(p.precio)}|{hoy}|0|"
            )
            if p.texto:
                lineas.append(f"~T|{pc}|{_texto(p.texto, avisos, pc)}|")
            posicion = "".join(f"{n}\\" for n in ruta + [j])
            lineas.append(
                f"~M|{cod}{sufijo}\\{pc}|{posicion}|{_num(p.cantidad)}||"
                f"{_texto(p.etiqueta, avisos, pc)}|"
            )
            if p.precio is None:
                avisos.append(f"«{pc}» se escribe sin precio (no consta).")
            if p.cantidad is None:
                avisos.append(f"«{pc}» se escribe sin cantidad (no consta).")

    capitulo(raiz, "##", [])
    contenido = "\r\n".join(lineas) + "\r\n"
    try:
        datos = contenido.encode("cp1252")
    except UnicodeEncodeError:
        datos = contenido.encode("cp1252", errors="replace")
        avisos.append("Algún carácter no existe en el juego ANSI y se ha sustituido por «?».")
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".parcial")
    temporal.write_bytes(datos)
    _verificar(temporal, raiz)
    temporal.replace(destino)
    return destino, avisos


def _esperadas(cap: CapituloBc3) -> list[tuple[str, float | None, float | None]]:
    filas = []
    for sub in cap.capitulos:
        filas += _esperadas(sub)
    filas += [(p.codigo, _cifra(p.cantidad), _cifra(p.precio)) for p in cap.partidas]
    return filas


def _cifra(v: float | None) -> float | None:
    """Como se relee una cifra escrita: con 6 decimales, y un 0 explícito es un campo
    anulado (pág. 2), que el lector lee como «no consta». Sin esto, anular una partida
    (cantidad 0) hacía fallar siempre la verificación (revisión 06-11-2026)."""
    if v is None:
        return None
    v = round(v, 6)
    return None if v == 0 else v


def _verificar(ruta: Path, raiz: CapituloBc3) -> None:
    """Relee el fichero con el lector de TRAZA: debe dar exactamente lo escrito."""
    leido = bc3.leer_partidas(bc3.leer_bc3(ruta))
    obtenidas = [(p.codigo, _cifra(p.cantidad), _cifra(p.precio)) for p in leido.partidas]
    if obtenidas != _esperadas(raiz):
        ruta.unlink(missing_ok=True)
        raise Bc3EscrituraError(
            "El BC3 generado no se relee igual que lo escrito; no se guarda. "
            f"Esperado {_esperadas(raiz)[:3]}…, leído {obtenidas[:3]}…"
        )
