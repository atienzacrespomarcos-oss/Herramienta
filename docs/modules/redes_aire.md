# Módulo: redes de aire (Etapa 5)

Estado: **en desarrollo**.

## Decisiones del usuario (07-11-2026)

| Pregunta | Decisión |
|---|---|
| Siguiente bloque | **Redes de aire** (hoja de ruta 3.2): la base de rooftop, UTA, ventilación y VRF de conductos. |
| Trazado | **Lo dibuja el usuario en AutoCAD**: ejes de conductos en una capa del DXF; los difusores y rejillas son bloques. |
| Método | **Pérdida de carga constante**, con límites de velocidad por tramo. |
| Caudales | **De las cargas** («Creo que estás hilando demasiado fino. Pero la primera»): el caudal del espacio se reparte a partes iguales entre sus terminales; un atributo CAUDAL del bloque manda. |
| Redes | **Impulsión, retorno y extracción/ventilación**. |
| Sección | **Rectangular con alto máximo** (falso techo); circular por tramo si se quiere. |

## Fuentes y criterios

### Pérdidas por rozamiento
- **Darcy-Weisbach con Colebrook**, como en el manual Climaver de Isover (cap. 6.2.1) y en
  ASHRAE Fundamentals (cap. 21).
  - Rugosidad de la chapa galvanizada: ε = 0,09 mm (ASHRAE).
  - El manual Climaver comprobó en laboratorio que Climaver PLUS R y neto pierden lo mismo
    que la chapa galvanizada, por eso usa el gráfico de ASHRAE.
  - Manual: <https://www.isover.es/documents/catalogos-manuales-y-guias/08-manual-conductos-2.pdf>
- **Diámetro equivalente de un rectangular**: De = 1,30·(a·b)^0,625/(a+b)^0,25 (Huebscher,
  manual Climaver p. 51).
- **Caso de comprobación** del manual: 600 × 600 mm con 1,70 m³/s da De = 656,3 mm y
  0,37 Pa/m, a 20 °C y 101,325 kPa.
- **Aire**:
  - densidad por gas ideal con la presión de la obra;
  - viscosidad 1,81·10⁻⁵ Pa·s, la del aire normal de ASHRAE a 20 °C.

### Pérdidas en accesorios
- Coeficientes del **manual Climaver, pp. 53–55**, que son los de ASHRAE para chapa. Se usan
  los dos accesorios que aparecen en una red leída del plano:
  - **codo de radio uniforme** (C′, K_Re y K_θ):
    - «b» es el lado en el plano del giro; en un plano en planta, el ancho;
    - por debajo de 20° se toma K_θ de 20°, del lado de la seguridad;
  - **derivación a bisel** (C_d y C_s).
- El manual tiene más piezas (reducción, Y, achaflanado, en Z, bordeo, derivación con
  radio). Se añadirán cuando la herramienta las distinga en el dibujo.
- **Errata del manual**: en K_Re de codos con r/b ≥ 0,75 y Re = 6·10⁴ pone 0,46. ASHRAE
  (tabla del codo de radio uniforme) da **1,46**, que es además el único valor que sigue la
  serie decreciente: se usa 1,46.
- Las tablas de ASHRAE se consultaron solo para comprobar esa errata. Su material
  suplementario prohíbe reproducirlas, así que no se copian al repositorio, que es público.

### Velocidades y presiones
- **Velocidad máxima** (manual Climaver, 4.3.4, por ruido regenerado):
  - 10 m/s en conductos principales;
  - 7,5 m/s en ramales;
  - 4 m/s en conductos próximos a terminales.
- **Pérdida de carga objetivo por defecto: 0,8 Pa/m**, la regla clásica de baja velocidad
  (0,1 in.c.a. por 100 ft = 0,82 Pa/m). Se cambia por red.
- **RITE IT 1.2.4.2.4**, caídas de presión máximas por componente:
  - unidad terminal de aire 40 Pa;
  - rejilla de retorno 20 Pa;
  - batería de calor 40 Pa;
  - batería de frío en seco 60 Pa;
  - batería de frío con deshumectación 120 Pa;
  - atenuador 60 Pa.
  Se toman como pérdida por defecto de difusores y rejillas. En extracción, 20 Pa: sus
  rejillas son de aspiración, como las de retorno.
