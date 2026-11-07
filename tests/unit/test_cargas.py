"""Motores solar y de cargas: casos de resultado conocido calculados a mano en la prueba
(docs/TESTING_STRATEGY.md §0.2)."""

from __future__ import annotations

import math

import pytest

from traza.core import psicrometria as ps
from traza.engines import cargas as cg
from traza.engines import solar
from traza.rules.usos import POR_CLAVE, caudal_exterior_m3h

# --- Solar --------------------------------------------------------------------------------


def _mediodia_julio_40n():
    # Día 202: δ = 23,45·sen(360·486/365) = 20,44°; altura = 90 − 40 + 20,44 = 70,44°.
    d = 23.45 * math.sin(2 * math.pi * 486 / 365)
    sen_alt = math.sin(math.radians(90 - 40 + d))
    i_dn = 1085 * math.exp(-0.207 / sen_alt)  # ≈ 871 W/m²
    return d, sen_alt, i_dn


def test_irradiancia_horizontal_a_mediodia():
    _, sen_alt, i_dn = _mediodia_julio_40n()
    i = solar.irradiancia(40, 7, 12, 0, 0)
    assert i.directa == pytest.approx(i_dn * sen_alt)
    assert i.difusa == pytest.approx(0.136 * i_dn)
    assert i.reflejada == pytest.approx(0, abs=1e-9)
    # ≈ 939 W/m² (≈ 298 Btu/h·ft²), el orden de las tablas de ASHRAE para 40° N en julio.
    assert i.total == pytest.approx(939, abs=2)


def test_irradiancia_fachada_sur_a_mediodia():
    d, sen_alt, i_dn = _mediodia_julio_40n()
    i = solar.irradiancia(40, 7, 12, 180, 90)
    assert i.directa == pytest.approx(i_dn * math.sin(math.radians(40 - d)))
    assert i.difusa == pytest.approx(0.136 * i_dn / 2)
    assert i.reflejada == pytest.approx(0.2 * i_dn * (sen_alt + 0.136) / 2)
    assert solar.irradiancia(40, 7, 12, 0, 90).directa == pytest.approx(0, abs=1e-6)  # norte


def test_simetria_este_oeste_y_noche():
    este = solar.irradiancia(40, 7, 9, 90, 90).total
    oeste = solar.irradiancia(40, 7, 15, 270, 90).total
    assert este == pytest.approx(oeste) and este > 500
    assert solar.irradiancia(40, 7, 2, 90, 90).total == 0


# --- Cargas -------------------------------------------------------------------------------

P = 101_325.0
CLIMA = cg.Clima(
    latitud=40, presion_pa=P, invierno_ts_c=-4, verano_ts_c=36, verano_w=0.010, oscilacion_c=14
)


def _local(**kw):
    base = dict(
        nombre="Local",
        area_m2=100,
        volumen_m3=300,
        t_invierno_c=21,
        t_verano_c=25,
        cerramientos=(
            cg.Cerramiento("Muro sur", "opaco", 30, 0.5),
            cg.Cerramiento("Ventana sur", "hueco", 6, 2.8, factor_solar=0.6),
            cg.Cerramiento("Solera", "terreno", 100, 0.2),
        ),
    )
    base.update(kw)
    return cg.Espacio(**base)


def _gasto(caudal_m3h, t, w):
    rho = P / (287.042 * (t + 273.15) * (1 + 1.607858 * w))
    return rho * caudal_m3h / 3600, 1006 + 1860 * w


def test_invierno_por_partidas():
    r = cg.invierno(_local(aire_exterior_m3h=100, infiltracion_m3h=30), CLIMA)
    d = {p.concepto: p.sensible_w for p in r.partidas}
    # ΔT = 21 − (−4) = 25 K.
    assert d["Transmisión por cerramientos opacos"] == pytest.approx(0.5 * 30 * 25)  # 375
    assert d["Transmisión por huecos"] == pytest.approx(2.8 * 6 * 25)  # 420
    assert d["Solera y terreno"] == pytest.approx(0.2 * 100 * 25)  # 500
    w = ps.humedad_especifica_relativa(21, 0.40, P)
    m, cp = _gasto(100, 21, w)
    assert d["Ventilación"] == pytest.approx(m * cp * 25)
    assert d["Ventilación"] == pytest.approx(840, abs=15)  # ≈ 0,34 W·h/(m³·K)·100·25
    assert d["Infiltración"] == pytest.approx(0.3 * d["Ventilación"])
    con_recuperador = cg.invierno(_local(aire_exterior_m3h=100, recuperacion=0.5), CLIMA)
    vent = {p.concepto: p.sensible_w for p in con_recuperador.partidas}["Ventilación"]
    assert vent == pytest.approx(d["Ventilación"] / 2)
    assert r.notas and r.total_w == pytest.approx(sum(d.values()))


def test_espacio_sin_calefaccion():
    r = cg.invierno(_local(t_invierno_c=None), CLIMA)
    assert r.total_w == 0 and "sin calefacción" in r.notas[0]


def test_perfil_de_temperatura_exterior():
    # Máxima a las 14–15 h solares, mínima a las 5 h (fracciones de ASHRAE).
    assert cg.temperatura_exterior(CLIMA, 15) == 36
    assert cg.temperatura_exterior(CLIMA, 5) == pytest.approx(36 - 14)
    assert cg.temperatura_exterior(CLIMA, 9) == pytest.approx(36 - 0.55 * 14)


