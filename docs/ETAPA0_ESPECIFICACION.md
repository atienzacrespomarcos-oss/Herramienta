# ETAPA 0 — Propuesta de especificación y arquitectura

**Proyecto:** entorno personal de ingeniería de instalaciones industriales (nombre provisional: `PROYECTO-X`; lo eliges tú)
**Estado:** BORRADOR PARA REVISIÓN. Nada de lo aquí escrito es definitivo hasta tu aprobación.
**Fecha:** 05-11-2026
**Alcance de este documento:** las 10 tareas de la «Instrucción inicial». No contiene código.

Convenciones de rigor usadas en todo el documento:

| Marca | Significado |
|---|---|
| **[V]** | Verificado en esta sesión contra una fuente citada (sección 13). |
| **[V2]** | Verificado solo con fuentes secundarias (colegios, asociaciones, fabricantes). Confirmar en BOE / documentación oficial antes de codificarlo. |
| **[C]** | Conocimiento técnico consolidado, no verificado en esta sesión. Se verificará antes de convertirlo en código o dato normativo. |
| **[P]** | Propuesta / decisión de diseño mía, pendiente de tu aprobación. |
| **[?]** | Dato que no tengo y necesito de ti. |

---

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
| Validación | **Programas de terceros** («el que más acceso tengas y más te fíes») | Ver §0.2: yo no puedo ejecutar programas de terceros desde esta sesión. |
| Entregables | **«Los que yo diga»** | Generador documental por plantillas (DOCX/XLSX/DXF/LISP); el contenido de cada entregable lo defines tú cuando toque, no se presupone. |
| Uso | **Solo tú, Windows** | Uso estrictamente personal, sin distribución: **PyMuPDF (AGPL) es aceptable** (ADR-0012 cerrado). No hace falta instalador. |
| Tu papel | **Usar y validar** | Documentación orientada a ingeniero: cada motor tendrá una ficha de método en lenguaje técnico (no de código) para que puedas auditarlo. |
| Orden | **Decido yo con criterio** | §9.1. |
| Repositorio | **Creas tú un repo nuevo** | Pendiente de que me pases `propietario/nombre`. |
| Nombre | **Propongo yo** | §0.3. |

## 0.2 Validación con programas de terceros — límite real

Desde esta sesión **no puedo ejecutar CYPE ni ningún otro programa de escritorio**. La comparación tiene que hacerse así:

1. Yo preparo para cada motor una **batería de casos de contraste** (datos de entrada completos, sencillos de introducir).
2. Tú los introduces en el programa de terceros que tengas y me pasas sus resultados (captura o listado).
3. Esos resultados quedan como caso de referencia en `tests/`, citando programa, versión y fecha; el motor debe reproducirlos dentro de una tolerancia escrita, y cada diferencia se explica (método distinto, coeficiente distinto…) o se corrige.

Recomendación: **CYPE** como referencia principal por estar implantado en España y aplicar normativa española, *si tienes licencia*. Necesito que me confirmes qué programa tienes realmente instalado: no puedo elegir uno al que no tengas acceso. Complemento sin coste: ejemplos resueltos de bibliografía técnica pública con página citada.

## 0.3 Propuesta de nombre

No he comprobado registros de marca (irrelevante para uso personal).

| Nombre | Motivo |
|---|---|
| **TRAZA** | Trazado de redes + trazabilidad de cada dato: las dos ideas centrales del programa. *Mi recomendación.* |
| PLENUM | Término propio de climatización; corto. |
| CAUCE | Por donde circula el fluido; suena a red. |
| NODO | El modelo es un grafo de nodos y conexiones. |

---

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

## 3. Investigación tecnológica

Criterios de evaluación: adecuación, mantenimiento activo, licencia, rendimiento, integración con Python/Qt, riesgo. Las versiones exactas se fijarán al crear el entorno (Etapa 1), comprobando ruedas (*wheels*) disponibles para Windows.

### 3.1 Tabla de evaluación

