# Requisitos del producto

> Origen: especificación de Etapa 0 (`docs/ETAPA0_ESPECIFICACION.md`, 05-11-2026).
> Marcas de rigor: **[V]** verificado con fuente · **[V2]** solo fuentes secundarias · **[C]** conocimiento sin verificar aún · **[P]** propuesta · **[?]** dato pendiente.

## 0. Resumen ejecutivo

1. **Es viable**, pero solo si se acepta una consecuencia: el alcance descrito (8 disciplinas + estructura + interpretación de planos + IA + AutoCAD bidireccional) equivale a varios productos comerciales completos. Para un único desarrollador asistido, la única estrategia que no produce un «programa demostrativo» es **construir en vertical**: un núcleo sólido y **una** cadena completa (documento → modelo → cálculo → comprobación → DXF/LISP → listados/memoria) antes de abrir la siguiente disciplina.
2. **Arquitectura recomendada [P]:** Python + PySide6 (Qt Widgets) + **un proyecto = una carpeta con una base SQLite** + motores de cálculo puros e independientes de la interfaz + biblioteca normativa como **datos versionados con cita de origen** + DXF (ezdxf) como formato gráfico principal y AutoLISP como complemento.
3. **Modelo central [P]:** elementos con identidad, **puertos y conexiones** (grafo computable), **procedencia por cada valor** (quién/qué fijó ese dato y de qué documento sale), estados explícitos (propuesta → calculado → comprobado → aprobado) y registro de cambios solo-añadir.
4. **Tres hallazgos de la investigación que cambian el planteamiento:**
   - **RSCIEI nuevo**: el RD 2267/2004 está **derogado** por el **RD 164/2025** (BOE 10-04-2025, en vigor 10-05-2025) **[V2]**. Para naves industriales es la norma central de PCI y no figuraba en el documento.
   - **DWG**: el ODA File Converter, vía habitual para leer/escribir DWG desde Python, es de uso **no comercial** salvo miembros de ODA **[V]**. Si lo usas en proyectos por los que cobras, no es aceptable. Propongo **DXF como formato de intercambio** (AutoCAD lo abre y guarda de forma nativa) y dejar DWG fuera.
   - **AutoLISP en AutoCAD LT**: solo desde **LT 2024**, sin creación de sólidos/mallas/superficies 3D y sin IDE Visual LISP **[V]**. Tu producto y versión de AutoCAD condicionan el diseño del generador LISP → pregunta nº 1.
5. **Reordenación de etapas [P]:** la interpretación de **planos PDF** pasa de la Etapa 2 a la Etapa 8 (es la parte con más incertidumbre técnica y no debe bloquear nada); la red de **conductos de aire** (común a climatización y ventilación) es la primera disciplina vertical; la **estructura** queda al final y con alcance a decidir por ti.

---

## 0.1 Decisiones del usuario (ronda de preguntas, 05-11-2026)

| Tema | Respuesta | Consecuencia en el diseño |
|---|---|---|
| AutoCAD | **Completo, versión 2013–2017**, Windows | Salida **DXF R2013 (AC1027)**, que abren todas las versiones 2013–2017 [C]. AutoLISP y Visual LISP (`vl-load-com`, `vla-*`) disponibles en AutoCAD completo para Windows [C]. Se prohíbe en el generador LISP cualquier función posterior a 2013 (lista blanca de funciones con test). Protocolo de prueba manual en tu AutoCAD. |
| Sistemas HVAC | **Todos, con máximo detalle** | Se desarrollan todos. El orden lo fijo yo por dependencias técnicas (§9.1). |
| Estructura | **Solo geometría** | Pilares, vigas, correas y cerchas como obstáculos/soportes para coordinación. Sin cálculo estructural. C-09 cerrado; Código Estructural y Eurocódigos salen del inventario normativo. |
| IA | **Proveedor externo con permiso por envío** | Interfaz de proveedor; cada envío de un documento requiere tu confirmación explícita y queda registrado (qué, cuándo, a quién). Sin IA, todo lo determinista sigue funcionando. |
| Normas UNE | **No disponibles; usar fuentes públicas** | Regla de procedencia: los valores tomados de fuentes públicas que reproducen una UNE (guías técnicas del Ministerio, catálogos de fabricantes, publicaciones técnicas) se marcan **«fuente secundaria»**, con URL, fecha de consulta y edición de la norma que dicen reproducir; se contrastan con al menos dos fuentes independientes cuando existan y **las discrepancias se muestran, no se resuelven en silencio**. Una fuente secundaria nunca se presenta como texto oficial. |
| Validación | Primero «programas de terceros»; el 06-11-2026 aclara que **no tiene ninguno instalado** y elige **ejemplos publicados** | Reglas en `TESTING_STRATEGY.md` §0.2. |
| Nombre | **TRAZA** (06-11-2026) | Repositorio `atienzacrespomarcos-oss/Herramienta`. |
| Entregas | **Rama + PR en borrador por bloque** (06-11-2026) | El usuario revisa y fusiona. |
| Entregables | **«Los que yo diga»** | Generador documental por plantillas (DOCX/XLSX/DXF/LISP); el contenido de cada entregable lo defines tú cuando toque, no se presupone. |
| Uso | **Solo tú, Windows** | Uso estrictamente personal, sin distribución: **PyMuPDF (AGPL) es aceptable** (ADR-0012 cerrado). No hace falta instalador. |
| Tu papel | **Usar y validar** | Documentación orientada a ingeniero: cada motor tendrá una ficha de método en lenguaje técnico (no de código) para que puedas auditarlo. |
| Orden | **Decido yo con criterio** | §9.1. |
| Repositorio | **Creas tú un repo nuevo** | Pendiente de que me pases `propietario/nombre`. |
| Nombre | **Propongo yo** | §0.3. |

