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
| Valores | Se guardan **tal como los da su fuente** (2 400 m³/h si así figura) con su unidad, comprobando que la unidad mide la magnitud correcta. |
| Procedencia | Obligatoria en cada valor: usuario, documento (con página), catálogo (con página), cálculo (solo lo escribe un motor), hipótesis (con justificación) o propuesta de IA (sin validez hasta que la confirmas). |
| Citas de PDF | Deben empezar por la página («p. 14», «p. 14, tabla 3») y la página tiene que existir en el documento. |
| Estados | borrador → propuesto → calculado → comprobado; **aprobar** y **reabrir** son órdenes aparte que exigen escribir el motivo y dejan una decisión registrada. |
| Aprobar | Exige fabricante y modelo y que no queden propuestas de IA sin confirmar. Un elemento aprobado no admite cambios hasta reabrirlo. |
| Deshacer / rehacer | De cualquier orden, en orden inverso. Deshacer la última aprobación está permitido porque es su inversa inmediata. |
| Registro de cambios | Cada modificación (y cada deshacer/rehacer) queda anotada con la fila antes y después. La base de datos impide editarlo o borrarlo. |
| Información pendiente | Lista de datos por confirmar, con su resolución escrita. |
| Copias de seguridad | Automática al abrir, manual cuando quieras y antes de restaurar. Se conservan las 30 más recientes. |

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
- `tests/integration/test_deshacer_propiedades.py`: 40 secuencias aleatorias de órdenes;
  deshacer todo devuelve el proyecto exactamente al estado inicial y rehacer todo, al final.
- `tests/unit/test_nucleo.py`: procedencia, unidades, tipos, estados, citas de página.
- `tests/unit/test_arquitectura.py`: separación entre capas y que nada escriba en la base de
  datos fuera de las órdenes.

## Limitaciones conocidas

- Sin interfaz todavía (bloque siguiente).
- El historial de deshacer vive mientras el proyecto está abierto; el registro de cambios,
  para siempre.
- Restaurar una copia exige tener el proyecto cerrado.
- Las citas de hojas de cálculo (hoja/celda) se aceptan como texto libre; su comprobación
  llega con la lectura de XLSX (Etapa 2).
