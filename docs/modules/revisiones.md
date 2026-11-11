# Módulo: revisiones del diseño (RF-009)

Estado: **implementado**.

## Decisión del usuario (11-11-2026)
Tras el control, «Revisiones del diseño»: guardar «Rev. 0, Rev. 1…» del proyecto y
comparar qué ha cambiado entre ellas.

## Cómo funciona (decisiones de método de TRAZA)
- **Emitir** (Archivo → Emitir revisión…):
  - Pide un nombre («Para oferta», «Planos rev. B») y una nota opcional, y congela el
    proyecto tal como está.
  - La copia es coherente (API de backup de SQLite) y se guarda en `revisiones/Rev N.db`,
    con su ficha `Rev N.json`: número, nombre, nota, fecha UTC, huella SHA-256 y versión de
    esquema. Las dos quedan de solo lectura.
  - El número sigue al mayor existente y **nunca se reutiliza**.
  - No es una orden: no cambia el modelo y no se deshace. Una revisión emitida no se borra
    desde TRAZA (línea roja 5: nada aprobado se modifica en silencio).
- **Revisión alterada**: si el `.db` falta o su huella no es la emitida, no se usa y se
  dice por qué.
  - La huella va en la ficha, junto al `.db`, así que detecta un cambio accidental (una
    copia a medias, un fichero dañado o tocado por otro programa). No protege frente a
    quien edite a propósito los dos ficheros; para eso no hace falta en una herramienta
    personal.
  - Una revisión de un TRAZA más nuevo, o ilegible, se avisa sin error.
- **Elementos renombrados**: se comparan por su nombre. Un espacio, red o sistema
  renombrado sale como «ya no está» (el nombre anterior) y «nuevo» (el nombre nuevo).
- **Claves**: un elemento se reconoce por su nombre. No hay dos iguales: el código del
  espacio es único, y las órdenes exigen nombre propio a cada red, sistema, circuito,
  subcuadro y salida.
- **Lo que no calcula**: si una parte no calcula (un error del motor, como una red con
  ciclo), entra con su motivo y el resto se compara.
- **Comparar** (Archivo → Comparar con una revisión…), entre una revisión y el estado
  actual, o entre dos revisiones:
  - La revisión se abre **en memoria**, migrada al esquema actual si es anterior; el
    fichero no se toca.
  - Se calcula con los mismos documentos del proyecto (guía del IDAE y planos), que son
    de solo-añadir.
  - Una revisión abierta rechaza cualquier orden.
- **Qué se compara** (`app/revisiones.resumen`): los datos y los resultados que deciden,
  con su unidad.
  - Espacios: superficie y alturas.
  - Cargas: uso, calefacción, refrigeración y aire exterior por espacio; totales.
  - Redes de aire: caudal, terminales conectados y presión necesaria.
  - Sistema hidráulico, por servicio: potencia, caudal, tubería y bomba del primario; por
    circuito, unidades, caudal, tubería y bomba.
  - Subcuadros: alimentación, interruptor general, CUMPLE de conjunto; por salida,
    potencia, cable y caída total.
  - Los números se redondean a la precisión con que se muestran (kW con 2 decimales, m³/h
    sin decimales, Pa sin decimales, m c.a. con 2…): una diferencia de coma flotante no es
    un cambio.
  - Lo que deja de calcular entra con el motivo, porque también es un cambio.
  - Las mediciones y la obra tienen su propio control (modificados y certificaciones) y no
    entran aquí.
- **Salida**:
  - En pantalla, un resumen (número de cambios por apartado).
  - En Excel, la hoja Resumen y la hoja Cambios: apartado, elemento, dato, si es nuevo,
    cambia o ya no está, antes, ahora, diferencia y unidad.

## Validación
- `tests/integration/test_revisiones.py`:
  - numeración y solo lectura;
  - una revisión abierta no admite órdenes y el fichero no cambia;
  - una revisión alterada se rechaza y su número no se reutiliza;
  - sin cambios, la comparación sale vacía;
  - un sistema hidráulico nuevo y un cambio de uso salen como dato y como resultado
    (la carga de refrigeración cambia);
  - el Excel tiene una fila por cambio;
  - la comparación entre dos revisiones da lo mismo.
- `tests/ui/test_revisiones_ventana.py`: emitir y comparar desde el menú.
