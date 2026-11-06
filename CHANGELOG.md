# Registro de cambios

## [Sin publicar]

### Etapa 0 — 05-11-2026
- Especificación y arquitectura iniciales.
- Decisiones del usuario: AutoCAD completo 2013–2017 (DXF R2013), todos los sistemas HVAC,
  estructura solo geometría, IA externa con permiso por envío, sin normas UNE (fuentes
  públicas marcadas como secundarias), uso personal en Windows.
- Prueba de viabilidad: ezdxf 1.4.5 escribe R2013 (AC1027) con XDATA y lo relee sin errores
  de auditoría; PySide6 6.12.0 arranca sin pantalla; pint 0.26.2 convierte unidades.
- ADR 0001–0012.

### 06-11-2026
- Nombre TRAZA confirmado; repositorio `Herramienta`.
- Validación con ejemplos publicados (el usuario no tiene programas de cálculo).
- Entregas por rama y PR en borrador.
