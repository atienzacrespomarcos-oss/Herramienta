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
        "Propuesta de control.xlsx",
        "Esquema de control.dxf",
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


def test_numeros_exactos_para_datos_y_redondeados_para_resultados():
    from traza.io.memoria import _n

    assert _n(0.25) == "0,25" and _n(2.75) == "2,75" and _n(0.37) == "0,37"
    assert _n(47.53219) == "47,5" and _n(1000.0) == "1000" and _n(3) == "3"


def test_dato_de_partida_tal_cual_en_la_justificacion(completo, tmp_path):
    from traza.app.ordenes import FijarAlturaEspacio

    p = completo
    ofi = next(e for e in p.espacios() if e["nombre"] == "OFICINAS")
    p.ejecutar(FijarAlturaEspacio(ofi["id"], "propia", altura=2.75))
    texto = _texto(p.exportar_memoria(tmp_path / "J"))
    assert "2,75" in texto


def test_comprobacion_de_los_subcuadros_se_calcula():
    from types import SimpleNamespace

    from traza.io.memoria import comprobacion

    bien = SimpleNamespace(
        intensidad_diseno_a=95.5, calibre_a=100, admisible_a=123.3, caida_total_pct=1.1
    )
    assert comprobacion(bien, 5.0)
    assert not comprobacion(SimpleNamespace(**{**vars(bien), "admisible_a": 90}), 5.0)
    assert not comprobacion(SimpleNamespace(**{**vars(bien), "caida_total_pct": 5.2}), 5.0)


def test_un_error_cualquiera_no_corta_los_entregables(completo, tmp_path, monkeypatch):
    p = completo

    def roto(*_a, **_k):
        raise KeyError("dato roto")

    monkeypatch.setattr(p, "exportar_unifilar", roto)
    monkeypatch.setattr(p, "calcular_sistema_hidraulico", roto)
    carpeta, hechos = p.generar_entregables(tmp_path)
    errores = {n: e for n, _, e in hechos if e}
    assert errores["Subcuadro «SC Clima» (unifilar DXF)"].startswith("KeyError")
    assert "Justificación de cálculos (Word)" not in errores
    texto = _texto(next(carpeta.glob("*.docx")))
    assert "Sin calcular: Sistema «Clima»: KeyError" in texto


def test_nombres_de_fichero_que_chocan_no_se_pisan(red, tmp_path):  # noqa: F811
    from tests.integration.test_redes_proyecto import _nave_con_conductos

    p, red_id, plano_id, nivel_id = red
    # Otro plano con el mismo nombre de fichero, desde otra carpeta.
    otra = tmp_path / "otra"
    otra.mkdir()
    p.leer_plano(
        p.incorporar_documento(_nave_con_conductos(otra)), "mm", ["A-ESPACIOS"], [], ["A-TEXTOS"]
    )
    # Dos redes cuyos nombres solo difieren en caracteres que Windows no admite.
    for titulo in ("Impulsión A/B", "impulsión A:B"):
        p.definir_red(
            titulo=titulo,
            tipo="impulsion",
            plano_id=plano_id,
            capa_ejes="M-IMPULSION",
            bloques_terminales=["DIFUSOR"],
            bloque_equipo="UTA",
            nivel_id=nivel_id,
        )
    carpeta, hechos = p.generar_entregables(tmp_path)
    rutas = [r for _, rs, _ in hechos for r in rs]
    assert len(rutas) == len(set(rutas)) == len(list(carpeta.iterdir()))
    nombres = {r.name for r in rutas}
    assert {"Plano Nave.xlsx", "Plano Nave (2).xlsx"} <= nombres
    assert {"Red Impulsión A-B.xlsx", "Red impulsión A-B (2).xlsx"} <= nombres


def test_red_sin_dimensionar_y_cargas_que_faltan_se_dicen(completo, tmp_path, monkeypatch):
    import dataclasses

    p = completo
    original = p.calcular_red
    monkeypatch.setattr(
        p, "calcular_red", lambda rid: dataclasses.replace(original(rid), calculo=None)
    )
    texto = _texto(p.exportar_memoria(tmp_path / "J"))
    assert "No se ha podido dimensionar la red" in texto
    assert "Sin calcular: Red «Impulsión oficinas»: no se ha podido dimensionar" in texto
    assert "Dimensionado: pérdida de carga constante" not in texto


def test_cargas_sin_clima_se_dicen(proyecto, tmp_path):
    from tests.integration.test_redes_proyecto import _nave_con_conductos

    from traza.app.ordenes import CrearNivel

    p = proyecto
    plano_id = p.leer_plano(
        p.incorporar_documento(_nave_con_conductos(tmp_path)),
        "mm",
        ["A-ESPACIOS"],
        [],
        ["A-TEXTOS"],
    )
    nivel = CrearNivel("PB", 0.0, 3.0)
    p.ejecutar(nivel)
    prop = p.propuestas(plano_id)[0]
    p.confirmar_contorno(plano_id, prop.handle, nivel.id, nombre="X")
    texto = _texto(p.exportar_memoria(tmp_path / "J"))
    assert "Sin calcular: Cargas: falta el clima y la obra" in texto


def test_propiedades_del_documento(completo, tmp_path):
    doc = Document(str(completo.exportar_memoria(tmp_path / "J")))
    assert doc.core_properties.title == f"Justificación de cálculos — {completo.nombre}"
    assert doc.core_properties.author == ""


