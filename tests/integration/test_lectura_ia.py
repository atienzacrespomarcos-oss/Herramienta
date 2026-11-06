"""Lectura de PDF y Excel con IA: las comprobaciones deciden, no la IA (ADR-0013).

La IA se sustituye por respuestas preparadas (correctas o erróneas a propósito) para probar
que cada error típico se detecta. La conexión real con Claude Code se prueba aparte con un
simulador del ejecutable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf
import pytest
from openpyxl import Workbook

from traza.ai import claude_code
from traza.app.ordenes import ConfirmarPartida, OrdenRechazada


def _num(texto, valor, donde):
    return {"texto": texto, "valor": valor, "donde": donde}


NULO = {"texto": None, "valor": None, "donde": None}


def _linea(desc, cant, prec, imp, donde="p. 1", codigo=None):
    return {
        "capitulo": "Climatización",
        "codigo": codigo,
        "descripcion": desc,
        "unidad": "ud",
        "donde": donde,
        "cantidad": cant,
        "precio": prec,
        "importe": imp,
    }


@pytest.fixture
def pdf_oferta(tmp_path: Path) -> Path:
    """Oferta en PDF con texto (como la que genera un programa de presupuestos)."""
    ruta = tmp_path / "Oferta proveedor.pdf"
    doc = pymupdf.open()
    pagina = doc.new_page()
    lineas = [
        "OFERTA Nº 123 - Proveedor de prueba",
        "Unidad de tratamiento de aire 2400 m3/h   1   12.500,00   12.500,00",
        "Conducto de chapa galvanizada   2.400   10,00   24.000,00",
        "Rejilla de impulsión doble deflexión   8   45,50   364,00",
        "TOTAL   36.864,00",
    ]
    for i, texto in enumerate(lineas):
        pagina.insert_text((40, 60 + 20 * i), texto, fontsize=9)
    doc.save(ruta)
    doc.close()
    return ruta


def _respuesta_correcta():
    return {
        "proveedor": "Proveedor de prueba",
        "total": _num("36.864,00", 36864.0, "p. 1"),
        "partidas": [
            _linea(
                "Unidad de tratamiento de aire 2400 m3/h",
                _num("1", 1, "p. 1"),
                _num("12.500,00", 12500.0, "p. 1"),
                _num("12.500,00", 12500.0, "p. 1"),
            ),
            # La IA lee «2.400» como 2,4: el importe lo resuelve a 2400.
            _linea(
                "Conducto de chapa galvanizada",
                _num("2.400", 2.4, "p. 1"),
                _num("10,00", 10.0, "p. 1"),
                _num("24.000,00", 24000.0, "p. 1"),
            ),
            _linea(
                "Rejilla de impulsión doble deflexión",
                _num("8", 8, "p. 1"),
                _num("45,50", 45.5, "p. 1"),
                _num("364,00", 364.0, "p. 1"),
            ),
        ],
    }


def _leer(proyecto, ruta, respuesta, proveedor="Proveedor A"):
    llamadas = []

    def falsa_ia(texto, imagenes):
        llamadas.append((texto, imagenes))
        return respuesta

    proyecto.extractor_ia = falsa_ia
    doc = proyecto.incorporar_documento(ruta, "oferta")
    med_id, avisos = proyecto.leer_medicion(doc, "oferta", proveedor)
    return med_id, avisos, llamadas


def test_pdf_correcto_entra_directo_y_resuelve_el_numero_ambiguo(proyecto, pdf_oferta):
    med_id, avisos, llamadas = _leer(proyecto, pdf_oferta, _respuesta_correcta())
    texto_enviado, imagenes = llamadas[0]
    assert "=== Página 1 ===" in texto_enviado and imagenes is None
    ps = proyecto.partidas(med_id)
    assert [p["estado"] for p in ps] == ["comprobada"] * 3
    assert ps[1]["cantidad"] == 2400.0, "«2.400» con importe 24.000,00 es 2400, no 2,4"
    med = proyecto.mediciones()[0]
    assert med["total_documento"] == 36864.0 and med["lector"] == "ia-claude-code"
    assert not any("NO coincide" in a for a in avisos)
    # El usuario indicó el proveedor: lo que diga la IA no se menciona ni se guarda.
    assert not any("identifica el proveedor" in a for a in avisos)
    assert med["proveedor"] == "Proveedor A"


def test_proveedor_leido_por_ia_se_avisa_pero_no_se_guarda(proyecto, pdf_oferta):
    _, avisos, _ = _leer(proyecto, pdf_oferta, _respuesta_correcta(), proveedor=None)
    assert any("Proveedor de prueba" in a and "sin comprobar" in a for a in avisos)
    assert proyecto.mediciones()[0]["proveedor"] is None


def test_numero_inventado_queda_a_revisar(proyecto, pdf_oferta):
    r = _respuesta_correcta()
    r["partidas"][2]["precio"] = _num("47,00", 47.0, "p. 1")  # no está en el documento
    med_id, _, _ = _leer(proyecto, pdf_oferta, r)
    rejilla = proyecto.partidas(med_id)[2]
    assert rejilla["estado"] == "a_revisar"
    assert any("«47,00» no aparece en la p. 1" in m for m in rejilla["motivos"])


def test_lectura_numerica_distinta_del_texto(proyecto, pdf_oferta):
    r = _respuesta_correcta()
    r["partidas"][2]["cantidad"] = _num("8", 9, "p. 1")
    med_id, _, _ = _leer(proyecto, pdf_oferta, r)
    assert any("la IA lee 9" in m for m in proyecto.partidas(med_id)[2]["motivos"])


def test_descripcion_que_no_esta_en_la_pagina(proyecto, pdf_oferta):
    r = _respuesta_correcta()
    r["partidas"][0]["descripcion"] = "Enfriadora de agua 50 kW"
    med_id, _, _ = _leer(proyecto, pdf_oferta, r)
    assert "la descripción no aparece en la p. 1" in proyecto.partidas(med_id)[0]["motivos"]


def test_importe_que_no_cuadra(proyecto, tmp_path):
    ruta = tmp_path / "o.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((40, 60), "Rejilla de impulsión   8   45,50   400,00", fontsize=9)
    doc.save(ruta)
    doc.close()
    r = {
        "proveedor": None,
        "total": NULO,
        "partidas": [
            _linea(
                "Rejilla de impulsión",
                _num("8", 8, "p. 1"),
                _num("45,50", 45.5, "p. 1"),
                _num("400,00", 400.0, "p. 1"),
            )
        ],
    }
    med_id, avisos, _ = _leer(proyecto, ruta, r)
    p = proyecto.partidas(med_id)[0]
    assert p["estado"] == "a_revisar"
    assert "cantidad × precio no coincide con el importe del documento" in p["motivos"]
    assert any("a revisar" in a for a in avisos)


def test_total_que_no_cuadra_se_avisa(proyecto, pdf_oferta):
    r = _respuesta_correcta()
    del r["partidas"][2]  # la IA se salta una línea
    _, avisos, _ = _leer(proyecto, pdf_oferta, r)
    assert any("NO coincide con el total del documento" in a for a in avisos)


def test_ambiguo_sin_importe_queda_a_revisar(proyecto, tmp_path):
    ruta = tmp_path / "o.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((40, 60), "Tubo de cobre 2.400 m", fontsize=9)
    doc.save(ruta)
    doc.close()
    r = {
        "proveedor": None,
        "total": NULO,
        "partidas": [_linea("Tubo de cobre", _num("2.400", 2400, "p. 1"), NULO, NULO)],
    }
    med_id, _, _ = _leer(proyecto, ruta, r)
    p = proyecto.partidas(med_id)[0]
    assert p["estado"] == "a_revisar" and any("ambiguo" in m for m in p["motivos"])


def test_confirmar_partida_revisada(proyecto, pdf_oferta):
    r = _respuesta_correcta()
    r["partidas"][2]["precio"] = _num("47,00", 47.0, "p. 1")
    med_id, _, _ = _leer(proyecto, pdf_oferta, r)
    pid = proyecto.partidas(med_id)[2]["id"]
    proyecto.ejecutar(ConfirmarPartida(pid))
    assert proyecto.partidas(med_id)[2]["estado"] == "confirmada"
    with pytest.raises(OrdenRechazada, match="Solo se confirman"):
        proyecto.ejecutar(ConfirmarPartida(proyecto.partidas(med_id)[0]["id"]))
    proyecto.deshacer()
    assert proyecto.partidas(med_id)[2]["estado"] == "a_revisar"


def test_pdf_escaneado_envia_imagenes_y_todo_queda_a_revisar(proyecto, tmp_path):
    ruta = tmp_path / "escaneado.pdf"
    doc = pymupdf.open()
    doc.new_page()  # página sin texto: como un escaneo
    doc.save(ruta)
    doc.close()
    r = {
        "proveedor": None,
        "total": NULO,
        "partidas": [_linea("Rejilla", _num("8", 8, "p. 1"), _num("45,50", 45.5, "p. 1"), NULO)],
    }
    med_id, avisos, llamadas = _leer(proyecto, ruta, r)
    assert llamadas[0][1] and llamadas[0][1][0].suffix == ".png"
    assert proyecto.partidas(med_id)[0]["estado"] == "a_revisar"
    assert any("escaneado" in a for a in avisos)
    assert not llamadas[0][1][0].exists(), "las imágenes temporales se borran"


@pytest.fixture
def xlsx_oferta(tmp_path: Path) -> Path:
    ruta = tmp_path / "Medición.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Medición"
    ws.append(["Código", "Descripción", "Ud", "Cantidad", "Precio", "Importe"])
    ws.append(["V01", "Ventilador helicoidal de cubierta", "ud", 4, 850.0, 3400.0])
    ws.append(["V02", "Compuerta cortafuegos", "ud", 6, 210.5, 1263.0])
    wb.save(ruta)
    return ruta


def test_excel_valores_exactos_de_celda(proyecto, xlsx_oferta):
    r = {
        "proveedor": None,
        "total": NULO,
        "partidas": [
            _linea(
                "Ventilador helicoidal de cubierta",
                _num("4", 4, "Medición!D2"),
                _num("850", 850, "Medición!E2"),
                _num("3400", 3400, "Medición!F2"),
                donde="Medición!2",
                codigo="V01",
            ),
            # La IA cita la celda de otra fila para el precio.
            _linea(
                "Compuerta cortafuegos",
                _num("6", 6, "Medición!D3"),
                _num("210,5", 210.5, "Medición!E2"),
                _num("1263", 1263, "Medición!F3"),
                donde="Medición!3",
                codigo="V02",
            ),
        ],
    }
    med_id, _, llamadas = _leer(proyecto, xlsx_oferta, r)
    assert "Medición!B2: Ventilador helicoidal de cubierta" in llamadas[0][0]
    ps = proyecto.partidas(med_id)
    assert ps[0]["estado"] == "comprobada"
    assert ps[1]["estado"] == "a_revisar"
    assert any("la IA lee 210.5" in m for m in ps[1]["motivos"])


def test_ia_no_disponible_se_explica(proyecto, pdf_oferta):
    def sin_ia(texto, imagenes):
        raise claude_code.IaNoDisponible("Claude Code no está instalado en este equipo.")

    proyecto.extractor_ia = sin_ia
    doc = proyecto.incorporar_documento(pdf_oferta)
    with pytest.raises(OrdenRechazada, match="no está instalado"):
        proyecto.leer_medicion(doc, "oferta")
    assert proyecto.mediciones() == []


# --- Conexión con Claude Code (simulador del ejecutable) ---------------------------------

SIMULADOR = r"""
import json, os, sys
args = sys.argv[1:]
# TRAZA envía la entrada en UTF-8. Leerla con sys.stdin.read() usaría la página de códigos
# de Windows (cp1252) y «Página» llegaría como «PÃ¡gina» (fallo visto en CI de Windows).
entrada = sys.stdin.buffer.read().decode("utf-8")
registro = {
    "args": args,
    "api_key_presente": "ANTHROPIC_API_KEY" in os.environ,
    "entrada": entrada[:200],
}
with open(os.environ["TRAZA_SIMULADOR_REGISTRO"], "w", encoding="utf-8") as f:
    json.dump(registro, f)
