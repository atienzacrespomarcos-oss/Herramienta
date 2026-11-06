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
| Lector PDF y Excel con IA (Claude Code, tu suscripción) | Implementado con comprobaciones deterministas (ADR-0013). Pendiente de probar con Claude Code real en tu equipo y con documentos tuyos. |
| Ampliaciones y modificaciones (Excel y BC3) | Pendiente |

## Lectura con IA de PDF y Excel

Cuando eliges un PDF o un Excel, TRAZA te pide permiso para enviarlo a Claude. Después:

- Cada línea entra **directa («Comprobada»)** si supera todas las comprobaciones: el texto
  de cada número está en la página/celda citada; el número es el que pone (se vuelve a leer
  con reglas propias); cantidad × precio = importe al céntimo.
- Si no, entra **«⚠ A revisar»** en naranja, con el motivo (pasa el ratón por la columna
  Estado o mira la lista de avisos). Tras comprobarla en el documento, «Confirmar partida
  revisada» la marca como «Confirmada por ti» (se puede deshacer).
- Si la suma de las partidas no da el total que declara el documento, se avisa: puede faltar
  o sobrar alguna línea.
- Un **PDF escaneado** se lee igualmente, pero sus líneas quedan todas «a revisar» (no hay
  texto con que comparar).
- El Excel sale con las columnas «Estado de la lectura» y «Motivo».

### Instalar Claude Code en tu Windows (una vez)

Según la guía oficial (https://code.claude.com/docs/en/setup.md): Windows 10 1809 o posterior,
4 GB de RAM y plan Pro o superior. No hace falta ser administrador.

1. Abre **PowerShell** y ejecuta: `irm https://claude.ai/install.ps1 | iex`
2. Cierra y vuelve a abrir PowerShell, escribe `claude` e inicia sesión con tu cuenta de
   Claude (tu suscripción). Después puedes cerrarlo.
3. No definas la variable `ANTHROPIC_API_KEY`: si existiera, TRAZA la ignora a propósito para
   que se use tu suscripción.

TRAZA necesita la versión nativa (`claude.exe`); si solo encuentra la de npm (`claude.cmd`),
lo dice.

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

## Ampliaciones y modificaciones (decisiones del usuario, 06-11-2026)

- **Base:** un modificado parte de una medición o presupuesto **ya leído** en TRAZA (el
  contratado).
- **Cambios posibles:**
  - **Variación** de una partida de la base: nueva cantidad (aumento o disminución, incluida
    la anulación con cantidad 0). El precio es el de la base.
  - **Partida nueva**: se elige una línea de una **oferta leída** en el proyecto; su código,
    unidad, descripción y precio vienen de esa oferta y quedan **enlazados a su origen**. La
    cantidad la pone el usuario.
  - Una «propuesta económicamente mejor» se expresa como: disminución (o anulación) de la
    partida de la base + partida nueva de la oferta.
- **Motivo obligatorio** en cada cambio: error de medición, fallo de diseño, mejora económica
  u otro, siempre con texto.
- **Salidas:**
  - **Excel**: contrato, modificado y diferencia por partida, en cantidad e importe, con
    motivo y origen del precio; totales.
  - **BC3: presupuesto completo actualizado** (el original con las cantidades nuevas y las
    partidas nuevas añadidas en un capítulo propio del modificado).
    - Si la base es un BC3, se parte del **fichero original** para conservar todo lo que
      TRAZA no interpreta (descompuestos, textos, pliegos…).
    - Si la base vino de PDF o Excel, el BC3 se genera solo con lo leído (sin
      descompuestos) y se avisa.
    - El BC3 generado se **vuelve a leer con el lector de TRAZA** y sus cantidades y precios
      se comparan con los del modificado antes de darlo por bueno.
- Validación pendiente: importar el BC3 en Presto o Arquímedes. El usuario no tiene esos
  programas; lo confirmará quien reciba el fichero.

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
