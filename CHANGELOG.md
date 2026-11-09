# Registro de cambios

## [Sin publicar]

### Justificación con el formato de los informes del usuario (09-11-2026)
- Con una plantilla sin estilos de título (la de Aliter), la justificación de cálculos
  sale como sus informes: título centrado, apartados en mayúsculas y negrita, texto
  justificado y tablas con cabecera gris.

### Flujo de trabajo · bloque 2: entregables (09-11-2026)
- Paso **Entregables** (Diseño y Ampliación): genera de una vez, en una carpeta nueva,
  los Excel de planos, cargas (Excel y PDF), redes (DXF, LISP y Excel), hidráulica (Excel
  y esquema DXF), unifilares de los subcuadros y la justificación en Word.
- **Justificación de cálculos en Word** (documento de apoyo): datos de partida con su
  procedencia, criterios con su norma y resultados de cada cálculo, sobre la plantilla de
  Word del usuario (se recuerda en el equipo).
- Las hipótesis de los Excel, con coma decimal.
- Dependencia: python-docx (MIT). TRAZA.exe con `--collect-data docx`.

### Flujo de trabajo · bloque 1 (09-11-2026)
- Tipos de encargo **Diseño · Oferta · Ampliación** con sus pasos (docs/modules/flujo.md);
  los proyectos de «presupuesto + instalación» y «solo instalación» pasan a Oferta.
- **Pasos con estado**: ✓ hecho, ○ pendiente (con lo que falta), ⚠ desactualizado (ha
  cambiado un paso anterior) y «Ver → Dar por revisado este paso».
- **Plano revisado o de ampliación**: sustituye el plano, empareja cada espacio y obstáculo
  con su contorno nuevo, enseña lo que cambia, recalcula todo y marca lo que depende.
- Ampliación: se confirman solo los espacios nuevos.
- Pedidos, fuera (decisión del usuario).
- Esquema V10: encargos nuevos, tabla `paso_revisado` y `plano.sustituido_por`.

### Etapa 8 · subcuadros eléctricos de clima (09-11-2026)
- Paso «Subcuadros de clima» (menú Electricidad): salidas propuestas desde los equipos ya
  dimensionados; intensidades (ITC-BT-47 en motores), secciones por intensidad admisible
  (GUÍA-BT-19, tablas A y E) y caída de tensión (Anexo 2, límite de la ITC-BT-19 sumando
  la alimentación), magnetotérmico (GUÍA-BT-22), diferencial (GUÍA-BT-24) y conductor de
  protección.
- Esquema unifilar en DXF R2013 con leyenda.
- Saneamiento, fuera de alcance por decisión del usuario.
- Esquema V9: tabla `subcuadro`.

### Etapa 7.B · esquema de principio en DXF (08-11-2026)
- «Agua → Exportar esquema de principio (DXF)…»: esquema R2013 sin escala con una banda
  por servicio (generador, primario, inercia, colectores, un ramal por circuito hasta sus
  unidades, expansión, seguridad y llenado), toda la valvulería e instrumentos, rótulos con
  tubos, caudales, alturas de bomba, Kv y presiones, capas por función y leyenda.

### Etapa 7 · sistema hidráulico de climatización (08-11-2026)
- Paso «Sistema hidráulico» (menú Agua): primario-secundario, 2 tubos (bomba de calor
  reversible) y 4 tubos (frío y calor independientes); circuitos por grupos de espacios
  con las potencias de las cargas.
- Dimensiona tuberías (≤ 40 mm c.a./m y ≤ 1,2 m/s hasta DN50), bombas, colectores,
  depósito de inercia (volumen mínimo del fabricante, solo con el agua del primario), vaso
  de expansión, presiones, válvulas (Kv, retención por DN, corte), aislamiento (RITE) y
  dilatación.
- Lista completa de elementos del esquema, cada uno con el artículo del RITE o la fuente
  que lo exige, y Excel (Resumen, Circuitos, Elementos, Hipótesis).
- Fuentes: RITE, guía IDAE nº 18 (comprobado contra sus ejemplos resueltos), guía IDAE de
  la bomba de calor (2023), ASHRAE, Caleffi, Carrier, Viega (UNE-EN 10255).
- Esquema V8: tabla `sistema_hidraulico`.
- Revisión independiente (sin bloqueantes): un espacio en dos circuitos se rechaza (su
  carga se sumaba dos veces); el diálogo vuelve con lo escrito si la orden rechaza algo;
  un espacio borrado no sale como id; cobre y plástico se piden por su medida y los
  umbrales del RITE usan su diámetro interior; vaciado total por la potencia de cada
  circuito; válvulas de corte y manguitos en todas las bombas, purgadores en colectores;
  PICV por caudal; circuitos sin potencia avisados también en 2 tubos; tabla de
  aislamiento transcrita en la ficha con su prueba.

