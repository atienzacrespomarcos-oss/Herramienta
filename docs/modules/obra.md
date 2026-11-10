# Obra: control de venta, costes, certificaciones y previsión

Estado: **diseño aprobado** (09-11-2026). **Bloques 1, 2a y 2b implementados** (crear obra,
venta, coste objetivo, coste real, previsión y certificaciones).

## Decisiones del usuario (09-11-2026)

| Pregunta | Decisión |
|---|---|
| Qué se quiere | «Implementar un control de costes y certificaciones de las obras. Y poder "crear obra" y que con los archivos que tu recibas puedas generar el Core de esa obra. Y a partir de ahí con el esqueleto seguir trabajando.» |
| Enfoque | «Debería ser parte de un todo integrado. Con un control de costes y venta. Con previsiones y parte de futuribles (si aprueban tal o no oferta).» |
| Cómo nace una obra | **Desde cero o desde una oferta**: se crea con sus documentos y, si viene de una Oferta, hereda sus partidas y documentos. |
| Coste objetivo | «Viene del Presto. Exporto a Excel mi coste objetivo, y luego agrupo por partidas (esto lo seguiré haciendo yo y adjuntándote el correspondiente documento agrupado como yo quiera).» TRAZA importa ese Excel tal cual lo agrupa el usuario; no reagrupa. |
| Alcance | **Solo por obra** (sin vista de cartera de todas las obras). |
| Futuribles | **Escenarios sí/no**: la previsión se ve sin futuribles y con los que el usuario marque. Sin porcentajes de probabilidad. |
| Documentos | En el uso diario se echan **en TRAZA, en el ordenador de trabajo**, «sin costes añadidos»: Excel y BC3 se leen en local sin IA; los PDF, con Claude Code y la suscripción del usuario (ADR-0013). Los documentos reales no van al repositorio (es público); las pruebas usan datos inventados. |
| Pedidos | Siguen fuera (09-11-2026). |

## Lo que muestran las plantillas del usuario (09-11-2026)

Son **plantillas inventadas** que el usuario compartió para enseñar su forma de trabajar,
no documentos de ninguna obra: «son plantillas inventadas y que no uses de ninguna forma
esto. Es parte complementaria que te enseñó mi forma de trabajar» (usuario, 09-11-2026).
No se usan como datos, no se copian al repositorio ni se usan en las pruebas; de ellas
solo se toma la **estructura** y la forma de trabajar:

- **Comparativo de costes** (Excel exportado de Presto y trabajado a mano, una hoja):
  - Columnas A–D: `Código`, `Nat` (Capítulo, Partida, Material, Mano de obra, Otros), `Ud`,
    `Resumen`. Debajo de cada partida, su descompuesto (recursos) y una fila de cierre con
    el código de la partida y su cantidad.
  - Grupos de tres columnas `CanObj · PrObj · ImpObj`: el primero, **OBJETIVO** (el
    coste objetivo de Presto); los demás, uno por **paquete de coste** (un proveedor o
    una subcontrata: «fabricante de equipos», «material frigorífico», «mano de obra
    frigorífica», «chapa», «fibra», «mano de obra de conductos», «difusión», «otros»,
    «elevación»…). Cada recurso del descompuesto se copia en la columna del paquete que
    lo va a pagar; las fórmulas `ROUND(Can×Pr; 2)` y las sumas de partida y capítulo
    reproducen las de Presto.
  - Al pie, a mano: lo **facturado por paquete** (a veces como suma de facturas,
    `=a+b+c*2`), la diferencia **objetivo − real** y la marca **CERRADO** cuando el
    paquete está liquidado.
  - Celdas de texto en lugar de precio («NO INCLUIDO …») para lo que no entra.
- **Plantilla de informe Word** (la de la empresa): logo en el encabezado y datos de la
  empresa en el pie; solo el estilo «Normal». Formato de sus informes: título centrado en
  negrita (14 pt), subtítulo (13 pt), títulos de apartado en MAYÚSCULAS y negrita (12 pt),
  texto justificado, tablas con cabecera gris (ECECEC) en negrita de 9,5 pt, y cierre con
  lugar, fecha, nombre y titulación.
