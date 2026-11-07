# Registro de funcionalidades

Estados: **Pendiente** · **En desarrollo** · **Implementada** (funciona, sin validar) ·
**Validada** (cumple los 8 puntos de finalización) · **Limitada** (funciona con límites
declarados).

Última actualización: 07-11-2026 (Etapa 4, cargas y ventilación).

| ID | Funcionalidad | Etapa | Estado | Notas |
|---|---|---|---|---|
| — | Especificación y arquitectura | 0 | Implementada | Pendiente de aprobación formal del usuario. |
| — | Prueba de viabilidad (ezdxf R2013 + XDATA, PySide6 sin pantalla, pint) | 0 | Implementada | Prueba desechable, fuera del producto. |
| RF-001, 002, 003*, 006, 007, 008, 010, 011, 012 | Núcleo de proyecto sin interfaz | 1 | Implementada | `docs/modules/nucleo.md`. *RF-003 parcial: geometría de espacios y obstáculos desde DXF (Etapa 3); sin conexiones. Pasa a Validada cuando lo uses desde la interfaz (bloque 2). |
| RF-009 | Revisiones de proyecto con nombre y comparación | 1–2 | Pendiente | |
| — | Interfaz: ventana principal, árbol, propiedades, documentos, historial, pendientes | 1 | Implementada | `docs/modules/interfaz.md`. Pasa a Validada cuando el usuario complete el escenario de aceptación con TRAZA.exe en su Windows. |
| — | TRAZA.exe con autoprueba | 1 | Implementada | Generado en GitHub Actions; pendiente de prueba del usuario. |
| RF-020, 021 | Gestión documental y vínculo dato ↔ documento | 1 | Implementada | PDF con comprobación de página citada; XLSX/DXF se incorporan pero su cita (hoja/celda) aún no se comprueba. |
| RF-027, 030, 040, 041 | Importación DXF, espacios, visor 2D | 3 | Implementada | `docs/modules/geometria.md`. Implementada con planos de prueba: lector DXF y geometría exacta (3.A), niveles, espacios y obstáculos con procedencia, propuestas confirmadas, bloques por espacio, longitudes por capa y Excel (3.B), y paso «Planos y espacios» con visor 2D (3.C). Falta validarla con un DXF real del usuario. |
| RF-101, 102 | Cargas térmicas y caudales de ventilación | 4 | Implementada | `docs/modules/cargas.md`. Clima de la guía del IDAE del usuario, 39 usos con fuentes, cerramientos típicos por tipo de construcción, fachadas automáticas del plano, invierno y verano por componentes en hora punta, aire exterior por uso, infiltración; paso «Cargas y ventilación» con informe Excel y PDF. Probado con casos calculados a mano y una estación inventada: falta validarlo con la guía real y un proyecto del usuario. |
| RF-100 | Redes de aire | 3.2 | Pendiente | |
| — | Ventilación y extracción industrial | 3.3 | Pendiente | |
| — | Rooftop | 3.4 | Pendiente | |
| RF-104 | VRF / expansión directa | 3.5 | Pendiente | |
| RF-105 | Hidrónico | 3.6 | Pendiente | |
| RF-200…205 | DXF, LISP, listados, memoria | 3 | Pendiente | |
| RF-110 | Electricidad BT | 4 | Pendiente | |
| RF-120, 130, 140, 150 | Fontanería, saneamiento, PCI, control | 5 | Pendiente | |
| RF-042…045 | Coordinación y trazados | 6 | Pendiente | |
| RF-160 | Estructura (solo geometría) | 7 | Pendiente | Sin cálculo estructural (decisión del usuario). |
| RF-024…029, 301, 302 | IA y documentos | 8 | Pendiente | Proveedor externo con permiso por envío. |
| RF-207 | DWG | — | Fuera de alcance | ADR-0008. |
| — | Mediciones: lector BC3 | 2 | Implementada | Según FIEBDC-3/2024. Validada solo con ficheros de prueba construidos según la norma: falta un BC3 real del usuario. |
| — | Mediciones: lector PDF y Excel con IA + comprobaciones | 2 | Implementada | ADR-0013. Probado con IA simulada; pendiente de Claude Code real y documentos del usuario. |
| — | Excel «con todo» para pedidos en el ERP | 2 | Implementada | Pendiente de que el usuario confirme columnas y que su ERP lo importa. |
| — | Ampliaciones y modificaciones (Excel y BC3) | 2 | Implementada | Paso «Modificados». BC3 verificado por relectura; falta importarlo en Presto/Arquímedes. |
| — | Interfaz por pasos según tipo de encargo | 2 | Implementada | Pasos: Documentación, Mediciones y ofertas, Equipos. Historial en «Ver». |
