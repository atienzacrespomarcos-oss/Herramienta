# ADR-0009 · Identificadores del modelo en XDATA
Estado: Propuesto · 05-11-2026
**Decisión:** APPID `TRAZA`; cada entidad exportada lleva el UUID de su elemento en XDATA
(código 1000). La reimportación compara por id y presenta diferencias como propuestas.
**Comprobado:** id escrito y recuperado tras guardar y releer el DXF (05-11-2026).
**Pendiente:** comprobar en AutoCAD del usuario que XDATA sobrevive a copiar, desplazar,
estirar y guardar.
