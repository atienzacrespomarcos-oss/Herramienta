"""Entregables y justificación de cálculos en Word (docs/modules/flujo.md, bloque 2).

Usuario (09-11-2026): la justificación «es de soporte en caso de que me hagan justificar
algo. Con plantilla de Aliter. Nada oficial», sin membrete de TRAZA.
"""

from __future__ import annotations

import zipfile

import pytest
from docx import Document
from tests.integration.test_hidronica_proyecto import _circuitos
from tests.integration.test_redes_proyecto import red  # noqa: F401 (fixture)
from tests.integration.test_subcuadros_proyecto import SALIDAS

from traza.app.ordenes import FijarCargasEspacio, OrdenRechazada


def _texto(ruta) -> str:
    doc = Document(str(ruta))
    partes = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for fila in t.rows:
            partes += [c.text for c in fila.cells]
    return "\n".join(partes)


@pytest.fixture
def completo(red):  # noqa: F811
    p, red_id, plano_id, nivel_id = red
    p.definir_sistema_hidraulico(titulo="Clima", tipo="2_tubos", circuitos=_circuitos(p))
    p.definir_subcuadro(titulo="SC Clima", salidas=SALIDAS, longitud_alimentacion_m=30.0)
    return p


def test_entregables_de_todo_el_diseno(completo, tmp_path):
    p = completo
    carpeta, hechos = p.generar_entregables(tmp_path)
    assert carpeta.parent == tmp_path and carpeta.name.startswith(f"{p.nombre} - Entregables ")
    assert [(n, e) for n, _, e in hechos if e] == []
    nombres = sorted(r.name for _, rutas, _ in hechos for r in rutas)
    assert nombres == sorted(x.name for x in carpeta.iterdir())
    for esperado in (
        "Cargas.xlsx",
        "Cargas.pdf",
        "Red Impulsión oficinas.dxf",
        "Red Impulsión oficinas.lsp",
        "Red Impulsión oficinas.xlsx",
        "Hidráulica Clima.xlsx",
        "Esquema hidráulico Clima.dxf",
        "Unifilar SC Clima.dxf",
        "Justificación de cálculos.docx",
        "Plano Nave.xlsx",
    ):
        assert esperado in nombres, esperado
    # Otra vez: carpeta nueva, nunca sobrescribe.
    otra, _ = p.generar_entregables(tmp_path)
    assert otra != carpeta and otra.exists()


def test_justificacion_con_cada_calculo_y_su_norma(completo, tmp_path):
    p = completo
    ruta = p.exportar_memoria(tmp_path / "J")
    assert ruta.suffix == ".docx"
    texto = _texto(ruta)
    for parte in (
        "Justificación de cálculos",
        "No es la memoria del proyecto",
        "1. Cargas térmicas y ventilación",
        "2. Redes de aire",
        "3. Sistema hidráulico",
        "4. Subcuadros eléctricos de clima",
        "Impulsión oficinas",
        "OFICINAS",
        "RITE IT 1.1.4.2",  # ventilación (hipótesis de cargas, las mismas que el Excel)
        "IDAE nº 18",  # hidráulica
        "GUÍA-BT-19",  # subcuadros
        "CUMPLE",
    ):
        assert parte in texto, parte
    # Coma decimal (sin «.» en los números de las tablas de resultados).
    cargas = p.calcular_cargas()
    ofi = next(x for x in cargas.espacios if x.nombre == "OFICINAS")
    assert f"{ofi.verano.total_w / 1000:.1f}".replace(".", ",") in texto


def test_lo_desactualizado_y_lo_que_no_calcula_se_dice(completo, tmp_path):
    p = completo
    p.ejecutar(FijarCargasEspacio(p.espacios()[0]["id"], "almacen", {}, {}))
    texto = _texto(p.exportar_memoria(tmp_path / "J"))
    assert "Estado al generar este documento" in texto
    assert "Redes de aire: desactualizado" in texto


def _plantilla(tmp_path, nombre="Aliter.docx"):
    doc = Document()
    doc.sections[0].header.paragraphs[0].text = "ALITER · cabecera de la plantilla"
    doc.add_paragraph("Texto de ejemplo de la plantilla")
    ruta = tmp_path / nombre
    doc.save(str(ruta))
    return ruta


def test_plantilla_docx_conserva_cabecera_y_vacia_el_cuerpo(completo, tmp_path):
    ruta = completo.exportar_memoria(tmp_path / "J", _plantilla(tmp_path))
    doc = Document(str(ruta))
    assert doc.sections[0].header.paragraphs[0].text == "ALITER · cabecera de la plantilla"
    assert "Texto de ejemplo" not in _texto(ruta)
    assert doc.paragraphs[0].text == "Justificación de cálculos"


def test_plantilla_dotx(completo, tmp_path):
    docx = _plantilla(tmp_path)
    dotx = tmp_path / "Aliter.dotx"
    tipo_docx = b"wordprocessingml.document.main+xml"
    tipo_dotx = b"wordprocessingml.template.main+xml"
    with zipfile.ZipFile(docx) as zin, zipfile.ZipFile(dotx, "w") as zout:
        for item in zin.infolist():
            datos = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                datos = datos.replace(tipo_docx, tipo_dotx)
            zout.writestr(item, datos)
    ruta = completo.exportar_memoria(tmp_path / "J", dotx)
    doc = Document(str(ruta))
    assert doc.sections[0].header.paragraphs[0].text == "ALITER · cabecera de la plantilla"


def test_plantilla_que_no_es_word(completo, tmp_path):
    malo = tmp_path / "Aliter.docx"
    malo.write_bytes(b"no es un zip")
    with pytest.raises(OrdenRechazada, match="plantilla"):
        completo.exportar_memoria(tmp_path / "J", malo)
    with pytest.raises(OrdenRechazada, match=r"\.docx o \.dotx"):
        completo.exportar_memoria(tmp_path / "J", tmp_path / "Aliter.pdf")


def test_proyecto_sin_calculos(proyecto, tmp_path):
    texto = _texto(proyecto.exportar_memoria(tmp_path / "J"))
    assert "No hay ningún cálculo hecho en el proyecto." in texto
    _, hechos = proyecto.generar_entregables(tmp_path)
    assert [n for n, _, _ in hechos] == ["Justificación de cálculos (Word)"]
