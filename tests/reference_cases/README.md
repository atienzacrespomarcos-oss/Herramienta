# Casos de referencia publicados: validación de los motores de cálculo

Regla del proyecto (`docs/TESTING_STRATEGY.md` §0.2): cada motor se contrasta con un
**ejemplo resuelto publicado y accesible** (entradas exactas, tolerancia escrita y
justificada). Si no se encuentra ninguno accesible, el motor queda **Limitado** con la razón
escrita, y no se ajusta el motor para «cuadrar».

Los casos anteriores a esta carpeta están en `tests/unit/` (se citan con su ubicación); los
nuevos van aquí. Revisado el 11-11-2026.

## Contrastados con un ejemplo o tabla publicada

| Motor | Fuente publicada | Qué se compara | Tolerancia | Prueba |
|---|---|---|---|---|
| Psicrometría | ASHRAE Handbook – Fundamentals 2017, cap. 1, tabla 3 (agua saturada) | Presión de saturación con los valores publicados. Humedad, entalpía y temperatura húmeda a 40/20 °C: **comprobación de coherencia** con las mismas ecuaciones de ASHRAE calculadas a mano (no son valores impresos en la fuente) | 0,2 % en presión de saturación (gas ideal frente a las tablas con factor de mejora) | `tests/unit/test_psicrometria.py` |
| Conductos | Manual Climaver (Isover), pág. 51, ejemplo resuelto; tablas de accesorios, pág. 53 | Diámetro equivalente y pérdida por rozamiento de un 600 × 600 a 1,70 m³/s; coeficientes de codos de la tabla | 1 mm en diámetro equivalente; ±5 % en rozamiento (lectura del gráfico de ASHRAE en la fuente); coeficientes de tabla exactos | `tests/unit/test_conductos.py` |
| Hidráulica | Guía técnica IDAE nº 18, apartado B (ejemplos resueltos) | Velocidad y pérdida por metro de un fancoil de 5 kW (22×1 y 25×1,5); vaso de expansión de 260 l a 50 °C; presiones del caso A | 0,005 m/s y 0,5 mm c.a./m (redondeo de la guía); 2 % en el vaso, holgura que cubre el redondeo del volumen útil que hace la guía | `tests/unit/test_hidraulica.py` |
| Subcuadros | Guía técnica de aplicación del REBT: GUÍA-BT Anexo 2 y GUÍA-BT-19 (tablas A y E) | Intensidad de una línea de 145 kW a 400 V y cos φ 0,90 (232,5 A, publicado); intensidades admisibles y factores de agrupamiento de tabla. La caída de tensión se comprueba contra las **expresiones** del Anexo 2 escritas en la prueba (no es un resultado publicado) | 0,05 A en la intensidad; valores de tabla exactos | `tests/unit/test_subcuadro.py` |
| Permeabilidad n50 | Guía de aplicación del DB HE 2019, Ejemplos prácticos I, págs. 98-100 (codigotecnico.org) | n50 = 6,6206 h⁻¹ de la «vivienda unifamiliar mínima», opción 3, con ventanas y puertas por separado | 0,00005 h⁻¹ (media unidad de la última cifra publicada) | `tests/reference_cases/test_cte_n50.py` |
| Catálogo de usos | Tabla de ASHRAE de caudales y ocupación, reproducida en la ayuda de Revit (Autodesk; fuente secundaria) | **Cotejo manual puntual**: 39 de 39 valores iguales (07-11-2026). La prueba no repite la comparación: vigila claves, fuentes y coherencia | — | `tests/unit/test_usos.py` |

## Limitados: sin ejemplo resuelto publicado accesible

| Motor | Por qué | Qué se ha hecho |
|---|---|---|
| Geometría solar (`engines/solar.py`) | El ejemplo del NREL (Reda y Andreas, *Solar Position Algorithm*, NREL/TP-560-34302) no es accesible desde el entorno de trabajo (11-11-2026: el servidor no responde al proxy de salida); los ejemplos de Duffie y Beckman están en un libro no público. | Fórmulas de Duffie y Beckman (declinación de Cooper) con casos de resultado conocido calculados a mano (`tests/unit/test_cargas.py`). Pendiente: el ejemplo del NREL en cuanto sea accesible. |
| Radiación de cielo despejado | Modelo de ASHRAE (Fundamentals 1972–2001), de acceso restringido. | Tabla A, B, C contrastada con la serie de EnergyPlus (DOE/NREL): menos del 0,2 % (07-11-2026), contraste puntual sin prueba automática. |
| Temperatura sol-aire y cargas de verano por componentes | ASHRAE Fundamentals, cap. 18, de acceso restringido; no se ha encontrado un ejemplo español público completo. | Componentes contrastados por separado (psicrometría, n50); casos a mano en `tests/unit/test_cargas.py`. |
| Infiltración (UNE-EN 12831, anexo D) | Norma UNE de pago: su ejemplo no es público. | Coeficientes e y ε de la norma, casos a mano. |
| Condiciones exteriores (guía del IDAE) | La guía prohíbe reproducir sus datos y el repositorio es público. | Se prueba el criterio con datos inventados (`tests/unit/test_clima.py`). **Lectura de la guía real comprobada a mano el 13-11-2026** (PDF del IDAE descargado, no guardado en el repositorio): 104 estaciones leídas; Madrid (Barajas) 582 m, −3,8 °C (99,6 %), 36,4 °C (0,4 %), y el diseño de ejemplo completo calculado con ella. |