- **RITE IT 1.2.4.2.5**, potencia específica de ventiladores (SFP, tabla 2.4.2.7):
  - en impulsión, SFP 4 (≤ 2000 W/(m³/s)) en climatización y SFP 3 en ventilación;
  - en extracción, SFP 3 en climatización y SFP 2 en ventilación;
  - el ventilador de retorno se clasifica como el de extracción: el RITE solo nombra
    impulsión y extracción.
- **RITE IT 1.2.4.2.3**: estanquidad de la red, clase ATC 4 o superior.

### Secciones comerciales
- **Circulares**: diámetros de la serie de la UNE-EN 1506, de 80 a 1250 mm, que es la gama
  de tubo helicoidal de Salvador Escoda: 80, 100, 125, 160, 200, 250, 315, 355, 400, 450,
  500, 560, 630, 710, 800, 900, 1000, 1120 y 1250 mm.
- **Rectangulares**:
  - lados en múltiplos de 50 mm (se fabrican a medida en chapa o Climaver);
  - relación de lados como máximo 4;
  - alto máximo por red (falso techo);
  - entre las secciones que cumplen, la de menor perímetro (menos material).

### Caudales
- **Impulsión** de un espacio: el mayor entre su aire exterior y el que pide su carga
  sensible de verano, Q = q_s/(ρ·c_p·ΔT).
  - Es la carga **del local**: sin la del aire exterior de ventilación, que se trata en el
    equipo, y con la infiltración, que entra en el local.
  - ΔT de impulsión = 10 K, el salto típico: ASHRAE impulsa a unos 13 °C con el local a
    24 °C, es decir, unos 11 K. Se toma algo menos, del lado de más caudal.
- **Retorno** de un espacio: su impulsión menos su aire exterior.
- **Extracción**: el aire exterior del espacio.
- **Reparto**: a partes iguales entre los terminales del espacio. El atributo CAUDAL del
  bloque, si lo tiene, manda.

## En el proyecto (`app/redes.py`, paso «Redes de aire»)
- **Qué se guarda** (esquema V6, tabla `red_aire`):
  - el nombre, el tipo, el plano y el nivel;
  - la capa de los ejes, los bloques de terminales y el bloque del equipo;
  - los criterios: pérdida de carga objetivo, alto máximo, forma, salto de impulsión y si
    es climatización o ventilación.
  - Los tramos y resultados se calculan del dibujo cada vez. Corregir el trazado es
    corregirlo en AutoCAD y volver a incorporar el DXF.
- **Lectura del dibujo** (`engines/topologia_conductos.py`):
  - extremos a menos de 5 cm se unen;
  - un extremo sobre otro eje es una derivación en T;
  - un terminal se conecta al extremo libre más cercano a menos de 1 m. Si no hay
    ninguno, se conecta al punto más cercano del eje, como un difusor montado sobre el
    conducto, que va en su propio ramal de longitud 0;
  - el equipo es el punto más cercano a su bloque, a menos de 2 m;
  - un anillo se rechaza: la red tiene que ser un árbol;
  - una rama sin terminal se avisa y no se calcula.
- **Codos**: cambios de dirección de más de 10° entre lados de al menos 0,5 m. Un arco
  dibujado por cuerdas cuenta como un solo codo. Radio igual al lado del giro (r/b = 1).
  En circulares se usa la tabla de rectangulares con a/b = 1.
- **Derivaciones**:
  - sigue «recto» el hijo de dirección más parecida al padre si se desvía menos de 45°;
  - coeficientes de la derivación a bisel a 90°: C_d = 1 en el ramal, C_s del paso según
    v_s/v_e y A_s/A_e.
  - En retorno y extracción (aire que converge) se usan los mismos coeficientes, como
    aproximación declarada: el manual no da tes convergentes.
- **Clase del tramo**:
  - principal: el tronco que, desde el equipo, sigue al hijo de más caudal;
  - terminal: el que acaba en un terminal;
  - ramal: el resto.
