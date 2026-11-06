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


@pytest.mark.parametrize(
    "texto", ["", "abc", "nan", "inf", "12 kW", "2 400", "2 4", "1_000", "2_4", "٢٤٠٠", "1,", ",5"]
)
def test_no_numeros(texto):
    with pytest.raises(ValueError):
        leer_numero(texto)


def test_escribir():
    assert escribir_numero(2400.0) == "2400"
    assert escribir_numero(12.5) == "12,5"
    assert escribir_numero(3) == "3"


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("1.234,56", [1234.56]),
        ("1,234.56", [1234.56]),
        ("2.400", [2400.0, 2.4]),
        ("2,400", [2400.0, 2.4]),
        ("12,5", [12.5]),
        ("12.5", [12.5]),
        ("1.250.000", [1250000.0]),
        ("1.250.000,75 €", [1250000.75]),
        ("350 €", [350.0]),
        ("-3,5", [-3.5]),
        ("2.40", [2.4]),
        ("abc", []),
        ("", []),
        ("1.2.3", []),
        # Revisión 06-11-2026:
        ("2 400", [2400.0]),
        ("2 400,50 €", [2400.5]),
        ("12 5", []),
        ("1 2 3", []),
        ("0,500", [0.5]),
        ("0.500", [0.5]),
        ("15 %", [15.0]),
    ],
)
def test_interpretaciones_documento(texto, esperado):
    from traza.core.numeros import interpretaciones_documento

    assert interpretaciones_documento(texto) == pytest.approx(esperado)
