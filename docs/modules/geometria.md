# Módulo: geometría desde planos DXF

Estado: **en desarrollo**. Hechos:
- 3.A: el lector DXF y la geometría de contornos;
- 3.B: niveles, espacios y obstáculos en el modelo, con su Excel.

Falta la interfaz (3.C).

## Decisiones del usuario (06-11-2026)

| Pregunta | Decisión |
|---|---|
| ¿De dónde salen los planos? | Del arquitecto o del cliente, con sus capas. No se supone ningún nombre de capa: el usuario dice qué capa es qué en cada proyecto. |
| ¿Cómo se definen los espacios? | TRAZA **propone** las polilíneas cerradas de las capas elegidas y el usuario confirma, corrige o descarta cada una. Nada entra sin confirmar (RF-030). |
| ¿Alturas? | Por **nivel** (cota y altura libre), que heredan sus espacios, con **excepciones** por espacio. Cubierta inclinada: altura mínima y máxima. |
| ¿Qué más sacar del DXF? | **Pilares y obstáculos**, **bloques** (cuántos por capa y espacio) y **longitudes por capa**. |

## Fuentes

- Autodesk, *DXF Reference* (AutoCAD 2018), consultada el 06-11-2026:
  - HEADER: `$INSUNITS` («Default drawing units for AutoCAD DesignCenter blocks»: 0 =
    Unitless, 4 = Millimeters, 5 = Centimeters, 6 = Meters, 14 = Decimeters…) y
    `$MEASUREMENT` (0 = English, 1 = Metric).
    <https://help.autodesk.com/cloudhelp/2018/ENU/AutoCAD-DXF/files/GUID-A85E8E67-27CD-4C59-BE61-4DC9FADBE74A.htm>
  - LWPOLYLINE: código 70 «Polyline flag (bit-coded); 1 = Closed», código 42 «Bulge».
    <https://help.autodesk.com/cloudhelp/2018/ENU/AutoCAD-DXF/files/GUID-748FC305-F3F2-4F74-825A-61F04D757A50.htm>
  - VERTEX: código 42, «The bulge is the tangent of one fourth the included angle for an
    arc segment, made negative if the arc goes clockwise from the start point to the
    endpoint. A bulge of 0 indicates a straight segment, and a bulge of 1 is a semicircle».
    <https://help.autodesk.com/cloudhelp/2018/ENU/AutoCAD-DXF/files/GUID-0741E831-599E-4CBF-91E1-8ADBCFD6556D.htm>
  - POLYLINE: código 70, «1 = This is a closed polyline», «8 = This is a 3D polyline».
    <https://help.autodesk.com/cloudhelp/2018/ENU/AutoCAD-DXF/files/GUID-ABF6B778-BE20-4B49-9B58-A94E64CEFFF3.htm>
- Biblioteca de lectura: ezdxf 1.4.5 (MIT), ADR-0008. Shapely (previsto en la especificación técnica) no hace falta: la geometría exacta es propia.

## Lector DXF (`io/dxf.py`)

Lee el **espacio modelo** y hace inventario, sin interpretar:

- **Unidades.** `$INSUNITS` solo se **propone**, porque la norma lo define como unidad por
  defecto de los bloques de DesignCenter, no como unidad del dibujo. El usuario la
  confirma viendo la medida total del dibujo con esa unidad: una nave de 80 m no puede medir
  80 km ni 8 cm. Si no es métrica o no consta, se avisa y la unidad la elige el usuario.
- **Capas.** Cuántas entidades de cada tipo tiene cada capa, si está apagada o congelada y
  su longitud.
- **Contornos cerrados** para proponer espacios y obstáculos:
  - LWPOLYLINE y POLYLINE 2D con el bit «Closed», y CIRCLE;
  - las polilíneas **abiertas cuyo último punto coincide con el primero**, habituales en
    planos ajenos. Se proponen marcadas como «no venía cerrada».
  - Contornos que **se cortan a sí mismos** (un «8», una corbata): se proponen
    **marcados**, porque su superficie no tiene sentido físico.
  - Contornos **sin superficie** (vértices en línea, círculo de radio 0, arcos que se anulan):
    no se proponen y se avisa.
- **Textos** (TEXT, MTEXT sin formato), para nombrar los espacios por el texto que caiga
  dentro. La posición de un TEXT es la de su justificación:
  - izquierda: el punto de inserción;
  - ALIGNED y FIT: el punto medio de sus dos puntos;
  - el resto: el punto de alineación.

  Con un texto centrado, el punto de inserción puede caer en el local de al lado.
- **Bloques insertados**: nombre, capa, punto, giro (en coordenadas universales), escala y
  atributos.