- **Presión necesaria**: la del camino crítico de la red, sin el equipo; filtros, baterías
  y atenuadores los da su fabricante. Para cada terminal se calcula la presión que su
  compuerta tiene que disipar para equilibrar.
- **SFP** (RITE IT 1.2.4.2.5): rendimiento mínimo del motoventilador = Δp de la red /
  límite de la categoría exigida. Es una cota inferior, porque el equipo suma su propia
  pérdida.
- **Listado Excel**: Resumen, Tramos, Accesorios, Terminales (con la presión a disipar),
  Medición (metros y superficie de conducto por sección) e Hipótesis.
- **Atributos de bloque**:
  - CAUDAL, en m³/h, manda sobre el de las cargas;
  - REF da el código del terminal; una REF repetida se distingue y se avisa.

- **Límites declarados**:
  - dos ejes colineales que se solapan en parte no se funden;
  - el alto «sin límite» llega a 3 m, el mayor lado que se fabrica de forma habitual;
  - con varios bloques de equipo iguales, se toma el más cercano a los ejes de la red.

## Salida a AutoCAD (`io/salida_autocad.py`, «Exportar a AutoCAD…»)
Decisión ADR-0008 / C-04 de la especificación: el DXF es la salida principal, la que se
comprueba en las pruebas; el LISP sirve para dibujar dentro del plano que el usuario tiene
abierto.
- **DXF R2013 (AC1027)**, el que abren AutoCAD 2013–2017. Va en las unidades y coordenadas
  del plano de partida, para superponerlo o copiarlo.
  - Capas por tipo de red (IMP, RET, EXT): `TRAZA-xxx-EJES`, `TRAZA-xxx-CONDUCTO` y
    `TRAZA-xxx-TEXTOS`.
  - Color: impulsión azul, retorno verde y extracción naranja; los textos en blanco/negro.
- **Contenido** (presentación limpia):
  - el eje;
  - el conducto a su ancho, con esquinas a inglete (limitado a 4 veces el semiancho en
    giros muy cerrados), codos cerrados y abierto solo por el lado al que llega un ramal;
  - una etiqueta por tramo, «600×300 · 2835 m³/h», centrada en el lado más largo, por
    encima del conducto según el sentido de lectura y separada de él una altura de texto;
  - una por terminal, «D01 · 1418 m³/h», debajo del terminal para no pisar las de los
    tramos;
  - textos de 0,15 m, centrados (alineación «medio-centro» del DXF).
- Si el DXF o el LISP están abiertos en AutoCAD, la herramienta lo dice y pide cerrarlo
  u otro nombre; los nombres de fichero propuestos quitan los caracteres que Windows no
  admite.
- **XDATA** (ADR-0009): APPID `TRAZA` con `id_red:tramo` o `id_red:terminal`, para
  reconocerlos al volver a leer el plano.
- **LISP** (`.lsp` junto al DXF): APPLOAD y el comando `TRAZA_RED`.
  - Crea las capas si no existen y dibuja con `entmake`.
  - Solo usa funciones que ya existían en AutoLISP 2013 (y en R14). La lista blanca está
    en `FUNCIONES_LISP` y la vigila una prueba.
  - Se escribe en la página de códigos de Windows (cp1252), la que lee AutoCAD 2013.
- **Protocolo de prueba en el AutoCAD del usuario** (pendiente):
  1. abrir el DXF;
  2. en el plano original, APPLOAD del .lsp y TRAZA_RED;
  3. comprobar que coincide con los ejes dibujados;
  4. copiar, mover y guardar, y comprobar que la XDATA sigue (ADR-0009).

## Pendiente
- Validar con un DXF real del usuario y contrastar con su cálculo previo (criterio de
  aceptación de la Etapa 3 de la hoja de ruta).
- Probar el DXF y el LISP en el AutoCAD del usuario (protocolo de arriba).
- Secciones fijadas a mano por tramo: el motor ya las admite (`seccion_fija`), pero la
  interfaz aún no las ofrece.
