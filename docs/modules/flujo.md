# Flujo de trabajo de la herramienta

Estado: **decidido** (09-11-2026); se construye por bloques. **Bloques 1 y 2 implementados** (09-11-2026).

## Decisiones del usuario (09-11-2026)

| Pregunta | Decisión |
|---|---|
| Pedidos | **Fuera**: «Ya te dije que olvidaras pedidos». |
| Cómo llegan los encargos | **Plano del cliente y diseño yo**, **proyecto ajeno a ofertar** y **ampliación de una instalación existente**. «Solo ejecución», no. |
| Tipos de encargo | **Diseño · Oferta · Ampliación** (sustituyen a «diseño + presupuesto + instalación», «presupuesto + instalación» y «solo instalación»). |
| Recorrido | **Pasos con estado**: cada paso marca hecho / pendiente / desactualizado (si cambia algo de un paso anterior, avisa de lo que hay que revisar) y dice qué falta para el siguiente. |
| Ampliación | **Diseñar la parte nueva** sobre el plano existente. |
| Oferta | **También recalcular**: además de leer y revisar el presupuesto, rehacer cargas, redes o cuadros para detectar errores del proyecto antes de ofertar. |
| Planos nuevos | «Quiero poder yo **proponer planos de ampliación o modificación y que se recalcule todo**»: en cualquier encargo se carga un plano revisado (o uno de ampliación) y todo lo que depende de él se recalcula y se marca para revisar. |
| Orden de los bloques | **1 → 2 → 3** (encargos y estado; entregables y memoria; oferta con recálculo). |
| Tabla de pasos por encargo | **Así** (la de abajo). |
| Entregables de un diseño | **Planos DXF/LISP**, **Excel de cálculo** y **memoria técnica en Word editable** (.docx). Presupuesto/BC3 del diseño, no. |
| Alcance de la memoria (09-11-2026) | «Es de soporte en caso de que me hagan justificar algo. Con plantilla de Aliter. Nada oficial». **Sin membrete** de TRAZA. |

## Pasos por tipo de encargo

| Paso | Diseño | Oferta | Ampliación |
|---|---|---|---|
| Documentación | ✓ | ✓ | ✓ |
| Planos y espacios | ✓ | ✓ (para recalcular) | ✓ (zonas nuevas marcadas) |
| Cargas y ventilación | ✓ | ✓ | ✓ (zonas nuevas) |
| Redes de aire | ✓ | ✓ | ✓ |
| Sistema hidráulico | ✓ | ✓ | ✓ |
| Subcuadros de clima | ✓ | ✓ | ✓ |
| Mediciones y ofertas | — | ✓ | — |
| Modificados | — | ✓ | — |
| Equipos | ✓ | ✓ | ✓ |
| Entregables (DXF/LISP, Excel, memoria) | ✓ | — | ✓ |

## Estado de cada paso
- **Pendiente**: le falta lo que necesita (p. ej. Cargas sin espacios confirmados), y lo
  dice: «Falta: confirmar espacios en Planos».
- **Hecho**: tiene datos y calcula sin error.
- **Desactualizado**: algo de un paso del que depende ha cambiado después (cargas →
  redes, hidráulica, cuadros); se marca hasta que se revise.
- Dependencias: Planos → Cargas → Redes de aire y Sistema hidráulico → Subcuadros →
  Entregables.

## Plan de entrega (por bloques)
1. **Encargos y pasos con estado**: los tres tipos nuevos (los proyectos existentes se
   pasan al más parecido), los pasos de cada tipo, el estado y «qué falta»; en ampliación,
   espacios marcados como existentes o nuevos; **plano revisado o de ampliación**: se
   carga y se recalcula todo lo que depende de él (espacios, cargas, redes, hidráulica,
   cuadros), con lo que cambia marcado para revisar.
2. **Entregables y memoria técnica**: un paso que saca de una vez los DXF/LISP y Excel de
   todo el diseño a una carpeta, y la memoria en Word con cada cálculo justificado por su
   norma.
3. **Oferta con recálculo**: comparar lo que dice el proyecto ajeno (mediciones,
   secciones, potencias) con lo que calcula la herramienta y listar las diferencias.

## Cómo está hecho el bloque 1 (decisiones de método, 09-11-2026)

### Encargos
- Tres tipos: `diseno`, `oferta`, `ampliacion`. Los proyectos anteriores con «presupuesto +
  instalación» o «solo instalación» pasan a **Oferta** (migración V10).
- Pasos visibles: la tabla de arriba. «Entregables» llega en el bloque 2.

### Estado de cada paso (`app/flujo.py`)
- Marca en la lista de pasos: **✓** hecho, **○** pendiente, **⚠** desactualizado; al
  pasar el ratón, lo que falta o lo que ha cambiado. Equipos no tiene estado; Modificados, solo ✓ cuando hay alguno.
- **Pendiente**: le faltan datos («Falta: leer el plano DXF», «Falta: el clima y la obra»,
  «Falta: definir un sistema hidráulico»…) o un elemento no se calcula (««Nave» no se
  calcula: …»).