| Área | Candidata | Licencia | Veredicto [P] | Notas |
|---|---|---|---|---|
| Lenguaje | Python 3.12/3.13 | PSF | **Adoptar** | Ecosistema científico y CAD (ezdxf, NumPy, SciPy, CoolProp). La versión concreta la decide la disponibilidad de ruedas de PySide6, CoolProp e IfcOpenShell. |
| Interfaz | **PySide6 (Qt Widgets)** | LGPLv3 / GPLv3 / comercial [V] | **Adoptar** | Binding oficial de Qt. Widgets (no QML): docks, árboles, tablas densas, `QUndoStack`. Alternativas descartadas: PyQt6 (GPL), web/Electron (doble pila, peor integración con el cálculo en Python). |
| Persistencia | **SQLite** | Dominio público [C] | **Adoptar** | Un fichero por proyecto, transaccional, sin servidor. **Precaución**: no abrir el proyecto directamente desde carpetas sincronizadas (OneDrive/Dropbox) o de red — riesgo de corrupción documentado por SQLite [C]; se trabaja en local y la copia de seguridad va a la carpeta sincronizada. |
| Acceso a datos / migraciones | SQLAlchemy 2 + Alembic | MIT [C] | **Adoptar (ADR)** | Alembic tiene «modo batch» para las limitaciones de `ALTER TABLE` de SQLite [C]. Alternativa más simple: `sqlite3` + migraciones propias con `PRAGMA user_version`. |
| Validación de datos | Pydantic 2 | MIT [C] | **Adoptar** | Esquemas de propiedades por tipo de elemento, con versión. |
| Unidades | **pint** | BSD [C] | **Adoptar en fronteras** | SI internamente (float), `pint` en entradas/salidas de motores y en la interfaz; tests de análisis dimensional. |
| Numérico | NumPy, SciPy | BSD [C] | **Adoptar** | Resolución de redes (sistemas no lineales), interpolación de curvas de ventiladores/bombas. |
| Hidráulica / mecánica de fluidos | **fluids** (C. Bell) | MIT [C, verificar] | **Evaluar en Etapa 3** | Incluye correlaciones de fricción y coeficientes de accesorios **con cita a la fuente original** en su documentación; encaja con la trazabilidad. Cada función usada se contrasta con la fuente primaria antes de adoptarla. |
| Propiedades de fluidos | **CoolProp** | MIT [V] | **Adoptar (Etapa 5)** | Refrigerantes, agua, aire húmedo (`HumidAirProp`). |
| Grafos | NetworkX | BSD [C] | **Adoptar** | Redes, caminos críticos, búsqueda de rutas (A*). |
| Geometría 2D | Shapely (GEOS) | BSD [C] | **Adoptar** | Polígonos de espacios, intersecciones, offsets. |
| Geometría 3D / B-Rep | Open CASCADE (OCCT) | LGPL-2.1 + excepción [V] | **Aplazar** | Pesado y complejo. Para interferencias de conductos/tuberías/bandejas bastan cajas orientadas y cilindros. Se reevalúa en Etapa 7 (estructura) o si IFC lo exige. |
| DXF | **ezdxf** | MIT [V] | **Adoptar** | Lectura/escritura DXF, XDATA/diccionarios de extensión para incrustar ids, bloques, cotas, tablas. No convierte a DWG [V]. |
| DWG | ODA File Converter | Uso no comercial salvo miembros ODA [V] | **Descartar** | Ver C-05. |
| IFC | IfcOpenShell | LGPL-3.0 (partes GPL-3.0 a revisar) [V] | **Aplazar (Etapa 9)** | Útil para recibir modelos BIM de arquitectura/estructura. |
| PDF (texto, vectores) | PyMuPDF | AGPL-3.0 o comercial [V] | **Candidata principal** | La mejor extracción de trazados vectoriales de PDF (`get_drawings`) [C]. La AGPL impone obligaciones al *distribuir* o *ofrecer por red*; para uso estrictamente personal y local no hay conflicto práctico, pero si se reparte el programa (A-06) sí. No es asesoramiento jurídico. |
| PDF (alternativa permisiva) | pypdfium2 / pdfplumber | Apache-2.0·BSD-3 / MIT [C] | **Alternativa** | Si A-06 = «se distribuirá». |
| OCR | Tesseract | Apache-2.0 [C] | **Etapa 8** | Para escaneados; calidad limitada en planos. |
| XLSX | openpyxl | MIT [C] | **Adoptar** | Lectura de mediciones y escritura de listados. |
| DOCX | python-docx (+ docxtpl) | MIT (docxtpl LGPL) [C] | **Adoptar** | Memorias sobre **tu** plantilla Word. |
| PDF de salida | Desde DOCX (Word/LibreOffice) o WeasyPrint | BSD [C] | **Decidir en Etapa 3** | Recomiendo DOCX como fuente única y PDF derivado. |
| Visor 2D | QGraphicsView (Qt) | (Qt) | **Adoptar** | Suficiente para planta de referencia con miles de entidades. |
| Visor 3D | pyqtgraph.opengl / VTK (PyVista + pyvistaqt) | MIT / BSD [C] | **Prototipo comparativo en Etapa 6** | Solo consulta e interferencias. |
| IA local | Ollama / llama.cpp | MIT [C] | **Opcional (Etapa 8)** | Depende del hardware (pregunta nº 2). |
| IA externa | API de proveedor (p. ej. Anthropic) | Servicio de pago por uso | **Opcional, nunca obligatoria** | Solo con autorización por envío (RF-303). |
| Pruebas | pytest, pytest-qt, hypothesis | MIT/MPL [C] | **Adoptar** | `hypothesis` para propiedades físicas (monotonía, conservación). |
| Calidad | ruff, mypy, import-linter | MIT/BSD [C] | **Adoptar** | `import-linter` impide que los motores importen Qt o la base de datos. |
| Entorno | uv | MIT/Apache [C] | **Adoptar** | Entorno reproducible con `uv.lock`. Para uso personal **no hace falta instalador**: se ejecuta desde el entorno. Empaquetado (PyInstaller/Nuitka) solo si se pide. |

### 3.2 Decisiones a documentar como ADR (Etapa 1)

