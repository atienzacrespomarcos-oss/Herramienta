"""Reglas del núcleo: procedencia, unidades, tipos y estados."""

from __future__ import annotations

import pytest

from traza.core.estados import Estado, transicion_permitida
from traza.core.procedencia import Origen, Procedencia, ProcedenciaInvalida
from traza.core.tipos import EQUIPO, ValorInvalido, validar_valor
from traza.core.unidades import UnidadInvalida, a_si, comprobar_compatible
from traza.io.pdf import pagina_citada

# --- Procedencia ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"origen": Origen.DOCUMENTO},  # sin documento
        {"origen": Origen.DOCUMENTO, "documento_id": "d"},  # sin localizador
        {"origen": Origen.DOCUMENTO, "documento_id": "d", "localizador": "   "},
        {"origen": Origen.CATALOGO, "localizador": "p. 3"},  # sin documento
        {"origen": Origen.USUARIO, "documento_id": "d", "localizador": "p. 1"},  # contradicción
        {"origen": Origen.HIPOTESIS},  # sin justificación
        {"origen": Origen.HIPOTESIS, "nota": " "},
        {"origen": Origen.CALCULO},  # sin registro de cálculo
        {"origen": Origen.USUARIO, "registro_calculo_id": "r"},
        {"origen": Origen.IA_PROPUESTA, "documento_id": "d"},  # cita incompleta
    ],
)
def test_procedencia_incompleta_se_rechaza(kwargs):
    with pytest.raises(ProcedenciaInvalida):
        Procedencia(**kwargs)


def test_procedencias_validas():
    Procedencia(Origen.USUARIO)
    Procedencia(Origen.DOCUMENTO, documento_id="d", localizador="p. 4")
    Procedencia(Origen.HIPOTESIS, nota="Velocidad objetivo elegida por el proyectista")
    Procedencia(Origen.CALCULO, registro_calculo_id="r")
    assert Procedencia(Origen.IA_PROPUESTA).requiere_confirmacion
    assert Procedencia(Origen.IA_PROPUESTA, documento_id="d", localizador="p. 2")
    assert not Procedencia(Origen.USUARIO).requiere_confirmacion


# --- Unidades ---------------------------------------------------------------------------


def test_conversion_unidades_habituales():
    assert a_si(2400, "m³/h", "m**3/s") == pytest.approx(2400 / 3600)
    assert a_si(12.5, "kW", "W") == pytest.approx(12500)
    assert a_si(1, "W/(m²·K)", "W/(m**2*K)") == pytest.approx(1)


def test_unidades_incompatibles_o_desconocidas():
    with pytest.raises(UnidadInvalida):
        comprobar_compatible("kW", "m**3/s")
    with pytest.raises(UnidadInvalida):
        comprobar_compatible("unidadinventada", "W")


# --- Tipos ------------------------------------------------------------------------------


def test_valores_validados_contra_el_tipo():
    potencia = EQUIPO.propiedad("potencia_frigorifica")
    validar_valor(potencia, 25.3, "kW")
    for valor, unidad in [
        (25.3, None),
        ("25", "kW"),
        (True, "kW"),
        (float("nan"), "kW"),
        (25.3, "m³/h"),
    ]:
        with pytest.raises((ValorInvalido, UnidadInvalida)):
            validar_valor(potencia, valor, unidad)
    fabricante = EQUIPO.propiedad("fabricante")
    validar_valor(fabricante, "Fabricante X", None)
    with pytest.raises(ValorInvalido):
        validar_valor(fabricante, "  ", None)
    with pytest.raises(ValorInvalido):
        validar_valor(fabricante, "X", "kW")


# --- Estados ----------------------------------------------------------------------------


def test_aprobado_no_tiene_salidas_por_avance():
    assert not any(transicion_permitida(Estado.APROBADO, e) for e in Estado)
    assert not any(transicion_permitida(e, Estado.APROBADO) for e in Estado)


# --- Citas de página --------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto,pagina",
    [
        ("p. 14", 14),
        ("p.14", 14),
        ("pág. 3, tabla 2", 3),
        ("Página 7", 7),
        ("p 2", 2),
        ("pliego", None),
        ("tabla 3", None),
        ("", None),
    ],
)
def test_pagina_citada(texto, pagina):
    assert pagina_citada(texto) == pagina