- **Desactualizado**: un paso del que depende (Planos → Cargas → Redes de aire y Sistema
  hidráulico → Subcuadros) ha cambiado después del último cambio propio o de la última
  revisión. Se quita cambiando el paso o con **Ver → Dar por revisado este paso** (se
  puede deshacer).
- Lo que cuenta como «cambio» sale del registro de cambios, y solo si cambia datos de
  cálculo: en Planos, la geometría confirmada y los niveles, espacios y obstáculos con sus
  propiedades (alturas, cotas); no las capas, los descartes, leer otro DXF ni aprobar o
  reabrir. En los demás,
  su propia tabla (cargas del proyecto y de cada espacio, redes, sistemas, subcuadros).
- Un cambio hecho por la misma
  orden que cambió un paso anterior no cuenta como revisión del paso (al revisar el plano,
  la red pasa al plano nuevo, pero nadie ha revisado la red).
- Deshacer un cambio también es un cambio: lo que dependía sigue marcado hasta revisarlo
  (preferible a darlo por bueno sin mirar).
- El estado **no lee la guía del IDAE** (tarda segundos y la lista se refresca a cada
  cambio): hasta pulsar «Calcular» en Cargas, Cargas, Redes e Hidráulica se dan por hechos
  si tienen sus datos; después, además, tienen que calcular.

### Plano revisado o de ampliación (Planos → «Plano revisado o de ampliación…»)
- Se elige el DXF nuevo (incorporado antes en Documentación). Tiene que tener las mismas
  capas que el plano al que sustituye; se lee con la misma unidad.
- **Emparejamiento** (`app/planos.emparejar`): un espacio u obstáculo confirmado es «el
  mismo» que el contorno del revisado del mismo papel que contiene un punto interior suyo
  y cuyo punto interior está dentro de él (se solapan de verdad); entre varios, el de
  superficie más parecida. Punto interior: el centroide o, si cae fuera (L, U), el centro
  del primer tramo interior de una horizontal. Los handles no sirven: AutoCAD u otro
  programa los renumera al guardar.
- Antes de aplicar se enseña el resumen: sin cambios, los que **cambian** (superficie antes
  → después), los que **ya no están** (se quitan) y cuántos **contornos nuevos** hay para
  confirmar, y si a alguna red de aire le falta su capa o sus bloques en el revisado.
- **«Sin cambios»** = misma forma en el mismo sitio: los mismos vértices a menos de 1 mm
  (empiece donde empiece el contorno y en cualquier sentido) y los mismos arcos
  (`core/geometria.mismo_contorno`). El resumen y la orden usan el mismo criterio. Un
  contorno desplazado o girado cambia aunque conserve superficie y perímetro.
  Se compara la secuencia (los mismos puntos unidos en otro orden son otra figura).
  Un contorno «sin cambios» se guarda con los vértices del revisado (diferencias de menos
  de 1 mm por redondeo) y conserva su superficie y su registro.
- Sustituir el plano, aunque sea por el mismo dibujo guardado otra vez, cuenta como cambio
  de Planos: lo que depende queda para revisar (se ha cargado un plano nuevo).
- Al aceptar, una sola orden (se deshace entera): plano nuevo con las mismas capas; cada
  elemento conserva su identidad (cargas, circuitos y redes siguen apuntándole) con su
  contorno nuevo, y su superficie y perímetro recalculados con registro nuevo (el anterior
  queda obsoleto); los que ya no están se quitan; las redes de aire pasan al plano nuevo;
  los descartes del plano anterior que siguen en el revisado se mantienen descartados.
- Todo lo demás se recalcula solo (las cargas, redes, hidráulica y cuadros se calculan
  siempre de lo guardado) y queda **⚠ desactualizado** para revisarlo.
- Se rechaza: si ningún elemento coincide (dibujo desplazado a otro punto base o en otra
  unidad); si un elemento **aprobado** cambia o desaparece (hay que reabrirlo con motivo;
  se dice antes de preguntar);
  si uno que ya no está tiene decisiones o pendientes registrados; si un contorno revisado
  se corta a sí mismo.
- El plano sustituido sigue en la base por la historia, pero ya no se ve ni se trabaja
  (ninguna orden lo acepta).
- Lo que se quita deja de existir para los circuitos hidráulicos y los subcuadros que lo
  usaban: esos pasos lo dicen («no se calcula») y quedan marcados.
- Coste: con la guía ya leída, la lista de pasos recalcula cargas, redes e hidráulica a
  cada cambio. Con los proyectos de prueba es instantáneo; si con un proyecto real se nota,
  se guardará el último resultado.

### Ampliación: zonas nuevas
- Se diseña la parte nueva: en el plano de la ampliación (o el existente con la ampliación
  dibujada) **solo se confirman los espacios nuevos**; lo existente se queda sin confirmar
  (en gris, como el resto del dibujo) o se descarta. Así cargas, redes, hidráulica y
  cuadros se calculan solo para la ampliación, sin una marca más que mantener. La pantalla
  lo dice («Confirmados (ampliación)», «Falta: confirmar los espacios de la ampliación»).

