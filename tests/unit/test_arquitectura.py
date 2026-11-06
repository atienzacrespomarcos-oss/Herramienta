"""Las reglas entre capas se comprueban en cada ejecución de pruebas, no solo en CI."""

from __future__ import annotations

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
    permitidos = {"persistence", "proyecto.py"}
    patron = ("INSERT INTO", "UPDATE ", "DELETE FROM")
    infractores = []
    for f in (RAIZ / "src" / "traza").rglob("*.py"):
        if permitidos & set(f.relative_to(RAIZ / "src" / "traza").parts):
            continue
        texto = f.read_text(encoding="utf-8")
        if any(p in texto for p in patron):
            infractores.append(str(f.relative_to(RAIZ)))
    assert not infractores, infractores
