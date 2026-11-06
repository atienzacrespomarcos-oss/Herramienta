import pytest

from traza.core.numeros import NumeroAmbiguo, escribir_numero, leer_numero


@pytest.mark.parametrize(
    "texto,valor",
    [
        ("2400", 2400),
        ("2400,5", 2400.5),
        ("2400.5", 2400.5),
        (" 12,5 ", 12.5),
        ("-3", -3),
        ("0,75", 0.75),
        ("1.25", 1.25),
        ("1e3", 1000.0),
    ],
)
def test_leer(texto, valor):
    assert leer_numero(texto) == valor


@pytest.mark.parametrize("texto", ["2.400", "1.250.000", "2.400,5", "-2.400"])
def test_ambiguos(texto):
    with pytest.raises(NumeroAmbiguo):
        leer_numero(texto)


@pytest.mark.parametrize("texto", ["", "abc", "nan", "inf", "12 kW"])
def test_no_numeros(texto):
    with pytest.raises(ValueError):
        leer_numero(texto)


def test_escribir():
    assert escribir_numero(2400.0) == "2400"
    assert escribir_numero(12.5) == "12,5"
    assert escribir_numero(3) == "3"