### Etapa 6 · ventilación sencilla (08-11-2026)
- Red de extracción o de impulsión de ventilación: el caudal de cada espacio puede salir
  de renovaciones por hora, según su volumen (tabla 3.6 del manual de Soler & Palau) o
  fijas (tabla 3.5 como guía). Nunca baja del aire exterior del espacio.
- Punto de trabajo del ventilador: caudal, presión de la red y potencia eléctrica máxima
  por la SFP exigida (RITE IT 1.2.4.2.5), en pantalla y en el Excel.
- Esquema V7: criterio de caudal y renovaciones de la red.
- Revisión independiente (sin bloqueantes): el aviso de espacios sin terminales no salta
  por las renovaciones; un texto erróneo en el campo de renovaciones deshabilitado ya no
  bloquea Aceptar; la hipótesis del Excel de una extracción por cargas ya no habla de ΔT.

### Etapa 5.B · salida a AutoCAD de las redes de aire (08-11-2026)
- «Exportar a AutoCAD…» en el paso Redes: un DXF R2013 y un LISP con el mismo contenido.
  - Contenido: ejes, conducto a su ancho (abierto solo donde llega un ramal) y etiquetas de
    sección y caudal por tramo y por terminal.
  - Capas por tipo de red, XDATA TRAZA con el id de cada tramo, unidades y coordenadas del
    plano de partida.
  - El LISP (APPLOAD + TRAZA_RED) dibuja la red dentro del plano abierto. Solo usa
    funciones de AutoLISP 2013 (lista blanca con prueba) y se escribe en cp1252.
- Pruebas:
  - el DXF se vuelve a leer con ezdxf (auditoría sin errores) y con el lector de TRAZA;
  - se comprueba la geometría de la T y de las esquinas;
  - el LISP se comprueba con paréntesis equilibrados, funciones permitidas y codificación.
- Correcciones de la revisión independiente:
  - un nombre de red con comillas o barra invertida rompía el LISP: se escapa;
  - etiquetas centradas sobre el conducto según el sentido de lectura y separadas una
    altura de texto; las de terminal, debajo, para no pisar las de los tramos;
  - los codos de dos tramos quedaban abiertos: se cierran;
  - el recorte de la T solo abre el lado al que llega el ramal, con tolerancia en 45°;
  - segmentos de longitud nula descartados; inglete limitado en giros cerrados;
  - el DXF abre encuadrado (zoom extensión);
  - fichero abierto en AutoCAD: mensaje claro en lugar de un error; nombres de fichero
    sin caracteres que Windows no admite.
- Correcciones de la segunda revisión:
  - el codo entre dos tramos de distinto ancho quedaba abierto (los lados se emparejaban
    por su semiancho): ahora por izquierda/derecha;
  - también se cierran dos tramos que salen (o llegan) al mismo punto, p. ej. dos salidas
    del equipo;
  - giro muy cerrado: chaflán en lugar de un pico de hasta 11 semianchos; el lado interior
    ya no se cruza consigo mismo;
  - reducción en línea o en la T (lado opuesto al ramal): se dibuja el escalón;
  - puntos casi repetidos del eje descartados también al buscar las uniones;
  - nombre de fichero: sin caracteres de control, punto final ni nombres reservados (CON,
    NUL…).
- Correcciones de la tercera revisión (sin bloqueantes):
  - T con reducción: cada lado del ramal se recorta con el tramo que tiene a ese lado (antes
    quedaba un hueco de 50 mm en la cara del estrecho);
  - vuelta en U tratada como tal (chaflán), no como tramo recto;
  - reducción con un quiebro de 1° o 2°: también lleva el escalón;
  - «NUL .txt» se reconoce como nombre reservado.

### Etapa 5 · redes de aire (07-11-2026)
- Paso «Redes de aire» para impulsión, retorno y extracción. Cada red se define por la capa
  de ejes que dibuja el usuario en AutoCAD, sus bloques de difusores o rejillas y el
  bloque del equipo.
- Los ejes del DXF se leen como un árbol de tramos: uniones, derivaciones en T, codos
  (también los dibujados como arco), terminales en los extremos o sobre el conducto, y
  detección de anillos y de ramas sin caudal.
