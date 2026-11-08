"""Ventilación ambiental por renovaciones por hora (docs/modules/redes_aire.md, «Ventilación»).

Fuente: Soler & Palau, *Manual práctico de ventilación*, cap. 3 «Ventilación ambiental»,
p. 41–42:
<https://info.solerpalau.com/hubfs/Ebooks/SPL%20-%20Manual%20pr%C3%A1ctico%20de%20ventilaci%C3%B3n/Manual%20de%20ventilacion_completo_LR.pdf>
- Tabla 3.5, renovaciones por tipo de local (orientativas), p. ej. fábricas en general y
  talleres de mecanizado 5–10, naves con hornos y baños sin campanas 30–60, talleres de
  pintura 40–60. Se citan para elegir unas renovaciones fijas.
- Tabla 3.6, la simplificación por volumen del recinto, que el manual dice que «da buenos
  resultados con carácter general». Es la que se aplica por defecto.
El manual añade el mínimo legal del RD 486/1997, anejo III (30 o 50 m³/h por trabajador): por
eso el caudal de un espacio es el mayor entre estas renovaciones y su aire exterior.
"""

from __future__ import annotations

FUENTE = "Soler & Palau, Manual práctico de ventilación, cap. 3, tabla 3.6"

#: Tabla 3.6: (volumen máximo del recinto en m³, renovaciones/hora). Los límites del manual se
#: solapan (≤ 1000 y 1000 ≤ V): el valor justo en el límite toma el tramo de menor volumen.
POR_VOLUMEN: tuple[tuple[float, float], ...] = (
    (1000.0, 20.0),
    (5000.0, 15.0),
    (10000.0, 10.0),
    (float("inf"), 6.0),
)

#: Rango de la tabla 3.5 (catedrales 0,5; talleres de pintura hasta 60).
RENOVACIONES_MIN = 0.5
RENOVACIONES_MAX = 60.0


def renovaciones_por_volumen(volumen_m3: float) -> float:
    """Renovaciones por hora de la tabla 3.6 para un recinto de ese volumen."""
    if volumen_m3 < 0:
        raise ValueError("El volumen no puede ser negativo.")
    for maximo, n in POR_VOLUMEN:
        if volumen_m3 <= maximo:
            return n
    raise AssertionError("inalcanzable: el último tramo no tiene límite")
