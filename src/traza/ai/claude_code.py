"""Extracción de partidas con Claude Code, usando la suscripción del usuario (ADR-0013).

Reglas, comprobadas en la documentación y en `claude --help` (v2.1.318, 06-11-2026):
- Sin `--bare` y sin `ANTHROPIC_API_KEY` en el entorno del proceso: con cualquiera de las
  dos, Claude Code no usa la sesión de la suscripción.
- `--tools ""` desactiva todas las herramientas: el documento llega como texto por la
  entrada estándar y la IA no puede tocar nada del equipo. Solo para páginas escaneadas se
  permite `Read`, y `--restricted` lo limita a la carpeta de trabajo, que es la carpeta
  temporal con las imágenes de esas páginas.
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
import tempfile
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


#: Variables que harían que Claude Code no usara la suscripción o enviara el documento a
#: otro destino: clave o token de API, servidor alternativo, o proveedores en la nube.
_VARIABLES_FUERA = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
)


def _entorno() -> dict[str, str]:
    env = dict(os.environ)
    for v in _VARIABLES_FUERA:
        env.pop(v, None)
    return env


def extraer(
    contenido: str,
    imagenes: dict[int, Path] | None = None,
    comando: list[str] | None = None,
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


def _ejecutar(
    base: list[str],
    contenido: str,
    imagenes: dict[int, Path] | None,
    instrucciones: str = INSTRUCCIONES,
    esquema: dict[str, Any] = ESQUEMA,
    clave: str = "partidas",
) -> dict[str, Any]:
    herramientas = ""
    carpeta = None
    if imagenes:
        carpeta = next(iter(imagenes.values())).resolve().parent
        # La lista de imágenes va con el documento por la entrada estándar (no en la línea
        # de órdenes, que en Windows tiene un límite de longitud).
        contenido += "\n\n=== Páginas sin texto: léelas como imagen con la herramienta Read ===\n"
        contenido += "\n".join(f"p. {n}: {r.resolve()}" for n, r in sorted(imagenes.items()))
        herramientas = "Read"
    args = [
        *base,
        "-p",
        instrucciones,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(esquema, ensure_ascii=False),
        "--tools",
        herramientas,
        "--permission-mode",
        "dontAsk",
        # Aislamiento (comprobado en `claude --help`, v2.1.318): sin ajustes de usuario ni de
        # proyecto, sin herramientas que ejecutan código, lectura limitada a la carpeta de
        # trabajo (la de las imágenes), sin servidores MCP y sin guardar la sesión en disco.
        "--restricted",
        "--strict-mcp-config",
        "--no-session-persistence",
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
            errors="replace",
            env=_entorno(),
            cwd=carpeta or tempfile.gettempdir(),
            timeout=TIEMPO_MAXIMO_S,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise IaError(f"Claude Code no ha respondido en {TIEMPO_MAXIMO_S // 60} minutos.") from exc
    except OSError as exc:
        raise IaNoDisponible(f"No se puede ejecutar Claude Code: {exc}") from exc
    return interpretar_salida(r.returncode, r.stdout, r.stderr, clave)


def interpretar_salida(
    codigo: int, stdout: str, stderr: str, clave: str = "partidas"
) -> dict[str, Any]:
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
    if not isinstance(salida, dict) or clave not in salida:
        raise IaError(
            "Claude Code no ha devuelto la extracción estructurada. "
            f"Mensaje: {str(datos.get('result', ''))[:500]}"
        )
    return salida


# --- Qué columna es qué en un Excel de certificación (docs/modules/obra.md, bloque 2b) ----
#
# Usuario (09-11-2026): «al final debes ser capaz de interpretar un Excel»; «yo puedo tener
# una plantilla pero un cliente funcione con otra». La IA SOLO dice qué columna es qué
# mirando las filas de títulos; no lee ni devuelve ninguna cifra (las lee TRAZA de las
# celdas, app/obra y io/certificacion_excel).

_COLUMNA = {"type": ["string", "null"], "description": "Letra de la columna (p. ej. «H») o null"}

ESQUEMA_MAPEO: dict[str, Any] = {
    "type": "object",
    "properties": {
        "hoja": {"type": "string"},
        "fila_titulos": {"type": "integer"},
        "columnas": {
            "type": "object",
            "properties": {
                rol: _COLUMNA
                for rol in (
                    "codigo",
                    "resumen",
                    "naturaleza",
                    "importe_origen",
                    "importe_anterior",
                    "importe_mes",
                    "porcentaje_origen",
                    "importe_presupuesto",
                )
            },
            "required": [
                "codigo",
                "resumen",
                "naturaleza",
                "importe_origen",
                "importe_anterior",
                "importe_mes",
                "porcentaje_origen",
                "importe_presupuesto",
            ],
            "additionalProperties": False,
        },
    },
    "required": ["hoja", "fila_titulos", "columnas"],
    "additionalProperties": False,
}

INSTRUCCIONES_MAPEO = """Eres un técnico de obra en España. Te paso las primeras filas de \
un Excel de CERTIFICACIÓN de obra (lo ejecutado sobre el presupuesto), con la referencia de \
cada celda. Di solo QUÉ COLUMNA ES QUÉ; no leas ni devuelvas ninguna cifra.

- "hoja" y "fila_titulos": la hoja y la fila donde están los títulos de las columnas.
- "columnas": la letra de la columna de cada dato, o null si no está:
  codigo (código de la partida o capítulo), resumen (descripción), naturaleza (si hay una
  columna que dice Capítulo/Partida), importe_origen (importe certificado A ORIGEN, es decir,
  acumulado hasta esta certificación), importe_anterior (certificado en las anteriores),
  importe_mes (certificado en ESTA certificación), porcentaje_origen (% ejecutado a origen),
  importe_presupuesto (importe del presupuesto, el 100 %).
- Si dudas entre dos columnas para un dato, pon null: es mejor no saberlo que equivocarse.
El Excel viene a continuación."""


def mapear_columnas(contenido: str, comando: list[str] | None = None) -> dict[str, Any]:
    """Pregunta a Claude Code qué columna es qué (sin cifras). `comando`, solo en pruebas."""
    if comando is not None:
        base = comando
    else:
        claude = disponible()
        if claude is None or claude.suffix.lower() in (".cmd", ".bat"):
            raise IaNoDisponible(
                "Para interpretar este Excel hace falta Claude Code (versión nativa) con tu "
                "suscripción: TRAZA no ha reconocido sus columnas por los títulos."
            )
        base = [str(claude)]
    return _ejecutar(base, contenido, None, INSTRUCCIONES_MAPEO, ESQUEMA_MAPEO, "columnas")