- **Cajetín** (DWG de AutoCAD 2018): no se lee sin conversor (ADR-0008). Exportado a DXF
  podría insertarse en los planos que genera TRAZA.
- **Hoja de cargas** (método Carrier en kcal/h, tablas de ganancia solar a 40° N),
  **cálculo de conductos** (fricción constante 0,1 mm c.a./m, sección, velocidad y m² de
  conducto) y **comparativa de equipos frigoríficos** (por local: carga, ratio W/m²,
  modelo de proyecto frente al propuesto, unidad exterior y simultaneidad, PVP con
  descuento y entregas): referencias de su forma de trabajar. Cargas y conductos ya los
  cubre TRAZA; la comparativa de equipos es del fabricante (VRF fuera de alcance).

## Decisiones del usuario tras ver los documentos (09-11-2026)

| Pregunta | Decisión |
|---|---|
| Coste real | **Por paquete con facturas**: cada paquete del comparativo con sus facturas (proveedor, nº, fecha, importe) y su estado abierto/cerrado. |
| Certificaciones | «Certifico yo lo que creo, no TRAZA. Solo informo»: TRAZA **registra** lo que el usuario certifica; no calcula la certificación. |
| Venta | **BC3 o Excel de Presto, y también PDF** del cliente (con Claude Code y las comprobaciones de ADR-0013). |
| Justificación de cálculos | **Con el formato de sus informes** cuando la plantilla no trae estilos de título (cambio aparte de Obra). |
| Previsión | «Quiero una **foto de lo real** (coste − venta hasta que yo actualice) y una **previsión que yo haga** de costes y posible certificación para saber». TRAZA no estima: muestra lo real y la previsión que introduce el usuario. |
| Certificaciones (detalle) | «Lo que te daré será **mi Excel de certificación**. Saco el presupuesto de venta del Presto. Y por meses-certificaciones hago las certificaciones sobre el 100 % de cada capítulo, partida y subpartida». TRAZA lee ese Excel (por partida, a origen, por mes). Falta un ejemplo. |
| Diseño | Aprobado el resto («Sí, construye»). |
| Venta y coste (09-11-2026) | «Coste real y previsión. **Venta real y previsión** (no confundir con ampliaciones y demás)». Venta real = lo **certificado** a origen; venta prevista = la que el usuario prevé a fin de obra. Las ampliaciones, modificados y ofertas pendientes **no** entran en la previsión: son futuribles (bloque 3). |
| Plantillas por cliente | «Yo puedo tener una plantilla pero un cliente funcione con otra»: TRAZA interpreta cualquier Excel de certificación (bloque 2b), no una plantilla fija. |
| Previsión (nivel) | «Cuando te hablo de previsión, yo lo quiero como un **número total**. El tema de hacerlo por paquetes a mí me sirve para ver qué partidas se me están descuadrando, en caso de que se me descuadren o viceversa, pero yo al final lo que quiero son números totales». |

## Diseño propuesto (para revisar con el usuario antes de construir)

### Crear obra
- Tipo de encargo nuevo **Obra**. Se crea desde cero o **pasando una Oferta a Obra**
  (hereda sus documentos, partidas leídas y modificados).
- Pasos: Documentación · **Venta** · **Coste objetivo** · **Coste real** ·
  **Certificaciones** · **Previsión** (y Planos, Cargas… si se quieren usar).

### Venta
- El **presupuesto contratado**: una medición ya leída (BC3, Excel o PDF) marcada como
  contratada. Se suman los **modificados aprobados** (los de «Modificados»).
- Por partida: código, resumen, cantidad, precio e importe de venta.

### Coste objetivo (Excel de Presto del usuario)
- Se importa tal cual: partidas con su objetivo (cantidad, precio, importe) y su reparto
  en **paquetes** (cada grupo de columnas con nombre en la fila de títulos).
- Comprobación al leer: la suma de los paquetes de cada partida = su objetivo, con un
  céntimo de tolerancia; si no, se avisa (recurso sin repartir). Los textos en lugar de
  precio («NO INCLUIDO …») se guardan como nota, no como cero.
