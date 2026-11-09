"""Subcuadros eléctricos de clima del proyecto (Etapa 8, docs/modules/electricidad.md).

Calcula un subcuadro guardado y propone salidas desde los equipos ya dimensionados en la
herramienta (sistemas hidráulicos y redes de aire). La potencia eléctrica la pone el
usuario con la ficha del modelo elegido (también la de los ventiladores).
"""

from __future__ import annotations

import json
from typing import Any

from traza.engines import subcuadro as sc


def salidas_guardadas(sub: dict[str, Any]) -> list[dict[str, Any]]:
    s = sub["salidas"]
    return json.loads(s) if isinstance(s, str) else s


def calcular(sub: dict[str, Any]) -> sc.ResultadoSubcuadro:
    salidas = [
        sc.Salida(
            s["nombre"],
            s["potencia_kw"],
            s["fases"],
            s["longitud_m"],
            s["motor"],
            s["variador"],
            s["cos_phi"],
            s["metodo"],
        )
        for s in salidas_guardadas(sub)
    ]
    return sc.calcular(
        salidas,
        sub["suministro"],
        sub["longitud_alimentacion_m"],
        sub["metodo_alimentacion"],
        sub["nombre"],
    )


def propuestas(sistemas: list, redes: list) -> list[dict[str, Any]]:
    """Salidas propuestas. `sistemas`: ResultadoSistema calculados; `redes`:
    ResultadoRedAire calculados. Potencia 0 = la pone el usuario (ficha del equipo)."""
    from traza.engines.hidraulica import SERVICIOS

    salidas: list[dict[str, Any]] = []

    def add(nombre, potencia=0.0, fases=3, motor=True, variador=False, longitud=20.0):
        salidas.append(
            {
                "nombre": nombre,
                "potencia_kw": round(potencia, 2),
                "fases": fases,
                "longitud_m": longitud,
                "motor": motor,
                "variador": variador,
                "cos_phi": 0.85,
                "metodo": "E",
            }
        )

    for r in sistemas:
        for s in r.servicios:
            sufijo = f"{r.sistema['nombre']}" + (
                f" {SERVICIOS[s.clave].lower()}" if len(r.servicios) > 1 else ""
            )
            generador = {"frio": "Enfriadora", "calor": "Generador de calor"}.get(
                s.clave, "Bomba de calor"
            )
            add(f"{generador} {sufijo}")
            add(f"Bomba primario {sufijo}")
            for c in s.circuitos:
                add(f"Bomba {c.datos.nombre} {sufijo}", variador=True)
                add(
                    f"Unidades {c.datos.nombre} {sufijo}",  # sin el número: «Proponer» la duplicaba
                    fases=1,
                    motor=False,
                    variador=True,
                )
    for r in redes:
        if r.calculo is None:
            continue
        # Potencia de la ficha del ventilador elegido, no la máxima de la SFP (una cota que
        # se quedaba sin revisar; revisión 09-11-2026).
        add(f"Ventilador {r.red['nombre']}")
    # Nombres únicos (la orden los exige).
    vistos: dict[str, int] = {}
    for s in salidas:
        n = vistos.get(s["nombre"], 0)
        vistos[s["nombre"]] = n + 1
        if n:
            s["nombre"] = f"{s['nombre']} ({n + 1})"
    return salidas