print(json.dumps({"type": "result", "is_error": False, "result": "ok",
                  "structured_output": {"proveedor": None, "total": None, "partidas": []}}))
"""


def test_llamada_a_claude_code_sin_clave_api_ni_herramientas(tmp_path, monkeypatch):
    simulador = tmp_path / "simulador.py"
    simulador.write_text(SIMULADOR, encoding="utf-8")
    registro = tmp_path / "registro.json"
    monkeypatch.setenv("TRAZA_SIMULADOR_REGISTRO", str(registro))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "no-debe-llegar")
    salida = claude_code.extraer("=== Página 1 ===\ntexto", None, [sys.executable, str(simulador)])
    assert salida["partidas"] == []
    r = json.loads(registro.read_text(encoding="utf-8"))
    assert not r["api_key_presente"], "con la clave de API no se usaría la suscripción"
    assert "--bare" not in r["args"]
    assert r["args"][r["args"].index("--tools") + 1] == ""
    assert r["args"][r["args"].index("--permission-mode") + 1] == "dontAsk"
    assert json.loads(r["args"][r["args"].index("--json-schema") + 1]) == claude_code.ESQUEMA
    assert r["entrada"].startswith("=== Página 1 ===")


@pytest.mark.parametrize(
    "codigo,stdout,mensaje",
    [
        (0, "no es json", "no válida"),
        (0, json.dumps({"is_error": True, "result": "Not logged in"}), "Not logged in"),
        (0, json.dumps({"is_error": False, "result": "texto suelto"}), "estructurada"),
        (1, json.dumps({"is_error": False, "structured_output": {"partidas": []}}), "error"),
    ],
)
def test_salidas_de_claude_code_que_no_valen(codigo, stdout, mensaje):
    with pytest.raises(claude_code.IaError, match=mensaje):
        claude_code.interpretar_salida(codigo, stdout, "")


def test_instalacion_npm_en_windows_se_rechaza(monkeypatch):
    monkeypatch.setattr(claude_code, "disponible", lambda: Path("C:/npm/claude.cmd"))
    with pytest.raises(claude_code.IaNoDisponible, match="versión nativa"):
        claude_code.extraer("x")
