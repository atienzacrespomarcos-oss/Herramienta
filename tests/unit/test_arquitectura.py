"""Las reglas entre capas se comprueban en cada ejecución de pruebas, no solo en CI."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def test_contratos_de_capas():
    lint = shutil.which("lint-imports", path=str(Path(sys.executable).parent))
    assert lint, "import-linter no instalado en el entorno del proyecto"
    r = subprocess.run([lint], cwd=RAIZ, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_ninguna_escritura_al_modelo_fuera_de_las_ordenes():
    """Solo persistence/ y la transacción de app/proyecto.py escriben en la base de datos."""
    paquete = RAIZ / "src" / "traza"
    permitidos = {paquete / "app" / "proyecto.py"}
    patron = re.compile(
        r"\b(insert|replace)\s+into\b|\bupdate\s+\w+\s+set\b|\bdelete\s+from\b"
        r"|executemany|executescript",
        re.IGNORECASE,
    )
    infractores = []
    for f in paquete.rglob("*.py"):
        if f in permitidos or (paquete / "persistence") in f.parents:
            continue
        if patron.search(f.read_text(encoding="utf-8")):
            infractores.append(str(f.relative_to(RAIZ)))
    assert not infractores, infractores
