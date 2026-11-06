"""Escritor BC3: lo que escribe se relee igual con el lector de TRAZA (FIEBDC-3/2024)."""

from __future__ import annotations

from pathlib import Path

import pytest

from traza.io import bc3
from traza.io.bc3_escritura import Bc3EscrituraError, CapituloBc3, PartidaBc3, escribir


def _obra() -> CapituloBc3:
    return CapituloBc3(
        "OBRA",
        "Nave de prueba — modificado nº 1",
        capitulos=[
            CapituloBc3(
                "01",
                "Climatización",
                capitulos=[
                    CapituloBc3(
                        "01.1",
                        "Equipos",
                        partidas=[
                            PartidaBc3(
                                "UTA01",
                                "ud",
                                "Unidad de tratamiento de aire",
                                "Texto largo.",
                                1.0,
                                12500.0,
                                "1.1.1",
                            ),
                        ],
                    ),
                ],
                partidas=[
                    PartidaBc3("CND01", "m2", "Conducto de chapa galvanizada", None, 2400.0, 10.0),
                    PartidaBc3("REJ01", "ud", "Rejilla de impulsión (sin precio)", None, 8.0, None),
                ],
            ),
        ],
    )


def test_escribe_y_relee_igual(tmp_path: Path):
    ruta, avisos = escribir(
        tmp_path / "mod.bc3", _obra(), propiedad="Ingeniero", comentario="Modificado nº 1"
    )
    b = bc3.leer_bc3(ruta)
    r = bc3.leer_partidas(b)
    assert b.version_formato == "FIEBDC-3/2016" and b.tipo_informacion == "2"
    assert b.juego_caracteres == "ANSI"
    assert [(p.codigo, p.cantidad, p.precio) for p in r.partidas] == [
        ("UTA01", 1.0, 12500.0),
        ("CND01", 2400.0, 10.0),
        ("REJ01", 8.0, None),
    ]
    uta = r.partidas[0]
    assert uta.capitulos == [("01", "Climatización"), ("01.1", "Equipos")]
    assert uta.texto == "Texto largo." and uta.etiqueta == "1.1.1"
    assert r.partidas[2].resumen == "Rejilla de impulsión (sin precio)", "tildes en ANSI"
    # Precio de capítulo = suma de sus líneas (pág. 8), para su comprobación.
    assert b.conceptos["01"].precios == [12500.0 + 24000.0]
    assert any("REJ01" in a and "sin precio" in a for a in avisos)
    assert not any("la medición (~M) suma" in a for a in r.avisos)


def test_caracteres_reservados_se_sustituyen_y_se_avisa(tmp_path: Path):
    obra = CapituloBc3(
        "R", "Obra", partidas=[PartidaBc3("P1", "ud", 'Tubo 1|2" ~ codo\\T', None, 1.0, 2.0)]
    )
    ruta, avisos = escribir(tmp_path / "x.bc3", obra, propiedad="", comentario="")
    leido = bc3.leer_partidas(bc3.leer_bc3(ruta)).partidas[0]
    assert leido.resumen == 'Tubo 1/2" / codo/T'
    assert any("caracteres reservados" in a for a in avisos)


def test_caracter_fuera_de_ansi_se_sustituye_y_se_avisa(tmp_path: Path):
    obra = CapituloBc3(
        "R", "Obra", partidas=[PartidaBc3("P1", "ud", "Caudal ≥ 2400 m³/h", None, 1.0, 2.0)]
    )
    ruta, avisos = escribir(tmp_path / "x.bc3", obra, propiedad="", comentario="")
    leido = bc3.leer_partidas(bc3.leer_bc3(ruta)).partidas[0]
    assert leido.resumen == "Caudal ? 2400 m³/h"  # «³» sí existe en ANSI; «≥» no
    assert any("no existe en el juego ANSI" in a for a in avisos)


@pytest.mark.parametrize(
    "obra,mensaje",
    [
        (
            CapituloBc3(
                "R",
                "O",
                partidas=[
                    PartidaBc3("P1", "ud", "a", None, 1, 1),
                    PartidaBc3("P1", "ud", "b", None, 1, 1),
                ],
            ),
            "repetido",
        ),
        (
            CapituloBc3("R", "O", partidas=[PartidaBc3("X" * 21, "ud", "a", None, 1, 1)]),
            "20 caracteres",
        ),
        (CapituloBc3("R", "O", partidas=[PartidaBc3("  ", "ud", "a", None, 1, 1)]), "código vacío"),
    ],
)
def test_codigos_no_validos(tmp_path: Path, obra, mensaje):
    with pytest.raises(Bc3EscrituraError, match=mensaje):
        escribir(tmp_path / "x.bc3", obra, propiedad="", comentario="")
    assert not (tmp_path / "x.bc3").exists()
