"""Extracción de partidas con Claude Code, usando la suscripción del usuario (ADR-0013).

Reglas, comprobadas en la documentación y en `claude --help` (v2.1.318, 06-11-2026):
- Sin `--bare` y sin `ANTHROPIC_API_KEY` en el entorno del proceso: con cualquiera de las
  dos, Claude Code no usa la sesión de la suscripción.
- `--tools ""` desactiva todas las herramientas: el documento llega como texto por la
  entrada estándar y la IA no puede tocar nada del equipo. Solo para PDF escaneados se
  permite `Read`, limitado a las imágenes de las páginas.
- `--permission-mode dontAsk`: deniega cualquier cosa que pidiera permiso.
- `--output-format json` + `--json-schema`: la respuesta se valida contra el esquema y
  llega en `structured_output`; si falta, la extracción ha fallado y se dice.

Este módulo NO decide si lo leído es correcto: solo transporta. Las comprobaciones son
deterministas y están en `app/lectura_ia.py`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

PROVEEDOR = "ia-claude-code"
VERSION = "1.0.0"  # versión de las instrucciones y del esquema, no de Claude Code
TIEMPO_MAXIMO_S = 15 * 60


class IaNoDisponible(RuntimeError):
    """Claude Code no está instalado o no se puede ejecutar."""


class IaError(RuntimeError):
    """Claude Code se ejecutó pero no devolvió una extracción válida."""


_NUMERO = {
    "type": "object",
    "properties": {
        "texto": {"type": ["string", "null"], "description": "Texto literal tal como aparece"},
        "valor": {"type": ["number", "null"]},
        "donde": {"type": ["string", "null"], "description": "«p. N» en PDF o «Hoja!B12» en Excel"},
    },
    "required": ["texto", "valor", "donde"],
    "additionalProperties": False,
}

ESQUEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "proveedor": {"type": ["string", "null"]},
        "total": _NUMERO,
        "partidas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "capitulo": {"type": ["string", "null"]},
                    "codigo": {"type": ["string", "null"]},
                    "descripcion": {"type": "string"},
                    "unidad": {"type": ["string", "null"]},
                    "donde": {"type": "string", "description": "«p. N» o «Hoja!fila» de la línea"},
                    "cantidad": _NUMERO,
                    "precio": _NUMERO,
                    "importe": _NUMERO,
                },
                "required": [
                    "capitulo",
                    "codigo",
                    "descripcion",
                    "unidad",
                    "donde",
                    "cantidad",
                    "precio",
                    "importe",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["proveedor", "total", "partidas"],
    "additionalProperties": False,
}

INSTRUCCIONES = """Eres un lector de ofertas, presupuestos y mediciones de instalaciones \
(climatización, ventilación, electricidad, fontanería) para un ingeniero en España.
Extrae TODAS las líneas que sean partidas (capítulos aparte), en el orden del documento.

Reglas estrictas:
1. No calcules, no completes, no corrijas y no deduzcas nada. Si un dato no está escrito en el
   documento, devuelve null.
2. Para cantidad, precio unitario, importe de la línea y total del documento devuelve:
   - "texto": el texto EXACTO tal como aparece (mismos puntos, comas y símbolos),
   - "valor": tu lectura numérica de ese texto,
   - "donde": la página («p. 3») o la celda exacta («Hoja1!E12») donde aparece.
3. "donde" de cada partida: la página («p. 3») o la fila de Excel («Hoja1!12»).
4. "capitulo": el título del capítulo o apartado en que está la línea, si lo hay.
5. Descuentos, portes o impuestos no son partidas: no los incluyas como tales.
6. "total": el total del documento antes de impuestos si aparece; si no, null.
El documento viene a continuación, con marcas de página o de celda."""


def disponible() -> Path | None:
    ruta = shutil.which("claude")
    return Path(ruta) if ruta else None


def _entorno() -> dict[str, str]:
    env = dict(os.environ)
    # Con ANTHROPIC_API_KEY definida, `claude -p` la usa siempre y factura por API.
    env.pop("ANTHROPIC_API_KEY", None)
    return env


def extraer(
    contenido: str, imagenes: list[Path] | None = None, comando: list[str] | None = None
) -> dict[str, Any]:
    """Envía el documento a Claude Code y devuelve la extracción (sin comprobar).

    `comando` sustituye al ejecutable (p. ej. [python, simulador.py]) solo en pruebas.
    """
    if comando is not None:
        return _ejecutar(comando, contenido, imagenes)
    claude = disponible()
    if claude is None:
        raise IaNoDisponible(
            "Claude Code no está instalado en este equipo. Instálalo e inicia sesión con tu "
            "suscripción para leer PDF y Excel con IA (el BC3 no lo necesita)."
        )
    if claude.suffix.lower() in (".cmd", ".bat"):
        # cmd.exe reinterpreta comillas y llaves del esquema JSON: solo la versión nativa.
        raise IaNoDisponible(
            "Se ha encontrado Claude Code instalado con npm (claude.cmd). TRAZA necesita la "
            "versión nativa (claude.exe), que instala el instalador oficial."
        )
    return _ejecutar([str(claude)], contenido, imagenes)


def _ejecutar(base: list[str], contenido: str, imagenes: list[Path] | None) -> dict[str, Any]:
    orden = INSTRUCCIONES
    herramientas = ""
    if imagenes:
        lista = "\n".join(f"- p. {i}: {p.resolve()}" for i, p in enumerate(imagenes, start=1))
        orden += (
            "\n\nEl documento es un PDF escaneado. Lee estas imágenes, una por página, "
            f"con la herramienta Read:\n{lista}"
        )
        herramientas = "Read"
    args = [
        *base,
        "-p",
        orden,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(ESQUEMA, ensure_ascii=False),
        "--tools",
        herramientas,
        "--permission-mode",
        "dontAsk",
    ]
    if herramientas:
        args += ["--allowedTools", herramientas]
    try:
        r = subprocess.run(
            args,
            input=contenido,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_entorno(),
            timeout=TIEMPO_MAXIMO_S,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise IaError(f"Claude Code no ha respondido en {TIEMPO_MAXIMO_S // 60} minutos.") from exc
    except OSError as exc:
        raise IaNoDisponible(f"No se puede ejecutar Claude Code: {exc}") from exc
    return interpretar_salida(r.returncode, r.stdout, r.stderr)


def interpretar_salida(codigo: int, stdout: str, stderr: str) -> dict[str, Any]:
    """Los fallos de sesión llegan por stdout con código 0: no basta mirar el código."""
    try:
        datos = json.loads(stdout)
    except json.JSONDecodeError:
        detalle = (stderr or stdout).strip()[:500]
        raise IaError(f"Respuesta de Claude Code no válida (código {codigo}): {detalle}") from None
    if not isinstance(datos, dict):
        raise IaError("Respuesta de Claude Code con formato inesperado.")
    if datos.get("is_error") or codigo != 0:
        raise IaError(f"Claude Code devolvió un error: {str(datos.get('result', ''))[:500]}")
    salida = datos.get("structured_output")
    if not isinstance(salida, dict) or "partidas" not in salida:
        raise IaError(
            "Claude Code no ha devuelto la extracción estructurada. "
            f"Mensaje: {str(datos.get('result', ''))[:500]}"
        )
    return salida