- Partidas de venta y de coste se enlazan por **código**; las que no casan se listan.

### Coste real (por paquete)
- Facturas por paquete: proveedor, nº, fecha, importe (sin IVA), documento opcional.
- Estado del paquete: **abierto** o **cerrado** (cerrar y reabrir quedan registrados).

### Certificaciones (las hace el usuario, en su Excel)
- Se lee el **Excel de certificación** del usuario: por capítulo, partida y subpartida, lo
  certificado a origen de cada mes sobre el 100 % de la venta. TRAZA no decide qué se
  certifica: lo registra y lo suma (cómo se interpreta cualquier Excel: «Bloque 2b»).
- Da el certificado del mes y a origen, por partida y total, y el % sobre la venta.

### Foto de lo real y previsión del usuario
- **Foto de lo real** (a la fecha de la última actualización): **venta real** (lo
  certificado a origen), **coste real** (lo facturado) y su diferencia (margen real hasta
  hoy); por paquete, objetivo frente a facturado.
- **Previsión**: la introduce el usuario como **dos totales**: coste previsto a fin de obra
  y **venta prevista** a fin de obra (con su fecha de actualización). TRAZA no la
  estima; la muestra junto a lo real y al objetivo, con el margen previsto que resulta.
- **Paquetes**: sirven para **ver dónde se descuadra** (objetivo frente a facturado de cada
  paquete, en más o en menos), no para la previsión.

### Futuribles (escenarios sí/no)
- Ofertas o modificados pendientes de aprobar, con su **venta** y su **coste estimado**.
- La previsión se muestra **sin** futuribles y **con** los marcados.

### Salidas
- En pantalla, lo que decide: venta, coste, margen y certificado (previsto y actual).
- Excel de control de la obra con todo el detalle (venta, objetivo por partida y paquete,
  facturas, certificaciones, previsión y futuribles).

## Cómo está hecho el bloque 1 (decisiones de método, 09-11-2026)

- **Encargo «Obra (venta, costes y certificaciones)»**. Una oferta pasa a obra cambiando
  el tipo de encargo (Ver → Tipo de encargo…): conserva sus documentos, mediciones y
  modificados. Pasos de Obra: los de cálculo, «Mediciones y ofertas», **Venta**,
  **Coste objetivo**, «Modificados» y «Equipos». El menú **Obra** solo se ve en obras.
- **Venta**: «Obra → Presupuesto contratado…» elige una medición ya leída (BC3, Excel o
  PDF, en «Mediciones y ofertas»). Se guarda en `meta` («venta_medicion»); esa medición
  no se puede quitar mientras sea la contratada. En pantalla: venta total y por capítulo
  de primer nivel. Cada línea se redondea al céntimo (como Presto). Se avisa de lo que
  puede dejar la venta corta o sin comprobar: partidas sin cantidad o sin precio, partidas
  «a revisar», partidas sin código (no se enlazan), líneas del documento no convertidas y
  diferencia con el total que declara el documento. Sin ninguna partida con importe, la
  venta **no consta** (no «0 €»). «Obra → Quitar presupuesto contratado» lo deja sin
  elegir (para releer su documento); se puede deshacer.
