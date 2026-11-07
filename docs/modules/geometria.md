# Módulo: geometría desde planos DXF

Estado: **en desarrollo**. Este bloque (3.A) entrega el lector DXF y la geometría de contornos;
faltan el modelo (3.B) y la interfaz (3.C).

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

## Pendiente

- 3.B Modelo:
  - niveles, espacios y obstáculos con procedencia (documento + handle de la entidad);
  - propuestas confirmadas por el usuario;
  - bloques por capa y espacio, y longitudes por capa, en Excel.
- 3.C Interfaz: paso «Planos», solo en encargos con diseño, con visor 2D.
- Validación con un **DXF real del usuario**: superficies y alturas frente a su medición
  manual, y capas y bloques reconocidos (criterio de la Etapa 2 de la hoja de ruta).
