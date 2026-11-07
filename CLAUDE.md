# TRAZA — instrucciones permanentes para Claude Code

Nombre confirmado por el usuario (06-11-2026); el repositorio se llama `Herramienta`. Herramienta **personal** de ingeniería de instalaciones para naves
industriales (mercado español). Usuario: ingeniero industrial que **usa y valida**, no
programa: explica en términos de ingeniería, no de código.

Si algo de aquí deja de ser cierto, corrígelo en el mismo cambio.

## Forma de trabajo con el usuario (pedida el 06-11-2026)

**Pregunta → respuesta con acciones.** Ante cada decisión: presentar opciones concretas
(con la recomendada marcada y su consecuencia), el usuario decide, Claude ejecuta. No
decidir por él lo que es suyo (alcance, prioridades, aspecto); sí resolver
sin preguntar lo puramente técnico, dejándolo escrito en un ADR o en la ficha del módulo.

**Actualización del 07-11-2026 (usuario; prevalece sobre el párrafo anterior):** «Solo quiero que pares cuando tengas dudas de
qué debe incorporar la herramienta, o cosas de cómo debe hacer algo. Si no, continúa con tu
criterio». Y: «Fusiona cuando esté en verde y sigue». Por tanto: parar solo ante dudas de
**qué** debe hacer la herramienta o **cómo** debe hacerlo para el usuario; lo demás se
resuelve y se documenta. Los PR se fusionan cuando la CI está en verde y la revisión
independiente no deja nada pendiente.

## Lo que el usuario quiere de la herramienta (06-11-2026)

- **Muy intuitiva y a medida**: solo lo que usa. Nada de pantallas o funciones «por si
  acaso». Antes de añadir algo, comprobar que responde a una necesidad que él ha dicho.
- Organizada en **pasos del proyecto**, adaptados al **tipo de encargo** (diseño +
  presupuesto + instalación / presupuesto + instalación / solo instalación). **Solo se ven
  los pasos que funcionan.**
- Prioridad 1: **leer ofertas, presupuestos y mediciones** (BC3, Excel y PDF), sacar un
  **Excel con todo** para sus pedidos (los hace en su ERP) y preparar **ampliaciones y
  modificaciones** (Excel y BC3). Ficha: `docs/modules/mediciones.md`.

## Antes de tocar nada

1. Lee `docs/FEATURE_REGISTER.md` (estado real de cada funcionalidad) y la ficha del
   módulo en `docs/modules/`.
2. Las decisiones de arquitectura están en `docs/adr/`. No contradigas un ADR sin escribir
   otro que lo sustituya.
3. El historial de la conversación no es memoria: lo que importe, a `docs/`.

## Líneas rojas

1. **No inventar.** Ningún valor, coeficiente, límite, artículo o tabla sin fuente. Sin
   fuente ⇒ «no consta» / NO EVALUABLE, nunca una cifra plausible.
2. **Procedencia por valor.** Toda propiedad del modelo lleva origen (usuario, documento,
   cálculo, catálogo, hipótesis, IA-propuesta). Una propiedad sin origen es un fallo.
3. **Fuentes secundarias marcadas.** El usuario no tiene normas UNE. Lo que se tome de
   fuentes públicas que reproducen una UNE se marca `fuente_secundaria` con URL, fecha de
   consulta y edición citada; se contrasta con ≥ 2 fuentes cuando existan; las
   discrepancias se muestran, no se resuelven en silencio.
4. **Comprobaciones con tres salidas:** CUMPLE / NO CUMPLE / NO EVALUABLE. Jamás un CUMPLE
   por defecto ni con un criterio `verificado: pendiente`.
5. **Nada aprobado se modifica en silencio.** Reabrir es una decisión registrada.
6. **Motores puros.** `engines/` y `rules/` no importan Qt, base de datos ni IA
   (lo vigila import-linter). Toda magnitud que cruza un motor lleva unidad.
