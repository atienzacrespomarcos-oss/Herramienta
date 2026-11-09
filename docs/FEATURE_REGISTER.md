# Registro de funcionalidades

Estados: **Pendiente** · **En desarrollo** · **Implementada** (funciona, sin validar) ·
**Validada** (cumple los 8 puntos de finalización) · **Limitada** (funciona con límites
declarados).

Última actualización: 09-11-2026 (flujo de trabajo, bloques 1 y 2).

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
| RF-100 | Redes de aire | 5 | Implementada | `docs/modules/redes_aire.md`. Ejes dibujados en AutoCAD (capa) y terminales como bloques; caudales de las cargas o del atributo CAUDAL; pérdida de carga constante con límites de velocidad; accesorios del manual Climaver; camino crítico, equilibrado y SFP (RITE); listado Excel con medición. Probado con un DXF de prueba y el ejemplo resuelto del manual Climaver; salida a AutoCAD (DXF R2013 con etiquetas y LISP) implementada. Ventilación sencilla (Etapa 6): caudal por renovaciones/h (tablas 3.5 y 3.6 del manual de S&P) y punto de trabajo del ventilador con la potencia máxima por SFP. Falta un DXF real del usuario y probar la salida en su AutoCAD. |
| — | Ventilación y extracción industrial | 3.3 | Pendiente | |
| — | Rooftop | 3.4 | Pendiente | |
| RF-104 | VRF / expansión directa | 3.5 | Pendiente | |
| RF-105 | Hidrónico | 7 | Implementada (cálculo y elementos) | `docs/modules/hidronica.md`. Primario-secundario, 2 y 4 tubos, circuitos de las cargas; diámetros, bombas, colectores, inercia, vaso, presiones, válvulas y aislamiento con RITE e IDAE nº 18; lista completa de elementos y Excel. Probado con los ejemplos resueltos de la guía IDAE nº 18. Esquema de principio en DXF R2013 con leyenda (7.B). Falta validar con un proyecto real y abrir el esquema en el AutoCAD del usuario. |
| RF-200…205 | DXF, LISP, listados, memoria | flujo 2 | Implementada | `docs/modules/flujo.md`. Paso «Entregables»: todos los DXF/LISP y Excel del diseño de una vez y la justificación de cálculos en Word sobre la plantilla del usuario (de apoyo, no la memoria oficial: decisión del usuario). Probado con proyectos de prueba; falta abrirla con la plantilla real de Aliter. |
| RF-110 | Subcuadros eléctricos de clima | 8 | Implementada | `docs/modules/electricidad.md`. Solo subcuadros de clima (decisión del usuario): salidas desde los equipos dimensionados, secciones por intensidad admisible y caída de tensión, magnetotérmico, diferencial, conductor de protección y unifilar DXF. Probado con las tablas y ejemplos de las guías del REBT y un subcuadro calculado a mano. Falta un subcuadro real del usuario. |
| RF-120, 140, 150 | Fontanería, PCI, control | 5 | Pendiente | |
| RF-130 | Saneamiento | — | Fuera de alcance | Decisión del usuario (09-11-2026): «saneamiento me da igual, no quiero incorporarlo». |
| RF-042…045 | Coordinación y trazados | 6 | Pendiente | |
| RF-160 | Estructura (solo geometría) | 7 | Pendiente | Sin cálculo estructural (decisión del usuario). |
| RF-024…029, 301, 302 | IA y documentos | 8 | Pendiente | Proveedor externo con permiso por envío. |
| RF-207 | DWG | — | Fuera de alcance | ADR-0008. |
| — | Mediciones: lector BC3 | 2 | Implementada | Según FIEBDC-3/2024. Validada solo con ficheros de prueba construidos según la norma: falta un BC3 real del usuario. |
| — | Mediciones: lector PDF y Excel con IA + comprobaciones | 2 | Implementada | ADR-0013. Probado con IA simulada; pendiente de Claude Code real y documentos del usuario. |
| — | Excel «con todo» de mediciones | 2 | Implementada | Ya no es para pedidos: el usuario los dejó fuera (09-11-2026). |
| — | Ampliaciones y modificaciones (Excel y BC3) | 2 | Implementada | Paso «Modificados». BC3 verificado por relectura; falta importarlo en Presto/Arquímedes. |
| — | Obra: venta y coste objetivo (bloque 1) | obra 1 | Implementada | `docs/modules/obra.md`. Presupuesto contratado, coste objetivo del Excel de Presto del usuario con sus paquetes, margen previsto. Probado con un comparativo inventado con la estructura del suyo; falta el de una obra real. Faltan coste real, certificaciones, previsión y futuribles. |
| — | Interfaz por pasos según tipo de encargo | 2 · flujo 1 | Implementada | `docs/modules/flujo.md`. Encargos Diseño · Oferta · Ampliación, pasos con estado (hecho, pendiente con lo que falta, desactualizado) y «dar por revisado». Historial en «Ver». |
| — | Plano revisado o de ampliación que recalcula todo | flujo 1 | Implementada | `docs/modules/flujo.md`. Emparejamiento por solape, resumen de cambios, una orden que se deshace entera, dependientes marcados para revisar. Probado con DXF de prueba: falta una revisión real de un plano del usuario. |
