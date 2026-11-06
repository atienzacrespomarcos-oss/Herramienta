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
| Ampliaciones y modificaciones (Excel y BC3) | Implementado (paso «Modificados»). Pendiente de que Presto/Arquímedes importe el BC3 en el entorno de quien lo reciba. |

## Lectura con IA de PDF y Excel

Cuando eliges un PDF o un Excel, TRAZA te pide permiso para enviarlo a Claude. Después:

- Cada línea entra **directa («Comprobada»)** solo si supera todas las comprobaciones:
  - la descripción está en la página (PDF) o fila (Excel) citada;
  - cantidad, precio, importe, unidad y código están **en el mismo renglón** que la
    descripción (en PDF, ese renglón y los tres siguientes; en Excel, la misma fila), y cada
    número aparece **completo** (un «2» no vale por estar dentro de «12» o «2.400»);
  - el número es el que pone el documento (TRAZA lo vuelve a leer con sus reglas);
  - con cantidad y precio, el documento tiene que dar el importe y cantidad × precio =
    importe (un céntimo de tolerancia por redondeo). Sin importe, «a revisar»: una
    cantidad y un precio intercambiados no se podrían detectar. Una línea con solo cantidad
    (una medición) sí puede entrar directa.
- Si no, entra **«⚠ A revisar»** en naranja, con el motivo (pasa el ratón por la columna
  Estado o mira la lista de avisos). Tras comprobarla en el documento, «Confirmar partida
  revisada» la marca como «Confirmada por ti» (se puede deshacer).
- Si la suma de los importes de las líneas no da el total que declara el documento (un
  céntimo de tolerancia), se avisa y el pie de la medición muestra el total del documento y
  la diferencia: puede faltar o sobrar alguna línea.
- Las **páginas escaneadas** (todo el PDF o algunas) se envían como imagen; sus líneas
  quedan «a revisar» (no hay texto con que comparar).
- El total en pantalla indica cuántas partidas «a revisar» incluye; en el Excel esas filas
  van resaltadas.
- La lectura se hace en segundo plano con una ventana de progreso (puede tardar minutos).
- Un documento ya leído no se vuelve a enviar a la IA.
- **Limitación:** se compara con el texto **extraído** del PDF, no con lo visible. Un PDF
  con texto oculto (en blanco, fuera de la página) podría colar una cifra.
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
| Excel | IA (Claude Code, con permiso por envío) + comprobaciones deterministas contra las celdas (ADR-0013). | Entra directo solo lo que se comprueba; el resto «a revisar» |
| PDF | IA (Claude Code, con permiso por envío) + comprobaciones deterministas contra el texto de cada renglón (ADR-0013). Páginas escaneadas: «a revisar». | Ídem |

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
    - El BC3 generado se **vuelve a leer con el lector de TRAZA** antes de darlo por bueno.
      Se comprueba:
      - que el código, la cantidad y el precio de cada partida son los del modificado;
      - que el lector no da ningún aviso nuevo, como una `~M` que no cuadre con su `~D`;
      - que los precios de los capítulos son los calculados.

      Con 6 decimales. Un 0 se relee como «anulado», como dice la pág. 2.
    - **No se modifica a ciegas** (revisión del 06-11-2026). Se rechaza, diciendo por qué,
      cuando la medición:
      - tiene líneas de expresión (tipo 3, pág. 22), que TRAZA no evalúa;
      - tiene líneas que no suman su total, con una tolerancia de una centésima, porque el
        programa de origen recalcula el total con las líneas;
      - tiene registros `~N`, que añaden líneas a la medición (pág. 23);
      - es de una partida repetida en el capítulo cuya `~M` no se puede identificar por
        POSICION (pág. 22);
      - no coincide en el original con el rendimiento del `~D`, porque no se sabe cuál de los
        dos es el bueno;
      - tiene líneas pero el total vacío.

      La línea que se añade es lo que falta para que las líneas sumen **exactamente** la
      cantidad nueva.
    - Una anulación se escribe con cantidad 0, que en BC3 es «campo anulado» (pág. 2), y
      **siempre se avisa**. Cómo lo interpreta otro programa no está comprobado.
    - Si un capítulo aplica porcentajes («%»/«&»), su precio se corrige solo con la
      diferencia de importe y se avisa.
    - Base leída de PDF o Excel: los códigos que faltan, se repiten, superan los 20
      caracteres o llevan caracteres reservados (`| \ ~ # % &`) se escriben con otro código, y
      se avisa de cada uno. Los capítulos no chocan con ningún código de partida.
- Validación pendiente: importar el BC3 en Presto o Arquímedes. El usuario no tiene esos
  programas; lo confirmará quien reciba el fichero.

### Cómo se usa (paso 3 «Modificados»)

1. «Nuevo modificado»: eliges la medición o presupuesto de base (el contratado) y un título.
   Se numeran solos (nº 1, nº 2…) por cada base. Un número **no se reutiliza nunca**, aunque
   se borre ese modificado, para que un «nº 2» ya entregado no pase a ser otro distinto.
2. «Cambiar cantidad de una partida»: buscas la partida (escribe parte del código o de la
   descripción), pones la **cantidad nueva total**, el motivo y la justificación. Con 0 se
   anula. Solo se ofrecen partidas con cantidad y lectura fiable (no «a revisar») que aún no
   están en el modificado. Cada partida se muestra con su capítulo y su nº de línea, para
   distinguir una misma partida repetida en dos capítulos. Admite como máximo 6 decimales,
   los que lleva el BC3.
3. «Añadir partida de una oferta»: buscas la línea entre las ofertas leídas (solo las fiables
   y con precio, no las ya añadidas ni las de la propia base), pones la cantidad, el motivo y
   la justificación. El precio y su origen (documento y línea) vienen de la oferta.
4. La tabla muestra, por cambio, contrato, nuevo, diferencia y diferencia de importe. Abajo
   salen los totales de contrato, modificado y diferencia. Son «parcial» si falta algún
   importe o si la base tiene líneas que el lector omitió. Además se avisa de las partidas
   de la base que siguen «a revisar».
5. «Exportar modificado a Excel»: hoja de cambios y hoja del presupuesto completo
   actualizado. Cada total va en su columna de importe. La hoja de cambios suma sus líneas y
   da el presupuesto completo, con los mismos avisos que la pantalla.
6. «Exportar presupuesto actualizado a BC3»: el original con las cantidades nuevas, una línea
   de medición con la diferencia y el motivo, los precios de capítulos corregidos y un
   capítulo `MODn` con las partidas nuevas. Todo lo demás del original queda igual. Antes de
   guardarlo se vuelve a leer y se compara; si no coincide, no se guarda.

Protecciones: no se puede quitar una medición que usa un modificado; una partida anulada
(0) se relee como «no consta» (pág. 2 de la norma); todo se puede deshacer.

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
5. Ningún dato leído por la IA entra directo sin superar las comprobaciones deterministas
   (ADR-0013); lo que no las supera queda «a revisar» con su motivo.

Los puntos 1 y 4 necesitan ficheros y programas del usuario: se validan con él.
