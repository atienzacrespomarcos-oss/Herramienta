# Módulo: mediciones, ofertas y modificados (Etapa 2)

Especificación aprobada por decisiones del usuario (06-11-2026).

## Estado (06-11-2026)

| Parte | Estado |
|---|---|
| Lector BC3 | Implementado. Pendiente de validar con un BC3 real del usuario. |
| Partidas en el proyecto con su origen; leer/quitar con deshacer | Implementado |
| Excel con todo | Implementado |
| Interfaz por pasos | Implementado (Documentación · Mediciones y ofertas · Equipos) |
| Tipo de encargo | Se elige al crear el proyecto, se muestra en el título y se puede cambiar. **Hoy no oculta ningún paso**: los tres pasos actuales sirven para los tres encargos. Los pasos de cálculo y planos, cuando existan, solo se verán en «diseño». |
| Lector Excel | Pendiente |
| Lector PDF | Pendiente |
| Ampliaciones y modificaciones (Excel y BC3) | Pendiente |

## Cómo se usa

1. **Documentación** → «Incorporar documento» (el BC3 de la oferta o medición).
2. «Leer medición u oferta» → eliges el documento, si es medición, oferta o presupuesto, y el
   proveedor. Se guardan todas las partidas con el sitio exacto del fichero de donde salen.
3. **Mediciones y ofertas** → capítulos y partidas en árbol, total, y debajo los **avisos**
   del lector (lo que no cuadra en el fichero). Las partidas sin precio aparecen como «no
   consta» y no se suman: el total se marca «parcial».
4. «Exportar Excel con todo» → hoja *Partidas* (documento, tipo, proveedor, capítulo, código,
   etiqueta, ud, descripción, cantidad, precio, importe, origen), hoja *Avisos de lectura* y
   hoja *Información*. Celdas vacías = no consta (nunca 0).
5. «Quitar medición» → quita las partidas leídas de ese documento (el documento se queda).
   Se puede deshacer.

## Por qué va primero

Es donde el usuario pierde más tiempo hoy: leer ofertas, presupuestos y mediciones y pasar
sus datos a Excel. Sus encargos van desde diseño + presupuesto + instalación hasta solo
instalación, así que este módulo sirve en **todos** los tipos de encargo.

## Qué tiene que hacer

1. **Leer** ofertas, presupuestos y mediciones en **BC3, Excel y PDF** (los tres; se
   construyen en ese orden porque van de exacto a interpretado).
2. Convertirlos en **partidas** (capítulo, código, unidad, descripción, cantidad, precio)
   donde **cada partida sabe de qué documento y de qué sitio sale** (registro BC3, hoja y
   fila de Excel, página de PDF).
3. Sacar **un Excel con todo** para que el usuario haga los pedidos en su ERP (los pedidos
   no los genera TRAZA).
4. Preparar **ampliaciones y modificaciones** cuando algo no cuadra: mediciones que no
   cuadran, fallos de diseño o propuestas económicamente mejores. Salida en **Excel y BC3**
   (para Presto/Arquímedes).

## Lectores

| Formato | Cómo se lee | Fiabilidad |
|---|---|---|
| BC3 (FIEBDC-3) | Según la especificación oficial de la Asociación FIEBDC (ver abajo). Exacto. | Determinista |
| Excel | El usuario indica una vez qué columna es qué (código, unidad, descripción, cantidad, precio); se recuerda por proveedor/formato. | Determinista tras la asignación |
| PDF | Detección de tablas; si el usuario lo autoriza documento a documento, ayuda de la IA externa. Todo lo leído así entra como **propuesta** a confirmar. | Interpretado |

### BC3: fuente y reglas aplicadas

Fuente: *Formato FIEBDC-3/2024*, Asociación FIEBDC,
https://www.fiebdc.es/web2/datos/uploads/Formato-FIEBDC-3-2024.pdf (consultado 06-11-2026).
Reglas tomadas del documento (págs. 2-23; páginas comprobadas sobre el PDF):

