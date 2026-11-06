# Módulo: interfaz (Etapa 1, bloque 2)

## Decisiones del usuario (06-11-2026)

- Distribución **clásica de ingeniería**: árbol de elementos a la izquierda, propiedades en el
  centro, y abajo pestañas Documentos · Historial · Pendientes. Paneles movibles.
- Tema de color **según Windows** (se usa el estilo nativo de Qt; no se fuerza claro u oscuro).
- Arranque mediante **TRAZA.exe** generado automáticamente en GitHub.

## Qué ves

| Zona | Contenido |
|---|---|
| Elementos (izquierda) | Árbol con código, tipo y estado. Los componentes cuelgan de su conjunto. |
| Propiedades (centro) | **Todas** las propiedades del tipo, tengan valor o no. Lo que falta aparece como «— no consta —» en gris. Cada valor muestra unidad, procedencia y fuente (documento · página, o justificación de la hipótesis). Las obligatorias para aprobar llevan «*». Doble clic = fijar valor. |
| Documentos | Nombre, tipo, páginas, fecha y **cuántos valores lo citan**. Doble clic = abrirlo con el programa de Windows. |
| Historial | Cada cambio: fecha (UTC), autor, orden, a qué afecta y qué campos cambió. |
| Pendientes | Información por confirmar y a qué elemento afecta. |

## Menús

Archivo (nuevo, abrir, cerrar, copia de seguridad, restaurar copia, salir) · Edición
(deshacer, rehacer) · Elemento (nuevo, fijar valor, borrar valor, confirmar propuesta de IA,
aprobar, reabrir) · Documentos (incorporar, abrir) · Pendientes (anotar, resolver) · Ayuda.

Las acciones que no aplican se desactivan: sin proyecto solo se puede crear, abrir, salir y
ver la ayuda; con un elemento aprobado seleccionado se desactivan las acciones que lo
modificarían (fijar, borrar, confirmar, aprobar) y se activa «Reabrir».

Ningún error se queda sin avisar: cualquier fallo (disco lleno, permisos, fichero en uso) se
muestra en un aviso y la operación no se da por hecha. Por seguridad, desde TRAZA solo se
abren documentos de tipo documental (PDF, Office, DXF/DWG, BC3, imágenes, texto); un `.bat`
o `.exe` incorporado no se ejecuta.

## Introducción de valores

- Procedencias elegibles a mano: «Lo indico yo», «Documento del proyecto», «Catálogo de
  fabricante», «Hipótesis de diseño (justificada)». **No** se ofrecen «Cálculo» (lo escribe un
  motor) ni «Propuesta de IA» (la genera la IA).
- Números con convención española. **«2.400» se rechaza por ambiguo** (¿2400 o 2,4?): hay que
  escribir 2400 o 2,4. Sin separador de miles ni espacios («2 400» también se rechaza).
- Potencias, caudales, tensiones y masas no admiten valores negativos.
- La unidad se escribe como en el documento (m³/h, kW, W/m²·K); se comprueba la magnitud.

## TRAZA.exe

- Se genera en cada cambio (pestaña **Actions** de GitHub → ejecución «Ejecutable Windows» →
  artefacto **TRAZA-windows**, se conserva 30 días). Es una carpeta: se descomprime y se abre
  `TRAZA.exe`. No requiere instalar Python.
- Antes de publicarse, el propio ejecutable ejecuta `--autoprueba` (crear proyecto, incorporar
  PDF, fijar valor citando página, aprobar, comprobar bloqueo, deshacer/rehacer). Si falla, no
  se publica. El resultado se escribe en un informe que el CI muestra; si el .exe fallara
  sin terminar, el trabajo se corta a los 20 minutos.
- `TRAZA.exe "C:\ruta\Proyecto.traza"` abre directamente un proyecto.

## Pruebas

`tests/ui/test_ventana.py` recorre la interfaz real con respuestas preparadas a los diálogos:
escenario de aceptación completo, pendientes, jerarquía, borrar valor, restaurar copia, y
que **ninguna acción del menú carece de función**. Los diálogos reales se prueban sin
mostrarse (número ambiguo, cita incompleta, orígenes ofrecidos).

## Limitaciones conocidas

- Fechas mostradas en UTC (no se convierte a hora local todavía).
- El visor 2D llega con la importación DXF (Etapa 2).
- El ejecutable no está firmado digitalmente: Windows SmartScreen puede avisar la primera vez
  («Más información» → «Ejecutar de todas formas»).
- El tema oscuro depende de la versión de Qt y de Windows: **pendiente de comprobar por el
  usuario** en su equipo.
