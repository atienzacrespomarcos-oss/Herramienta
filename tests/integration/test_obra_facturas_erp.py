"""Obra, bloque 4b: facturas desde el listado del ERP (docs/modules/obra.md).

Listados inventados, con las formas típicas de un ERP: CSV español con varias obras, Excel
sin base imponible (total, IVA y retención), tabla HTML guardada como .xls con títulos que
TRAZA no reconoce (los dice la IA simulada). Paquetes del comparativo inventado de
tests/integration/test_obra.py: EQUIPOS, CHAPA, MANO DE OBRA.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from openpyxl import Workbook
from tests.integration.test_obra import comparativo, obra  # noqa: F401 (fixture)
from tests.integration.test_obra_coste_real import con_coste  # noqa: F401 (fixture)

from traza.app.ordenes import OrdenRechazada

CSV = (
    "Listado de facturas recibidas;;;;;;;\r\n"
    "Proveedor;Nº factura;Fecha factura;Base imponible;% IVA;Cuota IVA;Total;Obra\r\n"
    "Climatización Pérez SL;F-001;03/10/2026;12.000,00;21%;2.520,00;14.520,00;OB-25 Nave\r\n"
    "Chapas Norte SA;7;15/10/2026;1.000,50;21%;210,11;1.210,61;OB-25 Nave\r\n"
    "Chapas Norte SA;8;20/10/2026;(100,00);21%;(21,00);(121,00);OB-25 Nave\r\n"
    "Otro Proveedor;X-1;21/10/2026;999,00;21%;209,79;1.208,79;OB-31 Oficinas\r\n"
    ";;;;;;;\r\n"
    "Total;;;12.900,50;;;;\r\n"
)


def _csv(tmp_path, texto=CSV, nombre="Facturas octubre.csv"):
    ruta = tmp_path / nombre
    ruta.write_bytes(texto.encode("cp1252"))
    return ruta


def _leer(p, ruta):
    return p.leer_facturas_erp(p.incorporar_documento(ruta))


def _elegir(propuestas, paquete_por_defecto="EQUIPOS"):
    return [
        {
            "paquete": x.paquete or paquete_por_defecto,
            "proveedor": x.leida.proveedor,
            "numero": x.leida.numero,
            "fecha": x.leida.fecha,
            "importe": x.leida.importe,
        }
        for x in propuestas
        if x.estado == "nueva"
    ]


def test_listado_csv_de_un_erp(con_coste, tmp_path):  # noqa: F811
    p = con_coste
    mapa, leido, propuestas = _leer(p, _csv(tmp_path))
    assert mapa.origen == "títulos" and mapa.fila_titulos == 2
    assert mapa.columnas["base"] == "D" and mapa.columnas["cuota_iva"] == "F"
    assert leido.obras == ["OB-25 Nave", "OB-31 Oficinas"]
    f = leido.facturas
    assert [(x.proveedor, x.numero, x.fecha, x.importe) for x in f[:3]] == [
        ("Climatización Pérez SL", "F-001", "2026-10-03", 12000.0),
        ("Chapas Norte SA", "7", "2026-10-15", 1000.5),
        ("Chapas Norte SA", "8", "2026-10-20", -100.0),  # abono
    ]
    assert all(x.estado == "nueva" for x in propuestas)
    assert propuestas[0].paquete is None  # sin historial: lo elige el usuario
    elegidas = _elegir([x for x in propuestas if x.leida.obra == "OB-25 Nave"])
    elegidas[1]["paquete"] = elegidas[2]["paquete"] = "CHAPA"
    p.importar_facturas(p.documentos()[-1]["id"], elegidas)
    por = {x.nombre: x.facturado for x in p.foto_obra().paquetes}
    assert por["EQUIPOS"] == 12000 and por["CHAPA"] == 900.5
    # Deshacer quita todas las del listado de una vez.
    p.deshacer()
    assert p.facturas() == []


def test_volver_a_importar_solo_las_nuevas(con_coste, tmp_path):  # noqa: F811
    """El ERP exporta el listado acumulado: las ya apuntadas no se repiten, y las de un
    proveedor conocido se proponen en su paquete."""
    p = con_coste
    _m, _l, propuestas = _leer(p, _csv(tmp_path))
    elegidas = _elegir(propuestas[:2])
    elegidas[1]["paquete"] = "CHAPA"
    p.importar_facturas(p.documentos()[-1]["id"], elegidas)
    acumulado = CSV.replace("12.000,00;21%", "12.500,00;21%").replace(
        "Total;;", "Chapas Norte SA;9;30/10/2026;300,00;21%;63,00;363,00;OB-25 Nave\r\nTotal;;"
    )
    _m, _l, propuestas = _leer(p, _csv(tmp_path, acumulado, "Facturas acumulado.csv"))
    estados = {(x.leida.proveedor, x.leida.numero): x for x in propuestas}
    assert estados[("Chapas Norte SA", "7")].estado == "apuntada"
    distinta = estados[("Climatización Pérez SL", "F-001")]
    assert distinta.estado == "distinta" and "no se cambia" in distinta.motivo
    nueva = estados[("Chapas Norte SA", "9")]
    assert nueva.estado == "nueva" and nueva.paquete == "CHAPA"
    assert nueva.motivo == "sus otras facturas van ahí"
    # Un paquete cerrado no se propone.
    p.cerrar_paquete("CHAPA")
    _m, _l, propuestas = _leer(p, _csv(tmp_path, acumulado + " ", "Facturas acumulado 2.csv"))
    nueva = next(x for x in propuestas if x.leida.numero == "9")
    assert nueva.paquete is None and "cerrado" in nueva.motivo


def test_sin_base_imponible_total_menos_iva_mas_retencion(con_coste, tmp_path):  # noqa: F811
    wb = Workbook()
    ws = wb.active
    ws.append(["Acreedor", "Su factura", "Fecha", "Total factura", "Total IVA", "Retención IRPF",
               "Concepto"])  # fmt: skip
    # Base 1000, IVA 21 % (210), retención 15 % (150): total 1060.
    ws.append(["Instalador SL", 1234, datetime(2026, 10, 5), 1060.0, 210.0, 150.0, "MANO DE OBRA"])
    ws.append(["Instalador SL", "1235", "sin fecha", 100.0, 21.0, 0, ""])
    ruta = tmp_path / "erp.xlsx"
    wb.save(ruta)
    mapa, leido, propuestas = _leer(con_coste, ruta)
    assert mapa.columnas["total"] == "D" and mapa.columnas["cuota_iva"] == "E"
    x = leido.facturas[0]
    assert x.numero == "1234" and x.importe == 1000.0 and x.base_calculada  # 1060 − 210 + 150
    assert any("total menos la cuota de IVA más la retención" in a for a in leido.avisos)
    assert leido.descartadas == [(3, "falta fecha")]
    assert propuestas[0].paquete == "MANO DE OBRA" and propuestas[0].motivo == "el listado lo dice"


def test_titulos_irreconocibles_los_dice_la_ia(con_coste, tmp_path):  # noqa: F811
    ruta = tmp_path / "export.xls"
    ruta.write_text(
        "<table><tr><td>Tercero sociedad</td><td>Doc. ext.</td><td>F. emisión</td>"
        "<td>Neto €</td></tr><tr><td>Pérez SL</td><td>A-9</td><td>01/10/2026</td>"
        "<td>1.500,00</td></tr></table>",
        encoding="utf-8",
    )
    p = con_coste
    preguntado = []

    def ia(texto):
        preguntado.append(texto)
        return {
            "hoja": "Tabla1",
            "fila_titulos": 1,
            "columnas": {
                "proveedor": "A",
                "numero": "B",
                "fecha": "C",
                "base": "D",
                "total": "Z",
                "cuota_iva": None,
            },  # fmt: skip
        }

    p.mapeador_facturas_ia = ia
    mapa, leido, _ = _leer(p, ruta)
    assert mapa.origen == "IA" and "1.500,00" not in mapa.columnas.values()
    assert "Tercero sociedad" in preguntado[0]
    assert leido.facturas[0].importe == 1500.0 and leido.facturas[0].fecha == "2026-10-01"
    # Si la IA dice una columna de importe sin números, se descarta y no se completa.
    p.mapeador_facturas_ia = lambda t: {
        "hoja": "Tabla1",
        "fila_titulos": 1,
        "columnas": {"proveedor": "A", "numero": "B", "fecha": "C", "base": "A"},
    }
    otro = tmp_path / "export2.xls"
    otro.write_text(ruta.read_text(encoding="utf-8").replace("A-9", "A-10"), encoding="utf-8")
    with pytest.raises(OrdenRechazada, match="No se ha podido saber"):
        _leer(p, otro)


def test_rechazos(con_coste, obra, tmp_path):  # noqa: F811
    p = con_coste
    _m, _l, propuestas = _leer(p, _csv(tmp_path))
    elegidas = _elegir(propuestas[:1])
    doc = p.documentos()[-1]["id"]
    with pytest.raises(OrdenRechazada, match="dos veces en el listado"):
        p.importar_facturas(doc, elegidas + elegidas)
    with pytest.raises(OrdenRechazada, match="no es un paquete"):
        p.importar_facturas(doc, [{**elegidas[0], "paquete": "INVENTADO"}])
    with pytest.raises(OrdenRechazada, match="No hay ninguna factura"):
        p.importar_facturas(doc, [])
    assert p.facturas() == []  # nada a medias


def test_sin_coste_objetivo(obra, tmp_path):  # noqa: F811
    p, _ = obra
    with pytest.raises(OrdenRechazada, match="Importa antes el coste objetivo"):
        _leer(p, _csv(tmp_path))


def _xlsx(tmp_path, nombre, filas):
    wb = Workbook()
    for f in filas:
        wb.active.append(f)
    ruta = tmp_path / nombre
    wb.save(ruta)
    return ruta


D = datetime(2026, 10, 5)


def test_proveedores_que_empiezan_por_total_no_son_filas_de_total(con_coste, tmp_path):  # noqa: F811
    ruta = _xlsx(tmp_path, "a.xlsx", [
        ["Proveedor", "Nº factura", "Fecha factura", "Base imponible"],
        ["Totalenergies SA", "TE-1", D, 500.0],
        ["Sumasa", "S-1", D, 200.0],
        ["Total", None, None, 700.0],
    ])  # fmt: skip
    _m, leido, _p = _leer(con_coste, ruta)
    assert [x.proveedor for x in leido.facturas] == ["Totalenergies SA", "Sumasa"]
    assert leido.descartadas == []


def test_abono_con_retencion_sin_base(con_coste, tmp_path):  # noqa: F811
    """Base −100, IVA −21, retención 15: total −106. Antes salía −70."""
    ruta = _xlsx(tmp_path, "b.xlsx", [
        ["Proveedor", "Nº factura", "Fecha", "Total factura", "Cuota IVA", "Retención"],
        ["Ingeniería SL", "A-1", D, -106.0, -21.0, 15.0],
        ["Ingeniería SL", "A-2", D, -106.0, -21.0, -15.0],
    ])  # fmt: skip
    _m, leido, _p = _leer(con_coste, ruta)
    assert [x.importe for x in leido.facturas] == [-100.0, -100.0]


def test_columna_de_iva_que_es_el_porcentaje(con_coste, tmp_path):  # noqa: F811
    """«IVA» = 21 es el tipo, no la cuota: la base no se calcula restando 21 €."""
    ruta = _xlsx(tmp_path, "c.xlsx", [
        ["Proveedor", "Nº factura", "Fecha", "Total", "IVA"],
        ["Pérez SL", "1", D, 1210.0, 21],
        ["Pérez SL", "2", D, 1210.0, 210.0],
    ])  # fmt: skip
    _m, leido, _p = _leer(con_coste, ruta)
    assert [x.numero for x in leido.facturas] == ["2"] and leido.facturas[0].importe == 1000
    assert "no cuadra con un tipo legal" in leido.descartadas[0][1]


def test_la_columna_mas_especifica_gana_y_las_repetidas_no(con_coste, tmp_path):  # noqa: F811
    ruta = _xlsx(tmp_path, "d.xlsx", [
        ["Fecha", "Proveedor", "Nº factura", "Fecha factura", "Base", "Base imponible"],
        [datetime(2026, 10, 31), "Pérez SL", "1", D, 999.0, 1000.0],
    ])  # fmt: skip
    mapa, leido, _p = _leer(con_coste, ruta)
    assert mapa.columnas["fecha"] == "D" and mapa.columnas["base"] == "F"
    assert leido.facturas[0].fecha == "2026-10-05" and leido.facturas[0].importe == 1000
    dos_bases = _xlsx(tmp_path, "e.xlsx", [
        ["Proveedor", "Nº factura", "Fecha factura", "Base 1", "Base 2"],
        ["Pérez SL", "1", D, 1000.0, 500.0],
    ])  # fmt: skip
    with pytest.raises(OrdenRechazada, match="varias columnas de base imponible"):
        _leer(con_coste, dos_bases)


def test_la_ia_no_puede_poner_el_total_como_base(con_coste, tmp_path):  # noqa: F811
    ruta = tmp_path / "f.xls"
    ruta.write_text(
        "<table><tr><td>Sociedad</td><td>Doc</td><td>Emitida</td><td>Total con IVA</td></tr>"
        "<tr><td>Pérez SL</td><td>9</td><td>01/10/2026</td><td>1.210,00</td></tr></table>",
        encoding="utf-8",
    )
    con_coste.mapeador_facturas_ia = lambda t: {
        "hoja": "Tabla1",
        "fila_titulos": 1,
        "columnas": {"proveedor": "A", "numero": "B", "fecha": "C", "base": "D"},
    }
    with pytest.raises(OrdenRechazada, match="No se ha podido saber"):
        _leer(con_coste, ruta)


def test_varias_lineas_repeticiones_y_nombres_distintos(con_coste, tmp_path):  # noqa: F811
    p = con_coste
    p.registrar_factura(
        paquete="CHAPA", proveedor="CHAPAS NORTE, S.A.", numero="F-7", fecha="2026-10-05",
        importe=300.0,
    )  # fmt: skip
    ruta = _xlsx(tmp_path, "g.xlsx", [
        ["Proveedor", "Nº factura", "Fecha factura", "Base imponible", "Cuota IVA"],
        ["Pérez SL", "1", D, 1000.0, 210.0],  # una línea por tipo de IVA: se suman
        ["Pérez SL", "1", D, 100.0, 10.0],
        ["Pérez SL", "1", D, 100.0, 10.0],  # repetida igual: no se suma dos veces
        ["Pérez SL", "2", D, 50.0, 10.5],
        ["Pérez SL", "2", datetime(2026, 10, 6), 50.0, 10.5],  # mismo nº, otra fecha
        ["Chapas Norte SA", "F7", D, 300.0, 63.0],  # ya apuntada, escrita de otra forma
    ])  # fmt: skip
    _m, leido, propuestas = _leer(p, ruta)
    uno = next(x for x in leido.facturas if x.numero == "1")
    assert uno.importe == 1100 and uno.lineas == 2
    assert any("línea repetida" in m for _f, m in leido.descartadas)
    estados = [(x.leida.numero, x.estado) for x in propuestas]
    assert estados == [("1", "nueva"), ("2", "nueva"), ("2", "repetida"), ("F7", "apuntada")]
    assert propuestas[3].paquete == "CHAPA"


def test_la_orden_no_admite_paquetes_cerrados(con_coste, tmp_path):  # noqa: F811
    p = con_coste
    _m, _l, propuestas = _leer(p, _csv(tmp_path))
    p.cerrar_paquete("EQUIPOS")
    with pytest.raises(OrdenRechazada, match="cerrado"):
        p.importar_facturas(p.documentos()[-1]["id"], _elegir(propuestas[:1]))
