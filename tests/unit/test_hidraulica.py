"""Motor hidráulico contra los ejemplos resueltos de la guía IDAE nº 18 y el RITE
(docs/modules/hidronica.md)."""

from __future__ import annotations

import pytest

from traza.engines import esquema_hidraulico as eh
from traza.engines import hidraulica as h
from traza.rules import hidraulica as rh

MCA = 9.80665  # Pa por mm c.a.


def _tubo(material, nombre):
    return next(t for t in rh.TUBOS[material] if t.nombre == nombre)


def test_ejemplo_resuelto_idae_ap_b():
    # Fancoil de 5 kW, 0,238 l/s, agua a 10 °C (IDAE nº 18, Ap. B): 22×1 → 0,76 m/s y
    # 44 mm c.a./m; 25×1,5 → 0,63 m/s y 28 mm c.a./m.
    a = h.agua(10)
    v, r = h.flujo(0.238e-3, _tubo("cobre", "22×1"), a)
    assert v == pytest.approx(0.76, abs=0.005) and r / MCA == pytest.approx(44, abs=0.5)
    v, r = h.flujo(0.238e-3, _tubo("cobre", "25×1,5"), a)
    assert v == pytest.approx(0.63, abs=0.005) and r / MCA == pytest.approx(28, abs=0.5)
    # El caudal del ejemplo: 5 kW con ΔT 5 °C.
    assert h.caudal_m3s(5000, 5, a) * 1000 == pytest.approx(0.238, abs=0.002)


def test_vaso_de_expansion_ejemplo_idae():
    # 260 l a 50 °C, Pi 0,7, Pm 1, PM 2 bar relativos → 9,5 l (la guía redondea Vu a 2,7 l).
    assert rh.coeficiente_expansion(50) == pytest.approx(0.0105, abs=1e-4)
    p = rh.Presiones(1.0, 0.7, 2.0, 2.3, 2.5, 6, 6)
    assert rh.volumen_vaso_l(260, 50, p) == pytest.approx(9.5, rel=0.02)


def test_presiones_como_los_ejemplos_de_la_guia():
    # Caso A de la guía: llenado 1,5 → máxima 2,5 y seguridad 3,0.
    p = rh.presiones((1.5 - 1.0) * 1e5 / (9.80665 * 1000))
    assert (p.llenado, p.maxima_servicio, p.seguridad) == pytest.approx((1.5, 2.5, 3.0))
    assert p.alivio == pytest.approx(2.8)  # RITE: máxima + 0,2 a 0,3
    assert p.prueba == 6.0 and p.nominal == 6
    assert p.inicial_vaso == pytest.approx(1.2)


def test_tablas_del_rite():
    assert (rh.dn_alimentacion(70, frio=False), rh.dn_alimentacion(70, frio=True)) == (15, 20)
    assert rh.dn_alimentacion(400.1, frio=True) == 40
    assert (rh.dn_vaciado(150, frio=False), rh.dn_vaciado(150, frio=True)) == (25, 32)
    assert rh.valvula_retencion(32) == "de clapeta"
    assert "muelle" in rh.valvula_retencion(40) and "muelle" in rh.valvula_retencion(150)
    assert "desmultiplicador" in rh.valvula_corte(100)
    # Aislamiento: 2 tubos (frío 7 °C y calor 45 °C), DN50 (60,3 mm) interior → 30 mm.
    assert rh.espesor_aislamiento_mm(60.3, "interior", 45, 7) == 30
    assert rh.espesor_aislamiento_mm(114.3, "interior", None, 7) == 40
    assert rh.espesor_aislamiento_mm(33.7, "exterior", 45, None) == 35


