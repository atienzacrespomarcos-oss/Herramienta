# Obra: control de venta, costes, certificaciones y previsión

Estado: **en diseño** (09-11-2026). Falta ver los documentos reales del usuario («DOCS
OBRA») para decidir cómo se lee cada uno; nada se construye antes.

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

## Lo que muestran los documentos del usuario (09-11-2026)

Vistos fuera del repositorio (no se copian aquí nombres de clientes, proveedores ni
importes). Lo que importa es su estructura:

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

## Propuesta de núcleo (a confirmar con los documentos)

| Parte | Sale de | Da |
|---|---|---|
| Venta | Presupuesto contratado (BC3/Excel/PDF) + modificados aprobados | Venta por partida |
| Coste objetivo | Excel de Presto agrupado por el usuario: objetivo por partida y su reparto en paquetes | Coste por partida y por paquete, margen previsto |
| Certificaciones | Ejecutado cada mes, a origen por partida | Importe del mes y a origen, % ejecutado |
| Coste real | Por **paquete de coste** (como en su comparativo): facturas y estado abierto/cerrado | Desviación por paquete y total |
| Previsión a fin de obra | Lo anterior | Venta, coste y margen finales |
| Futuribles | Ofertas y modificados pendientes de aprobar | Escenario sin ellos y con los marcados |

## Pendiente

- Ver los documentos de «DOCS OBRA» (presupuesto contratado, Excel de Presto agrupado,
  una certificación y lo que se use para el coste real) y decidir la lectura de cada uno.
- Construir por bloques: crear obra y núcleo → certificaciones → costes y previsión →
  futuribles.
