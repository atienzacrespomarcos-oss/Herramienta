"""Catálogo de usos: cada valor propuesto lleva su fuente y es coherente.

Los números concretos se cotejaron uno a uno con la tabla de ASHRAE reproducida en la ayuda
de Revit (39 de 39 iguales, 07-11-2026). Aquí se prueba lo que no debe romperse al ampliarlo.
"""

from __future__ import annotations

import pytest

from traza.engines.clima import COBERTURAS
from traza.rules.usos import GRUPOS, IDA_PERSONA, IDA_SUPERFICIE, POR_CLAVE, USOS

METODOS = {"persona_ida", "superficie_ida", "trabajador", "fijo", "lamina"}


def test_claves_unicas_y_grupos():
    assert len(POR_CLAVE) == len(USOS)
    # Lo que el usuario pidió cubrir (07-11-2026).
    for g in ("Oficinas", "Hotel", "Sanitario", "Comercial", "Logística", "Industria", "Frío",
              "Salas limpias"):  # fmt: skip
        assert g in GRUPOS


@pytest.mark.parametrize("uso", USOS, ids=lambda u: u.clave)
def test_cada_uso_tiene_fuentes_y_valores_coherentes(uso):
    assert uso.tipo_ashrae and uso.fuente_temperaturas and uso.ventilacion.fuente
    assert uso.personas_100m2 > 0 and uso.sensible_btuh > 0 and uso.latente_btuh >= 0
    assert uso.iluminacion_w_ft2 > 0 and uso.equipos_w_ft2 > 0
    assert uso.cobertura in COBERTURAS
    v = uso.ventilacion
    assert v.metodo in METODOS
    if v.metodo == "persona_ida":
        assert v.valor in IDA_PERSONA
    if v.metodo == "superficie_ida":
        # El RITE no admite el método por superficie en IDA 1 (tabla 1.4.2.4).
        assert v.valor in IDA_SUPERFICIE
    if uso.t_invierno is not None:
        assert uso.t_invierno <= uso.t_verano


def test_conversiones_a_unidades_si():
    oficina = POR_CLAVE["oficina_abierta"]
    # 250 Btu/h = 73,3 W; 200 Btu/h = 58,6 W; 1,1 W/ft² = 11,8 W/m²; 5 personas/100 m².
    assert oficina.sensible_w == pytest.approx(73.27, abs=0.01)
    assert oficina.latente_w == pytest.approx(58.61, abs=0.01)
    assert oficina.iluminacion_w_m2 == pytest.approx(11.84, abs=0.01)
    assert oficina.m2_persona == pytest.approx(20.0)


def test_criterios_normativos_por_uso():
    # RITE: 21/25 °C; IDA 1 en hospitales; IDA 3 en habitaciones de hotel.
    assert (POR_CLAVE["despacho"].t_invierno, POR_CLAVE["despacho"].t_verano) == (21, 25)
    assert POR_CLAVE["habitacion_hospital"].ventilacion.valor == 1
    assert POR_CLAVE["habitacion_hotel"].ventilacion.valor == 3
    # IDAE 5.2: cobertura alta en hospitales y centros de cálculo.
    assert POR_CLAVE["quirofano"].cobertura == "alta"
    assert POR_CLAVE["centro_calculo"].cobertura == "alta"
    # RD 486/1997: 50 m³/h por trabajador y trabajo ligero 14–25 °C.
    almacen = POR_CLAVE["almacen"]
    assert almacen.ventilacion.metodo == "trabajador" and almacen.ventilacion.valor == 50
    assert (almacen.t_invierno, almacen.t_verano) == (14, 25)
    # UNE 100713: 1200 m³/h de aire exterior por quirófano.
    assert POR_CLAVE["quirofano"].ventilacion.valor == 1200
    # RD 1109/1991: congelados a −18 °C o menos.
    assert POR_CLAVE["camara_congelacion"].t_verano <= -18
    # RITE IT 1.1.4.1.2.3: aire de piscina con un máximo de 30 °C.
    assert POR_CLAVE["piscina"].t_verano <= 30
    assert POR_CLAVE["sala_limpia_iso7"].impulsion_renovaciones == pytest.approx(45)
