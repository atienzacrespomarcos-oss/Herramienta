"""Comprobaciones deterministas de lo que lee la IA (ADR-0013).

Decisión del usuario: lo que lee la IA entra **directo si cuadra**; lo que no, «a revisar».
Quien decide si cuadra es este módulo, no la IA. Cada línea pasa estas pruebas:

1. **El texto existe donde dice.** El texto literal de cada número (y el principio de la
   descripción) tiene que aparecer en la página citada del PDF, o el valor tiene que estar
   en la celda citada del Excel. Así se descarta una cifra inventada o de otra línea.
2. **El número es el que pone.** TRAZA vuelve a leer el texto literal con sus propias reglas
   (`interpretaciones_documento`) y la lectura de la IA tiene que ser una de ellas. Así se
   caza «2.400» leído como 2,4.
3. **Cuadra la línea.** Si el documento da importe: cantidad × precio = importe (al céntimo).
   Si un número es ambiguo («2.400»), esta prueba decide; si no puede, queda «a revisar».
4. **Cuadra el documento.** Si el documento da total, la suma de importes debe coincidir.
   Si no, se avisa en la medición (las líneas pueden estar bien y faltar alguna).

Tolerancias (criterio de TRAZA, no de norma): un céntimo por línea; para el total, medio
céntimo por línea más medio céntimo, por el redondeo de cada importe.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from traza.app.ordenes import PartidaNueva
from traza.core.numeros import interpretaciones_documento
from traza.io import excel_lectura
from traza.io.pdf import pagina_citada, texto_paginas

TOL_LINEA = 0.01
_REF_CELDA = re.compile(r"^(?P<hoja>.+)!(?P<col>[A-Za-z]{1,3})(?P<fila>[0-9]+)$")
_REF_FILA = re.compile(r"^(?P<hoja>.+)!(?P<fila>[0-9]+)$")


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.replace(" ", " ")).strip().lower()


class Fuente:
    """Lo que hay realmente en el documento, para contrastar con la IA."""

    def texto_para_ia(self) -> str:
        raise NotImplementedError

    def comprobar_numero(
        self, texto: str | None, valor: float, donde: str | None
    ) -> tuple[list[float], str | None]:
        """(lecturas posibles, motivo de rechazo o None)."""
        raise NotImplementedError

    def comprobar_linea(self, descripcion: str, donde: str) -> str | None:
        raise NotImplementedError


class FuentePdf(Fuente):
    def __init__(self, ruta: Path) -> None:
        self.paginas = texto_paginas(ruta)
        self._norm = [_norm(p) for p in self.paginas]

    @property
    def escaneado(self) -> bool:
        return not any(p.strip() for p in self.paginas)

    def texto_para_ia(self) -> str:
        return "\n".join(f"=== Página {i} ===\n{t}" for i, t in enumerate(self.paginas, 1))

    def _pagina(self, donde: str | None) -> tuple[int | None, str | None]:
        n = pagina_citada(donde or "")
        if n is None:
            return None, f"no indica página («{donde}»)"
        if not 1 <= n <= len(self.paginas):
            return None, f"cita la p. {n} y el documento tiene {len(self.paginas)}"
        if not self.paginas[n - 1].strip():
            return None, f"la p. {n} es una imagen: no se puede comprobar contra el documento"
        return n, None

    def comprobar_numero(self, texto, valor, donde):
        n, motivo = self._pagina(donde)
        if motivo:
            return [], motivo
        if not texto or not texto.strip():
            return [], "no copia el texto literal del número"
        if _norm(texto) not in self._norm[n - 1]:
            return [], f"«{texto}» no aparece en la p. {n}"
        return interpretaciones_documento(texto), None

    def comprobar_linea(self, descripcion, donde):
        n, motivo = self._pagina(donde)
        if motivo:
            return motivo
        palabras = _norm(descripcion).split()[:4]
        if palabras and " ".join(palabras) not in self._norm[n - 1]:
            return f"la descripción no aparece en la p. {n}"
        return None


class FuenteExcel(Fuente):
    def __init__(self, ruta: Path) -> None:
        self.ruta = ruta
        self.celdas = excel_lectura.celdas(ruta)
        self.texto, self.avisos = excel_lectura.volcar(ruta)

    def texto_para_ia(self) -> str:
        return self.texto

    def comprobar_numero(self, texto, valor, donde):
        m = _REF_CELDA.match((donde or "").strip())
        if not m:
            return [], f"no indica una celda exacta («{donde}»)"
        clave = f"{m['hoja'].strip(chr(39))}!{m['col'].upper()}{m['fila']}"
        if clave not in self.celdas:
            return [], f"la celda {clave} está vacía o no existe"
        real = self.celdas[clave]
        if isinstance(real, bool):
            return [], f"la celda {clave} no contiene un número"
        if isinstance(real, int | float):
            return [float(real)], None  # valor guardado en el fichero: exacto
        return interpretaciones_documento(str(real)), None

    def comprobar_linea(self, descripcion, donde):
        m = _REF_FILA.match((donde or "").strip()) or _REF_CELDA.match((donde or "").strip())
        if not m:
            return f"no indica la fila de Excel («{donde}»)"
        hoja, fila = m["hoja"].strip("'"), m["fila"]
        textos = [
            _norm(str(v))
            for k, v in self.celdas.items()
            if k.startswith(f"{hoja}!") and re.fullmatch(r"[A-Z]+" + fila, k.split("!", 1)[1])
        ]
        palabras = " ".join(_norm(descripcion).split()[:4])
        if not any(palabras in t for t in textos):
            return f"la descripción no aparece en la fila {fila} de «{hoja}»"
        return None


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
    for n, linea in enumerate(extraido.get("partidas", []), start=1):
        r.partidas.append(_comprobar_linea(n, linea, fuente))
    _comprobar_total(extraido.get("total") or {}, fuente, r)
    revisar = sum(p.estado == "a_revisar" for p in r.partidas)
    if revisar:
        r.avisos.append(
            f"{revisar} partida(s) leídas por IA no superan las comprobaciones: «a revisar»."
        )
    return r


def _comprobar_linea(n: int, ln: dict[str, Any], fuente: Fuente) -> PartidaNueva:
    motivos: list[str] = []
    descripcion = (ln.get("descripcion") or "").strip()
    donde = (ln.get("donde") or "").strip()
    if not descripcion:
        motivos.append("sin descripción")
    else:
        m = fuente.comprobar_linea(descripcion, donde)
        if m:
            motivos.append(m)

    lecturas: dict[str, list[float]] = {}
    valores: dict[str, float | None] = {}
    for campo in ("cantidad", "precio", "importe"):
        dato = ln.get(campo) or {}
        valor = dato.get("valor")
        if valor is None and not dato.get("texto"):
            valores[campo] = None
            continue
        if valor is None:
            motivos.append(f"{campo}: hay texto «{dato.get('texto')}» pero ningún valor")
            valores[campo] = None
            continue
        valores[campo] = float(valor)
        posibles, motivo = fuente.comprobar_numero(
            dato.get("texto"), float(valor), dato.get("donde") or donde
        )
        if motivo:
            motivos.append(f"{campo}: {motivo}")
            continue
        if not any(_cerca(float(valor), x) for x in posibles):
            motivos.append(f"{campo}: la IA lee {valor} y el documento dice «{dato.get('texto')}»")
            continue
        lecturas[campo] = posibles

    cantidad, precio = _resolver(lecturas, valores, motivos)
    return PartidaNueva(
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


def _resolver(lecturas, valores, motivos) -> tuple[float | None, float | None]:
    """Elige cantidad y precio; si hay importe, exige que cuadren y resuelve ambigüedades."""
    c, p, i = (lecturas.get(k) for k in ("cantidad", "precio", "importe"))
    cantidad, precio = valores.get("cantidad"), valores.get("precio")
    if c and p and i:
        combos = [(x, y) for x in c for y in p for z in i if abs(x * y - z) <= TOL_LINEA]
        distintos = {(round(x, 9), round(y, 9)) for x, y in combos}
        if not combos:
            motivos.append("cantidad × precio no coincide con el importe del documento")
        elif len(distintos) > 1:
            motivos.append("número ambiguo en el documento que el importe no resuelve")
        else:
            cantidad, precio = combos[0]
        return cantidad, precio
    for campo, lista in (("cantidad", c), ("precio", p), ("importe", i)):
        if lista and len(lista) > 1:
            motivos.append(f"{campo} ambiguo en el documento (p. ej. «2.400»: ¿2400 o 2,4?)")
    return cantidad, precio


def _comprobar_total(total: dict[str, Any], fuente: Fuente, r: ResultadoIA) -> None:
    valor = total.get("valor")
    if valor is None:
        return
    posibles, motivo = fuente.comprobar_numero(total.get("texto"), float(valor), total.get("donde"))
    if motivo or not any(_cerca(float(valor), x) for x in posibles):
        r.avisos.append(
            f"El total del documento que lee la IA ({valor}) no se puede comprobar: "
            f"{motivo or 'no coincide con el texto'}."
        )
        return
    if len(posibles) > 1:
        r.avisos.append(f"El total del documento «{total.get('texto')}» es ambiguo.")
        return
    r.total_documento = posibles[0]
    importes = [
        p.cantidad * p.precio for p in r.partidas if p.cantidad is not None and p.precio is not None
    ]
    suma = sum(importes)
    tolerancia = 0.005 * len(importes) + 0.005
    if len(importes) < len(r.partidas):
        r.avisos.append(
            f"{len(r.partidas) - len(importes)} partida(s) sin cantidad o precio: no se "
            "puede comprobar el total del documento."
        )
    elif abs(suma - r.total_documento) > tolerancia:
        r.avisos.append(
            f"La suma de las partidas ({round(suma, 2)}) NO coincide con el total del documento "
            f"({r.total_documento}): puede faltar o sobrar alguna línea, o haber descuentos."
        )