## Cómo está hecho el bloque 2 (decisiones de método, 09-11-2026)

### Paso «Entregables» (Diseño y Ampliación; menú Entregables)
- **Generar entregables…**: se elige una carpeta y se crea dentro una subcarpeta nueva
  «<proyecto> - Entregables AAAA-MM-DD hhmm» (nunca se sobrescribe nada). Dentro:
  - Excel de cada plano;
  - cargas en Excel y PDF;
  - de cada red de aire, DXF R2013, LISP y Excel;
  - de cada sistema hidráulico, Excel y esquema de principio DXF;
  - de cada subcuadro, el unifilar DXF;
  - la justificación de cálculos en Word.
  Al terminar dice cuántos ficheros y, de lo que no se ha podido generar, el motivo. Un
  error en uno, del tipo que sea, se apunta y no impide los demás.
- Nombres sin repetir: si dos entregables darían el mismo fichero (dos planos «Planta.dxf»
  de carpetas distintas, redes «A/B» y «A:B», mayúsculas, que Windows no distingue), el
  segundo lleva « (2)». Nunca se pisa uno con otro.
- El menú Entregables solo se ve en Diseño y Ampliación, como el paso.
- Si hay pasos **⚠ desactualizados**, pregunta antes de generar; la justificación lo dice
  en «Estado al generar este documento».
- Si la guía del IDAE no está leída en la sesión, se lee (en segundo plano) antes.
- **Solo la justificación de cálculos (Word)…**: el documento suelto, donde se elija.
- Nombres de fichero válidos en Windows (`core/ficheros.nombre_valido`).
- Coste: genera en el hilo de la ventana y recalcula cargas por cada entregable; con los
  proyectos de prueba es inmediato. Si con un proyecto real tarda, se calculará una vez y
  se mostrará el avance.

### Justificación de cálculos (`io/memoria.py`)
- Documento de **apoyo** («nada oficial»): por cálculo, datos de partida con su procedencia,
  método y criterios con su norma, y resultados. Apartados:
  - cargas y ventilación: datos de partida y clima, método, resultados por espacio, y de
    cada espacio la procedencia de cada dato y el desglose por partidas;
  - redes de aire: resumen, criterios y tramos;
  - sistema hidráulico: resumen por servicio, criterios, circuitos, y los elementos con la
    norma o fuente que los exige;
  - subcuadros: criterios del REBT y sus guías, y por línea Ib, sección, Iz, protección,
    diferencial, caída de tensión y CUMPLE / NO CUMPLE.
- Los criterios son **los mismos textos** que las hojas «Hipótesis» de los Excel
  (`informe_*.hipotesis`): el Word y el Excel no pueden decir cosas distintas. Los de los
  subcuadros resumen «Criterios elegidos» de `electricidad.md`.
- Números con **coma decimal** (también en las hipótesis de los Excel, que antes salían
  con punto).
- Lo que no se puede calcular se dice («Sin calcular: …»), nunca se omite en silencio:
  cargas sin clima o sin espacios, una red que no se puede dimensionar (sus avisos, sin
  describir un método que no se ha aplicado), un error inesperado de cualquier cálculo.
- **Cifras**: un número con hasta 3 decimales (un dato de partida: 0,25; 2,75 m;
  0,37 kW) se escribe tal cual se usó; con más (un resultado), a 1 decimal.
- **Subcuadros**: método de instalación y longitud de cada línea, para poder rehacer el
  cálculo; la columna «Comprobación» se **calcula** con los valores de la línea (I diseño
  ≤ In ≤ Iz y caída total ≤ límite), no se lee de un indicador.
- Propiedades del documento (título, fecha) propias, no las de la plantilla; sin autor.
- Se escribe aparte y se sustituye: un fallo a medias no deja un .docx roto.
- Una plantilla .dotx renombrada a .docx también se abre.
- **Formato de sus informes** (usuario, 09-11-2026: «Sí, como mis informes»): si la
  plantilla no trae estilos de título (la de Aliter solo tiene «Normal»), la
  justificación sale como sus informes: proyecto y título centrados en negrita (14 y
  13 pt), subtítulo, línea de guiones, apartados en MAYÚSCULAS y negrita (12 pt), texto
  justificado con 8 pt de separación y tablas con cabecera gris ECECEC en negrita de
  9,5 pt. Sin cierre de lugar, fecha y firma (es un documento de apoyo). Con una
  plantilla que sí trae estilos de título, se usan los suyos.
- **Plantilla**: «Entregables → Plantilla de Word…» (.docx o .dotx). Se recuerda en el
  equipo, no en el proyecto (es la de Aliter para todos). Se conservan sus estilos,
  encabezado, pie y página, y se vacía su cuerpo. Si a la plantilla le falta un estilo
  (Word solo guarda los usados), se imita con formato directo. Si la plantilla no se
  encuentra, se avisa y el documento sale sin ella.
- TRAZA.exe: `--collect-data docx` (la plantilla interna de python-docx); la autoprueba
  genera una justificación.
- Dependencia nueva: python-docx 1.2.0 (MIT).