- Caudales:
  - salen de las cargas del espacio: la impulsión es lo que pide la carga sensible con un
    salto de 10 K, o el aire exterior si es mayor; el retorno es la impulsión menos el aire
    exterior; la extracción es el aire exterior;
  - se reparten entre los terminales del espacio;
  - el atributo CAUDAL del bloque manda.
- Dimensionado por pérdida de carga constante (0,8 Pa/m por defecto) con velocidad máxima
  por tipo de tramo (10 / 7,5 / 4 m/s, manual Climaver):
  - rectangulares de 50 mm con relación ≤ 4 y alto máximo;
  - circulares de la UNE-EN 1506.
- Rozamiento por Colebrook, comprobado con el ejemplo resuelto del manual Climaver.
- Accesorios con los coeficientes del manual Climaver (ASHRAE), con una errata corregida.
- Camino crítico, presión a disipar en cada terminal, SFP exigida por el RITE y rendimiento
  mínimo del motoventilador.
- Listado Excel con tramos, accesorios, terminales, medición e hipótesis.
- Esquema V6: `red_aire`. Un nivel que usa una red no se quita.
- CLAUDE.md: se preguntan menos detalles finos de método; se deciden y se documentan.
- La topología se lee con una rejilla espacial: 2000 segmentos pasan de 97 s a 0,2 s.
- Presentación limpia en Cargas y Redes, según el criterio del usuario: pocas columnas y el
  detalle en pestañas o en el Excel.
- Revisión independiente, con todos los fallos corregidos y cada uno con su prueba:
  - un espacio con caudal sin terminales en la red se avisa, y el caudal total cuenta solo
    los terminales conectados;
  - dos terminales en el mismo punto cuentan los dos;
  - las polilíneas cerradas conservan su lado de cierre;
  - con varios equipos iguales se toma el más cercano a los ejes;
  - el alto «sin límite» ya no se queda en 1 m;
  - la relación a/b de los codos usa el ancho como lado en el plano del giro;
  - el paso recto se decide solo entre ramas con caudal;
  - el equipo se engancha al punto de eje más cercano;
  - la impulsión sale de la carga del local, sin la del aire exterior;
  - se quita el código de accesorios que no se usaba.

### Etapa 4 · cargas y ventilación (07-11-2026)
- Criterio de fuentes del usuario: buscar, usar y citar, sin etiquetas de «no verificado»
  (CLAUDE.md y ADR-0015).
- Clima de proyecto: se lee la guía del IDAE que el usuario incorpora como documento, y
  cada valor se cita con su página. Percentiles según la cobertura del uso, obra a otra cota
  y psicrometría de ASHRAE.
- Zona climática del CTE por provincia y altitud, generada del Anejo B.
- Catálogo de 39 usos (oficinas, hotel, sanitario, comercial, logística, industria, frío,
  salas limpias, piscina, CPD). Cada valor lleva su fuente:
  - ocupación, personas, iluminación y equipos de ASHRAE;
  - temperaturas del RITE y del RD 486;
  - ventilación del RITE, el RD 486 y la UNE 100713;
  - huecos de ASHRAE 90.1.
- Cerramientos típicos por tipo de construcción, según el Catálogo de Elementos
  Constructivos del CTE (vidrios, marcos, huecos), las U límite del CTE, el panel sándwich,
  la chapa, el edificio anterior a 1980 y la solera por la ISO 13370.
- Motores:
  - radiación de cielo despejado de ASHRAE;
  - invierno por partidas;
  - verano por componentes hora a hora, con hora punta por espacio y simultánea;
  - infiltración UNE-EN 12831 con n50 del CTE.
- Fachadas automáticas desde los contornos del plano, por orientación, con corrección por
  sector.
- Paso «Cargas y ventilación»:
  - uso propuesto por el nombre del espacio, y todo lo demás propuesto con su fuente;
  - el usuario cambia lo que quiera;
  - fachadas marcadas en el visor;
  - informe en Excel (todo el detalle) y en PDF (presentable).
- Esquema V5: `cargas_proyecto` y `cargas_espacio`. El tipo «espacio» pasa a la versión 2.
- Revisión independiente, con todos los fallos corregidos y cada uno con su prueba:
  - la cubierta va donde no hay otro espacio encima, no solo en el nivel más alto (una nave
    con oficinas en otra planta se quedaba sin cubierta);
  - la solera se calcula con la losa entera;
  - el aire exterior seco ya no resta carga latente;
  - las cámaras se calculan sin aire de confort y con el calor de personas de ASHRAE
    Refrigeration, y quedan fuera de la simultánea;
  - salones de actos y CPD pasan a IDA 3, según el RITE;
  - «Almacén de racks» ya no se propone como CPD;
  - un dato roto ya no tumba la ventana, y temperaturas y altitud tienen rangos físicos;
  - las hipótesis del informe ya no dependen del primer espacio, y el Excel incluye la
    orientación de cada cerramiento;
  - el visor muestra un nivel cada vez;
  - el diálogo ya no redondea lo guardado;
  - al quitar un espacio se avisa de que se quitan sus datos de cargas.
