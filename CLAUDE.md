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
Y (07-11-2026, ante preguntas sobre el caudal de los difusores): «Creo que estás hilando
demasiado fino». Preguntar solo decisiones de alcance o de forma de trabajar; los detalles
de método (fuentes de un dato, hipótesis por defecto, formatos) se deciden con criterio y
se documentan en la ficha del módulo.

## Lo que el usuario quiere de la herramienta (06-11-2026)

- **Muy intuitiva y a medida**: solo lo que usa. Nada de pantallas o funciones «por si
  acaso». Antes de añadir algo, comprobar que responde a una necesidad que él ha dicho.
- **Presentación limpia** (07-11-2026): «Herramienta profesional y completa no quiere decir
  herramienta recargada. Una presentación limpia es clave». En pantalla, lo que decide
  (resultado y unidades); el detalle completo, en una pestaña aparte o en el Excel. Tablas
  con pocas columnas, textos de resumen cortos.
- Organizada en **pasos del proyecto con estado** (hecho / pendiente / desactualizado y
  qué falta), adaptados al **tipo de encargo**: **Diseño · Oferta · Ampliación**
  (09-11-2026; ficha `docs/modules/flujo.md`). **Solo se ven los pasos que funcionan.**
  Planos revisados o de ampliación propuestos por el usuario: **se recalcula todo** lo que
  depende de ellos. Entregables de un diseño: DXF/LISP, Excel y la **justificación de
  cálculos** en Word (de apoyo, «nada oficial», sobre la plantilla de Aliter que elige el
  usuario; sin membrete de TRAZA).
- Prioridad 1: **leer ofertas, presupuestos y mediciones** (BC3, Excel y PDF) y preparar
  **ampliaciones y modificaciones** (Excel y BC3). Ficha: `docs/modules/mediciones.md`.
- **Obra** (09-11-2026, ficha `docs/modules/obra.md`): control **por obra** de venta, coste
  objetivo (Excel de Presto agrupado por el usuario), certificaciones, coste real,
  previsión a fin de obra y **futuribles en escenarios sí/no**. Nace desde cero o desde
  una oferta. Los documentos reales del usuario no van al repositorio (es público).
- **Ficheros de ejemplo del usuario** (09-11-2026): son **plantillas inventadas** que
  enseñan su forma de trabajar («no uses de ninguna forma esto»). Se toma de ellas la
  estructura y el método; nunca sus datos, ni en el código, ni en las pruebas, ni en docs.
- **Pedidos: fuera** (09-11-2026: «Ya te dije que olvidaras pedidos»). No proponer Excel de
  pedidos ni enlazar el diseño con pedidos.

## Antes de tocar nada

1. Lee `docs/FEATURE_REGISTER.md` (estado real de cada funcionalidad) y la ficha del
   módulo en `docs/modules/`.
2. Las decisiones de arquitectura están en `docs/adr/`. No contradigas un ADR sin escribir
   otro que lo sustituya.
3. El historial de la conversación no es memoria: lo que importe, a `docs/`.

## Líneas rojas

> **Criterio del usuario sobre fuentes (07-11-2026), prevalece sobre las versiones
> anteriores de las líneas 1, 3 y 4:** «No siempre vas a encontrar fuentes 100 % fiables y
> a mí me da exactamente igual. No quiero cosas como "no verificado", "no comprobado" o
> cosas así. Quiero una herramienta que eleve mi nivel y me permita ser mucho más
> eficiente. Cuando ocurran cosas así, busca y fíate de lo que encuentres».
> Y sobre cerramientos: «Nunca me dan esos datos. Presupón los típicos dependiendo del
> tipo de construcción».

1. **No inventar, pero no bloquear.** Ningún valor, coeficiente o tabla sale de la nada:
   sale de una fuente publicada que se busca y se usa (norma, guía, manual, catálogo de
   fabricante, tabla técnica reconocida), o de un valor típico del tipo de construcción o
   de uso con su fuente. **Nunca** se muestra «no verificado», «no comprobado» ni «no
   evaluable» por falta de una fuente «perfecta»: se busca la mejor disponible y se usa.
   «No consta» queda solo para un dato del proyecto que el usuario no ha dado y que no
   tiene un valor típico razonable.
2. **Procedencia por valor.** Toda propiedad del modelo lleva origen (usuario, documento,
   cálculo, catálogo, hipótesis, IA-propuesta). Una propiedad sin origen es un fallo. Los
   valores típicos y de tablas llevan su fuente citada (documento, apartado, URL): sirve
   para consultarla, no para ponerla en duda.
3. **Fuentes.** Se citan con su referencia (y URL cuando la hay). Si dos fuentes dicen
   cosas distintas, se elige con criterio de ingeniería la más reconocida en el mercado
   español y se deja escrita la elección en la ficha del módulo; no se traslada la duda
   al usuario.
4. **Comprobaciones:** CUMPLE / NO CUMPLE, con el criterio y su fuente. Un CUMPLE nunca
   se da por defecto: se calcula.
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
- Fuera de alcance (decisión del usuario): **saneamiento** (09-11-2026); diseño de **VRF** y
  selección de **ventiladores** («cada fabricante tiene su software», 08-11-2026; VRF
  confirmado el 11-11-2026); **PCI**, **AF y ACS** (11-11-2026). Dentro, pendientes
  (11-11-2026): coordinación de trazados, estructura solo geometría, IA sobre documentos y
  planos en PDF (vectorial y escaneado). Ver `docs/FEATURE_REGISTER.md`.
- Validación: el usuario **no tiene programas de cálculo**. Los motores se prueban con
  ejemplos resueltos publicados cuando existen y, si no, con casos de resultado conocido
  calculados a mano en la prueba (reglas en `docs/TESTING_STRATEGY.md` §0.2). El estado
  «Limitada»/«Validada» es solo del registro interno (`FEATURE_REGISTER.md`): la
  herramienta no enseña etiquetas de «no validado».
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
  `uv run pyinstaller --noconfirm --windowed --name TRAZA --collect-data pint --collect-data docx scripts/traza_exe.py`.
- Lanzar la app: `uv run python -m traza [carpeta.traza]`.

## Trampas conocidas

- La interfaz no abre diálogos directamente: todo pasa por `ui/dialogos.Preguntas`, que los
  tests sustituyen. Una acción nueva que llame a QMessageBox/QFileDialog directamente no se
  puede probar: añádela a `Preguntas`.
- `--collect-data pint` y `--collect-data docx` son imprescindibles en PyInstaller: sin
  ellos el .exe arranca y falla al primer valor con unidad o al generar el Word.
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