| ADR | Decisión propuesta |
|---|---|
| 0001 | Python + PySide6 Widgets. |
| 0002 | Proyecto = carpeta (`proyecto.db` + `documentos/` por hash + `exportaciones/` + `copias/`). |
| 0003 | SQLite + SQLAlchemy/Alembic (o alternativa mínima). |
| 0004 | SI interno, pint en fronteras, unidades de visualización configurables. |
| 0005 | Procedencia por valor (tabla de propiedades con origen) frente a JSON opaco. |
| 0006 | Motores de cálculo puros, versionados, con registro de cálculo. |
| 0007 | Normativa como datos citados y versionados; nada de umbrales «en el código». |
| 0008 | DXF como intercambio principal; LISP complementario; DWG descartado. |
| 0009 | Ids del modelo incrustados en XDATA con APPID propio. |
| 0010 | Interfaz única de órdenes (*commands*) usada por UI, scripts y asistente IA. |
| 0011 | OCCT aplazado; interferencias con primitivas simples. |
| 0012 | Licencia de PDF (PyMuPDF vs. permisivas) según A-06. |

---

## 4. Programas de referencia

No tengo acceso a estos programas en esta sesión; lo que sigue se limita a su función **conocida y pública** [C]. Para un análisis funcional fino (flujos, pantallas, carencias) necesito tu experiencia de uso → pregunta nº 6.

| Programa | Ámbito | Qué tomar como referencia | Qué evitar / dónde aportar |
|---|---|---|---|
| CYPE (instalaciones, CYPELEC, estructuras, Open BIM) | Cálculo de instalaciones y estructuras con normativa española | Comprobaciones con referencia a artículo, listados justificativos, normativa española integrada. | Ciclo modelo ↔ AutoCAD a tu medida; procedencia de cada dato; interpretación de ofertas y mediciones. |
| Autodesk Revit (MEP) | BIM paramétrico | Sistemas conectados (conectores), propiedades por elemento, tablas de planificación. | Peso del modelado BIM completo; aquí no se modela arquitectura. |
| MagiCAD | MEP sobre AutoCAD/Revit | Etiquetado inteligente y dimensionado sobre el dibujo. | Dependencia de la plataforma CAD. |
| ETAP / Ecodial / DmELECT | Cálculo eléctrico | Unifilar como vista del modelo, cortocircuito, selectividad con curvas reales. | Selectividad sin curvas del fabricante = no evaluable (se declara). |
| Herramientas de selección VRF de fabricantes | Diseño VRF | Reglas de tubería frigorífica, carga adicional, tablas de corrección. | Atadas a un fabricante; aquí las reglas del fabricante son datos citados e intercambiables. |
| Hojas de cálculo propias | Todo | Rapidez, transparencia de la fórmula. | Sin trazabilidad ni coherencia entre hojas: es precisamente lo que el modelo central resuelve. |

---

## 5. Marco normativo inicial

Se cargará como **datos** en `normativa/`, con versión y fuente. Esta tabla es el inventario, **no** el contenido.

| Norma | Disciplina | Estado comprobado hoy | Uso previsto |
|---|---|---|---|
| RITE — RD 1027/2007; última modificación de fondo RD 178/2021 | Clima / ventilación (bienestar) | [V2] Vigente con modificaciones. Hay un proyecto de reforma en tramitación; **no he podido confirmar** si se ha publicado. Confirmar en BOE antes de Etapa 3. | Calidad de aire, eficiencia, aislamiento, ámbito. |
| REBT — RD 842/2002 e ITC-BT | Electricidad | [V2] Vigente con modificaciones; listado de normas de la ITC-BT-02 actualizado por resoluciones; proyecto de modificación de varias ITC notificado a la UE. | Previsión, secciones, ΔU, protecciones, tierras. |
| **RSCIEI — RD 164/2025** (deroga RD 2267/2004) | PCI en establecimientos industriales | [V2] Publicado BOE 10-04-2025; en vigor 10-05-2025. | Caracterización, sectorización, requisitos de instalaciones PCI en naves. |
| RIPCI — RD 513/2017 | PCI (instalaciones) | [C] Vigente; según COAM, modificado por el RD 164/2025 [V2]. | Diseño/instalación de equipos PCI. |
| CTE — RD 314/2006 (DB SI, HS, HE, SE…) | Varias | [C] Vigente con modificaciones; confirmar texto consolidado. | Fontanería (HS4), saneamiento (HS5), ventilación (HS3 en su ámbito), acciones (SE-AE). |
| Código Estructural — RD 470/2021 | Estructura | [V2] En vigor desde 10-11-2021; deroga EHE-08 y EAE; el DB SE-A sigue aplicándose en edificación según colegios profesionales. | Etapa 7 (si se decide). |
| Eurocódigos (UNE-EN 1990–1999 + Anejos Nacionales) | Estructura | [C] | Etapa 7. |
| NCSE-02 — RD 997/2002 | Sismo | [C] | Etapa 7. |
| RSIF — RD 552/2019 | Refrigeración | [C] | Carga de refrigerante, clasificación de sistemas, documentación. |
| REP — RD 809/2021 | Equipos a presión | [C] | Cuando corresponda. |
| RD 486/1997 (lugares de trabajo) | Ventilación de naves | [C] | Caudal mínimo por trabajador y condiciones ambientales en locales de trabajo. |
| Reglamento (UE) 2024/573 (gases fluorados) | Refrigeración | [C] | Restricciones de refrigerantes. |
| Normas UNE / UNE-EN citadas por los reglamentos | Todas | Derechos de autor (AENOR). | **Solo** con tu ejemplar (C-03). |
| Guía IDAE «Condiciones climáticas exteriores de proyecto» | Cargas térmicas | [C] | Datos climáticos de proyecto con fuente. |