## 1. Requisitos identificados y clasificados

Codificación: `RF` funcional, `RNF` no funcional, `RN` normativo/metodológico, `RR` restricción. Prioridad MoSCoW: **M** imprescindible, **S** debería, **C** podría, **W** fuera de alcance por ahora. «Et.» = etapa propuesta (sección 9).

### 1.1 Núcleo y modelo de proyecto

| ID | Requisito | Prior. | Et. |
|---|---|---|---|
| RF-001 | Crear, abrir, guardar, cerrar proyectos locales. | M | 1 |
| RF-002 | Modelo central único compartido por todas las disciplinas (sin duplicar datos). | M | 1 |
| RF-003 | Cada elemento: id único, disciplina, tipo, localización/geometría, propiedades físicas y técnicas, material, fabricante/modelo, conexiones, relaciones, datos de cálculo, restricciones, estado de validación, documentos de referencia, historial. | M | 1 |
| RF-004 | Redes como grafo computable (equipo → tramo → derivación → terminal; cuadro → protección → línea → subcuadro → circuito → receptor). | M | 1 |
| RF-005 | Comprobación de coherencia del grafo (tramos sueltos, bucles indebidos, medios incompatibles, caudales no conservados). | M | 3 |
| RF-006 | Distinguir propuesta / cálculo ejecutado / resultado comprobado / decisión aprobada. | M | 1 |
| RF-007 | No modificar silenciosamente un diseño aprobado; reabrirlo es una acción explícita registrada. | M | 1 |
| RF-008 | Registro de cambios consultable y revisión de hipótesis usadas. | M | 1 |
| RF-009 | Versiones (revisiones) de proyecto y comparación entre ellas. | S | 1–2 |
| RF-010 | Copias de seguridad automáticas y restauración. | M | 1 |
| RF-011 | Deshacer/rehacer. | S | 1 |
| RF-012 | Lista de información pendiente de confirmar. | M | 1 |

### 1.2 Gestión e interpretación documental

| ID | Requisito | Prior. | Et. |
|---|---|---|---|
| RF-020 | Incorporar documentos (PDF, DOCX, XLSX, CSV, DXF, imágenes) al proyecto con huella (hash) y sin modificarlos. | M | 1 |
| RF-021 | Vincular cualquier dato del modelo con su documento de origen (página/celda/región). | M | 1 |
| RF-022 | Extracción de partidas de mediciones/presupuestos tabulares (XLSX/CSV) — determinista. | S | 2 |
| RF-023 | Extracción de texto/tablas de PDF con capa de texto — determinista. | S | 2 |
| RF-024 | Identificar equipos, fabricantes, modelos, potencias, caudales, dimensiones, cantidades (IA asistida). | S | 8 |
| RF-025 | Contraste entre documentos y detección de contradicciones/ausencias. | S | 8 |
| RF-026 | Crear estructura inicial del proyecto a partir de la documentación (como **propuesta** que el usuario confirma). | C | 8 |
| RF-027 | Interpretación de planos: espacios, cotas, escala, cerramientos, pilares, símbolos/bloques, capas. Desde **DXF** (determinista). | M | 2 |
| RF-028 | Ídem desde **PDF vectorial** (heurístico, con confianza). | S | 8 |
| RF-029 | Ídem desde **PDF escaneado / imagen** (visión artificial, confianza baja). | C | 8 |
| RF-030 | Toda identificación automática con nivel de confianza y confirmación/corrección por el usuario. | M | 2 |

