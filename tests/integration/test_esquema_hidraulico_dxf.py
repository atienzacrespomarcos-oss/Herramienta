"""Esquema de principio en DXF R2013 (docs/modules/hidronica.md): se vuelve a leer, lleva
todos los grupos de elementos, sus medidas y su leyenda."""

from __future__ import annotations

import ezdxf
import pytest
from tests.integration.test_hidronica_proyecto import _circuitos, red  # noqa: F401

from traza.app.ordenes import OrdenRechazada
from traza.io import esquema_hidraulico_dxf as ed


def _textos(doc) -> str:
    return "\n".join(t.dxf.text for t in doc.modelspace().query("TEXT"))


@pytest.mark.parametrize("tipo, bandas", [("2_tubos", 1), ("4_tubos", 2)])
def test_esquema_completo_y_legible(red, tmp_path, tipo, bandas):  # noqa: F811
    p, _, _, _ = red
    sid = p.definir_sistema_hidraulico(titulo="Clima", tipo=tipo, circuitos=_circuitos(p))
    ruta = p.exportar_esquema_hidraulico(sid, tmp_path / "Esquema")
    assert ruta.name == "Esquema.dxf"
    doc = ezdxf.readfile(ruta)
    assert doc.dxfversion == "AC1027" and not doc.audit().has_errors
    assert {n for n, _c in ed.CAPAS.values()} <= {c.dxf.name for c in doc.layers}
    texto = _textos(doc)
    r = p.calcular_sistema_hidraulico(sid)
    assert len(r.servicios) == bandas
    for s in r.servicios:
        assert f"Colector impulsión {s.colector.tubo.nombre}" in texto
        assert f"Primario {s.primario.tubo.nombre}" in texto
        for c in s.circuitos:
            assert c.datos.nombre in texto
            assert ed._rotulo_tubo(c) in texto
    for grupo in ("VASO", "RED", "DES", "Alivio", "Seguridad", "LEYENDA", "Bomba primario"):
        assert grupo in texto, grupo
    # Texto en estilo TrueType (la fuente SHX por defecto no tiene «Δ» ni «≥»).
    assert doc.styles.get(ed.ESTILO).dxf.font == "arial.ttf"
    assert all(t.dxf.style == ed.ESTILO for t in doc.modelspace().query("TEXT"))
    assert "Manguito antivibratorio" in texto and "aguas abajo" in texto
    # Todo lleva XDATA TRAZA con el id del sistema.
    assert all(e.get_xdata("TRAZA")[0].value == f"{sid}:esquema" for e in doc.modelspace())


def test_sin_servicios_no_hay_esquema(tmp_path):
    from types import SimpleNamespace as N

    with pytest.raises(ValueError, match="no hay esquema"):
        ed.escribir_esquema(tmp_path / "X", "P", N(servicios=(), sistema={"id": "s"}))


def test_fichero_abierto_en_autocad(red, tmp_path, monkeypatch):  # noqa: F811
    p, _, _, _ = red
    sid = p.definir_sistema_hidraulico(titulo="Clima", tipo="2_tubos", circuitos=_circuitos(p))

    def bloqueado(*_a, **_k):
        raise PermissionError(13, "Permission denied", str(tmp_path / "E.dxf"))

    monkeypatch.setattr(ed, "escribir_esquema", bloqueado)
    with pytest.raises(OrdenRechazada, match="abierto en AutoCAD"):
        p.exportar_esquema_hidraulico(sid, tmp_path / "E")


def test_lo_dibujado_coincide_con_la_lista(red, tmp_path, monkeypatch):  # noqa: F811
    """Se cuentan las llamadas de dibujo: manguitos, vaciados, retenciones con su sentido,
    filtros de 0,25 mm solo con conexión > DN15 y nombres largos recortados."""
    p, _, _, _ = red
    c = _circuitos(p)
    c[1]["nombre"] = "Nave de producción norte"
    sid = p.definir_sistema_hidraulico(titulo="Clima", tipo="2_tubos", circuitos=c)
    r = p.calcular_sistema_hidraulico(sid)
    llamadas: dict[str, list] = {}
    for metodo in ("manguito", "retencion", "filtro", "valvula"):
        original = getattr(ed._Dibujo, metodo)

        def espia(self, *a, _m=metodo, _o=original, **k):
            llamadas.setdefault(_m, []).append((a, k))
            return _o(self, *a, **k)

        monkeypatch.setattr(ed._Dibujo, metodo, espia)
    doc = ezdxf.readfile(p.exportar_esquema_hidraulico(sid, tmp_path / "E"))
    s = r.servicios[0]
    n = len(s.circuitos)
    # Generador (2) + bomba de primario (2) + 2 por bomba de circuito; 2 más en la leyenda.
    assert len(llamadas["manguito"]) == 4 + 2 * n + 1
    # Retención: primario con flujo hacia −x, circuitos hacia +y.
    sentidos = [k.get("sentido", 1) for a, k in llamadas["retencion"]]
    assert sentidos.count(-1) == 1 and sentidos.count(1) == n + 1  # + leyenda
    # Vaciados («V»): total del primario, depósito de inercia y uno por circuito.
    vaciados = [k for a, k in llamadas["valvula"] if k.get("marca") == "V"]
    assert len(vaciados) == 2 + n
    # Filtros: 1 mm del primario y de cada circuito, 0,25 mm por unidad con conexión > DN15,
    # llenado y leyenda.
    finos = sum(1 for x in s.circuitos if x.conexion.tubo.dn > 15)
    assert len(llamadas["filtro"]) == 1 + n + finos + 1 + 1
    texto = _textos(doc)
    assert f"×{s.circuitos[0].datos.unidades}" in texto
    recortado = "Nave de producción norte"[: ed.LARGO_NOMBRE - 1] + "…"
    assert recortado in texto and "Nave de producción norte" not in texto
