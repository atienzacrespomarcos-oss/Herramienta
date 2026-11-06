# ADR-0005 · Procedencia por valor
Estado: Propuesto · 05-11-2026
**Contexto:** «no inventar» exige saber de dónde sale cada cifra.
**Decisión:** tabla `propiedad` (elemento, clave, valor, unidad, origen, referencia, registro
de cálculo, confirmado), validada contra esquemas Pydantic versionados por tipo de elemento.
**Descartado:** JSON opaco por elemento (pierde la procedencia por campo).
**Riesgo:** deriva hacia EAV inmanejable; se revisa con el primer caso real (Etapa 3).
