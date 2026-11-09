# Obra: control de venta, costes, certificaciones y previsión

Estado: **en diseño** (09-11-2026). Documentos vistos; diseño propuesto pendiente de
la revisión del usuario.

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

## Decisiones del usuario tras ver los documentos (09-11-2026)

| Pregunta | Decisión |
|---|---|
| Coste real | **Por paquete con facturas**: cada paquete del comparativo con sus facturas (proveedor, nº, fecha, importe) y su estado abierto/cerrado. |
| Certificaciones | «Certifico yo lo que creo, no TRAZA. Solo informo»: TRAZA **registra** lo que el usuario certifica; no calcula la certificación. |
| Venta | **BC3 o Excel de Presto, y también PDF** del cliente (con Claude Code y las comprobaciones de ADR-0013). |
| Justificación de cálculos | **Con el formato de sus informes** cuando la plantilla no trae estilos de título (cambio aparte de Obra). |

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

### Certificaciones (las hace el usuario)
- Registro: nº, fecha, **importe certificado del mes** (sin IVA) y documento opcional.
  TRAZA suma el certificado **a origen** y lo compara con la venta (% certificado).

### Previsión a fin de obra
- **Venta prevista** = contratado + modificados aprobados.
- **Coste previsto** por paquete: cerrado → lo facturado; abierto → el mayor entre su
  objetivo y lo ya facturado (un paquete abierto no se da por más barato de lo que va
  costando). Total = suma de paquetes.
- **Margen previsto** (importe y % sobre venta), y desviación frente al objetivo.
- **Pendiente de certificar** = venta prevista − certificado a origen.

### Futuribles (escenarios sí/no)
- Ofertas o modificados pendientes de aprobar, con su **venta** y su **coste estimado**.
- La previsión se muestra **sin** futuribles y **con** los marcados.

### Salidas
- En pantalla, lo que decide: venta, coste, margen y certificado (previsto y actual).
- Excel de control de la obra con todo el detalle (venta, objetivo por partida y paquete,
  facturas, certificaciones, previsión y futuribles).

## Pendiente

- Revisión del diseño por el usuario.
- Construir por bloques: (1) crear obra, venta y coste objetivo; (2) coste real,
  certificaciones y previsión; (3) futuribles y Excel de control.