- Registros que empiezan por `~`; campos separados por `|`, subcampos por `\`. Se ignora lo
  que haya entre el último `|` de un registro y el siguiente `~`, y los blancos, tabuladores
  y fines de línea delante de `~`, `|` y `\` (pág. 2).
- Números sin separador de miles y con **punto** decimal (pág. 3).
- `~V`: `JUEGO_CARACTERES` puede ser `850`, `437` (DOS) o `ANSI` (Windows); **vacío = 850**
  (pág. 4).
- `~C | CODIGO {\CODIGO} | UNIDAD | RESUMEN | {PRECIO\} | {FECHA\} | TIPO |`; raíz termina en
  `##`, capítulos en `#`; con y sin `#` es el mismo concepto (págs. 7-8). TIPO 0 sin
  clasificar, 1 mano de obra, 2 maquinaria y medios auxiliares, 3 materiales, 4 componentes
  adicionales de residuo, 5 clasificación de residuo (págs. 8-9).
- `~D | PADRE | <HIJO\FACTOR\RENDIMIENTO\> |`, con un tercer campo más completo que se lee
  con preferencia; FACTOR y RENDIMIENTO valen 1.0 por defecto; los hijos con `%` o `&` son
  porcentajes sobre las líneas anteriores, **no partidas** (págs. 9-10). Si un precio sale a
  la vez de `~C` y de `~D`, **prima `~D`** (págs. 8 y 10): TRAZA usa el de la descomposición
  cuando se puede calcular y avisa de la diferencia.
- Cantidad de una partida = **rendimiento** de su línea en el `~D` del capítulo (pág. 22:
  MEDICION_TOTAL debe coincidir con él). Un factor distinto de 1 en esa línea se avisa y no se
  aplica. Sin rendimiento explícito ni `~M`, la cantidad **no consta** (el 1.0 por defecto no
  es una medición).
- Los códigos sinónimos (`~C|A\B|`) se resuelven en `~D`, `~M` y `~T` (pág. 7).
- Una partida repetida en un capítulo se distingue por la POSICION de su `~M` (pág. 22).
- Un 0 explícito anula el campo (pág. 2): precio o cantidad 0 = no consta, con aviso.
- `~T | CODIGO | TEXTO |` (pág. 15).
- `~M | [PADRE\]HIJO | {POSICION\} | MEDICION_TOTAL | {líneas} | [ETIQUETA] |`;
  MEDICION_TOTAL debe coincidir con el rendimiento del `~D` correspondiente (págs. 21-23).

Discrepancia anotada: el texto del `~V` de la edición 2024 dice «la actual es FIEBDC-3/2016».
Se registra la versión que declare cada fichero.

Limitaciones iniciales del lector (se declaran al usuario, no se ocultan):
- No se evalúan las **expresiones** de las líneas de medición (anexo 2): se usa
  MEDICION_TOTAL y se avisa si no coincide con el rendimiento del `~D`.
- No se aplican los **porcentajes** `%`/`&`: ni sobre capítulos (sus líneas no se suman y la
  medición se marca con líneas omitidas, total «parcial») ni dentro de descomposiciones (se
  usa el precio del `~C`, con aviso).
- Con varios precios (rótulos del `~V`) se usa el primero, con aviso.
- No se aplican los decimales del `~K`.
- Registros no usados todavía (`~K` salvo lectura, `~P`, `~L`, `~G`, `~E`, `~O`, `~X`…) se
  conservan sin interpretar.

## Pasos del proyecto (interfaz)

Decisión del usuario: la herramienta se organiza en **pasos del proyecto**, adaptados al
**tipo de encargo** (diseño + presupuesto + instalación / presupuesto + instalación / solo
instalación), y **solo se ven los pasos que ya funcionan**.

Pasos previstos con este módulo: **Documentación** → **Mediciones** → **Modificados**, junto
al paso **Equipos** existente.

## Criterios de aceptación

1. Un BC3 real exportado de Presto o Arquímedes se lee con sus capítulos, partidas,
   cantidades y precios; el total coincide con el del programa de origen.
2. Cada partida muestra su origen (documento + registro/posición).
3. El Excel «con todo» incluye capítulo, código, unidad, descripción, cantidad, precio,
   importe y origen, y se abre en Excel sin avisos.
4. Un modificado exportado a BC3 se importa en Presto/Arquímedes.
5. Ningún dato leído de PDF entra sin confirmación.

Los puntos 1 y 4 necesitan ficheros y programas del usuario: se validan con él.
