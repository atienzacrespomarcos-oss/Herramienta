# Hoja de ruta y riesgos

> Origen: especificación de Etapa 0 (`docs/ETAPA0_ESPECIFICACION.md`, 05-11-2026).
> Marcas de rigor: **[V]** verificado con fuente · **[V2]** solo fuentes secundarias · **[C]** conocimiento sin verificar aún · **[P]** propuesta · **[?]** dato pendiente.

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
