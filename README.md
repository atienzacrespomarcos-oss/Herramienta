# TRAZA

Entorno personal de ingeniería de instalaciones para naves industriales: de la
documentación inicial (ofertas, mediciones, planos DXF) al diseño, cálculo, comprobación
normativa, coordinación y documentación para AutoCAD.

**Estado:** implementados diseño (planos, cargas, redes de aire, sistema hidráulico,
subcuadros, control), entregables, mediciones y modificados, obra y revisiones; pendientes
de validar con proyectos reales. Estado de cada parte en `docs/FEATURE_REGISTER.md`.

## Usarlo en Windows

1. Descarga la última versión (enlace fijo, se actualiza con cada cambio):
   https://github.com/atienzacrespomarcos-oss/Herramienta/releases/latest/download/TRAZA-windows.zip
2. Descomprímelo entero en una carpeta tuya y abre `TRAZA\TRAZA.exe`. Si Windows SmartScreen
   avisa: «Más información» → «Ejecutar de todas formas» (el ejecutable no está firmado).
3. Sigue **«Guía de prueba.docx»**, que va en el ZIP junto a la carpeta **Ejemplos de
   prueba** (ficheros inventados). Misma guía en `docs/GUIA_DE_PRUEBA.md`.

Para leer **PDF y Excel con IA** hace falta Claude Code instalado con tu suscripción (lo
explica la guía). El BC3, el DXF y los Excel con títulos reconocibles no lo necesitan.

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
| `docs/GUIA_DE_PRUEBA.md` | Guía de prueba del paquete para Windows |
| `docs/normativa/INVENTARIO.md` | Normativa considerada y su estado |
| `docs/adr/` | Decisiones de arquitectura |
| `docs/ETAPA0_ESPECIFICACION.md` | Especificación original completa (registro histórico) |
