"""Genera la carpeta «Ejemplos de prueba» del paquete de TRAZA para Windows.

Uso: uv run python scripts/ejemplos_prueba.py <carpeta destino>

Son los mismos ficheros **inventados** con los que pasan las pruebas automáticas (se
importan de `tests/`): lo que la Guía de prueba manda hacer con ellos está probado de punta
a punta (`tests/integration/test_ejemplos_prueba.py`). Ningún dato es de un proyecto real
(el repositorio es público).

La guía climática del IDAE no se incluye (no se reproduce): la Guía de prueba dice de dónde
descargarla.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

DISENO = "1 Diseño"
OFERTA = "2 Oferta"
OBRA = "3 Obra"
PUNTOS = (
    "Sistema;Equipo;Señal;Tipo;Cantidad\n"
    "UTA-1;Ventilador de impulsión;Orden de marcha;SD;1\n"
    "UTA-1;Ventilador de impulsión;Estado;ED;1\n"
    "UTA-1;Ventilador de impulsión;Fallo variador;ED;1\n"
    "UTA-1;Ventilador de impulsión;Velocidad;SA;1\n"
    "UTA-1;Batería de agua;Válvula de 3 vías;SA;1\n"
    "UTA-1;Impulsión;Temperatura de impulsión;EA;1\n"
    "UTA-1;Filtros;Filtro sucio (presostato);ED;1\n"
    "Zonas;Oficinas;Temperatura ambiente;EA;4\n"
    "Zonas;Sala de reuniones;CO2;EA;1\n"
)


def generar(destino: Path) -> dict[str, Path]:
    """Escribe los ejemplos en `destino` y devuelve {nombre corto: ruta}."""
    import tempfile

    from tests.integration.test_obra import BC3_VENTA, comparativo
    from tests.integration.test_obra_certificaciones import SUYO, excel
    from tests.integration.test_obra_facturas_erp import CSV
    from tests.integration.test_redes_proyecto import _nave_con_conductos
    from tests.ui.test_ventana import BC3_PRUEBA

    destino = Path(destino)
    for sub in (DISENO, OFERTA, OBRA):
        (destino / sub).mkdir(parents=True, exist_ok=True)
    salida: dict[str, Path] = {}
    with tempfile.TemporaryDirectory() as tmp:
        plano = _nave_con_conductos(Path(tmp))
        salida["plano"] = destino / DISENO / "Nave ejemplo.dxf"
        salida["plano"].write_bytes(plano.read_bytes())
    salida["puntos"] = destino / DISENO / "Listado de puntos ejemplo.csv"
    salida["puntos"].write_text(PUNTOS, encoding="utf-8")
    salida["oferta"] = destino / OFERTA / "Oferta climatización ejemplo.bc3"
    salida["oferta"].write_bytes(BC3_PRUEBA.encode("cp1252"))
    salida["venta"] = destino / OBRA / "Presupuesto contratado ejemplo.bc3"
    salida["venta"].write_bytes(BC3_VENTA.encode("cp1252"))
    salida["coste"] = comparativo(destino / OBRA / "Coste objetivo ejemplo (Presto).xlsx")
    salida["certificacion"] = excel(
        destino / OBRA / "Certificación ejemplo.xlsx", SUYO, titulo_en=3
    )
    salida["facturas"] = destino / OBRA / "Facturas ERP ejemplo.csv"
    salida["facturas"].write_bytes(CSV.encode("cp1252"))
    (destino / "LEEME.txt").write_text(
        "Ficheros INVENTADOS para probar TRAZA siguiendo la «Guía de prueba».\n"
        "Ningún dato es de un proyecto real.\n"
        "La guía climática del IDAE no va incluida: la Guía de prueba dice de dónde "
        "descargarla.\n",
        encoding="utf-8",
    )
    return salida


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python scripts/ejemplos_prueba.py <carpeta destino>")
    for nombre, ruta in generar(Path(sys.argv[1])).items():
        print(f"{nombre}: {ruta}")