- **Longitud por capa** de LINE, ARC, CIRCLE, LWPOLYLINE y POLYLINE, **en planta**
  (proyección XY: una tubería 3D que sube 5 m cuenta solo su recorrido en planta).

Coordenadas:
- Las entidades en coordenadas de objeto (OCS: LWPOLYLINE, POLYLINE 2D, CIRCLE, ARC, TEXT,
  INSERT) se pasan a las universales (WCS) con su extrusión: puntos, cotas y giros.
- Con extrusión (0,0,-1), que es dibujo en espejo, el arco cambia de sentido y su bulge de
  signo.
- En LINE, MTEXT y POLYLINE 3D la extrusión no mueve la geometría y no se mira.

**Lo que no lee, y siempre avisa:**

| Caso | Aviso |
|---|---|
| Contenido de bloques | Si el plano está dentro de un bloque, aunque sea a través de otros bloques, dice cuál y pide descomponerlo (DESCOMP). |
| Referencias externas (xref) | Pide unirlas (UNIRREF) antes de exportar. |
| Espacio papel | Dice en qué presentaciones hay dibujo y cuántas entidades, y pide pasarlo al modelo (CAMBIOESPACIO). |
| Otros tipos de entidad (sombreados, sólidos, cotas…) | Dice cuáles y cuántos. Si los muros o pilares están así, hay que elegir otra capa o dibujar su contorno. |
| SPLINE y ELLIPSE | Se cuentan pero no se miden: su longitud no tiene fórmula cerrada. |
| Polilíneas ajustadas con PEDIT (Curva o Spline) | Se quitan los puntos de control (VERTEX 16) y se usa la curva generada, que es una aproximación. |
| Entidades fuera de planta (extrusión no vertical) | Se omiten. |
| Defectos de formato | Se leen con la recuperación de ezdxf y se dice cuántos había. |
| Una entidad que no se puede leer | Se dice cuál (handle, capa) y por qué; el resto del plano se lee. |

**Aproximaciones de dibujo** (solo para el visor, nunca para medir): polilíneas y círculos
se aplanan con una flecha de una milésima de su tamaño; los arcos sueltos, en pasos de 5°.

## Geometría (`core/geometria.py`, puro)

Contorno = polilínea cerrada con tramos rectos o en arco (bulge). **Superficie y perímetro
exactos**, sin aproximar los arcos:

- ángulo incluido θ = 4·atan(bulge);
- longitud del arco = c·(|θ|/2)/sen(|θ|/2), con c la cuerda;
- superficie = polígono de cuerdas (fórmula de Gauss, con signo) + Σ segmentos circulares
  (c²/8)·(θ − sen θ)/sen²(θ/2). Si |θ| es pequeño, «θ − sen θ» resta dos números casi
  iguales y pierde cifras. Por eso:
  - para |θ| < 10⁻² se usa su serie θ³/6 − θ⁵/120 + θ⁷/5040;
  - para |θ| < 10⁻⁶, su límite c²·θ/12.

Las coordenadas se toman respecto al primer vértice: así un plano georreferenciado (UTM en mm,
~4·10⁹) no pierde cifras.

**Aproximación declarada:** para saber si un punto (un texto, un bloque) cae dentro de un
contorno, los arcos se sustituyen por cuerdas con una flecha máxima de **1 mm**. Solo se usa
para clasificar puntos, nunca para medir. La flecha va en metros: el contorno se pasa antes a
metros con la unidad confirmada. Un punto exactamente sobre el borde puede quedar dentro o
fuera.

**Autointersección:** dos tramos no contiguos que se cruzan o se tocan, o dos contiguos que
vuelven uno sobre otro, se comprueban sobre el contorno aplanado. Solo se comparan los tramos
cuyas cajas se solapan, con un barrido por x, para que un contorno de miles de vértices no
tarde. **Limitación:** «colineal» y «se toca» se comparan de forma exacta. Un contorno que
vuelve sobre sí mismo con coordenadas no enteras puede no detectarse como «se corta». Se
queda entonces en «sin superficie», que también se avisa: nunca entra como espacio bueno.

**Polilíneas ajustadas con PEDIT:**
- Spline: se quitan los puntos de control y se usa la curva generada.
- Curva: se usan sus vértices y arcos tal como vienen.

Las dos están por validar con un DXF real.

**Validación:** figuras de resultado conocido (rectángulo, círculo con dos semicírculos,
semicírculo hacia fuera y hacia dentro, cuarto de círculo, arco de 270°), pruebas con
hypothesis (traslación y bulges cualesquiera) y casos límite (bulge diminuto, coordenadas
UTM).

