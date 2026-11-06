# Metodología de ingeniería

Cómo se escribe, documenta y valida un motor de cálculo o una comprobación normativa.

## 1. Jerarquía de fuentes

| Nivel | Tipo | Ejemplo | Uso |
|---|---|---|---|
| 1 | Texto oficial | BOE (RD, ITC, DB del CTE) | Requisitos obligatorios. |
| 2 | Guía oficial no vinculante | Guías técnicas del Ministerio / IDAE | Interpretación y datos de apoyo. |
| 3 | Fuente secundaria que reproduce una norma | Catálogo de fabricante con tablas UNE, publicación técnica | Solo marcada `fuente_secundaria`, con contraste. |
| 4 | Bibliografía técnica | Manuales con ejemplos resueltos | Métodos y casos de referencia. |
| 5 | Criterio de fabricante | Manual técnico de un equipo concreto | Solo para ese equipo y versión del manual. |
| 6 | Hipótesis de diseño | Velocidad objetivo elegida por el ingeniero | Declarada como hipótesis, nunca como norma. |

Un dato de nivel 3 nunca se presenta como texto oficial. Si dos fuentes de nivel 3 discrepan,
el programa muestra ambas y pide decisión.

## 2. Ficha de método (obligatoria por motor)

`docs/modules/<motor>.md`, escrita para un ingeniero:

- Objeto y ámbito (y qué queda fuera).
- Entradas con unidades y de dónde salen.
- Hipótesis.
- Método y ecuaciones, con referencia.
- Datos tabulados usados, con fuente y nivel.
- Aproximaciones declaradas y su efecto esperado.
- Comprobaciones que emite y su criterio.
- Casos de referencia y tolerancias.
- Limitaciones conocidas.

## 3. Registro de cálculo

Cada ejecución guarda: motor, versión, fecha, hash de entradas, entradas con unidad y
procedencia, hipótesis, método, referencias, resultados con unidad, comprobaciones,
advertencias y aproximaciones. Si cambian las entradas, el registro pasa a **obsoleto**.

## 4. Entradas normativas

Formato YAML en `data/normativa/` (ver `docs/normativa/INVENTARIO.md`). Campos
obligatorios: `id`, `norma`, `version`, `tipo` (obligatorio / recomendacion / hipotesis /
criterio_fabricante), `ambito`, `contenido`, `fuente` (documento, localizador, URL, nivel),
`verificado_por`, `fecha_verificacion`. Con `verificado_por: pendiente` el resultado
máximo es NO EVALUABLE.

## 5. Tolerancias

Cada caso de referencia declara su tolerancia y su motivo (redondeo de la fuente, lectura
de gráfico, diferencia de método). Sin tolerancia escrita, el caso no cuenta.