Estructura de cada entrada normativa [P]:

```yaml
id: REBT.ITC-BT-19.2.2.2
norma: REBT (RD 842/2002)
version: "texto consolidado BOE, fecha ..."
tipo: obligatorio | recomendacion | hipotesis | criterio_fabricante
ambito: "instalaciones interiores o receptoras"
contenido: { ...parámetros... }
fuente: { documento: "BOE-A-2002-18099", localizador: "ITC-BT-19 apdo. 2.2.2", url: ... }
verificado_por: usuario | pendiente
fecha_verificacion: 2026-..-..
```

Una entrada con `verificado_por: pendiente` **no** puede emitir un «CUMPLE»; solo «no evaluable: criterio sin verificar».

---

## 6. Arquitectura técnica propuesta

### 6.1 Capas

```
┌──────────────────────────────────────────────────────────────────────┐
│ ui/  PySide6: ventana principal, árbol, propiedades, tablas, visores, │
│      alertas, documentos, historial, asistente                       │
└───────────────▲──────────────────────────────────────────────────────┘
                │ solo llama a órdenes y consultas
┌───────────────┴──────────────────────────────────────────────────────┐
│ app/  Órdenes (commands) con deshacer, consultas, flujo de estados,  │
│       orquestación de cálculos, detección de resultados obsoletos    │
└──▲──────────▲───────────▲────────────▲─────────────▲─────────────────┘
   │          │           │            │             │
┌──┴───┐ ┌────┴─────┐ ┌───┴──────┐ ┌───┴────────┐ ┌──┴───────────────┐
│core/ │ │engines/  │ │rules/    │ │coordination│ │io/ dxf, lisp,    │
│modelo│ │cálculo   │ │normativa │ │conflictos  │ │ xlsx, docx, pdf, │
│puro, │ │puro, sin │ │como datos│ │geometría   │ │ ingesta docs     │
│unid. │ │Qt ni BD  │ │+ checks  │ │            │ │                  │
└──▲───┘ └──────────┘ └──────────┘ └────────────┘ └──────────────────┘
   │
┌──┴───────────────────────────────────────────────────────────────────┐
│ persistence/  SQLite, repositorios, migraciones, copias, revisiones  │
└──────────────────────────────────────────────────────────────────────┘
ai/  Proveedor (local/externo) → produce PROPUESTAS de órdenes, nunca escribe en el modelo
```

Reglas de dependencia (comprobadas automáticamente con `import-linter`):

1. `engines/` y `rules/` no importan `ui/`, `persistence/` ni `ai/`. Reciben datos y devuelven resultados.
2. `ui/` no toca la base de datos: solo `app/`.
3. `ai/` solo puede emitir órdenes de `app/` marcadas como propuesta.
4. Toda modificación del modelo pasa por una orden ⇒ registro de cambios + deshacer garantizados por construcción.

### 6.2 Patrón de motor de cálculo

```python
# Esquema conceptual (no es código definitivo)
@engine(id="air.duct.friction", version="1.0.0")
def friccion_tramo(entrada: EntradaTramo) -> RegistroCalculo:
    ...
RegistroCalculo = {
  motor, version, fecha, hash_entradas,
  entradas (con unidades y procedencia), hipotesis[], metodo (+ecuaciones),
  referencias[] (id de entrada normativa o bibliográfica), resultados (con unidades),
  comprobaciones[] (regla, valor, límite, CUMPLE/NO CUMPLE/NO EVALUABLE),
  advertencias[], aproximaciones_declaradas[]
}
```

- Si cambian las entradas de un cálculo aprobado, su registro pasa a **obsoleto** (comparando `hash_entradas`) y aparece en alertas; no se recalcula ni se sobrescribe en silencio.
- Tres resultados posibles de una comprobación: **CUMPLE**, **NO CUMPLE**, **NO EVALUABLE** (falta dato, criterio no verificado o fuera de ámbito). Nunca un «CUMPLE» por defecto.

### 6.3 Asistente en lenguaje natural

`texto → (IA) plan de órdenes propuesto → comprobación de datos suficientes (determinista) → muestra el plan → el usuario acepta → ejecución por app/ → resultados revisables`. Si faltan datos, la respuesta es la lista de lo que falta, no una suposición.

---

## 7. Modelo central de datos (borrador)

### 7.1 Entidades