### 1.3 Geometría, coordinación y restricciones

| ID | Requisito | Prior. | Et. |
|---|---|---|---|
| RF-040 | Geometría libre: plantas irregulares, varias alturas, cubiertas inclinadas, obstáculos existentes. | M | 2 |
| RF-041 | Visor 2D de referencia (planta) con capas del DXF y elementos del modelo. | M | 2 |
| RF-042 | Visor 3D de consulta/coordinación (no edición CAD). | S | 6 |
| RF-043 | Motor común de conflictos: elementos, localización, tipo, gravedad, criterio aplicable, soluciones posibles, estado. | M | 6 |
| RF-044 | Aceptar/rechazar/modificar recomendaciones. | M | 6 |
| RF-045 | Optimización de trazados con criterios explícitos y comparables (distancia, accesorios, pérdidas, pendientes, accesibilidad, obstáculos, alturas, coste, normativa). | C | 6–8 |

### 1.4 Disciplinas (cálculo y dimensionado)

| ID | Disciplina | Contenido mínimo para considerarla «completa» | Prior. | Et. |
|---|---|---|---|---|
| RF-100 | Conductos de aire (clima + ventilación) | Red, caudales, dimensionado (velocidad / pérdida de carga constante / recuperación estática), pérdidas por fricción y accesorios, camino crítico, equilibrado, ventilador, etiquetado, listados, DXF/LISP. | M | 3 |
| RF-101 | Caudales de ventilación | Calidad de aire (RITE IT 1.1.4.2 en su ámbito), lugares de trabajo (RD 486/1997), extracción localizada, renovaciones como **hipótesis declarada**. | M | 3 |
| RF-102 | Cargas térmicas | Método declarado, datos climáticos con fuente, cerramientos, ocupación, iluminación, equipos, ventilación, infiltraciones. | M | 3 |
| RF-103 | Selección de equipos | A partir de catálogos con documento de origen; sin catálogo → «no consta». | S | 3 |
| RF-104 | VRF/expansión directa: redes frigoríficas | Reglas del **fabricante** (longitudes, desniveles, diámetros, carga adicional) + RSIF/UNE-EN 378 (carga máxima por local). | S | 5 |
| RF-105 | Hidrónica | Red, diámetros, pérdidas, bombas, equilibrado, válvulas. | S | 5 |
| RF-110 | Electricidad BT | Previsión, cuadros, circuitos, Ib, sección por Iz y ΔU, protecciones, diferenciales, cortocircuito, selectividad (si hay datos), tierras, canalizaciones, unifilar, cuadros de características. | M | 4 |
| RF-120 | Fontanería | Caudales simultáneos, diámetros, presiones, pérdidas, grupos de presión, ACS y retorno. | S | 5 |
| RF-130 | Saneamiento | Colectores, bajantes, pendientes, arquetas. | C | 5 |
| RF-140 | PCI | Detección, BIE, rociadores, abastecimiento, sectorización (RSCIEI / RIPCI / normas UNE de diseño). | C | 5+ |
| RF-150 | Control y comunicaciones | Arquitectura, listado de puntos (E/S), protocolos (BACnet, Modbus, KNX), esquemas de control. | C | 5+ |
| RF-160 | Estructura de nave | Geometría, pórticos, correas, arriostramientos, acciones y combinaciones, comprobaciones, cimentación. | C | 7 |

### 1.5 Salidas y documentación

| ID | Requisito | Prior. | Et. |
|---|---|---|---|
| RF-200 | Exportación DXF con capas, bloques, textos, cotas y etiquetas configurables. | M | 3 |
| RF-201 | Generación de AutoLISP (capas, entidades, bloques, etiquetas, tablas). | M | 3 |
| RF-202 | Correspondencia entidad DXF ↔ elemento del modelo; reimportación con detección de cambios. | S | 3 (lectura) / 6 (reconciliación) |
| RF-203 | Registro de cada exportación: versión, fecha, contenido, hash. | M | 3 |
| RF-204 | Listados XLSX (tramos, líneas, protecciones, equipos, mediciones). | M | 3 |
| RF-205 | Memoria de cálculo DOCX/PDF con entradas, unidades, hipótesis, método, referencias, resultados, comprobaciones y advertencias. | M | 3 |
| RF-206 | IFC (lectura de modelos de terceros / exportación). | C | 9 |
| RF-207 | DWG. | **W** | — (ver §2, C-05) |