def test_verano_cargas_internas_y_ventilacion():
    e = _local(
        cerramientos=(),
        personas=10,
        sensible_persona_w=73.3,
        latente_persona_w=58.6,
        iluminacion_w=1000,
        equipos_w=500,
        aire_exterior_m3h=450,
    )
    r = cg.verano(e, CLIMA)
    assert r.hora_solar == 14 and r.t_exterior_c == 36  # la hora más calurosa
    d = {p.concepto: p for p in r.partidas}
    assert (d["Personas"].sensible_w, d["Personas"].latente_w) == pytest.approx((733, 586))
    w_i = ps.humedad_especifica_relativa(25, 0.5, P)
    m, cp = _gasto(450, 25, w_i)
    assert d["Ventilación"].sensible_w == pytest.approx(m * cp * 11)
    assert d["Ventilación"].latente_w == pytest.approx(m * 2_501_000 * (0.010 - w_i))
    assert r.notas and len(r.perfil_w) == 24 and max(r.perfil_w) == pytest.approx(r.total_w)


def test_verano_cubierta_con_temperatura_sol_aire():
    cubierta = cg.Cerramiento("Cubierta", "opaco", 100, 0.5, azimut=0, inclinacion=0)
    r = cg.verano(_local(cerramientos=(cubierta,)), CLIMA)
    h = r.hora_solar
    i = solar.irradiancia(40, 7, h, 0, 0).total
    t_sa = cg.temperatura_exterior(CLIMA, h) + 0.052 * i - 3.9
    assert r.partidas[0].sensible_w == pytest.approx(0.5 * 100 * (t_sa - 25))
    assert 12 <= h <= 14  # entre el sol más alto y el aire más caliente


def test_hora_punta_por_orientacion_y_simultaneidad():
    def con_ventana(azimut):
        v = cg.Cerramiento("Ventana", "hueco", 20, 2.8, azimut=azimut, factor_solar=0.6)
        return _local(cerramientos=(v,))

    este, oeste = cg.verano(con_ventana(90), CLIMA), cg.verano(con_ventana(270), CLIMA)
    assert este.hora_solar < 12 < oeste.hora_solar
    hora, total = cg.verano_simultaneo([con_ventana(90), con_ventana(270)], CLIMA)
    assert total < este.total_w + oeste.total_w  # no coinciden en la misma hora
    assert total == pytest.approx(este.perfil_w[hora - 1] + oeste.perfil_w[hora - 1])


def test_particion_con_local_no_acondicionado_y_errores():
    p = cg.Cerramiento(
        "Al almacén", "interior", 20, 1.0, t_contigua_invierno_c=10, t_contigua_verano_c=30
    )
    r = cg.invierno(_local(cerramientos=(p,)), CLIMA)
    assert r.partidas[0].sensible_w == pytest.approx(20 * 11)
    with pytest.raises(ValueError):
        cg.Cerramiento("Sin dato", "interior", 20, 1.0)
    with pytest.raises(ValueError):
        cg.Cerramiento("Rara", "ventanal", 20, 1.0)
    with pytest.raises(ValueError):
        _local(recuperacion=1.2)


def test_infiltracion_cte_y_en_12831():
    # Nave de 50 × 100 × 10 m nueva: Ao = 3000 + 5000 m², sin huecos.
    n = cg.n50(50_000, 8000, 0, cg.CO_OPACO["nuevo"], cg.CH_CLASE[3])
    assert n == pytest.approx(0.629 * 16 * 8000 / 50_000)  # 1,61 h⁻¹
    v = cg.infiltracion_m3h(50_000, n, fachadas_expuestas=4, altura_m=10)
    assert v == pytest.approx(2 * 50_000 * n * 0.03)  # ≈ 4830 m³/h, 0,1 ren/h
    assert cg.infiltracion_m3h(1000, 5, 1, 20) == pytest.approx(2 * 1000 * 5 * 0.02 * 1.2)
    assert cg.infiltracion_m3h(1000, 5, 0, 5) == 0


def test_caudal_exterior_por_uso():
    assert caudal_exterior_m3h(POR_CLAVE["oficina_abierta"], 200, 10) == pytest.approx(450)
    assert caudal_exterior_m3h(POR_CLAVE["almacen"], 2000, 4) == pytest.approx(200)
    assert caudal_exterior_m3h(POR_CLAVE["aseos"], 100, 0) == pytest.approx(198)
    assert caudal_exterior_m3h(POR_CLAVE["quirofano"], 40, 6) == 1200
    assert caudal_exterior_m3h(POR_CLAVE["piscina"], 300, 30) == pytest.approx(2700)


def test_aire_exterior_seco_no_resta_latente():
    # w exterior 0,006 < w interior (25 °C, 50 %): sin crédito deshumectante.
    seco = cg.Clima(
        latitud=40, presion_pa=P, invierno_ts_c=-4, verano_ts_c=36, verano_w=0.006, oscilacion_c=14
    )
    r = cg.verano(_local(cerramientos=(), aire_exterior_m3h=1000, infiltracion_m3h=100), seco)
    d = {p.concepto: p for p in r.partidas}
    assert d["Ventilación"].latente_w == 0 and d["Infiltración"].latente_w == 0
    assert any("deshumectante" in n for n in r.notas)