| Entidad | Contenido | Comentario |
|---|---|---|
| `proyecto` | Metadatos, ubicación, perfil normativo (qué versión de cada norma), unidades de visualización. | |
| `revision` | Instantáneas con nombre (Rev. 0, Rev. A…) y comparación. | RF-009 |
| `documento` | Fichero (sha256), tipo, origen, fecha de incorporación, clasificación (oferta, plano, ficha…). | Ficheros en `documentos/<sha256>`; nunca se modifican. |
| `referencia_origen` | documento + página/hoja/celda/región + texto extraído + método (manual/determinista/IA) + confianza. | Base de la trazabilidad (RF-021). |
| `nivel`, `espacio`, `obstaculo` | Geometría de edificio: polígono, cotas, alturas, uso, ocupación. | Planta libre (RF-040). |
| `sistema` | Disciplina, tipo, medio (aire, agua, R-32…), parámetros de diseño, clasificación bienestar/proceso. | |
| `elemento` | id (UUID), disciplina, tipo, código visible (UTA-01, T-12…), sistema, espacio, estado, bloqueado. | Núcleo. |
| `propiedad` | elemento, clave, valor, unidad, **origen** (usuario / documento / cálculo / catálogo / hipótesis / IA-propuesta), ref_origen, registro_calculo, confirmado. | Procedencia por valor (ADR-0005). Validada contra el esquema del tipo. |
| `geometria_elemento` | Polilínea 3D (lineales), punto+rotación+caja (equipos), sección. | |
| `puerto` | elemento, nombre, medio, sentido (entrada/salida/bidireccional), posición. | Inspirado en el concepto de puertos de distribución de IFC. |
| `conexion` | puerto_a ↔ puerto_b. | Hace la red computable (RF-004). |
| `catalogo_*` | Biblioteca de fabricantes **fuera** del proyecto, con documento origen. Al usarse, se copia una instantánea al proyecto. | Un cambio de catálogo no altera un proyecto en silencio. |
| `entrada_normativa` | Ver §5. Biblioteca fuera del proyecto; el proyecto fija versiones. | |
| `registro_calculo` | Ver §6.2. | RN-04 |
| `comprobacion` | regla, elementos, valor, límite, resultado, margen, registro_calculo. | |
| `conflicto` | elementos, localización, tipo, gravedad, criterio, soluciones, estado (abierto/aceptado/rechazado/resuelto). | RF-043 |
| `decision` | Aprobaciones/reaperturas con motivo y fecha. | RF-006/007 |
| `pendiente` | Información por confirmar, con origen y elemento afectado. | RF-012 |
| `cambio` | Registro solo-añadir: orden, entidad, campo, antes, después, autor (usuario/motor/IA/importación), fecha. | RF-008 |
| `exportacion` | Formato, fecha, versión, hash, mapa elemento ↔ handle DXF. | RF-203 |

### 7.2 Ejemplo: tramo de conducto

```
elemento  T-IMP-012  tipo=conducto_rectangular  sistema=IMP-UTA-01  estado=calculado
  puertos: entrada ← T-IMP-011.salida ; salida → D-IMP-012A.entrada , T-IMP-013.entrada
  propiedades:
    caudal          2 400 m³/h   origen=cálculo (suma aguas abajo)   reg=calc#88
    ancho×alto      500×300 mm   origen=propuesta motor               reg=calc#91
    velocidad       4,44 m/s     origen=cálculo                       reg=calc#91
    material        chapa galv.  origen=documento (pliego p.14)       ref=doc#3/p14
    rugosidad       [valor]      origen=hipótesis declarada + fuente   ref=bib#…
    Δp/L, Δp tramo  …            origen=cálculo                       reg=calc#92
  geometría: polilínea 3D, cota inferior +4,20 m
  comprobaciones: velocidad ≤ criterio de diseño (hipótesis del proyecto, no norma)
```
(Los valores del ejemplo ilustran el formato; no son un cálculo.)

### 7.3 Estados

```
borrador ──► propuesto ──► calculado ──► comprobado ──► APROBADO (bloqueado)
   ▲              │             │              │              │
   └──────────────┴── cambio de entrada ⇒ «obsoleto» ◄────────┘ reabrir = decisión explícita registrada
```

---

## 8. Estructura de carpetas y documentación

```
proyecto-x/
├── README.md  CLAUDE.md  CHANGELOG.md  pyproject.toml  uv.lock
├── docs/
│   ├── PRODUCT_REQUIREMENTS.md        (sección 1-2 de este documento)
│   ├── TECHNICAL_SPECIFICATION.md     (sección 3, 6)
│   ├── DATA_MODEL.md                  (sección 7)
│   ├── ENGINEERING_METHODOLOGY.md     (cómo se escribe un motor, referencias, tolerancias)
│   ├── TESTING_STRATEGY.md            (sección 11)
│   ├── DEVELOPMENT_ROADMAP.md         (sección 9)
│   ├── FEATURE_REGISTER.md            (Pendiente / En desarrollo / Implementada / Validada / Limitada)
│   ├── adr/0001-....md …
│   ├── modules/<modulo>.md            (especificación + criterios de aceptación por módulo)
│   └── normativa/INVENTARIO.md
├── src/proyectox/
│   ├── core/          modelo, ids, unidades, procedencia, estados
│   ├── persistence/   bd, repositorios, migraciones, copias, revisiones
│   ├── app/           órdenes, consultas, orquestación, obsolescencia
│   ├── engines/       air/ ventilation/ thermal/ refrigerant/ hydronic/ electrical/ plumbing/ drainage/ fire/ structure/
│   ├── rules/         carga y evaluación de la biblioteca normativa
│   ├── coordination/  geometría, interferencias, rutas
│   ├── io/            dxf/ lisp/ xlsx/ docx/ pdf/ ingest/
│   ├── ai/            interfaz de proveedor, adaptadores, traducción a órdenes
│   └── ui/            ventana, docks, modelos de tabla Qt, visores
├── data/              normativa/*.yaml  plantillas/ (capas, bloques, memorias)  catalogos/
└── tests/
    ├── unit/  reference_cases/ (con cita de la fuente)  property/ (hypothesis)
    ├── integration/  golden/ (DXF, LISP, XLSX de referencia)  ui/ (pytest-qt)
```