def test_criterios_de_diametro():
    a = h.agua(7)
    # Hasta DN50 manda también la velocidad (≤ 1,2 m/s); por encima, solo 392 Pa/m.
    q = 10 / 3600
    e = h.elegir_tubo(q, "acero", a)
    assert e.tubo.dn == 65 and e.velocidad_m_s <= 1.2  # en DN50 iría a 1,29 m/s
    grande = h.elegir_tubo(120 / 3600, "acero", a)
    assert grande.friccion_pa_m <= rh.PERDIDA_MAXIMA_PA_M and grande.tubo.dn > 50
    assert not grande.aviso
    assert h.elegir_tubo(500 / 3600, "acero", a).aviso  # más de DN150: se avisa


def _sistema():
    cs = [h.Circuito("C1", 60_000, 50_000, 6, 40), h.Circuito("UTA", 90_000, 70_000, 1, 25)]
    return h.calcular_servicio("frio_calor", cs, altura_instalacion_m=8)


def test_servicio_dos_tubos_completo():
    s = _sistema()
    # 150 kW de frío con ΔT 5 °C (manda frente a 120 kW de calor).
    assert s.potencia_kw == pytest.approx(150)
    assert s.caudal_m3s == pytest.approx(150_000 / (h.agua(7).densidad * h.agua(7).cp * 5))
    assert s.colector.velocidad_m_s <= 0.9
    assert s.colector.tubo.interior_m >= s.primario.tubo.interior_m
    # Inercia: el mínimo (3,5 l/kW) menos SOLO el agua del primario.
    assert s.volumen_minimo_l == pytest.approx(525)
    assert s.inercia_l == pytest.approx(525 - s.volumen_primario_l)
    assert s.volumen_instalacion_l > s.volumen_primario_l
    for c in s.circuitos:
        # Altura = 2·1,3·R·L + unidad + válvula (autoridad 1).
        tuberia = 2 * 1.3 * c.tubo.friccion_pa_m * c.datos.longitud_m
        assert c.altura_bomba_pa == pytest.approx(tuberia + 2 * c.datos.perdida_terminal_pa)
        assert c.aislamiento_mm == 30 or c.aislamiento_mm == 40
    assert s.t_min_c == 5 and s.t_max_c == 45


def test_elementos_sin_omitir_ninguno():
    """Lo que exige el RITE está en la lista, con su artículo."""
    lista = eh.elementos(_sistema())
    texto = {e.elemento for e in lista}
    for obligatorio in (
        "Desconector",
        "Contador",
        "Válvula automática de alivio",
        "Válvula de seguridad con accionamiento manual",
        "Vaso de expansión cerrado de membrana",
        "Válvula de vaciado total",
        "Presostato de mínima",
        "Bomba de primario",
        "Bomba secundaria de velocidad variable",
        "Válvula de equilibrado",
        "Válvula de equilibrado (también de corte)",
        "Purgador automático",
        "Filtro de malla 1 mm",
        "Filtro de malla 0,25 mm",
        "Manómetro diferencial",
        "Colector de impulsión",
        "Colector de retorno",
    ):
        assert obligatorio in texto, obligatorio
    assert all(e.norma for e in lista)
    alivio = next(e for e in lista if e.elemento == "Válvula automática de alivio")
    assert alivio.dn >= 20
    # 150 kW > 70 kW: válvulas independientes de la presión y medida obligatoria.
    assert any("PICV" in e.elemento for e in lista)
    assert all("recomendado" not in e.norma for e in lista)
    unidades = [e for e in lista if e.zona == "Unidades de C1" and e.elemento == "Válvula de corte"]
    assert unidades[0].cantidad == 6


def test_errores_de_datos():
    with pytest.raises(ValueError, match="al menos un circuito"):
        h.calcular_servicio("frio", [])
    with pytest.raises(ValueError, match="salto"):
        h.calcular_servicio(
            "frio", [h.Circuito("C", 1, 0, 1, 1)], temperaturas=h.Temperaturas(12, 7)
        )
    with pytest.raises(ValueError, match="fuera de la tabla"):
        h.agua(95)