- **Coste objetivo** (`io/coste_presto.py`): «Obra → Importar coste objetivo (Excel de
  Presto)…» con el Excel incorporado en Documentación.
  - Se busca la fila con «Código», «Nat», «Resumen»; cada grupo `CanObj · PrObj ·
    ImpObj` toma el nombre escrito encima de cualquiera de sus tres columnas. El primero es
    el OBJETIVO; los demás, los paquetes.
  - Cuentan las filas `Nat = Partida` (con sus importes por grupo) y las **líneas añadidas a
    mano**: sin naturaleza, con resumen (y código, si lo tienen) y el **precio escrito** (o,
    sin precio, el importe escrito). No lo son las filas de cierre (su resumen es el código
    de la partida o capítulo que cierran, aunque el Excel venga pegado como valores) ni las
    de TOTAL. **Cada línea contada como añadida a mano se declara** en los avisos.
  - **Contraste con el TOTAL del propio Excel** (la última fila cuyo resumen empieza por
    «TOTAL»): si la suma leída no coincide al céntimo, se avisa; si no hay TOTAL, se dice
    que no se ha podido contrastar.
  - Se avisa también: códigos de partida repetidos (se cuentan los dos), importes
    negativos, grupos sin nombre (se llaman «Paquete N»), errores de la hoja (#…). Un
    nombre de paquete repetido rechaza el Excel diciendo cuál. El nombre de un grupo es un
    texto: un número o una fórmula encima de una columna no pasa por nombre.
  - Se leen los resultados guardados por Excel; una fórmula sin resultado se avisa.
  - Un texto en lugar de precio («NO INCLUIDO …») se guarda como nota, con importe 0.
  - Comprobación: objetivo − suma de paquetes > 1 céntimo → aviso «sin repartir».
  - Probado con un comparativo inventado propio (en las pruebas) con la misma estructura;
    falta el comparativo de una obra real del usuario.
  - Uno por obra: importar otro lo sustituye (se puede deshacer). Esquema V11.
- **Revisión independiente (09-11-2026)**: la regla de la línea añadida a mano podía contar
  dos veces un cierre en valores o perder una línea con código; corregido como se describe
  arriba, con pruebas de cada caso. También: división por cero con objetivo 0, céntimo
  exacto que avisaba, importes en el formato del resto de la aplicación («1.234,50 €»).
- **Comparación** (`app/obra.py`): margen previsto = venta − objetivo, y su % sobre la
  venta. Partidas enlazadas por código (sin espacios a los lados ni mayúsculas); las que
  no casan se cuentan en pantalla.

## Cómo está hecho el bloque 2a (decisiones de método, 09-11-2026)

- **Coste real** (paso «Coste real»): facturas apuntadas a los paquetes del coste objetivo
  (proveedor, nº, fecha, importe sin IVA; un abono, en negativo). Un proveedor no repite
  número. Arriba, cada paquete con su objetivo, lo facturado, la diferencia (objetivo −
  facturado) y si está abierto o cerrado; abajo, las facturas del paquete elegido.
  - **Descuadres**: se listan los paquetes que ya se han pasado de su objetivo.
  - **Cerrar paquete**: queda liquidado; no admite facturas nuevas ni cambios en las suyas
    hasta reabrirlo (cerrar y reabrir quedan en el registro de cambios).
  - Si se reimporta el coste objetivo y un paquete cambia de nombre, sus facturas siguen
    en la lista con su paquete marcado «ya no está en el objetivo»: se pueden corregir
    (eligiendo un paquete del objetivo), quitar o reabrir su paquete. Si el objetivo de un
    paquete **cerrado** cambia al reimportar, se avisa.
  - Importes al céntimo; un importe que redondea a 0 se rechaza. El mismo proveedor y
    número no se repiten aunque cambien mayúsculas o espacios.
  - Sin facturas al empezar la obra, el paso no lleva marca (no es un pendiente).
- **Previsión** (paso «Previsión», «Obra → Actualizar mi previsión…»): dos totales que
  pone el usuario, **venta** y **coste** a fin de obra, con nota opcional y su fecha. Una
  tabla de tres columnas: **contrato y objetivo** (venta, objetivo, margen), **real a
  hoy** (venta real = certificado, coste real = facturado, margen real) y **tu
  previsión** (venta, coste, margen previsto, con su %). Las ampliaciones, modificados y
  ofertas pendientes no entran: son futuribles (bloque 3).
- La venta real (certificado a origen) llega con las certificaciones (bloque 2b); hasta
  entonces, no consta («—»). Esquema V12 (`factura`, `paquete_cerrado`, `prevision`).

## Bloque 2b: certificaciones (decisiones de método, 09-11-2026)

Usuario (09-11-2026): «No necesitas plantilla (quizá te pase alguna pero al final debes ser
capaz de interpretar un Excel)». Por eso:
1. Reconocer las columnas por sus títulos (código, resumen, importe a origen, del mes,
   anterior, % a origen, importe de presupuesto…), lo específico antes que lo general.
2. Si no se reconocen, Claude Code (suscripción del usuario, ADR-0013) **solo dice qué
   columna es qué** mirando las filas de títulos; las cifras las lee TRAZA de las celdas.
3. Las líneas se enlazan con las partidas de la venta por código (capítulos y subtotales
   no suman dos veces) y la suma se contrasta con la fila de TOTAL del Excel.
4. Antes de importar, se enseña lo entendido (qué columna es qué y el total a origen) para
   que el usuario lo confirme.

Cómo está hecho (`io/certificacion_excel.py`, `app/obra.cruzar_certificacion`):
- **Columnas por título** en las primeras 40 filas de cada hoja; se elige la fila con el
  mapa más completo. Títulos normalizados (sin acentos, mayúsculas ni puntos) y comparados
  por «contiene» en orden: % a origen, anterior, a origen, de esta certificación, de
  presupuesto, naturaleza, código, descripción. Un título con «cantidad», «medición»,
  «precio» o «unitario» nunca es un importe («Cantidad a origen» no es el importe).
- **Importe a origen** de una fila: su columna; si no, anterior + esta certificación; si
  no, % a origen × importe de presupuesto (el % en tanto por uno o por ciento según el
  mayor valor de la columna).
- **Sin títulos reconocibles**: se pasan a Claude Code las 25 primeras filas de cada hoja
  (títulos y muestra) y solo dice la hoja, la fila de títulos y la letra de cada columna.
  Se comprueba contra el fichero: la hoja existe y cada columna tiene título en esa fila;
  si no, se descarta (no se adivina). Sin código e importe a origen, se rechaza.
- **Cruce con la venta**: solo suman las filas cuyo código es una partida del presupuesto
  contratado; las de capítulo (código de capítulo de la venta o naturaleza «Capítulo»)
  no suman; las demás con importe se listan como «no son partidas de la venta». Se avisa
  si una partida supera su venta (más del 100 %), si un código se repite y si la suma no
  cuadra con la fila TOTAL del Excel. Si ningún código casa, se rechaza («¿es la
  certificación de esta obra?»).
- **Revisión independiente (09-11-2026)**, corregido:
  - un título con «%» («% anterior», «% actual», «Origen %») ni de cantidades o unidades
    («Uds. a origen») se toma nunca por un importe en euros; un % a origen tiene que decir
    que es un porcentaje; su escala (tanto por uno o por ciento) la da el formato de la
    celda y, sin formato, el mayor valor de las filas con código;
  - las líneas **sin código** con importe se listan como «no son partidas de la venta» con
    su importe (no se descartan en silencio); se avisa de las partidas de la venta sin
    código (no se pueden certificar desde el Excel);
  - con **varias hojas** se lee la que más partidas casa con la venta, y se dice;
  - la fila TOTAL puede estar en la columna de código; un «Total con IVA» o «Total
    capítulo» no es el total certificado;
  - el mapa de la IA se comprueba con las mismas reglas (título que vale para su dato,
    columnas distintas, números bajo una columna de importe);
  - si todas las partidas de la venta están a 0 € (fórmulas sin resultado guardado), se
    rechaza; un código repetido en la venta suma todas sus líneas;
  - en la lista de certificaciones se anota la que sigue a números saltados (incluye lo de
    las que faltan) y la que baja respecto a la anterior.
- Cada certificación guarda su número, fecha, el importe a origen por partida, el total y
  el mapa con que se leyó. Lo de cada certificación = a origen − la anterior. La **venta
  real** es el total a origen de la última. Esquema V13.

## Bloque 3: futuribles y Excel de control (decisiones de método, 09-11-2026)

- **Futurible** = una oferta o un modificado pendiente de aprobar, con título, **venta**,
  **coste estimado** y una nota. La venta, o la escribe el usuario (una oferta que no está
  en TRAZA), o es la de un **modificado de TRAZA sobre el presupuesto contratado**: la
  diferencia de importe de sus cambios, línea a línea al céntimo (como la venta),
  **calculada siempre al día** (si el modificado cambia, el futurible le sigue; no se
  copia una cifra). El coste lo estima el usuario: TRAZA no lo inventa.
- Venta y coste pueden ser negativos (un modificado o una oferta pueden quitar alcance).
- Un modificado solo puede estar en un futurible; no se borra un modificado del que sale la
  venta de un futurible. Su venta **no consta** (no se suma, ni como 0) y se dice cuando
  el modificado aún no tiene cambios, tiene cambios sin cantidad o sin precio, o ya no es
  del presupuesto contratado (se eligió otro). Un marcado sin venta deja el escenario sin
  cifra («—»), con el aviso en Previsión (si hay previsión) y en el resumen del Excel
  (revisión 09-11-2026).
- **Escenario sí/no**: cada futurible se marca o no (doble clic o «Sí / no en el
  escenario»). «Con futuribles marcados» = **tu previsión + la venta y el coste estimado de
  los marcados**. Tu previsión nunca cambia por ellos («no confundir con ampliaciones»).
  Sin previsión, no hay escenario que sumar. Aprobado o descartado: se quita de la lista
  (y, si se aprueba, el usuario actualiza su previsión).
- En pantalla: paso **Futuribles** (lista con venta, coste, margen y sí/no) y una columna
  más en **Previsión**, «Con futuribles marcados».
- **Excel de control** («Obra → Exportar Excel de control…»): hojas Resumen (las cuatro
  miradas: contrato y objetivo, real a hoy, tu previsión, con futuribles), Venta y
  objetivo por partida, Paquetes, Facturas, Certificaciones, **Certificado por partida**
  (lo certificado a origen de cada partida en cada certificación y su %) y Futuribles.
  Las reglas de todos los Excel de TRAZA: números como números, lo que no consta vacío
  (nunca 0), textos ajenos nunca como fórmula, guardado atómico. Esquema V14.

## Crear obra desde documentos (decisiones del usuario, 10-11-2026)

| Tema | Decisión |
|---|---|
| Cómo nace | Echar **todos los documentos recibidos** (unas veces más, otras menos) y que TRAZA genere la obra. |
| Presupuesto | «Habrá **1 presupuesto** y mediciones, planos, etc.»: el presupuesto es la venta contratada, sin preguntar. |
| Facturas | «Las **exporto de mi ERP** y te las subo»: TRAZA interpreta ese listado (sin plantilla fija). |
| Formatos | «Deberás tener la estructura para que **lo que yo te pase, sea lo que sea, te valga**». |
| Datos reales | «No quiero darte nada hasta que no esté hecho»; «no voy a pasarte obra real hasta terminar la herramienta 100 %». Todo se prueba con documentos inventados de muchas formas. |

Bloques: (4a) cualquier hoja de cálculo (.xlsx, .xlsm, .xls, .csv) en todos los lectores;
(4b) facturas desde el listado del ERP; (4c) crear obra desde documentos (reconocer cada
uno, enseñar lo entendido, montar la obra; y echar documentos nuevos durante la obra).

## Bloque 4a: cualquier hoja de cálculo (decisiones de método, 10-11-2026)

- Todos los lectores (presupuesto en Excel con la IA, comparativo de Presto,
  certificaciones y, después, facturas) abren lo mismo: **.xlsx, .xlsm, .xls y .csv**
  (`io/hoja_calculo.py`). Se convierte al mismo libro, celda a celda en la misma posición:
  las referencias «Hoja!B12» que citan las comprobaciones siguen valiendo.
- **.xls** (Excel 97-2003, xlrd, licencia BSD): guarda el resultado de cada fórmula, no la
  fórmula; las fechas salen como fechas y se conserva el formato de número (para reconocer
  porcentajes).
- **Se mira el contenido, no la extensión**: muchos ERP guardan como «.xls» una tabla HTML,
  un XML de Excel 2003, texto con separadores o un .xlsx; todos se leen. Un binario que no
  es hoja (un PDF renombrado) se rechaza diciéndolo.
- **.csv y tablas de texto**: UTF-8 o Windows-1252 (lo habitual en un ERP español); el
  separador es el que da a casi todas las líneas el mismo número de campos (a igualdad,
  «;»). Regla de oro (revisión 10-11-2026): **solo se convierte lo inequívoco**; lo demás
  queda como texto y los lectores lo tratan como «no consta».
  - **Códigos, no números**: con un cero delante («01», «08001», «0001234») o con varios
    separadores que no son de miles («01.02.03»), se quedan como texto, y **toda su
    columna** también («1.001» junto a «01.002» es un código, no mil uno). Así el cruce por
    código con la venta no se rompe.
  - **Fechas solo con el año de 4 cifras** (dd/mm/aaaa, dd.mm.aaaa, dd-mm-aaaa,
    aaaa-mm-dd): «01.02.03» es un código, no una fecha.
  - Importes con «€», negativos entre paréntesis o con el signo detrás, miles con espacio
    («1 234,56»), porcentajes («21 %» → 0,21).
  - **Columnas de códigos**, de tres formas:
    1. Por su título en una fila de títulos (de las 15 primeras, las que tienen dos o más
       textos: delante suele haber cabecera del documento), palabra entera
       al principio: «Código», «Cód.», «Ref.», «Capítulo», «Partida», «Nº», «Número»,
       «Factura», «Pos.», «Orden», «Línea», «Artículo», «Ítem», «NIF», «CP»… («Cantidad
       partida», «Partida alzada», «Nº uds.», «Noviembre», «Capacidad» no).
    2. Porque al menos el 30 % de sus valores tienen forma de código.
    3. Porque dos textos distintos darían el mismo número con distintos decimales («1.1» y
       «1.10»: capítulos distintos, no la misma cantidad).
    Sus valores no votan la convención y una celda suelta («01» encima de los importes) no
    convierte en texto una columna de importes.
  - La **convención decimal se decide por fichero**, con lo que demuestran las columnas
    que no son de códigos:
    1. Un número con punto y coma a la vez («1.234,56») es prueba fuerte.
    2. Coma con 1-2 o 4+ cifras («12,5») demuestra la coma decimal. Punto igual («12.50»)
       demuestra el punto, pero **no basta para leer los ambiguos** («1.250»: mil
       doscientos cincuenta o uno con veinticinco), que quedan como texto: «1.10» puede ser
       un código de capítulo sin título (los códigos usan puntos, no comas).
    3. Sin prueba: con «;» o en una tabla HTML, coma decimal como Excel en España; con otro
       separador, punto, y los ambiguos quedan como texto. Con pruebas contradictorias,
       los ambiguos quedan siempre como texto.
  - Un número que **contradice** la convención («1234.56» donde la coma es el decimal) o
    con un grupo de miles mal formado («0,125» con coma de miles) **se queda como texto**:
    reinterpretarlo sería inventar una cifra.
  - Fechas siempre día/mes/año (convención española).
- **Tablas HTML y XML de Excel 2003**: cada celda en su columna (`colspan`, `ss:Index`,
  `ss:MergeAcross`), también si una `<td>` no se cierra; una celda combinada en varias
  filas, una tabla dentro de otra o posiciones que se pisan descolocarían las celdas, y el
  fichero se rechaza diciéndolo. Cada hoja del XML (o cada tabla del HTML) es una hoja.
  Los comentarios de celda no son su valor. En el XML, un dato «Number» o «DateTime» se
  toma con su tipo (números con punto); uno «String» (hay ERP que escriben así los
  importes) se interpreta con las reglas de arriba.
- En el comparativo de costes, un .xls o un CSV no guardan fórmulas: no se distingue un
  precio escrito de uno calculado, y se avisa de que las líneas tomadas como añadidas a mano
  pueden ser subtotales (el contraste con el TOTAL lo confirma).
- Un texto ajeno que empieza por «=» se guarda como texto, nunca como fórmula.

## Bloque 4b: facturas desde el listado del ERP (decisiones de método, 10-11-2026)

- «Obra → Importar facturas del ERP…» (paso Coste real) lee el listado tal como lo exporta
  el ERP (cualquier hoja de cálculo, bloque 4a), sin plantilla.
- **Columnas** (proveedor, nº de factura, fecha, base imponible, total, cuota de IVA,
  retención, obra o centro de coste, concepto) por sus títulos. Cada título vale para un
  solo dato, con exclusiones («% IVA», «Tipo», «Cód. IVA» no son la cuota; «Total con IVA»
  no es la base; una fecha de vencimiento, de pago o contable no es la de la factura;
  «Tipo/Estado factura» no es el número). Entre varias columnas que valen para lo mismo,
  **gana el título más específico** («Fecha factura» antes que «Fecha»; «Base imponible»
  antes que «Base»); si dos columnas de importe empatan («Base 1», «Base 2»: varios tipos
  de IVA), no se elige ninguna y se dice que se exporte con el total por factura.
- Si no se reconocen, Claude Code dice qué columna es qué (solo letras). TRAZA lo comprueba
  con las mismas reglas y, además, **rechaza una columna cuyo título es, por sí solo, de
  otro dato** («Total con IVA» propuesta como base).
- El coste es la **base imponible** (sin IVA). Sin columna de base: **total − cuota de IVA
  ± retención**, con el signo del total (un abono resta). Y se comprueba que la cuota y la
  retención cuadran con un **tipo legal**: IVA 21, 10, 4 % (Ley 37/1992, arts. 90 y 91), 5 %
  (RDL 20/2022) y 0 % (exentas, e inversión del sujeto pasivo en obra, art. 84.Uno.2.f);
  retención de IRPF 15, 7, 19, 2 o 1 % (Ley 35/2006 y RD 439/2007, arts. 95 y 101), con 0,6
  puntos de margen por redondeo. Sin tipos con recargo de equivalencia: es régimen del
  comercio minorista (art. 154), no de una instaladora, y 26,2 y 11,4 coinciden con 21/79 y
  10/90, lo que dejaba pasar una base un 21 % corta (revisión 10-11-2026). Si no cuadran
  (la columna es el %, o la línea mezcla tipos o suplidos), la factura no se importa y se
  dice que se apunte a mano. Con base, cuota y total, si no cuadran entre sí, se avisa.
  «Total neto» es la base; «Neto a pagar» y la **retención de garantía** (se descuenta del
  pago, no es IRPF ni cambia el coste) no se usan.
- **Filas**: una de total («Total», «Suma»… como palabra entera y sin nº de factura) no
  cuenta; «Totalenergies» o «Sumasa» son proveedores. Una fila sin proveedor, número, fecha
  o importe, o con importe 0, no se importa y se lista con el motivo. Una factura en varias
  líneas (una por tipo de IVA) se suma; una línea repetida igual, no.
- **La misma factura** es la del mismo proveedor y número aunque cambien mayúsculas,
  acentos, espacios o puntuación («CHAPAS NORTE, S.A.» y «Chapas Norte SA»; «F-001» y
  «F001»), también al escribirlas a mano.
- **Solo las nuevas**: una ya apuntada no se repite; con otro importe o fecha, **no se
  cambia** (se avisa para corregirla a mano). El mismo proveedor y número con otra fecha
  dentro del listado se enseña como repetida y no se importa.
- **Obra**: si el listado tiene columna de obra, se confirma siempre: con una sola obra, se
  pregunta si es esta; con varias (o facturas sin obra), se elige.
- **Paquete**: TRAZA lo **propone**, el usuario decide en una tabla antes de importar: (1) si
  el listado trae en «obra» o «concepto» exactamente el nombre de un paquete; (2) si no, el
  paquete donde están las demás facturas de ese proveedor (si todas en uno y sigue en el
  objetivo). Un paquete cerrado no se propone ni admite facturas.
- Todas en una sola orden: deshacer las quita todas; con una mal, no entra ninguna.

## Pendiente

- Probar el bloque completo con una obra real del usuario (venta, comparativo,
  certificaciones de su plantilla y de un cliente, facturas) en su ordenador.