---

## 9. Hoja de ruta propuesta

No doy plazos en semanas: dependen de tu dedicación y de las respuestas de §12. Cada etapa termina con revisión de alcance y actualización del registro de funcionalidades.

| Etapa | Contenido | Criterio de aceptación (resumen) |
|---|---|---|
| **0** | Esta especificación, ADR, documentación base. | Aprobada por ti. |
| **1. Núcleo** | Proyecto-carpeta, BD y migraciones, modelo con procedencia, órdenes con deshacer, registro de cambios, estados, copias, gestión documental (incorporar y vincular), pendientes, ventana principal (árbol, propiedades, documentos, historial, alertas). | Crear proyecto, incorporar un PDF, crear un elemento, fijar una propiedad citando página del PDF, aprobar, intentar modificar ⇒ bloqueado; deshacer/rehacer; cerrar y reabrir sin pérdidas; copia restaurable. Tests verdes; ningún botón sin acción. |
| **2. Geometría DXF** | Importación DXF (capas, bloques, polilíneas, textos, cotas), escala/unidades, niveles, espacios y obstáculos **confirmados** por el usuario, visor 2D, lectura de mediciones XLSX. | Con un DXF real tuyo: espacios con superficie y altura correctos frente a medición manual, capas y bloques reconocidos con confianza y corrección. |
| **3. Primera vertical: redes de aire** | Caudales (ventilación/clima, con norma o hipótesis declarada), red de conductos con puertos, dimensionado por métodos declarados, pérdidas (fricción + accesorios con fuente), camino crítico, ventilador, comprobaciones, etiquetado, **DXF + LISP**, listados XLSX, memoria DOCX. Cargas térmicas a continuación con datos climáticos con fuente. | Un proyecto real tuyo reproducido y contrastado contra tu cálculo previo (CYPE/Excel) dentro de tolerancias fijadas por escrito; DXF abierto en tu AutoCAD con etiquetas correctas; reimportación detecta un cambio hecho a mano. |
| **4. Electricidad BT** | Receptores, cuadros, líneas, Ib, sección por Iz (tablas de tu UNE) y ΔU, protecciones, diferenciales, Icc, unifilar DXF, cuadros de características. | Contraste con un proyecto real tuyo; selectividad solo con curvas de fabricante cargadas, si no «no evaluable». |
| **5. Hidráulica, frigorífica, fontanería, saneamiento** | Hidrónica (bombas, equilibrado), redes frigoríficas VRF con reglas del fabricante, fontanería (CTE DB HS4), saneamiento (HS5). | Idem por disciplina. |
| **6. Coordinación** | Visor 3D de consulta, interferencias, espacios de mantenimiento, conflictos con estados, primeras propuestas de trazado con criterios explícitos. | Conflictos reales detectados en un proyecto con estructura y redes de dos disciplinas. |
| **7. Estructura** | Según decisión C-09. | A definir. |
| **8. IA y documentos** | Extracción asistida de ofertas/pliegos/fichas, PDF vectorial y escaneado, contraste entre documentos, órdenes en lenguaje natural. | Banco propio de documentos con resultados esperados (precisión medida; nunca un valor sin referencia de origen). |
| **9. Consolidación** | Expedientes, mediciones, IFC, plantillas avanzadas. | — |

### 9.1 Orden de los sistemas HVAC dentro de la Etapa 3 (y 5) [P]

Criterio: construir primero lo que reutilizan los demás, para no escribir dos veces el mismo motor.

| Paso | Bloque | Por qué en este orden | Reutiliza |
|---|---|---|---|
| 3.1 | **Espacios, cargas térmicas y caudales de ventilación** | Son la entrada de **todos** los sistemas: sin carga y caudal no se dimensiona nada. | Geometría de Etapa 2 |
| 3.2 | **Redes de aire (conductos)** | Común a rooftop, UTA, ventilación y VRF con unidades de conductos. Ejercita toda la arquitectura (grafo, cálculo, normativa, DXF/LISP, listados). | 3.1 |
| 3.3 | **Ventilación y extracción industrial** + selección de ventiladores | Casi todo es 3.2 más criterios de caudal y curvas de ventilador. | 3.1, 3.2 |
| 3.4 | **Rooftop** | Equipo + red de aire: lo nuevo es la selección del equipo con datos de catálogo. | 3.1–3.3 |
| 3.5 | **VRF / expansión directa** | Motor nuevo (red frigorífica) con reglas **del fabricante** + RSIF/UNE-EN 378 (carga por local). | 3.1, 3.2 (unidades de conductos) |
| 3.6 | **Hidrónico: enfriadora/bomba de calor, UTA, fancoils** | Motor nuevo (red hidráulica, bombas, equilibrado) que después reutilizan fontanería y PCI. | 3.1, 3.2, 3.3 |