### 1.6 Asistente e IA

| ID | Requisito | Prior. | Et. |
|---|---|---|---|
| RF-300 | IA opcional y modular; todo lo esencial funciona sin conexión. | M | 1 (interfaz) |
| RF-301 | Órdenes en lenguaje natural traducidas a **las mismas órdenes** que usa la interfaz, con comprobación de datos suficientes antes de ejecutar. | S | 8 |
| RF-302 | La IA no fija valores: genera **propuestas** con procedencia «IA» que el usuario confirma. | M | 8 |
| RF-303 | Documentos privados en local salvo autorización expresa por envío. | M | 1 |

### 1.7 No funcionales

| ID | Requisito |
|---|---|
| RNF-01 | Aplicación de escritorio local, uso personal, sin servicios externos para lo esencial. |
| RNF-02 | Separación interfaz / aplicación / dominio / motores / persistencia / E-S. |
| RNF-03 | Mantenible por un desarrollador asistido: arquitectura simple, pocas dependencias, sin microservicios. |
| RNF-04 | Reproducibilidad: mismo input + misma versión de motor ⇒ mismo resultado, registrado. |
| RNF-05 | Interfaz profesional de alta densidad (árbol, propiedades, tablas, alertas), sin elementos decorativos ni botones muertos. |
| RNF-06 | Integridad de datos ante cierres inesperados; copias automáticas. |
| RNF-07 | Rendimiento: proyectos de miles a decenas de miles de elementos sin degradación perceptible (objetivos numéricos en §11). |
| RNF-08 | Trazabilidad: toda cifra mostrada sabe de dónde viene. |

### 1.8 Normativos y metodológicos

| ID | Requisito |
|---|---|
| RN-01 | No inventar artículos, tablas, límites ni exigencias. Sin fuente verificable ⇒ se declara la limitación. |
| RN-02 | Biblioteca normativa versionada (norma, versión, fecha, artículo/tabla, fuente). |
| RN-03 | Distinguir **requisito obligatorio** / **recomendación técnica** / **hipótesis de diseño** / **criterio del fabricante**. |
| RN-04 | Cada cálculo registra entradas, unidades, hipótesis, método, referencias, resultados, comprobaciones, advertencias, fecha y versión. |
| RN-05 | Cada motor con tests unitarios, casos de referencia publicados, límites, análisis dimensional y tolerancias. |
| RN-06 | Toda aproximación se identifica expresamente como tal. |

### 1.9 Restricciones

| ID | Restricción |
|---|---|
| RR-01 | No desarrollar un sustituto de AutoCAD ni un editor CAD. |
| RR-02 | Ninguna suscripción ni API de pago obligatoria. |
| RR-03 | No datos ficticios en la aplicación (los casos de prueba viven en `tests/`, nunca en la aplicación). |
| RR-04 | Decisiones irreversibles justificadas mediante ADR. |

---

## 2. Contradicciones, ambigüedades y dependencias

### 2.1 Contradicciones / tensiones

