# Programas de referencia

> Origen: especificación de Etapa 0 (`docs/ETAPA0_ESPECIFICACION.md`, 05-11-2026).
> Marcas de rigor: **[V]** verificado con fuente · **[V2]** solo fuentes secundarias · **[C]** conocimiento sin verificar aún · **[P]** propuesta · **[?]** dato pendiente.

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
