# Obra: control de venta, costes, certificaciones y previsión

Estado: **diseño aprobado** (09-11-2026). **Bloque 1 implementado** (crear obra, venta y
coste objetivo).

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
  certifica: lo registra y lo suma (lectura por diseñar con un ejemplo real).
- Da el certificado del mes y a origen, por partida y total, y el % sobre la venta.

### Foto de lo real y previsión del usuario
- **Foto de lo real** (a la fecha de la última actualización): venta certificada a origen,
  coste facturado, y su diferencia (margen real hasta hoy); por paquete, objetivo frente
  a facturado.
- **Previsión**: la introduce el usuario (coste y certificación previstos). TRAZA no la
  estima; la muestra junto a lo real y al objetivo (granularidad por concretar al
  construir el bloque 2).

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

## Pendiente

- Revisión del diseño por el usuario.
- Un ejemplo del Excel de certificación del usuario (para el bloque 2).
- Construir por bloques: ~~(1) crear obra, venta y coste objetivo~~ (hecho); (2) coste real,
  certificaciones, foto de lo real y previsión del usuario; (3) futuribles y Excel de
  control.