Electricidad (Etapa 4) va después porque necesita las potencias eléctricas de los equipos ya seleccionados en 3.4–3.6.

**Justificación de los cambios respecto al brief:** (1) PDF de planos a Etapa 8 por incertidumbre técnica (RF-028/029) y porque el DXF cubre el mismo objetivo de forma determinista; (2) conductos antes que el resto de HVAC porque son comunes a climatización y ventilación y ejercitan toda la arquitectura (grafo, geometría, cálculo, normativa, DXF/LISP, listados, memoria); (3) la extracción documental **básica** (incorporar, vincular, leer XLSX) se adelanta a las Etapas 1–2 porque la trazabilidad la necesita desde el principio.

---

## 10. Riesgos técnicos principales

| # | Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|---|
| R1 | Alcance inabarcable ⇒ muchas pantallas a medias. | Alta | Muy alto | Vertical por disciplina; criterio de terminado; registro de «Limitadas». |
| R2 | Falta de tablas normativas (UNE) ⇒ cálculos incompletos o inventados. | Alta | Muy alto | Tablas solo desde tu ejemplar; «no evaluable» explícito; test que falla si una comprobación no cita fuente. |
| R3 | Interpretación de planos PDF poco fiable. | Alta | Alto | DXF primero; confianza + confirmación; Etapa 8. |
| R4 | Ausencia de casos de referencia contrastados para validar motores. | Media | Muy alto | Ejemplos resueltos de bibliografía citada + tus proyectos reales ya calculados (pregunta nº 6). |
| R5 | AutoCAD LT anterior a 2024 ⇒ sin AutoLISP. | ? | Alto | DXF como salida principal (C-04). |
| R6 | Corrupción de proyecto por carpetas sincronizadas. | Media | Alto | Trabajo en local + copias a la carpeta sincronizada. |
| R7 | Modelo de datos demasiado genérico (EAV inmanejable) o demasiado rígido. | Media | Alto | Tabla de propiedades **validada por esquemas versionados** por tipo; revisar en la Etapa 3 con el primer caso real. |
| R8 | Desincronización modelo ↔ DXF editado en AutoCAD. | Alta | Medio | Ids en XDATA; reimportación con diferencias como propuestas. |
| R9 | Reglas de fabricante (VRF) cambian entre modelos/versiones. | Alta | Medio | Reglas como datos citados por documento y versión del manual. |
| R10 | Hardware insuficiente para IA local útil. | ? | Medio | IA opcional; proveedor externo con autorización por envío. |
| R11 | Normativa cambia (reforma RITE en curso; modificaciones REBT). | Alta | Medio | Biblioteca versionada; el proyecto fija la versión con la que se calculó. |
| R12 | Rendimiento con DXF grandes. | Media | Medio | Importación por capas seleccionadas; índices espaciales; objetivos de §11. |
| R13 | Licencias (AGPL/LGPL) si el uso deja de ser personal. | Baja | Medio | ADR-0012; alternativas permisivas identificadas. |

---

## 11. Criterios objetivos de calidad

**Motores de cálculo**
- 100 % de las funciones de cálculo con al menos un **caso de referencia publicado y citado** (autor, obra, página) y tolerancia escrita.
- Tests de propiedades (`hypothesis`): monotonía física (más caudal ⇒ más pérdida en el mismo tramo), conservación de caudal en nudos, invariancia ante cambio de unidades.
- Cobertura de ramas ≥ 90 % en `engines/` y `rules/` (en el resto, objetivo orientativo, no fin en sí mismo).
- Ninguna magnitud cruza la frontera de un motor sin unidad declarada (test automático).
- Toda comprobación devuelve CUMPLE / NO CUMPLE / NO EVALUABLE y cita una entrada normativa o una hipótesis declarada (test automático que falla si no).

**Integridad y trazabilidad**
- 0 propiedades sin origen en el modelo (consulta de auditoría en el test de integración).
- 0 elementos aprobados modificados sin una `decision` de reapertura (test de integración).
- Cierre forzado del proceso a mitad de una orden ⇒ proyecto íntegro al reabrir (test).

**Interoperabilidad**
- DXF generado: legible por ezdxf con auditoría sin errores y comparado con un *golden*; abierto en tu AutoCAD según protocolo manual documentado.
- Ida y vuelta DXF: 100 % de entidades exportadas reconocidas por id al reimportar.

**Interfaz**
- Test que recorre todas las acciones de menú/barra y falla si alguna no tiene manejador.
- Toda cifra mostrada permite ver su origen en ≤ 1 clic.
- Objetivos de rendimiento iniciales [P] (a medir en tu equipo): abrir proyecto de 10 000 elementos < 3 s; recalcular una red de 500 tramos < 1 s; importar DXF de 50 000 entidades < 15 s.

