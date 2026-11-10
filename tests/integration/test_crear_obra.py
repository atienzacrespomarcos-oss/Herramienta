"""Crear la obra desde sus documentos: qué es cada uno (app/clasificar; docs/modules/obra.md,
bloque 4c). Documentos inventados de cada tipo."""

from __future__ import annotations

import ezdxf
from tests.integration.test_obra import BC3_VENTA, comparativo
from tests.integration.test_obra_certificaciones import SUYO, excel
from tests.integration.test_obra_facturas_erp import CSV

from traza.app import clasificar
from traza.app.ordenes import CambiarEncargo

#: Un BC3 sin precios: una medición.
BC3_MEDICION = (
    "~V|AUTOR|FIEBDC-3/2016|PRUEBA||ANSI|Prueba|2|\n"
    "~C|MED##||Mediciones|0||0|\n~C|CND01|m2|Conducto||0|\n"
    "~D|MED##|CND01\\1\\120\\|\n"
)


def documentos(tmp_path, pdf):
    venta = tmp_path / "Presupuesto cliente.bc3"
    venta.write_bytes(BC3_VENTA.encode("cp1252"))
    otro = tmp_path / "Presupuesto antiguo.bc3"
    otro.write_bytes(BC3_VENTA.replace("|20000|", "|9000|").encode("cp1252"))
    medicion = tmp_path / "Mediciones.bc3"
    medicion.write_bytes(BC3_MEDICION.encode("cp1252"))
    plano = tmp_path / "Planta.dxf"
    ezdxf.new("R2013").saveas(plano)
    word = tmp_path / "Memoria.docx"
    word.write_bytes(b"PK\x03\x04 no es un docx de verdad")
    facturas = tmp_path / "Facturas.csv"
    facturas.write_bytes(CSV.encode("cp1252"))
    return [
        venta,
        otro,
        medicion,
        comparativo(tmp_path / "Costes.xlsx"),
        excel(tmp_path / "Certificacion.xlsx", SUYO, titulo_en=3),
        facturas,
        plano,
        pdf,
        word,
    ]


def test_que_es_cada_documento(proyecto, tmp_path, pdf_3_paginas):
    p = proyecto
    p.ejecutar(CambiarEncargo("obra"))
    ids = [p.incorporar_documento(r) for r in documentos(tmp_path, pdf_3_paginas)]
    docs = {d["id"]: d for d in p.documentos()}
    propuestas = clasificar.clasificar(p, [docs[i] for i in ids])
    tipos = {x.nombre: x.tipo for x in propuestas}
    assert tipos == {
        "Presupuesto cliente.bc3": "presupuesto",  # el de mayor importe
        "Presupuesto antiguo.bc3": "medicion",
        "Mediciones.bc3": "medicion",
        "Costes.xlsx": "coste_objetivo",
        "Certificacion.xlsx": "certificacion",
        "Facturas.csv": "facturas",
        "Planta.dxf": "plano",
        pdf_3_paginas.name: "documentacion",  # un PDF solo se lee con la IA si se elige
        "Memoria.docx": "documentacion",
    }
    por = {x.nombre: x for x in propuestas}
    assert por["Certificacion.xlsx"].numero == 3  # «CERTIFICACIÓN Nº 3» en su cabecera
    assert "mayor importe de 2" in por["Presupuesto cliente.bc3"].motivo
    # Solo la IA lee un PDF o un Excel no reconocido: se dice, y no se propone sin pedirlo.
    pdf = por[pdf_3_paginas.name]
    assert not pdf.con_ia() and pdf.con_ia("presupuesto")
    assert not por["Presupuesto cliente.bc3"].con_ia()
    assert por["Memoria.docx"].posibles == ("documentacion",)
    # El orden de montaje: presupuesto, mediciones, coste, certificaciones, facturas.
    plan = clasificar.orden_de_montaje([(x, x.tipo) for x in propuestas])
    assert [x.tipo for x, _t in plan] == [
        "presupuesto",
        "medicion",
        "medicion",
        "coste_objetivo",
        "certificacion",
        "facturas",
    ]


def test_con_venta_contratada_no_se_propone_otro_presupuesto(proyecto, tmp_path):
    p = proyecto
    p.ejecutar(CambiarEncargo("obra"))
    venta = tmp_path / "Venta.bc3"
    venta.write_bytes(BC3_VENTA.encode("cp1252"))
    med_id, _ = p.leer_medicion(p.incorporar_documento(venta), "presupuesto")
    p.fijar_venta_contratada(med_id)
    nuevo = tmp_path / "Revisado.bc3"
    nuevo.write_bytes(BC3_VENTA.replace("|500|", "|600|").encode("cp1252"))
    doc = p.incorporar_documento(nuevo)
    (x,) = clasificar.clasificar(p, [d for d in p.documentos() if d["id"] == doc])
    assert x.tipo == "medicion" and "presupuesto" in x.posibles
