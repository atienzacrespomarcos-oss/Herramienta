# Módulo: núcleo del proyecto (Etapa 1, bloque 1)

## Objetivo

Guardar el proyecto de forma que **cada valor sepa de dónde sale**, que **nada aprobado se
modifique en silencio** y que **todo cambio quede registrado y se pueda deshacer**. Es la
base sobre la que se apoyan todos los cálculos posteriores.

## Qué hace (para el ingeniero)

| Función | Comportamiento |
|---|---|
| Proyecto | Una carpeta `Nombre.traza/` con la base de datos, los documentos, las exportaciones y las copias. No sobrescribe un proyecto existente. |
| Documentos | Al incorporar un documento se copia al almacén del proyecto, se comprueba que la copia es idéntica (huella SHA-256), queda de solo lectura y no se admite dos veces. De los PDF se guarda el número de páginas. |
| Elementos | Cada elemento tiene código único (UTA-01…), tipo y estado. En esta etapa solo existe el tipo genérico «Equipo» (fabricante, modelo, potencias, caudal de aire, tensión, masa). |
| Valores | Se guardan **tal como los da su fuente** (2 400 m³/h si así figura) con su unidad, comprobando que la unidad mide la magnitud correcta. Se admite la notación española: en «W/m²·K» todo lo que sigue a la barra es denominador; con dos barras sin paréntesis la unidad se rechaza por ambigua. |
| Procedencia | Obligatoria en cada valor: usuario, documento (con página), catálogo (con página), cálculo (solo lo escribe un motor), hipótesis (con justificación) o propuesta de IA (sin validez hasta que la confirmas). |
| Citas de PDF | Deben empezar por la página («p. 14», «p. 14, tabla 3») y la página tiene que existir en el documento. |
| Estados | borrador → propuesto → calculado → comprobado. «Calculado» y «comprobado» **solo los fija un motor** al ejecutarse: marcarlos a mano sería un indicador de cumplimiento sin comprobación. **Aprobar** y **reabrir** son órdenes aparte que exigen escribir el motivo y dejan una decisión registrada. |
| Aprobar | Exige fabricante y modelo y que no queden propuestas de IA sin confirmar. Un elemento aprobado no admite cambios —tampoco componentes nuevos colgados de él— hasta reabrirlo. |
| Quién hace qué | La IA solo puede **proponer** valores y señalar información pendiente; no confirma, no aprueba, no reabre. Solo la IA genera propuestas de IA. |
| Deshacer / rehacer | De cualquier orden, en orden inverso. Deshacer la última aprobación está permitido porque es su inversa inmediata. |
| Registro de cambios | Cada modificación (y cada deshacer/rehacer) queda anotada con la fila antes y después. La base de datos impide editarlo o borrarlo. |
| Información pendiente | Lista de datos por confirmar, con su resolución escrita. |
| Copias de seguridad | Automática al abrir, manual cuando quieras, antes de restaurar y antes de actualizar el formato del proyecto. Solo se podan las automáticas de apertura (se guardan las 30 últimas); las demás no se borran solas. Si la base de datos está dañada, se aparta como «danada» y se restaura igualmente. |

## Doble protección

Las reglas de procedencia se comprueban en el programa **y** en la propia base de datos
(restricciones CHECK). Si un error de programación saltara la primera barrera, la base de
datos se negaría a guardar un valor sin procedencia.

## Decisiones técnicas

- Base de datos SQLite con migraciones propias (ADR-0003, actualizado).
- Diario clásico de SQLite (no WAL): el proyecto es **un solo fichero** de base de datos, sin
  ficheros auxiliares que se pierdan al copiar la carpeta.
- Deshacer genérico por «foto de fila antes/después»: ninguna orden programa su propia
  inversa, que es donde suelen esconderse los fallos.

## Pruebas

- `tests/integration/test_proyecto.py`: escenario de aceptación completo y cada regla.
- `tests/integration/test_deshacer_propiedades.py`: 60 secuencias aleatorias con **todas**
  las órdenes del núcleo (incluidas las de la IA y el motor); cada rechazo no deja rastro,
  deshacer todo devuelve el estado inicial y rehacer todo, el final.
- `tests/integration/test_revision_nucleo.py`: un test por cada fallo de la revisión.
- `tests/unit/test_nucleo.py`: procedencia, unidades, tipos, estados, citas de página.
- `tests/unit/test_arquitectura.py`: separación entre capas y que nada escriba en la base de
  datos fuera de las órdenes.

## Limitaciones conocidas

- La interfaz está en `docs/modules/interfaz.md`.
- El historial de deshacer vive mientras el proyecto está abierto; el registro de cambios,
  para siempre.
- Restaurar una copia exige tener el proyecto cerrado.
- En esta etapa se puede aprobar desde cualquier estado (es aprobar datos de selección,
  sin cálculo). Cuando existan motores, cada tipo de elemento exigirá su cálculo y sus
  comprobaciones antes de poder aprobarse.
- Las citas de hojas de cálculo (hoja/celda) se aceptan como texto libre; su comprobación
  llega con la lectura de XLSX (Etapa 2).
