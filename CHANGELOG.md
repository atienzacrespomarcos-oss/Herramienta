# Registro de cambios

## [Sin publicar]

### Etapa 3 · geometría DXF, bloque A (06-11-2026)
- Lector DXF (ezdxf). Hace inventario del espacio modelo:
  - capas;
  - contornos cerrados, incluidas las polilíneas que cierran de hecho;
  - textos;
  - bloques con atributos;
  - longitudes por capa en planta.
- La unidad del dibujo se propone desde `$INSUNITS` y la confirma el usuario.
- Avisa de bloques que contienen el plano, xref, SPLINE y ELLIPSE, y entidades fuera de
  planta.
- Geometría de contornos con arcos (bulge): superficie y perímetro exactos, estables con
  bulges diminutos y con coordenadas UTM.
- La autoprueba de TRAZA.exe lee también un DXF.
- Revisión independiente, con todos los fallos corregidos y cada uno con su prueba:
  - aviso de espacio papel (estaba prometido y no existía);
  - posición real de los textos justificados;
  - las LINE con extrusión ya no se descartan;
  - polilíneas ajustadas;
  - contornos que se cortan (marcados) o sin superficie (no se proponen);
  - tipos no leídos;
  - bloques anidados;
  - giro y cota en espejo;
  - arco de 0° a 360°;
  - serie para arcos casi rectos;
  - «está dentro» en metros y con el contorno aplanado guardado.
- Segunda revisión: contorno abierto de 3 puntos que cierra con arco; la comprobación de
  cruces barre por x (comparada con la de todos los pares en 400 polígonos al azar);
  caché acotada; limitaciones declaradas.
- ADR-0014 y ficha `docs/modules/geometria.md`, con las fuentes de Autodesk citadas.

### Etapa 2 · modificados (06-11-2026)
- Paso «Modificados»: sobre una medición leída, variaciones de cantidad (aumento,
  disminución, anulación) y partidas nuevas tomadas de ofertas leídas, con motivo y
  justificación obligatorios; numeración automática; todo deshacible.
- Excel del modificado (cambios con totales + presupuesto actualizado).
- BC3 del presupuesto completo actualizado a partir del original (lo no tocado queda igual),
  o generado si la base vino de PDF/Excel; siempre verificado por relectura.
- Esquema de proyecto V3.
- Revisión independiente, con todos los fallos corregidos y cada uno con su prueba:
  - El buscador de partidas podía aplicar el cambio a otra partida con el mismo texto.
  - Anular una partida de una base leída de PDF o Excel impedía exportar el BC3.
  - El BC3 ya no se toca a ciegas cuando la medición tiene expresiones, líneas que no suman
    el total, registros `~N` o una partida repetida sin POSICION.
  - La relectura comprueba también los avisos del lector y los precios de los capítulos.
  - El lector identifica la `~M` por POSICION siempre que la partida se repite.
  - Los totales avisan de las líneas omitidas y de las partidas «a revisar» de la base.
  - En el Excel, cada total va en su columna.
  - Los códigos que se cambian en el BC3 generado se avisan, y ya no chocan con los
    capítulos.
  - Los números de modificado no se reutilizan.
  - Las cantidades admiten como máximo 6 decimales.
  - Una oferta no se añade a sí misma como partida nueva.
  - Errores de lectura con mensaje claro.
- Segunda revisión, centrada en las correcciones:
  - Se rechaza una `~M` que en el original no coincide con su `~D`.
  - La línea añadida cuadra exacta con la cantidad nueva.
  - Las anulaciones (escritas con 0) se avisan.
  - Se aceptan registros válidos sin separador final.
  - El BC3 avisa de las líneas omitidas y de las partidas «a revisar» de la base.

### Etapa 2 · mediciones (06-11-2026, en curso)
- Lector BC3 según la especificación oficial FIEBDC-3/2024 (páginas citadas).
- Partidas guardadas en el proyecto con su origen exacto; leer y quitar se deshacen.
- Excel con todo para hacer los pedidos en el ERP.
- Interfaz por pasos (Documentación · Mediciones y ofertas · Equipos) según el tipo de
  encargo, con página de bienvenida sin proyecto e historial en «Ver».
- Esquema de proyecto V2 (los proyectos V1 se actualizan solos, con copia previa).
- Lectura de PDF y Excel con IA (Claude Code con la suscripción del usuario), con permiso
  por envío y comprobaciones deterministas: lo que cuadra entra directo, lo que no queda
  «a revisar» con su motivo y se puede confirmar tras revisarlo.

### Etapa 1 · bloque 2 — interfaz y ejecutable (06-11-2026)
- Ventana principal clásica: árbol de elementos, propiedades con procedencia y fuente en cada
  fila («no consta» visible), pestañas Documentos/Historial/Pendientes.
- Menús completos del núcleo; acciones desactivadas cuando no aplican.
- Lectura de números con convención española; «2.400» se rechaza por ambiguo.
- TRAZA.exe generado en GitHub Actions con autoprueba previa a su publicación.
- Forma de trabajo «pregunta → opciones → decide el usuario → ejecuta Claude» en CLAUDE.md.

### Etapa 1 · bloque 1 — núcleo sin interfaz (06-11-2026)
- Proyecto como carpeta `.traza` con base SQLite, almacén de documentos de solo lectura y
  copias de seguridad (al abrir, manual, antes de restaurar; se conservan 30).
- Procedencia obligatoria por valor, comprobada en el programa y en la base de datos.
- Unidades comprobadas por magnitud; valores guardados tal como los da su fuente.
- Estados con aprobación y reapertura motivadas; bloqueo de lo aprobado.
- Órdenes con deshacer/rehacer y registro de cambios inalterable.
- Citas de PDF comprobadas contra el número real de páginas.
- Pruebas: 52 (incluye 60 secuencias aleatorias de deshacer/rehacer). CI en Windows y Linux.
- Corregido tras revisión independiente: la IA podía confirmar sus propias propuestas;
  «calculado»/«comprobado» se podían marcar a mano; la notación «W/m²·K» se interpretaba
  como (W/m²)·K; la copia «al abrir» se hacía después de actualizar el formato; no se podía
  restaurar una base de datos dañada; las copias manuales se perdían tras 30 aperturas; se
  podían colgar componentes de un elemento aprobado; varias fugas en fallos a medias.
- ADR-0003 aceptado: `sqlite3` con migraciones propias en lugar de SQLAlchemy/Alembic.

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
