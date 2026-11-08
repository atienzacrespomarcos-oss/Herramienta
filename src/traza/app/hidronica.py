"""Sistemas hidráulicos del proyecto (Etapa 7, docs/modules/hidronica.md).

Junta los circuitos guardados (espacios, unidades, longitud) con las cargas de esos
espacios y llama al motor. 2 tubos: un servicio frío/calor con bomba de calor reversible.
4 tubos: dos servicios independientes, frío y calor, con los mismos circuitos.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any

from traza.engines import esquema_hidraulico as eh
from traza.engines import hidraulica as h


@dataclass(frozen=True)
class ResultadoSistema:
    sistema: dict[str, Any]
    servicios: tuple[h.Servicio, ...]
    elementos: tuple[eh.Elemento, ...]
    potencias: dict[str, dict[str, float]]  # circuito → {"frio": W, "calor": W}
    avisos: tuple[str, ...] = field(default=())

    @property
    def potencia_total_kw(self) -> float:
        return sum(s.potencia_kw for s in self.servicios)


def circuitos_guardados(sistema: dict[str, Any]) -> list[dict[str, Any]]:
    c = sistema["circuitos"]
    return json.loads(c) if isinstance(c, str) else c


def calcular(sistema: dict[str, Any], cargas) -> ResultadoSistema:
    """`cargas`: ResultadoCargas del proyecto (sus espacios dan las potencias)."""
    por_id = {e.espacio_id: e for e in cargas.espacios}
    avisos: list[str] = []
    circuitos, potencias = [], {}
    for c in circuitos_guardados(sistema):
        frio = calor = 0.0
        for eid in c["espacios"]:
            e = por_id.get(eid)
            if e is None:
                avisos.append(
                    f"{c['nombre']}: un espacio no tiene cargas o ya no existe; no suma potencia."
                )
                continue
            frio += max(e.verano.total_w, 0.0)
            calor += max(e.invierno.total_w, 0.0)
        potencias[c["nombre"]] = {"frio": frio, "calor": calor}
        circuitos.append(
            h.Circuito(
                c["nombre"],
                frio,
                calor,
                c["unidades"],
                c["longitud_m"],
                c["perdida_terminal_kpa"] * 1000,
                c["exterior"],
            )
        )
    t = h.Temperaturas(
        sistema["frio_impulsion"],
        sistema["frio_retorno"],
        sistema["calor_impulsion"],
        sistema["calor_retorno"],
    )
    claves = ["frio_calor"] if sistema["tipo"] == "2_tubos" else ["frio", "calor"]
    servicios = []
    for clave in claves:
        util = [
            c
            for c in circuitos
            if (clave == "frio" and c.potencia_frio_w > 0)
            or (clave == "calor" and c.potencia_calor_w > 0)
            or (clave == "frio_calor" and max(c.potencia_frio_w, c.potencia_calor_w) > 0)
        ]
        for c in circuitos:
            if c not in util:
                avisos.append(
                    f"{h.SERVICIOS[clave]}: «{c.nombre}» no tiene potencia; no se calcula."
                )
        if not util:
            avisos.append(f"{h.SERVICIOS[clave]}: ningún circuito tiene potencia; no se calcula.")
            continue
        servicios.append(
            h.calcular_servicio(
                clave,
                util,
                sistema["material"],
                t,
                longitud_primario_m=sistema["longitud_primario_m"],
                altura_instalacion_m=sistema["altura_m"],
                volumen_minimo_l_kw=sistema["volumen_minimo_l_kw"],
            )
        )
    total_kw = sum(s.potencia_kw for s in servicios)
    elementos = [e for s in servicios for e in _con_servicio(s, eh.elementos(s, total_kw), claves)]
    for s in servicios:
        avisos.extend(s.avisos)
    return ResultadoSistema(sistema, tuple(servicios), tuple(elementos), potencias, tuple(avisos))


def _con_servicio(s: h.Servicio, elementos, claves) -> list[eh.Elemento]:
    """Con 4 tubos, cada zona dice si es de frío o de calor."""
    if len(claves) == 1:
        return elementos
    prefijo = h.SERVICIOS[s.clave]
    return [replace(e, zona=f"{prefijo} · {e.zona}") for e in elementos]