## Modelo (3.B): niveles, espacios y obstáculos

**Cómo se lee un plano** (`plano`, esquema V4). Lo decide el usuario y queda guardado:
- unidad confirmada (mm, cm, dm o m);
- capas de **espacios**, de **obstáculos** y de **nombres**. Si no se eligen capas de
  nombres, valen los textos de todas.

Las capas tienen que existir en el dibujo, y una capa no puede ser a la vez de espacios y de
obstáculos. La unidad no se cambia si ya hay geometría confirmada con ella, porque sus
superficies ya no corresponderían al plano.

**Propuestas** (`app/planos.py`):
- Son todos los contornos cerrados de las capas elegidas que aún no están confirmados ni
  descartados.
- Cada una lleva su superficie y su perímetro en m y los textos de la capa de nombres que
  caen dentro.
- Solo se **sugiere** nombre si cae **un** texto. Con varios, elegir uno sería suponer.
- Descartar una propuesta la quita de la lista. Se puede recuperar.

**Confirmar** (`ConfirmarContorno`) crea un **espacio** (ESP-001…) o un **obstáculo**
(OBS-001…), según la capa, colgado de un **nivel** (NIV-01…). Cada valor lleva su origen:

| Valor | Origen |
|---|---|
| Contorno | Tabla `geometria`: en metros, con la entidad del DXF (handle y capa) de la que sale. |
| Superficie y perímetro | **Cálculo**, con su registro: motor `geometria.contorno` 1.0.0, huella de las entradas (documento, handle, unidad, vértices), fórmula y «sin aproximaciones». Los calcula la propia orden con el núcleo a partir de los vértices, que lee `Proyecto` del DXF por su handle (la orden no relee el DXF). No se pueden pisar ni borrar a mano: un resultado de cálculo se cambia cambiando sus datos de partida. |
| Nombre | El **texto del plano**, citado con su handle y capa, o el que escribe el usuario (origen «usuario»). |
| Alturas | Ninguna admite 0. **Nivel**: cota (admite negativa, sótanos) y altura libre. **Espacio**: en uno de tres modos (`FijarAlturaEspacio`): la del nivel, altura propia, o cubierta inclinada con mínima < máxima. Cambiar de modo quita los valores del anterior. **Obstáculo**: cota inferior y altura; sin altura, ocupa toda la del nivel solo si arranca del suelo; si está elevado y no consta su altura, «no consta». Las consultas dicen si la altura es «propia», «del nivel» o «inclinada». |

Un contorno que **se corta a sí mismo no se confirma**: su superficie no tiene sentido.
Hay que corregirlo en el plano.

**Quitar** un espacio u obstáculo lo devuelve a las propuestas. Todo se puede deshacer.
No se quitan:
- un nivel con espacios;
- un elemento aprobado, que primero hay que reabrir;
- un elemento con decisiones o pendientes registrados, porque forman parte de su historia.
  **Limitación:** un espacio que se aprobó alguna vez tiene decisiones y ya no se puede
  quitar. Si su contorno cambia, se confirma el nuevo.

**Lo aprobado no cambia por su nivel:** con un espacio u obstáculo aprobado, no se pueden
cambiar las propiedades de su nivel, porque hereda su altura. Tampoco se pueden añadir ni
quitar espacios de un nivel aprobado.

Los nombres de capa **no distinguen mayúsculas**, como en AutoCAD.

**Bloques por espacio:**
- Se cuentan por nombre, capa y espacio según su **punto de inserción**.
- Un bloque que cae en varios espacios (uno dentro de otro) cuenta en el más pequeño, y se
  dice cuántos hay así.
- Los que no caen en ningún espacio salen como «Fuera de los espacios confirmados».
- **Limitación:** se comparan con todos los espacios del plano, sin separar por nivel. Un DXF
  con varias plantas dibujadas una encima de otra mezclaría sus bloques; dibujadas una al
  lado de otra, no.

**Longitudes por capa**, en metros y en planta.

**Excel del plano**, con estas hojas:
- Espacios;
- Obstáculos;
- Bloques;
- Longitudes por capa;
- Información: unidad, capas, notas y avisos de lectura.

Lo que no consta queda vacío.

Los niveles, espacios y obstáculos no aparecen en el paso «Equipos»: se crean con su
geometría desde «Planos».

## Pendiente

- 3.C Interfaz: paso «Planos», solo en encargos con diseño, con visor 2D.
- Validación con un **DXF real del usuario**: superficies y alturas frente a su medición
  manual, y capas y bloques reconocidos (criterio de la Etapa 2 de la hoja de ruta).
