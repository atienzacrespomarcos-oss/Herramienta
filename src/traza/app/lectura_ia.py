"""Comprobaciones deterministas de lo que lee la IA (ADR-0013).

Decisión del usuario: lo que lee la IA entra **directo si cuadra**; lo que no, «a revisar».
Quien decide si cuadra es este módulo, no la IA. Cada línea pasa estas pruebas:

1. **Está en su renglón.** La descripción se localiza en la página citada (PDF) o en la fila
   citada (Excel). Cantidad, precio, importe, unidad y código tienen que estar **en ese
   mismo renglón** (en PDF: el renglón de la descripción y los tres siguientes, por si la
   descripción ocupa varias líneas; en Excel: la misma hoja y fila).
2. **Es el número completo.** El texto de cada número tiene que aparecer como número entero
   (sin una cifra, punto o coma pegados): «2» no vale porque haya un «12» o un «2.400».
3. **El número es el que pone.** TRAZA vuelve a leer ese texto con sus reglas
   (`interpretaciones_documento`) y la lectura de la IA tiene que ser una de ellas.
4. **Cuadra la línea.** Con cantidad y precio, el documento tiene que dar el importe y
   cantidad × precio = importe (tolerancia de un céntimo por redondeo). Sin importe no hay
   forma de detectar una cantidad y un precio intercambiados: queda «a revisar».
5. **Cuadra el documento.** Si el documento da total, la suma de los importes de sus líneas
   tiene que coincidir con él (un céntimo). Si no coincide, se avisa y se muestra.

Historial de fallos corregidos (revisión 06-11-2026), para no reintroducirlos: el número se
buscaba como subcadena en toda la página (un «2» pasaba siempre), no se ataba a la línea, la
falta de importe dejaba la línea «comprobada» sin contraste, y unidad y código no se
comprobaban.

Limitación declarada: se comprueba el texto **extraído** del PDF, no lo visible. Un PDF con
texto oculto (blanco, fuera de página) podría pasar. Ver ADR-0013.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from traza.app.ordenes import PartidaNueva
from traza.core.numeros import interpretaciones_documento
from traza.io import excel_lectura
from traza.io.pdf import pagina_citada, palabras_paginas, texto_paginas

TOL_LINEA = 0.01  # un céntimo: redondeo del importe de una línea
RENGLONES_POR_LINEA = 4  # el de la descripción y 3 más (descripciones en varias líneas)
_REF_CELDA = re.compile(r"^(?P<hoja>.+)!\$?(?P<col>[A-Za-z]{1,3})\$?(?P<fila>[0-9]+)$")
_REF_FILA = re.compile(r"^(?P<hoja>.+)!(?P<fila>[0-9]+)$")


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", str(t).replace(" ", " ")).strip().lower()


def _hoja(nombre: str) -> str:
    """Quita solo un par de comillas envolventes («'Hoja 1'» → «Hoja 1»)."""
    n = nombre.strip()
    return n[1:-1] if len(n) > 1 and n[0] == n[-1] == "'" else n


def _como_numero(texto: str, contenido: str) -> bool:
    """El número aparece entero: sin cifra, punto ni coma pegados por delante ni detrás."""
    t = re.escape(_norm(texto))
    return re.search(rf"(?<![0-9.,]){t}(?![0-9])(?![.,][0-9])", contenido) is not None


def _como_palabra(texto: str, contenido: str) -> bool:
    t = re.escape(_norm(texto))
    return re.search(rf"(?<![\w]){t}(?![\w])", contenido) is not None


@dataclass
class Linea:
    """Dónde está una línea del documento y qué texto contiene su renglón."""

    texto: str  # normalizado
    motivo: str | None = None  # por qué no se ha podido localizar


class Fuente:
    """Lo que hay realmente en el documento, para contrastar con la IA."""

    def texto_para_ia(self) -> str:
        raise NotImplementedError

    def localizar(self, descripcion: str, donde: str) -> Linea:
        raise NotImplementedError

    def numero(
        self, linea: Linea, texto: str | None, donde: str | None
    ) -> tuple[list[float], str | None]:
        """(lecturas posibles, motivo de rechazo o None)."""
        raise NotImplementedError


class FuentePdf(Fuente):
    def __init__(self, ruta: Path) -> None:
        self.paginas = texto_paginas(ruta)
        self.renglones = [_renglones(p) for p in palabras_paginas(ruta)]

    @property
    def paginas_sin_texto(self) -> list[int]:
        return [i for i, p in enumerate(self.paginas, start=1) if not p.strip()]

    @property
    def escaneado(self) -> bool:
        return len(self.paginas_sin_texto) == len(self.paginas)

    def texto_para_ia(self) -> str:
        return "\n".join(f"=== Página {i} ===\n{t}" for i, t in enumerate(self.paginas, 1))

    def localizar(self, descripcion: str, donde: str) -> Linea:
        n = pagina_citada(donde or "")
        if n is None:
            return Linea("", f"no indica página («{donde}»)")
        if not 1 <= n <= len(self.paginas):
            return Linea("", f"cita la p. {n} y el documento tiene {len(self.paginas)}")
        renglones = self.renglones[n - 1]
        if not renglones:
            return Linea("", f"la p. {n} es una imagen: no se puede comprobar contra el documento")
        palabras = _norm(descripcion).split()
        inicio = " ".join(palabras[:4])
        candidatos = [i for i, r in enumerate(renglones) if inicio and inicio in r]
        if not candidatos:
            return Linea("", f"la descripción no aparece en la p. {n}")
        ventanas = [" ".join(renglones[i : i + RENGLONES_POR_LINEA]) for i in candidatos]
        completas = [v for v in ventanas if all(_como_palabra(p, v) for p in palabras)]
        if not completas:
            return Linea("", f"la descripción completa no aparece junta en la p. {n}")
        # Varios renglones iguales: se comprueba contra cualquiera de ellos (la IA no puede
        # colar un número que no esté en alguno de los renglones que empiezan igual).
        return Linea(" ¦ ".join(completas))

    def numero(self, linea, texto, donde):
        if not texto or not texto.strip():
            return [], "no copia el texto literal del número"
        if not any(_como_numero(texto, v) for v in linea.texto.split(" ¦ ")):
            return [], f"«{texto}» no está, como número completo, en el renglón de la línea"
        return interpretaciones_documento(texto), None


def _renglones(palabras: list[tuple[float, float, float, float, str]]) -> list[str]:
    """Agrupa palabras en renglones por su altura en la página (tablas incluidas)."""
    if not palabras:
        return []
    alturas = sorted(w[3] - w[1] for w in palabras)
    tolerancia = max(alturas[len(alturas) // 2] / 2, 1.0)
    renglones: list[list[tuple[float, float, float, float, str]]] = []
    centros: list[float] = []  # altura media del primer elemento de cada renglón
    for w in sorted(palabras, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        centro = (w[1] + w[3]) / 2
        if renglones and abs(centro - centros[-1]) <= tolerancia:
            renglones[-1].append(w)
        else:
            renglones.append([w])
            centros.append(centro)
    return [_norm(" ".join(x[4] for x in sorted(r, key=lambda w: w[0]))) for r in renglones]


class FuenteExcel(Fuente):
    def __init__(self, ruta: Path) -> None:
        libro = excel_lectura.leer_libro(ruta)
        self.texto = libro.texto
        self.celdas = libro.celdas
        self.avisos = libro.avisos

    def texto_para_ia(self) -> str:
        return self.texto

    def _fila(self, hoja: str, fila: str) -> dict[str, Any]:
        return {
            k: v
            for k, v in self.celdas.items()
            if k.rsplit("!", 1)[0] == hoja and re.fullmatch(r"[A-Z]+" + fila, k.rsplit("!", 1)[1])
        }

    def localizar(self, descripcion, donde):
        d = (donde or "").strip()
        m = _REF_FILA.match(d) or _REF_CELDA.match(d)
        if not m:
            return Linea("", f"no indica la fila de Excel («{donde}»)")
        hoja, fila = _hoja(m["hoja"]), m["fila"]
        celdas = self._fila(hoja, fila)
        if not celdas:
            return Linea("", f"la fila {fila} de «{hoja}» está vacía o no existe")
        texto = " ".join(_norm(v) for v in celdas.values())
        if not all(_como_palabra(p, texto) for p in _norm(descripcion).split()):
            return Linea("", f"la descripción no aparece en la fila {fila} de «{hoja}»")
        return Linea(f"{hoja}!{fila}\t{texto}")

    def numero(self, linea, texto, donde):
        m = _REF_CELDA.match((donde or "").strip())
        if not m:
            return [], f"no indica una celda exacta («{donde}»)"
        hoja, fila = _hoja(m["hoja"]), m["fila"]
        if linea.texto.split("\t", 1)[0] != f"{hoja}!{fila}":
            return [], f"la celda {hoja}!{m['col'].upper()}{fila} no es de la fila de la línea"
        clave = f"{hoja}!{m['col'].upper()}{fila}"
        if clave not in self.celdas:
            return [], f"la celda {clave} está vacía o no existe"
        real = self.celdas[clave]
        if isinstance(real, bool):
            return [], f"la celda {clave} no contiene un número"
        if isinstance(real, int | float):
            return [float(real)], None  # valor guardado en el fichero: exacto
        return interpretaciones_documento(str(real)), None


@dataclass
class ResultadoIA:
    partidas: list[PartidaNueva] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    total_documento: float | None = None
    proveedor: str | None = None


def _cerca(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def comprobar(extraido: dict[str, Any], fuente: Fuente) -> ResultadoIA:
    r = ResultadoIA(proveedor=(extraido.get("proveedor") or None))
    importes_doc: list[float | None] = []
    for n, linea in enumerate(extraido.get("partidas", []), start=1):
        partida, importe = _comprobar_linea(n, linea, fuente)
        r.partidas.append(partida)
        importes_doc.append(importe)
    _comprobar_total(extraido.get("total") or {}, fuente, r, importes_doc)
    revisar = sum(p.estado == "a_revisar" for p in r.partidas)
    if revisar:
        r.avisos.append(
            f"{revisar} partida(s) leídas por IA no superan las comprobaciones: «a revisar»."
        )
    return r


def _valor(dato: dict[str, Any], campo: str, motivos: list[str]) -> float | None:
    v = dato.get("valor")
    if v is None:
        if dato.get("texto"):
            motivos.append(f"{campo}: hay texto «{dato.get('texto')}» pero ningún valor")
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        motivos.append(f"{campo}: valor no numérico «{v}»")
        return None


def _comprobar_linea(
    n: int, ln: dict[str, Any], fuente: Fuente
) -> tuple[PartidaNueva, float | None]:
    motivos: list[str] = []
    descripcion = (ln.get("descripcion") or "").strip()
    donde = (ln.get("donde") or "").strip()
    linea = fuente.localizar(descripcion, donde) if descripcion else Linea("", "sin descripción")
    if linea.motivo:
        motivos.append(linea.motivo)

    lecturas: dict[str, list[float]] = {}
    valores: dict[str, float | None] = {}
    for campo in ("cantidad", "precio", "importe"):
        dato = ln.get(campo) or {}
        valores[campo] = _valor(dato, campo, motivos)
        if valores[campo] is None or linea.motivo:
            continue
        posibles, motivo = fuente.numero(linea, dato.get("texto"), dato.get("donde") or donde)
        if motivo:
            motivos.append(f"{campo}: {motivo}")
        elif not any(_cerca(valores[campo], x) for x in posibles):
            motivos.append(
                f"{campo}: la IA lee {valores[campo]} y el documento dice «{dato.get('texto')}»"
            )
        else:
            lecturas[campo] = posibles

    if not linea.motivo:
        texto_renglon = linea.texto.split("\t", 1)[-1]
        for campo in ("unidad", "codigo"):
            v = (ln.get(campo) or "").strip()
            if v and not _como_palabra(v, texto_renglon):
                motivos.append(f"{campo} «{v}» no está en el renglón de la línea")

    cantidad, precio, importe = _resolver(lecturas, valores, motivos)
    partida = PartidaNueva(
        capitulo=[[ln.get("capitulo") or "", ""]] if ln.get("capitulo") else [],
        codigo=ln.get("codigo") or None,
        etiqueta=None,
        unidad=ln.get("unidad") or None,
        resumen=descripcion or None,
        texto=None,
        cantidad=cantidad,
        precio=precio,
        localizador=f"{donde or '¿?'} (línea {n} leída por IA)",
        estado="a_revisar" if motivos else "comprobada",
        motivos=motivos,
    )
    return partida, importe


def _resolver(lecturas, valores, motivos):
    """Elige cantidad, precio e importe; exige que cuadren y resuelve ambigüedades."""
    c, p, i = (lecturas.get(k) for k in ("cantidad", "precio", "importe"))
    cantidad, precio, importe = valores["cantidad"], valores["precio"], valores["importe"]
    if cantidad is None and precio is None:
        motivos.append("sin cantidad ni precio")
        return cantidad, precio, importe
    if cantidad is not None and precio is not None:
        if importe is None:
            motivos.append(
                "la línea no da importe: no se puede contrastar cantidad × precio (podrían "
                "estar intercambiados)"
            )
            return cantidad, precio, importe
        if c and p and i:
            combos = [(x, y, z) for x in c for y in p for z in i if abs(x * y - z) <= TOL_LINEA]
            distintos = {(round(x, 9), round(y, 9)) for x, y, _ in combos}
            if not combos:
                motivos.append("cantidad × precio no coincide con el importe del documento")
            elif len(distintos) > 1:
                motivos.append("número ambiguo en el documento que el importe no resuelve")
            else:
                cantidad, precio, importe = combos[0]
        return cantidad, precio, importe
    for campo, lista in (("cantidad", c), ("precio", p), ("importe", i)):
        if lista and len(lista) > 1:
            motivos.append(f"{campo} ambiguo en el documento (p. ej. «2.400»: ¿2400 o 2,4?)")
    return cantidad, precio, importe


def _comprobar_total(
    total: dict[str, Any], fuente: Fuente, r: ResultadoIA, importes: list[float | None]
) -> None:
    motivos: list[str] = []
    valor = _valor(total, "total", motivos)
    if valor is None:
        if motivos:
            r.avisos.append(f"Total del documento: {motivos[0]}.")
        return
    posibles: list[float] = []
    if isinstance(fuente, FuentePdf):
        n = pagina_citada(total.get("donde") or "")
        if n is None or not 1 <= n <= len(fuente.paginas):
            motivo = "no indica una página válida"
        elif not any(_como_numero(total.get("texto") or "", rg) for rg in fuente.renglones[n - 1]):
            motivo = f"«{total.get('texto')}» no está, como número completo, en la p. {n}"
        else:
            motivo, posibles = None, interpretaciones_documento(total.get("texto") or "")
    else:
        m = _REF_CELDA.match((total.get("donde") or "").strip())
        clave = f"{_hoja(m['hoja'])}!{m['col'].upper()}{m['fila']}" if m else None
        real = fuente.celdas.get(clave) if clave else None  # type: ignore[attr-defined]
        if isinstance(real, int | float) and not isinstance(real, bool):
            motivo, posibles = None, [float(real)]
        else:
            motivo = f"no está en una celda numérica («{total.get('donde')}»)"
    if motivo or not any(_cerca(valor, x) for x in posibles):
        r.avisos.append(
            f"El total del documento que lee la IA ({valor}) no se puede comprobar: "
            f"{motivo or 'no coincide con el texto'}."
        )
        return
    if len(posibles) > 1:
        r.avisos.append(f"El total del documento «{total.get('texto')}» es ambiguo.")
        return
    r.total_documento = posibles[0]
    if any(x is None for x in importes):
        r.avisos.append(
            f"{sum(x is None for x in importes)} línea(s) sin importe: no se puede comprobar "
            "la suma contra el total del documento."
        )
        return
    suma = sum(importes)  # importes del propio documento, ya redondeados
    if abs(suma - r.total_documento) > TOL_LINEA:
        r.avisos.append(
            f"La suma de las partidas ({round(suma, 2)}) NO coincide con el total del documento "
            f"({r.total_documento}): puede faltar o sobrar alguna línea, o haber descuentos."
        )