- Segunda revisión:
  - el uso se propone por inicio de palabra («Zona de distribución» no es UCI);
  - «Recepción de mercancías» se propone como almacén;
  - las cámaras no suman infiltración por la envolvente;
  - los diálogos validan los mismos rangos que las órdenes;
  - el visor se encuadra al reabrir un proyecto;
  - se avisa de una solera sin perímetro expuesto.

### Etapa 3 · geometría DXF, bloque C (07-11-2026)
- Paso «Planos y espacios», solo en encargos con diseño. Permite:
  - leer un DXF eligiendo la unidad (con la medida total a la vista) y las capas por rol;
  - revisar las propuestas resaltadas en el visor y confirmarlas o descartarlas;
  - crear niveles y fijar la altura de cada espacio (del nivel, propia o inclinada);
  - quitar elementos;
  - ver bloques por espacio y longitudes por capa;
  - exportar el Excel del plano.
- Visor 2D de referencia (zoom y desplazamiento).
- Un DXF grande se lee en segundo plano con progreso.
- Pruebas de interfaz: el aviso de error inesperado se reconoce por su título. Antes se
  miraba el texto, y un fallo de tipo «AttributeError» habría pasado inadvertido.
- Forma de trabajo actualizada en CLAUDE.md: Claude para solo ante dudas sobre qué debe
  hacer la herramienta o cómo, y fusiona cuando la CI está en verde.
- Revisión independiente, con todos los fallos corregidos y cada uno con su prueba:
  - «Quitar» ya se habilita para un nivel;
  - con varios textos dentro no se preselecciona ningún nombre;
  - sin unidad declarada hay que elegirla;
  - la selección se conserva por id tras refrescar;
  - el menú «Planos» solo sale en encargos con diseño;
  - un plano ilegible no deja la ventana a medias;
  - lectura en segundo plano también al abrir el proyecto;
  - el visor no pierde el zoom;
  - las capas apagadas no se dibujan;
  - las unidades del lector, las órdenes y el diálogo, atadas con un test.
- Segunda revisión:
  - un plano que vuelve a leerse se reencuadra;
  - el visor vacío no queda fuera de cuadro;
  - la selección de niveles se conserva también sin plano;
  - refrescar no recoloca la vista;
  - pruebas con la ventana mostrada (zoom), de las capas apagadas y de la lectura en
    segundo plano al abrir.

### Etapa 3 · geometría DXF, bloque B (07-11-2026)
- Esquema V4: `plano` (unidad confirmada, capas de espacios, obstáculos y nombres;
  propuestas descartadas) y `geometria` (contorno en metros con su entidad DXF).
- Tipos nivel, espacio y obstáculo. Alturas por nivel, con excepciones por espacio y
  obstáculo.
- Propuestas de contornos con superficie, perímetro y textos de dentro. Se confirman como
  espacio u obstáculo, se descartan o se recuperan.
- Superficie y perímetro con origen «cálculo» y su registro (motor, versión, entradas y
  fórmula). El nombre sale del texto del plano, citado, o del usuario.
- Bloques por capa y espacio, longitudes por capa y Excel del plano.
- Los niveles, espacios y obstáculos no salen en «Equipos».
- Revisión independiente, con todos los fallos corregidos y cada uno con su prueba:
  - el Excel ya no convierte en fórmula un texto con «=» en ninguna fila;
  - no se puede quitar un espacio de un nivel aprobado;
  - no se cambia el nivel de un espacio aprobado que hereda su altura;
  - los resultados de cálculo no se pisan ni se borran a mano;
  - altura de espacio en tres modos coherentes; alturas que no admiten 0;
  - un obstáculo elevado no hereda la altura del nivel;
  - los tipos de plano no se crean por otra vía;
  - descartar solo lo que es una propuesta;
  - capas sin distinguir mayúsculas;
  - el historial muestra los elementos quitados.
- Segunda revisión: repetir una altura propuesta por la IA la hace del usuario; una misma
  capa con otras mayúsculas ya no sale partida; las capas se guardan con el nombre del DXF;
  el bloqueo de un nivel dice qué elementos aprobados dependen de él.

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
