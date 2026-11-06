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


def _linea(desc, cant, prec, imp, donde="p. 1", codigo=None, unidad="ud"):
    return {
        "capitulo": "Climatización",
        "codigo": codigo,
        "descripcion": desc,
        "unidad": unidad,
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
        "Unidad de tratamiento de aire 2400 m3/h   ud   1   12.500,00   12.500,00",
        "Conducto de chapa galvanizada   m2   2.400   10,00   24.000,00",
        "Rejilla de impulsión doble deflexión   ud   8   45,50   364,00",
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
                unidad="m2",
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
    assert any("«47,00» no está, como número completo" in m for m in rejilla["motivos"])


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
    doc.new_page().insert_text(
        (40, 60), "Rejilla de impulsión   ud   8   45,50   400,00", fontsize=9
    )
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
    doc.new_page().insert_text((40, 60), "Tubo de cobre   m   2.400", fontsize=9)
    doc.save(ruta)
    doc.close()
    r = {
        "proveedor": None,
        "total": NULO,
        "partidas": [_linea("Tubo de cobre", _num("2.400", 2400, "p. 1"), NULO, NULO, unidad="m")],
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
    imagenes = llamadas[0][1]
    assert list(imagenes) == [1] and imagenes[1].suffix == ".png"
    assert proyecto.partidas(med_id)[0]["estado"] == "a_revisar"
    assert any("Páginas sin texto (escaneadas): 1" in a for a in avisos)
    assert not imagenes[1].exists(), "las imágenes temporales se borran"


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
    # Cita una celda de otra fila: se detecta antes incluso de comparar el valor.
    assert any("no es de la fila de la línea" in m for m in ps[1]["motivos"])


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
    "entorno_limpio": not any(v in os.environ for v in (
        "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK")),
    "cwd": os.path.realpath(os.getcwd()),
    "entrada_completa": entrada,
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


# --- Revisión del 06-11-2026: cada fallo grave, con su prueba ------------------------------


def _pdf(tmp_path: Path, lineas: list[str], nombre="o.pdf", paginas_vacias=0) -> Path:
    ruta = tmp_path / nombre
    doc = pymupdf.open()
    pagina = doc.new_page()
    for i, texto in enumerate(lineas):
        pagina.insert_text((40, 60 + 20 * i), texto, fontsize=9)
    for _ in range(paginas_vacias):
        doc.new_page()
    doc.save(ruta)
    doc.close()
    return ruta


def test_un_digito_suelto_no_vale_por_estar_dentro_de_otro_numero(proyecto, tmp_path):
    ruta = _pdf(tmp_path, ["Codo de 90 grados   ud   12   5,00   60,00"])
    r = {
        "proveedor": None,
        "total": NULO,
        "partidas": [
            _linea(
                "Codo de 90 grados",
                _num("2", 2, "p. 1"),
                _num("5,00", 5.0, "p. 1"),
                _num("60,00", 60.0, "p. 1"),
            )
        ],
    }
    med_id, _, _ = _leer(proyecto, ruta, r)
    p = proyecto.partidas(med_id)[0]
    assert p["estado"] == "a_revisar"
    assert any("«2» no está, como número completo" in m for m in p["motivos"])


def test_numero_de_otra_linea_no_vale(proyecto, tmp_path):
    ruta = _pdf(
        tmp_path,
        [
            "Rejilla de retorno   ud   4   30,00   120,00",
            "Rejilla de impulsión   ud   8   45,50   364,00",
        ],
    )
    r = {
        "proveedor": None,
        "total": NULO,
        "partidas": [
            # Precio y importe tomados del renglón de la rejilla de retorno.
            _linea(
                "Rejilla de impulsión",
                _num("4", 4, "p. 1"),
                _num("30,00", 30.0, "p. 1"),
                _num("120,00", 120.0, "p. 1"),
            )
        ],
    }
    med_id, _, _ = _leer(proyecto, ruta, r)
    p = proyecto.partidas(med_id)[0]
    assert p["estado"] == "a_revisar"
    assert any("cantidad: «4» no está" in m for m in p["motivos"])


def test_cantidad_y_precio_sin_importe_quedan_a_revisar(proyecto, tmp_path):
    ruta = _pdf(tmp_path, ["Rejilla de impulsión   ud   8   45,50"])
    r = {
        "proveedor": None,
        "total": NULO,
        "partidas": [
            _linea("Rejilla de impulsión", _num("45,50", 45.5, "p. 1"), _num("8", 8, "p. 1"), NULO)
        ],
    }
    med_id, _, _ = _leer(proyecto, ruta, r)
    p = proyecto.partidas(med_id)[0]
    assert p["estado"] == "a_revisar"
    assert any("podrían estar intercambiados" in m for m in p["motivos"])


def test_solo_cantidad_en_una_medicion_entra_directa(proyecto, tmp_path):
    ruta = _pdf(tmp_path, ["Tubo de cobre 1/2   m   125,40"])
    r = {
        "proveedor": None,
        "total": NULO,
        "partidas": [
            _linea("Tubo de cobre 1/2", _num("125,40", 125.4, "p. 1"), NULO, NULO, unidad="m")
        ],
    }
    med_id, _, _ = _leer(proyecto, ruta, r)
    assert proyecto.partidas(med_id)[0]["estado"] == "comprobada"


def test_unidad_y_codigo_se_comprueban(proyecto, tmp_path):
    ruta = _pdf(tmp_path, ["CL-01   Conducto de chapa   m2   10   20,00   200,00"])
    r = {
        "proveedor": None,
        "total": NULO,
        "partidas": [
            _linea(
                "Conducto de chapa",
                _num("10", 10, "p. 1"),
                _num("20,00", 20.0, "p. 1"),
                _num("200,00", 200.0, "p. 1"),
                codigo="CL-02",
                unidad="m",
            )
        ],
    }
    med_id, _, _ = _leer(proyecto, ruta, r)
    motivos = proyecto.partidas(med_id)[0]["motivos"]
    assert "unidad «m» no está en el renglón de la línea" in motivos
    assert "codigo «CL-02» no está en el renglón de la línea" in motivos


def test_total_se_compara_al_centimo(proyecto, tmp_path):
    ruta = _pdf(tmp_path, ["Rejilla de impulsión   ud   8   45,50   364,00", "TOTAL   364,02"])
    r = {
        "proveedor": None,
        "total": _num("364,02", 364.02, "p. 1"),
        "partidas": [
            _linea(
                "Rejilla de impulsión",
                _num("8", 8, "p. 1"),
                _num("45,50", 45.5, "p. 1"),
                _num("364,00", 364.0, "p. 1"),
            )
        ],
    }
    _, avisos, _ = _leer(proyecto, ruta, r)
    assert any("NO coincide con el total del documento" in a for a in avisos)


def test_pdf_con_algunas_paginas_escaneadas(proyecto, tmp_path):
    ruta = _pdf(tmp_path, ["Rejilla de impulsión   ud   8   45,50   364,00"], paginas_vacias=1)
    r = {
        "proveedor": None,
        "total": NULO,
        "partidas": [
            _linea(
                "Rejilla de impulsión",
                _num("8", 8, "p. 1"),
                _num("45,50", 45.5, "p. 1"),
                _num("364,00", 364.0, "p. 1"),
            ),
            _linea("Algo escaneado", _num("3", 3, "p. 2"), NULO, NULO, donde="p. 2"),
        ],
    }
    med_id, avisos, llamadas = _leer(proyecto, ruta, r)
    assert list(llamadas[0][1]) == [2], "solo la página sin texto va como imagen"
    assert [p["estado"] for p in proyecto.partidas(med_id)] == ["comprobada", "a_revisar"]
    assert any("Páginas sin texto (escaneadas): 2" in a for a in avisos)


def test_documento_ya_leido_no_se_envia_a_la_ia(proyecto, pdf_oferta):
    _leer(proyecto, pdf_oferta, _respuesta_correcta())
    llamadas = []
    proyecto.extractor_ia = lambda texto, imagenes: llamadas.append(1)
    doc = proyecto.documentos()[0]["id"]
    with pytest.raises(OrdenRechazada, match="ya está leído"):
        proyecto.leer_medicion(doc, "oferta")
    assert llamadas == []


def test_valor_no_numerico_de_la_ia_no_aborta(proyecto, tmp_path):
    ruta = _pdf(tmp_path, ["Rejilla de impulsión   ud   8"])
    r = {
        "proveedor": None,
        "total": NULO,
        "partidas": [
            _linea(
                "Rejilla de impulsión", {"texto": "8", "valor": "ocho", "donde": "p. 1"}, NULO, NULO
            )
        ],
    }
    med_id, _, _ = _leer(proyecto, ruta, r)
    assert any("valor no numérico" in m for m in proyecto.partidas(med_id)[0]["motivos"])


def test_aislamiento_de_la_llamada_y_paginas_escaneadas_por_entrada(tmp_path, monkeypatch):
    simulador = tmp_path / "simulador.py"
    simulador.write_text(SIMULADOR, encoding="utf-8")
    registro = tmp_path / "registro.json"
    monkeypatch.setenv("TRAZA_SIMULADOR_REGISTRO", str(registro))
    for v in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK"):
        monkeypatch.setenv(v, "no-debe-llegar")
    imagenes = tmp_path / "imgs"
    imagenes.mkdir()
    img = imagenes / "pagina_002.png"
    img.write_bytes(b"png")
    claude_code.extraer("texto", {2: img}, [sys.executable, str(simulador)])
    r = json.loads(registro.read_text(encoding="utf-8"))
    for bandera in ("--restricted", "--strict-mcp-config", "--no-session-persistence"):
        assert bandera in r["args"]
    assert r["args"][r["args"].index("--tools") + 1] == "Read"
    assert r["entorno_limpio"]
    assert f"p. 2: {img.resolve()}" in r["entrada_completa"]
    assert r["cwd"] == str(imagenes.resolve())
