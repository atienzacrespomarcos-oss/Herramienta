# TRAZA

Entorno personal de ingeniería de instalaciones para naves industriales: de la
documentación inicial (ofertas, mediciones, planos DXF) al diseño, cálculo, comprobación
normativa, coordinación y documentación para AutoCAD.

**Estado:** Etapa 1 (núcleo + interfaz) en revisión.

## Usarlo en Windows

1. En GitHub: pestaña **Actions** → última ejecución verde de «Ejecutable Windows».
2. Descargar el artefacto **TRAZA-windows** y descomprimirlo.
3. Abrir `TRAZA.exe`. Si Windows SmartScreen avisa: «Más información» → «Ejecutar de todas
   formas» (el ejecutable no está firmado).

Para leer **PDF y Excel con IA** hace falta Claude Code instalado con tu suscripción: ver
«Instalar Claude Code en tu Windows» en `docs/modules/mediciones.md`. El BC3 no lo necesita.

Para desarrollo: `uv sync` y `uv run python -m traza`.

## Documentación

| Documento | Contenido |
|---|---|
| `docs/PRODUCT_REQUIREMENTS.md` | Requisitos, decisiones del usuario, contradicciones y dependencias |
| `docs/TECHNICAL_SPECIFICATION.md` | Tecnologías evaluadas y arquitectura |
| `docs/DATA_MODEL.md` | Modelo central de datos |
| `docs/ENGINEERING_METHODOLOGY.md` | Fuentes, fichas de método, registro de cálculo |
| `docs/TESTING_STRATEGY.md` | Validación y criterios objetivos de calidad |
| `docs/DEVELOPMENT_ROADMAP.md` | Etapas, orden de sistemas HVAC y riesgos |
| `docs/FEATURE_REGISTER.md` | Estado real de cada funcionalidad |
| `docs/normativa/INVENTARIO.md` | Normativa considerada y su estado |
| `docs/adr/` | Decisiones de arquitectura |
| `docs/ETAPA0_ESPECIFICACION.md` | Especificación original completa (registro histórico) |