def test_plantilla_dotx_con_extension_docx(completo, tmp_path):
    docx = _plantilla(tmp_path)
    renombrada = tmp_path / "Aliter2.docx"
    with zipfile.ZipFile(docx) as zin, zipfile.ZipFile(renombrada, "w") as zout:
        for item in zin.infolist():
            datos = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                datos = datos.replace(
                    b"wordprocessingml.document.main+xml", b"wordprocessingml.template.main+xml"
                )
            zout.writestr(item, datos)
    ruta = completo.exportar_memoria(tmp_path / "J", renombrada)
    assert Document(str(ruta)).sections[0].header.paragraphs[0].text.startswith("ALITER")


def test_comprobacion_con_la_tolerancia_del_motor_y_sin_calibre():
    from types import SimpleNamespace

    from traza.io.memoria import comprobacion

    # Iz·factor con ruido de coma flotante: el motor acepta 63 A; el Word también.
    justa = SimpleNamespace(
        intensidad_diseno_a=60.0, calibre_a=63, admisible_a=62.99999999999999, caida_total_pct=2
    )
    assert comprobacion(justa, 5.0)
    moldeada = SimpleNamespace(
        intensidad_diseno_a=200.0, calibre_a=None, admisible_a=210.0, caida_total_pct=2
    )
    assert comprobacion(moldeada, 5.0)
    assert not comprobacion(SimpleNamespace(**{**vars(moldeada), "admisible_a": 190.0}), 5.0)


def test_dato_de_partida_con_cuatro_decimales_sin_redondear():
    from traza.io.memoria import _exacto

    assert _exacto(0.0625) == "0,0625" and _exacto("texto") == "texto" and _exacto(3) == 3


def test_word_abierto_nombra_el_documento_y_no_deja_temporales(completo, tmp_path, monkeypatch):
    from pathlib import Path

    original = Path.replace

    def abierto(self, destino):
        if str(self).endswith(".parcial"):
            raise PermissionError(13, "Permission denied", str(self))
        return original(self, destino)

    monkeypatch.setattr(Path, "replace", abierto)
    with pytest.raises(OrdenRechazada, match=r"«.*J\.docx»: ¿está abierto en Word"):
        completo.exportar_memoria(tmp_path / "J")
    assert not list(tmp_path.glob("*.parcial"))


def test_nombre_con_punto_da_sus_extensiones(red, tmp_path):  # noqa: F811
    p, _, plano_id, nivel_id = red
    p.definir_red(
        titulo="Red 1.5",
        tipo="impulsion",
        plano_id=plano_id,
        capa_ejes="M-IMPULSION",
        bloques_terminales=["DIFUSOR"],
        bloque_equipo="UTA",
        nivel_id=nivel_id,
    )
    carpeta, hechos = p.generar_entregables(tmp_path)
    nombres = {r.name for n, rs, _ in hechos if "«Red 1.5»" in n for r in rs}
    assert nombres == {"Red Red 1.5.dxf", "Red Red 1.5.lsp", "Red Red 1.5.xlsx"}


def _plantilla_solo_normal(tmp_path):
    """Como la plantilla de informes del usuario: sin estilos de título ni de lista."""
    from docx.oxml.ns import qn

    doc = Document()
    doc.sections[0].footer.paragraphs[0].text = "EMPRESA · pie de la plantilla"
    estilos = doc.styles.element
    for s in list(estilos.iterchildren(qn("w:style"))):
        nombre = s.find(qn("w:name"))
        if nombre is not None and nombre.get(qn("w:val")).lower().startswith(
            ("heading", "title", "list bullet", "table grid")
        ):
            estilos.remove(s)
    ruta = tmp_path / "Informe.docx"
    doc.save(str(ruta))
    return ruta


def test_con_plantilla_sin_titulos_sale_con_el_formato_de_sus_informes(completo, tmp_path):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Pt

    doc = Document(str(completo.exportar_memoria(tmp_path / "J", _plantilla_solo_normal(tmp_path))))
    assert doc.sections[0].footer.paragraphs[0].text == "EMPRESA · pie de la plantilla"
    p = [x for x in doc.paragraphs if x.text.strip()]
    assert p[0].text == completo.nombre.upper() and p[0].alignment == WD_ALIGN_PARAGRAPH.CENTER
    assert p[0].runs[0].bold and p[0].runs[0].font.size == Pt(14)
    assert p[1].text == "JUSTIFICACIÓN DE CÁLCULOS" and p[1].runs[0].font.size == Pt(13)
    apartado = next(x for x in p if x.text.startswith("1. "))
    assert apartado.text == "1. CARGAS TÉRMICAS Y VENTILACIÓN" and apartado.runs[0].bold
    assert apartado.runs[0].font.size == Pt(12)
    assert p[2].text == "Documento de apoyo" and p[2].runs[0].bold
    assert set(p[3].text) == {"-"} and p[3].alignment == WD_ALIGN_PARAGRAPH.LEFT
    cuerpo = next(x for x in p if x.text.startswith("Documento de apoyo:"))
    assert cuerpo.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY
    assert cuerpo.paragraph_format.space_after == Pt(8)
    celda = doc.tables[0].rows[0].cells[0]
    assert celda._tc.tcPr.find(qn("w:shd")).get(qn("w:fill")) == "ECECEC"
    assert celda.paragraphs[0].runs[0].bold
    assert celda.paragraphs[0].runs[0].font.size == Pt(9.5)
    dato = doc.tables[0].rows[1].cells[0].paragraphs[0].runs[0]
    assert dato.font.size == Pt(9.5)
    # Sin «Table Grid» en la plantilla, la tabla lleva su propia rejilla.
    hijos = [h.tag for h in doc.tables[0]._tbl.tblPr]
    assert qn("w:tblBorders") in hijos
    # En el orden del esquema (antes de tblLook), o Word lo da por dañado.
    assert hijos.index(qn("w:tblBorders")) < hijos.index(qn("w:tblLook"))
