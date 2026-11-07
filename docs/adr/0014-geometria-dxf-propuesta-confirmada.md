# ADR-0014 · Geometría desde DXF: inventario, unidad confirmada y propuestas confirmadas
Estado: Aceptado · 06-11-2026

**Contexto:** los planos vienen del arquitecto o del cliente (decisión del usuario), con
capas y unidades ajenas. Un plano mal interpretado contamina todo lo que se calcule después:
cargas, caudales y redes.

**Decisión:**
1. **El lector solo hace inventario.** Lee capas, contornos cerrados, textos, bloques y
   longitudes del espacio modelo, y no decide qué es cada cosa. Lo decide el usuario,
   capa a capa, en cada proyecto.
2. **La unidad del dibujo la confirma el usuario.** `$INSUNITS` es solo una propuesta,
   porque Autodesk la define como unidad de los bloques de DesignCenter. Se muestra la
   medida total del dibujo con la unidad elegida para que un error salte a la vista.
3. **Espacios y obstáculos son propuestas** hasta que el usuario los confirma (RF-030).
   Confirmados, guardan su procedencia: documento DXF y handle de la entidad.
4. **Medidas exactas.** La superficie y el perímetro de los contornos con arcos se calculan
   con fórmula cerrada (bulge). La única aproximación, el aplanado a 1 mm para clasificar
   puntos, está declarada y no se usa para medir.
5. **Lo que no se lee se dice:** bloques por dentro, xref, espacio papel, tipos de entidad
   que no son trazos ni textos, SPLINE y ELLIPSE, polilíneas ajustadas y entidades
   fuera de planta. Los contornos que se cortan a sí mismos se proponen marcados.

**Alternativas descartadas:**
- Reconocer espacios por nombres de capa fijos. No sirve con planos ajenos.
- Detectar el recinto con un clic entre muros. Es frágil con planos sucios y lo descartó el
  usuario para este bloque.
- Aproximar arcos con la geometría de Shapely para medir. Introduce un error que no hace
  falta.

**Consecuencias:**
- La primera lectura de un plano exige que el usuario elija capas y confirme la unidad.
- Un plano dentro de un bloque o con xref hay que prepararlo en AutoCAD antes de leerlo,
  y TRAZA dice cómo.