**Proceso**
- Ninguna funcionalidad pasa a «Validada» sin cumplir los 8 puntos del criterio de finalización del brief.
- Revisión en contexto nuevo (subagente revisor) antes de cerrar cada módulo.

---

## 12. Preguntas para ti, por prioridad

1. **AutoCAD:** ¿AutoCAD completo o LT, y qué versión (año)? ¿Usas bloques/capas de una plantilla de empresa que puedas compartir (DWT/DWG exportado a DXF)?
2. **Equipo:** ¿Windows 10/11? ¿RAM y GPU (para valorar IA local)? ¿Sueles trabajar en carpetas sincronizadas (OneDrive/Dropbox/red)?
3. **Primera vertical:** ¿qué sistema predomina en tus naves (VRF, rooftop, enfriadora + UTA/fancoils, aerotermia, ventilación/extracción industrial)? ¿Trabajas también instalaciones de proceso (fuera del RITE)?
4. **Repositorio:** no puedo crear repositorios desde esta sesión. ¿Puedes crear uno vacío en GitHub (privado) y añadirlo a la sesión? ¿Nombre del programa? Hasta entonces este documento vive en una carpeta temporal de la sesión.
5. **Normas UNE:** ¿tienes acceso legítimo (suscripción AENOR, ejemplares) a las normas que citan REBT/RITE/CTE/RSCIEI? Sin ellas, varias comprobaciones serán «no evaluables».
6. **Validación:** ¿puedes aportar 2–3 proyectos reales ya resueltos (anonimizados) con su cálculo (CYPE, Excel, memoria) para usarlos como casos de contraste?
7. **IA:** ¿aceptas un proveedor externo con autorización por envío, o solo local?
8. **Fabricantes y catálogos:** ¿con qué marcas trabajas habitualmente y tienes sus manuales técnicos (tablas de selección, reglas de tubería)?
9. **Entregables:** ¿qué documentos finales generas (memoria de legalización por CCAA, memoria de cálculo, mediciones, planos)? ¿Tienes plantillas Word/Excel propias?
10. **Estructura:** ¿solo geometría para coordinación o cálculo completo de nave (C-09)?
11. **Uso:** ¿solo tú, en tu equipo (A-06)?
12. **Tu perfil de programación:** ¿vas a leer/modificar código o solo usar y validar? Cambia el nivel de documentación interna necesario.

---

## 13. Fuentes consultadas en esta sesión

- Autodesk — AutoLISP en AutoCAD LT 2024 (novedades y limitaciones): https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-LT-WhatsNew/files/GUID-5FB57480-C9BE-4E3D-BEDF-D86035928FFA.htm ; https://www.autodesk.com/blogs/autocad/autocad-lt-2024-autolisp/
- PyMuPDF — doble licencia AGPL/comercial: https://pypi.org/project/PyMuPDF/1.19.0/
- ezdxf — licencia MIT, sin conversión a DWG, recomienda ODA File Converter: https://ezdxf.readthedocs.io/en/stable/introduction.html
- Open Design Alliance — ODA File Converter, uso no comercial salvo miembros: https://www.opendesign.com/node/3218
- Qt for Python — licencias LGPLv3/GPLv3/comercial: https://doc.qt.io/qtforpython/
- OCCT — LGPL-2.1 con excepción: https://dev.opencascade.org/doc/overview/html/occt_public_license.html
- IfcOpenShell — LGPL-3.0: https://www.github.com/IfcOpenShell/IfcOpenShell
- CoolProp — MIT: https://salsa.debian.org/kkremitzki/coolprop/-/blob/master/LICENSE
- Código Estructural RD 470/2021: https://www.boe.es/eli/es/rd/2021/06/29/470 ; coexistencia con DB SE-A: https://arquitectes.cat/es/printpdf/36268 ; https://www.ietcc.csic.es/wp-content/uploads/2021/11/jornada_codigo_estructural_24nov.pdf
- RSCIEI RD 164/2025: https://www.coam.org/actualidad-noticias-nuevo-reglamento-seguridad-contra-incendios-establecimientos/ ; https://www.tecnifuego.org/comunicacion/rsciei-2025-vs-2004-que-cambia-y-como-afecta-los-establecimientos-industriales ; https://www.coial.org/publicado-el-nuevo-reglamento-de-seguridad-contra-incendios-en-los-establecimientos-industriales/
- RITE, estado y reforma en tramitación: https://www.activatie.org/noticia?2601-Consulta-p%C3%BAblica-sobre-el-el-proyecto-de-RD-que-modifica-el-RITE= ; https://www.caloryfrio.com/noticias/normativas/nuevo-rite.html
- REBT, texto consolidado y modificaciones: https://www.boe.es/buscar/pdf/2002/BOE-A-2002-18099-consolidado.pdf ; https://www.coeib.com/noticia/real-decreto-por-el-que-se-modifican-el-reglamento-electrotecnico-para-baja-tension-y-el-reglamento-sobre-condiciones-tecnicas-y-garantias-de-seguridad-en-instalaciones-electricas-de-alta-tension-e-itcs ; https://www.boe.es/diario_boe/txt.php?id=BOE-A-2020-612