7. **La IA solo propone órdenes**; no escribe en el modelo. Ningún documento sale del
   equipo sin confirmación explícita por envío. Excepción decidida por el usuario para la
   **lectura de documentos** (ADR-0013): lo leído por la IA entra directo **solo si pasa las
   comprobaciones deterministas** (texto literal presente en la página/celda citada, número
   reinterpretado con la regla española, números en el mismo renglón que su descripción,
   importes y totales con un céntimo de tolerancia); si no, «a revisar».
   La IA se usa vía Claude Code con la suscripción del usuario (sin `--bare`, sin
   `ANTHROPIC_API_KEY` en el entorno del proceso).
8. **Toda modificación del modelo pasa por una orden** (deshacer + registro de cambios).
9. **Toda aproximación se declara** en el registro de cálculo.

## Entorno del usuario (condiciona las salidas)

- Windows, uso solo personal. AutoCAD **completo 2013–2017** ⇒ DXF **R2013 (AC1027)**;
  AutoLISP/Visual LISP solo con funciones existentes en 2013 (lista blanca con test).
- Sin DWG (ODA File Converter: no comercial salvo miembros).
- Estructura: **solo geometría**, sin cálculo estructural.
- Validación: el usuario **no tiene programas de cálculo**. Los motores se validan con
  ejemplos resueltos publicados y localizables (reglas en `docs/TESTING_STRATEGY.md` §0.2).
  Sin ejemplo publicado, el motor queda «Limitada», nunca «Validada».
- Entregas: **una rama y un PR en borrador por bloque**. Desde el 07-11-2026 Claude lo
  fusiona cuando la CI está en verde y la revisión independiente no deja nada pendiente
  (petición del usuario, ver «Forma de trabajo»).

## Comandos

- Entorno: `uv sync` (Python 3.12, fijado en `.python-version` y `uv.lock`).
- Pruebas: `uv run python -m pytest` (segundos). Con `QT_QPA_PLATFORM=offscreen` sin pantalla.
- Estilo: `uv run ruff check .` y `uv run ruff format --check .`
- Capas: `uv run lint-imports` (también lo ejecuta `tests/unit/test_arquitectura.py`).
- CI (`.github/workflows/ci.yml`) repite todo en **Windows y Linux**.
- Ejecutable: `.github/workflows/ejecutable.yml` genera TRAZA.exe (PyInstaller) y lo publica
  como artefacto solo si pasa `TRAZA.exe --autoprueba`. En local:
  `uv run pyinstaller --noconfirm --windowed --name TRAZA --collect-data pint scripts/traza_exe.py`.
- Lanzar la app: `uv run python -m traza [carpeta.traza]`.

## Trampas conocidas

- La interfaz no abre diálogos directamente: todo pasa por `ui/dialogos.Preguntas`, que los
  tests sustituyen. Una acción nueva que llame a QMessageBox/QFileDialog directamente no se
  puede probar: añádela a `Preguntas`.
- `--collect-data pint` es imprescindible en PyInstaller: sin él el .exe arranca y falla al
  primer valor con unidad.
- Una conexión SQLite abierta bloquea el fichero en Windows (no en Linux): cierra siempre
  ante error. El CI de Windows lo cazó el 06-11-2026.
- Toda escritura en la base de datos pasa por `Proyecto.ejecutar` (órdenes) o por
  `persistence/`. Un test busca `INSERT/UPDATE/DELETE` fuera de ahí y falla.
- Las migraciones no usan `executescript` (hace COMMIT implícito y rompe la atomicidad).
- `bool` es subclase de `int`: `validar_valor` lo excluye a propósito; no lo «simplifiques».
- En contenedores Linux sin pantalla, PySide6 necesita `libegl1` y `QT_QPA_PLATFORM=offscreen`
  (comprobado 05-11-2026).
- Los heredocs de bash corrompen barras invertidas: para regex o escapes usa la
  herramienta de edición.

## Cómo cerrar una tarea

Una funcionalidad solo pasa a «Validada» cumpliendo los 8 puntos de
`docs/TESTING_STRATEGY.md`. Actualiza `FEATURE_REGISTER.md` y `CHANGELOG.md` en el mismo
cambio. Revisión final por un subagente en contexto nuevo.
