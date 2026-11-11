"""Propuesta de control del proyecto (docs/modules/control.md).

Toma lo ya diseñado (cargas por espacio, redes de aire, sistemas hidráulicos) y se lo da al
motor puro `engines/control.py`. No guarda nada: se recalcula con el proyecto y siempre está
al día; lo que el usuario se lleva es el Excel.
"""

from __future__ import annotations

from dataclasses import dataclass

from traza.engines import control as mc
from traza.engines.hidraulica import SERVICIOS


@dataclass(frozen=True)
class PropuestaControl:
    resultado: mc.ResultadoControl
    avisos: tuple[str, ...]


def entradas(cargas, redes: list, sistemas: list) -> tuple[list, list, list, bool, list[str]]:
    """`cargas`: ResultadoCargas o None; `redes`: ResultadoRedAire; `sistemas`:
    ResultadoSistema. Devuelve las entradas del motor y los avisos."""
    avisos: list[str] = []
    espacios = []
    if cargas is not None:
        for c in cargas.espacios:
            espacios.append(
                mc.EspacioControl(
                    c.nombre or c.codigo,
                    c.uso.clave,
                    c.uso.nombre,
                    c.uso.t_invierno is not None,
                    c.uso.ventilacion.metodo,
                )
            )
    aire = [
        mc.RedControl(
            r.red["nombre"], r.red["tipo"], r.caudal_total_m3h, bool(r.red["climatizacion"])
        )
        for r in redes
    ]
    servicios = []
    for r in sistemas:
        total_kw = sum(s.potencia_kw for s in r.servicios)
        for s in r.servicios:
            servicios.append(
                mc.ServicioControl(
                    r.sistema["nombre"],
                    SERVICIOS[s.clave],
                    s.clave in ("frio", "frio_calor"),
                    s.clave in ("calor", "frio_calor"),
                    total_kw,
                    tuple(
                        mc.CircuitoControl(c.datos.nombre, c.datos.unidades) for c in s.circuitos
                    ),
                )
            )
    if servicios:
        refrigeracion = any(s.frio for s in servicios)
    else:
        # Sin sistema hidráulico TRAZA no sabe con qué se climatiza (p. ej. expansión
        # directa, fuera de alcance): se supone frío y calor, lo habitual en terciario.
        refrigeracion = True
        if espacios:
            avisos.append(
                "Sin sistema hidráulico: se supone calefacción y refrigeración (THM-C3) en "
                "los espacios climatizados"
            )
    return espacios, aire, servicios, refrigeracion, avisos


def proponer(cargas, redes: list, sistemas: list, avisos_previos=()) -> PropuestaControl:
    espacios, aire, servicios, refrigeracion, avisos = entradas(cargas, redes, sistemas)
    resultado = mc.proponer(espacios, aire, servicios, refrigeracion)
    return PropuestaControl(resultado, tuple(avisos_previos) + tuple(avisos))
