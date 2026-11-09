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

## Propuesta de núcleo (a confirmar con los documentos)

| Parte | Sale de | Da |
|---|---|---|
| Venta | Presupuesto contratado (BC3/Excel/PDF) + modificados aprobados | Venta por partida |
| Coste objetivo | Excel de Presto agrupado por el usuario | Coste por partida, margen previsto |
| Certificaciones | Ejecutado cada mes, a origen por partida | Importe del mes y a origen, % ejecutado |
| Coste real | Por ver en los documentos del usuario | Desviación frente al objetivo |
| Previsión a fin de obra | Lo anterior | Venta, coste y margen finales |
| Futuribles | Ofertas y modificados pendientes de aprobar | Escenario sin ellos y con los marcados |

## Pendiente

- Ver los documentos de «DOCS OBRA» (presupuesto contratado, Excel de Presto agrupado,
  una certificación y lo que se use para el coste real) y decidir la lectura de cada uno.
- Construir por bloques: crear obra y núcleo → certificaciones → costes y previsión →
  futuribles.