| ID | Tensión | Propuesta de resolución [P] |
|---|---|---|
| C-01 | **Alcance vs. «mantenible por un único desarrollador».** El alcance completo es mayor que el de CYPE MEP + parte de CYPE 3D + un extractor documental. | Vertical por disciplina, criterio de «terminado» estricto (§12 del brief) y registro de funcionalidades **Limitadas**. Revisión del alcance al cerrar cada etapa. |
| C-02 | **«Sin datos ficticios» vs. «casos de referencia y pruebas».** | Los casos de referencia son datos **publicados y citados** que viven solo en `tests/`. La aplicación nunca los carga. |
| C-03 | **«No inventar normativa» vs. normas UNE de pago.** Muchas tablas imprescindibles (p. ej. intensidades admisibles de cables, referenciadas por el REBT a norma UNE) están en normas UNE con derechos de autor, no en el BOE. | La biblioteca solo incluye lo que puedas aportar desde **tu** ejemplar legítimo o del BOE. Sin tabla cargada, el motor no calcula ese punto y lo dice. → Pregunta nº 5. |
| C-04 | **«Generar AutoLISP» vs. «resultados verificables».** El LISP no se puede ejecutar ni probar sin AutoCAD; el DXF sí (ezdxf lo lee y lo valida en los tests). | **DXF como salida principal y verificada**; LISP para lo que solo tiene sentido dentro de un dibujo abierto (insertar en tu DWG existente, usar tus bloques, etiquetar). Se prueba la *generación* del LISP (sintaxis, contenido) y se documenta un protocolo de prueba manual en AutoCAD. |
| C-05 | **«Estudiar DWG» vs. licencias.** ODA File Converter: uso no comercial salvo miembro de ODA [V]. LibreDWG es GPL y de cobertura parcial [C]. | DWG fuera del alcance (W). AutoCAD exporta/importa DXF de forma nativa; tú haces `DXFOUT`/`DXFIN` o abres el DXF. ADR específico. |
| C-06 | **«Integración bidireccional» vs. «AutoCAD es solo el motor gráfico».** Si se edita geometría en AutoCAD, el modelo queda desincronizado. | Regla: **el modelo manda**. La reimportación del DXF detecta diferencias (por id embebido en XDATA) y las presenta como **propuestas de cambio** a aceptar o rechazar. Nunca se sobrescribe en silencio. |
| C-07 | **«IA local y opcional» vs. «interpretación avanzada de planos y documentos».** Los modelos locales que caben en un portátil rinden bastante menos que los de API en visión y documentos largos [C]. | Interfaz de proveedor única; local por defecto; proveedor externo solo con autorización **por envío**. Expectativas de calidad medidas con un banco de pruebas propio (§11). |
| C-08 | **«Optimización de trazados» depende de geometría 3D fiable**, que depende de la interpretación de planos, que es la parte más incierta. | Primero trazado asistido sobre geometría **confirmada por el usuario** (DXF + alturas introducidas). Optimización automática después, con criterios explícitos. |
| C-09 | **Estructura con Eurocódigos** en un programa personal: es la disciplina con más responsabilidad y menos relación con el núcleo (instalaciones). | Decisión tuya (pregunta nº 10): (a) solo geometría estructural como obstáculo/soporte de coordinación, o (b) cálculo completo en Etapa 7. Recomiendo (a) hasta que el resto esté validado. |
| C-10 | **«Aplicación nativa»** vs. desarrollo en un contenedor Linux en la nube. | El código es multiplataforma (Qt); los tests corren en Linux sin pantalla; la validación de interfaz y AutoCAD se hace en tu Windows. → Pregunta nº 2. |

### 2.2 Ambigüedades a cerrar

| ID | Ambigüedad |
|---|---|
| A-01 | ¿Qué tipología HVAC es la más habitual en tus naves (VRF, rooftop, enfriadora + UTA/fancoils, aerotermia, ventilación industrial)? Define qué se valida primero. |
| A-02 | Ámbito RITE en naves: el RITE se aplica a instalaciones térmicas destinadas a bienestar e higiene; las de proceso industrial quedan fuera en lo que no sea bienestar [C]. El programa debe permitir marcar cada sistema como «bienestar» o «proceso» y aplicar el marco correspondiente. ¿Trabajas ambos? |
| A-03 | «Selección de equipos»: ¿con qué fabricantes trabajas y dispones de sus catálogos/manuales técnicos? Sin ellos, no hay selección, solo dimensionado. |
| A-04 | «Documentación final»: ¿memoria técnica para legalización (formato de cada Comunidad Autónoma), memoria de cálculo, pliego, mediciones? ¿Tienes plantillas? |
| A-05 | «Coste estimado» en optimización: ¿con qué base de precios (propia, BEDEC, banco de precios de una CCAA)? Sin base de precios, ese criterio no se usa. |
| A-06 | «Uso personal»: ¿el software se usará solo en tu equipo, o también en el de compañeros de tu empresa? Afecta a licencias (AGPL, LGPL) y a la distribución. |

### 2.3 Dependencias críticas (orden obligado)

```
Modelo de datos + persistencia + procedencia ──┬──> Motores de cálculo (registro de cálculo)
                                                ├──> Gestión documental (vínculo dato ↔ documento)
                                                └──> Registro de cambios / estados
Importación DXF + niveles/espacios ──────────────> Trazado de redes ──> Exportación DXF/LISP con etiquetas
Biblioteca normativa (datos citados) ────────────> Comprobaciones ──> Conflictos / alertas
Catálogos de fabricante con origen ──────────────> Selección de equipos
Geometría 3D confirmada ─────────────────────────> Interferencias ──> Optimización de trazados
Órdenes de aplicación (API interna estable) ─────> Asistente IA (usa las mismas órdenes)
```

---
