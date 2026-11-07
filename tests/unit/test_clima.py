"""Condiciones exteriores de proyecto (criterios de la guía del IDAE) y lector de la guía.

Los datos de estación de estas pruebas son INVENTADOS a propósito (la guía prohíbe
reproducir los suyos y el repositorio es público): lo que se prueba es el criterio.
"""

from __future__ import annotations

import pytest

from traza.core import psicrometria as ps
from traza.engines.clima import DatosEstacion, condiciones
from traza.io.clima_idae import GuiaNoReconocida, leer_pagina

EST = DatosEstacion(
    altitud_m=500, ts_996=-4.0, ts_99=-2.5, hum_coin=80, ts_04=37.0, thc_04=20.0, ts_1=35.5,
    thc_1=19.5,
)  # fmt: skip


def test_percentiles_segun_cobertura():
    n = condiciones(EST)
    a = condiciones(EST, "alta")
    assert (n.invierno_ts, n.verano_ts) == (-2.5, 35.5)
    assert (a.invierno_ts, a.verano_ts) == (-4.0, 37.0)
    assert n.verano_th == pytest.approx(19.5, abs=1e-3)  # misma cota: la coincidente
    assert n.invierno_hr == pytest.approx(0.80)
    assert n.presion_pa == pytest.approx(ps.presion_atmosferica(500))


def test_obra_por_encima_de_la_estacion():
    # 300 m por encima: −3 °C en las secas, misma humedad absoluta (anexo 7.3).
    c = condiciones(EST, altitud_obra_m=800)
    assert c.correccion_cota_c == pytest.approx(3.0)
    assert (c.invierno_ts, c.verano_ts) == pytest.approx((-5.5, 32.5))
    w_est = ps.humedad_especifica_bulbo_humedo(35.5, 19.5, ps.presion_atmosferica(500))
    assert c.verano_w == pytest.approx(w_est)
    assert c.verano_th < 19.5  # más fría y a menos presión, misma w → húmeda menor
    assert c.invierno_hr > 0.80  # misma humedad absoluta a menos temperatura
    assert "anexo 7.3" in c.notas[0]


def test_obra_por_debajo_de_la_estacion():
    c = condiciones(EST, altitud_obra_m=100)
    assert c.correccion_cota_c == 0 and c.verano_ts == 35.5
    assert "por debajo" in c.notas[0]


def test_cobertura_no_prevista():
    with pytest.raises(ValueError):
        condiciones(EST, "maxima")


PAGINA = """Guía técnica
Provincia
Estación
Indicativo
Ficticia
Villa Ficticia (Aeropuerto)
0000
Ubicación: AEROPUERTO
Nº de observaciones y periodo
a.s.n.m. (m)
Lat.
Long.
T seca
Hum. relativa
T terreno
Rad
612
41
O30’00’’
02
O15’00’’E
87.600
Condiciones proyecto calefacción (Temperatura seca exterior mínima)
TSMIN (
OC)
TS_ 99,6 (
OC)
TS_ 99 (
OC)
OMDC (
OC)
HUMcoin (%)
OMA (
OC)
-12,0
-5,0
-3,5
13,0
85
42,0
Condiciones proyecto refrigeración (Temperatura SECA exterior máxima)
TSMAX (
OC)
TS_ 0,4 (
OC)
THC_0,4 (
OC)
TS_1 (
OC)
THC_1 (
OC)
TS_ 2 (
OC)
THC_2 (
OC)
OMDR (
OC)
41,0
37,0
20,1
35,6
19,8
34,0
19,5
18,0
Condiciones proyecto refrigeración (Temperatura húmeda exterior máxima)
TH_ 0,4 (
OC)
TSC_0,4 (
OC)
TH_ 1 (
OC)
TSC_1 (
OC)
TH_ 2 (
OC)
TSC_2 (
OC)
21,5
33,0
21,0
32,0
20,2
31,5
Valores medios mensuales
"""


def test_lector_de_ficha_de_estacion():
    e = leer_pagina(PAGINA, 42)
    assert (e.provincia, e.nombre, e.indicativo, e.pagina) == (
        "Ficticia",
        "Villa Ficticia (Aeropuerto)",
        "0000",
        42,
    )
    assert (
        e.altitud_m == 612
        and e.latitud == pytest.approx(41.5)
        and e.longitud == pytest.approx(2.25)
    )
    assert (e.ts_996, e.ts_99, e.hum_coin) == (-5.0, -3.5, 85)
    assert (e.ts_1, e.thc_1, e.omdr) == (35.6, 19.8, 18.0)
    assert (e.th_04, e.tsc_04, e.tsc_2) == (21.5, 33.0, 31.5)


def test_ficha_con_solo_temperaturas_humedas():
    # Algunas estaciones de la guía dan solo TH 0,4/1/2 %: la seca coincidente no consta.
    texto = PAGINA.replace("21,5\n33,0\n21,0\n32,0\n20,2\n31,5\n", "21,5\n21,0\n20,2\n")
    e = leer_pagina(texto, 1)
    assert (e.th_04, e.th_1, e.th_2) == (21.5, 21.0, 20.2) and e.tsc_04 is None


def test_longitud_oeste_negativa_y_pagina_que_no_es_ficha():
    e = leer_pagina(PAGINA.replace("O15’00’’E", "O15’00’’W"), 1)
    assert e.longitud == pytest.approx(-2.25)
    assert leer_pagina("Índice\nObjetivo\n", 1) is None
    with pytest.raises(GuiaNoReconocida):
        leer_pagina(PAGINA.replace("-3,5\n", "texto\n"), 1)
