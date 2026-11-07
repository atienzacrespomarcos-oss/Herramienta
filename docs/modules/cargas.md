# Módulo: cargas térmicas y ventilación (Etapa 4)

Estado: **implementada** (pendiente de validar con la guía real y un proyecto del usuario).

## Decisiones del usuario (07-11-2026)

| Pregunta | Decisión |
|---|---|
| Siguiente bloque | **Cargas y ventilación**. |
| Usos | **Todos**: hoteles, hospitales, logística de grandes superficies, producción industrial, oficinas y vestuarios, frío, salas limpias… «Debe ser una herramienta muy completa». |
| Para qué | Detectar errores de dimensionado de otros, proponer alternativas, planos más profesionales y dimensionar todo aguas abajo. |
| Método de verano | «Que no me genere fricción»: **por componentes en hora punta**, con informe presentable. |
| Cerramientos | «Nunca me dan esos datos. **Presupón los típicos** dependiendo del tipo de construcción». |
| Ocupación, iluminación, equipos, temperaturas, ventilación | **Propuesta por uso** con tablas publicadas; el usuario cambia lo que quiera. |
| Fuentes | «Busca y fíate de lo que encuentres»: sin etiquetas de «no verificado» (ADR-0015). |
| Ocupación | **ASHRAE, densidades de diseño** (para cargas y ventilación). |
| Huecos en fachada | «Haz lo que recomiendes, pero la herramienta es completa; no gastar mucho tiempo»: **% propuesto por uso** (ASHRAE 90.1), cambiable por espacio. |
| Fachadas | **Automático y reviso**: salen del plano, se ven en rojo en el visor y se corrigen por orientación. |
| Informe | **Excel + PDF**. |

## Fuentes y criterios adoptados

### Clima exterior de proyecto
- **IDAE, «Guía técnica. Condiciones climáticas exteriores de proyecto» (2010)**, documento
  reconocido del RITE, 104 estaciones de AEMET.
  <https://www.idae.es/uploads/documentos/documentos_12_Guia_tecnica_condiciones_climaticas_exteriores_de_proyecto_e4e5b769.pdf>
  - La guía **prohíbe reproducir sus datos** y el repositorio es **público**: TRAZA no los
    copia. Lee el PDF en el equipo del usuario (`io/clima_idae.py`), lo incorpora al
    proyecto como documento y cita cada valor con su página.
  - Percentiles (apartado 5.2):
    - cobertura **alta** (hospitales, clínicas, residencias de ancianos, centros de
      cálculo): TS 99,6 % y TS 0,4 % con THC 0,4 %;
    - **normal**: TS 99 % y TS 1 % con THC 1 %.
  - Obra a otra cota (anexo 7.3): −1 °C por cada 100 m por encima de la estación; por
    debajo, la misma temperatura; humedad absoluta constante.
  - Presión según la altitud (apartado 5.1).
  - Tres estaciones (páginas 25, 81 y 115) dan solo las temperaturas húmedas TH 0,4/1/2 %,
    sin la seca coincidente: se leen así.
- **Psicrometría**: ASHRAE Handbook – Fundamentals (2017), cap. 1 (gas ideal; se aparta
  menos del 1 % de sus tablas).

### Zona climática y cerramientos
- **Zona climática**: CTE DB HE, Anejo B, tabla a, por provincia y altitud (texto legal,
  reproducible). Generada con `scripts/extraer_zonas_cte.py` →
  `src/traza/rules/zonas_cte.py`. Comprobada con las capitales: Madrid D3, Barcelona C2,
  Sevilla B4, Burgos E1, Las Palmas α3, Zaragoza D3, Valladolid D2, Granada C3.
- **U límite** para edificio nuevo: CTE DB HE, tabla 3.1.1.a-HE1, por zona de invierno
  (α, A, B, C, D, E). Muros 0,80/0,70/0,56/0,49/0,41/0,37; cubiertas
  0,55/0,50/0,44/0,40/0,35/0,33; huecos 3,2/2,7/2,3/2,1/1,8/1,80 W/m²K.
- **Resistencias superficiales**: UNE-EN ISO 6946. Rsi = 0,13 en flujo horizontal (muros),
  0,10 hacia arriba (cubiertas en invierno) y 0,17 hacia abajo; Rse = 0,04 m²K/W.
  Reproducidas en varias fuentes coincidentes (foro técnico de Edilclima y calculadoras
  basadas en la norma).
- **Panel sándwich de poliuretano**: λ = **0,024 W/mK**, el de las fichas de fabricantes
  españoles (Deformac, EN 14509:2013). Otros declaran 0,022 (Arqmat, Balex): se elige el
  español, que además está del lado de la seguridad. U = 1/(Rsi + e/λ + Rse).
- **Vidrios** (fichas de fabricantes):
  - simple U ≈ 5,6–5,8;
  - doble sin capa 2,6–3,0;
  - doble bajo emisivo 1,0–1,4 W/m²K, con g = 0,62 (SGG Climalit Plus Planitherm XN).

### Uso de los espacios
- **Temperaturas interiores**: RITE IT 1.1.4.1.2, tabla 1.4.1.1. Cálculo de calefacción a
  21 °C y de refrigeración a 25 °C; humedad 40–50 % en invierno y 45–60 % en verano.
- **Calidad de aire interior**: RITE IT 1.1.4.2.2. IDA 1 en hospitales, clínicas,
  laboratorios y guarderías; IDA 2 en oficinas, zonas comunes de hoteles, residencias,
  aulas y piscinas; IDA 3 en comercios, habitaciones de hotel, restaurantes y gimnasios;
  IDA 4 calidad baja.
- **Caudal de ventilación**: RITE IT 1.1.4.2.3.
  - Por persona (tabla 1.4.2.1): 20 / 12,5 / 8 / 5 dm³/s.
  - Por superficie, en locales sin ocupación permanente (tabla 1.4.2.4): no aplicable en
    IDA 1; 0,83 / 0,55 / 0,28 dm³/(s·m²) en IDA 2 a 4.
  - Piscinas: 2,5 dm³/(s·m²) de lámina de agua y playa.
  - Hospitales: UNE 100713.
- **Lugares de trabajo** (industria, logística): RD 486/1997, anexo III.
  - 30 m³/h por trabajador en trabajo sedentario en ambiente no caluroso ni contaminado, y
    50 m³/h en el resto.
  - Temperatura de 17–27 °C en trabajo sedentario y de 14–25 °C en trabajo ligero; humedad
    relativa del 30–70 %.
- **Hospitales** (UNE 100713:2005, a través de la NTP 859 del INSST):
  - quirófanos de clase I, con 1200 m³/h mínimos de aire exterior;
  - caudal de referencia de 2400 m³/h;
  - quirófano A: ≥ 20 renovaciones por hora de aire exterior, recomendadas 35 movimientos
    por hora;
  - B: 20 por hora, 100 % exterior;
  - C: ≥ 15 por hora, 100 % exterior.
- **Salas limpias**, en renovaciones por hora (tabla de referencia de Mecart):
  - ISO 6: 90–180;
  - ISO 7: 30–60;
  - ISO 8: 10–25;
  - ISO 5: flujo unidireccional.
- **Ocupación, calor de las personas, iluminación y equipos** (decisión del usuario:
  «ASHRAE diseño»): valores por defecto por tipo de espacio de ASHRAE, tal como los
  reproduce Autodesk en la ayuda de Revit («Space Type Data»; calor de las personas según
  ASHRAE Handbook – Fundamentals, tabla 1). Catálogo en `src/traza/rules/usos.py`, guardado
  en las unidades de origen (personas/100 m², Btu/h, W/ft²) y convertido a SI: 1 Btu/h =
  0,29307 W; 1 W/ft² = 10,764 W/m². Los 39 usos se cotejaron uno a uno con la tabla de
  origen el 07-11-2026 (39 de 39 iguales).
  - Se descarta la densidad del CTE DB SI (tabla 2.1): es de evacuación, no de diseño
    térmico, y sobredimensiona.
  - La iluminación del CTE DB HE3 (tabla 3.2) es una potencia máxima: queda como
    comprobación, no como valor de cálculo.
- **Cámaras frigoríficas**: congelación a −20 °C (RD 1109/1991: ultracongelados a −18 °C o
  menos); refrigeración a 2 °C (producto fresco 0–4 °C); sala de manipulación a 12 °C.
  La carga de producto se mete como proceso.
- **Piscinas**: aire 1–2 °C por encima del agua con un máximo de 30 °C, HR < 65 % (RITE
  IT 1.1.4.1.2.3); agua de 24 a 30 °C (IT 1.1.4.3.2): se toma el aire a 28 °C.
- **Aparcamientos**: CTE DB HS3, 120 l/s por plaza.

### Cerramientos típicos (`src/traza/rules/cerramientos.py`)
Entran como **hipótesis** con su fuente; el usuario los cambia.
- **CTE, Catálogo de Elementos Constructivos** (CEC v06.3, marzo 2010),
  <https://www.codigotecnico.org/pdf/Programas/CEC/CAT-EC-v06.3_marzo_10.pdf>:
  - 3.15.2 vidrios:
    - sencillo de 4 mm: U 5,7 vertical / 6,9 horizontal, g 0,85;
    - doble 4-12-4: 2,8 / 3,4, g 0,76;
    - bajo emisivo (0,1 ≥ ε > 0,03) 4-12-4: 1,8 / 2,4, g 0,63.
  - 3.16 marcos, U vertical / horizontal:
    - metálico: 5,7 / 7,2;
    - con rotura de puente térmico de 4–12 mm: 4,0 / 4,5;
    - con rotura de más de 12 mm: 3,2 / 3,5;
    - madera: 2,2 / 2,4;
    - PVC de 2 cámaras: 2,2 / 2,4;
    - PVC de 3 cámaras: 1,8 / 1,9.
  - 4.3.1.1 huecos: se ponderan vidrio y marco con
    U_H = (1 − FM)·U_v + FM·U_m y F_H = (1 − FM)·g + FM·0,04·U_m·α.
    - Con estas fórmulas se reproducen las tablas del CEC; las pruebas lo comprueban.
    - El CEC tabula FM del 20 % y del 40 % e interpola entre ellos: se toma **30 %**.
    - α = 0,8 (marco oscuro, como en el CEC).
  - 4.2.11 panel sándwich: U = 1/(0,17 + R del panel), es decir, Rsi + Rse de la
    ISO 6946. El CEC da para el alma de PUR λ de 0,022 a 0,037: se usa 0,024, el de la ficha
    de Deformac.
- **Espesor típico del panel**: catálogos de Novacero (cubierta 25–50 mm, fachada
  40–50 mm) y Obramat (cubierta de 30 mm). Se toman **40 mm en fachada y 30 mm en cubierta**.
- **Tipos de construcción**:
  - edificio nuevo CTE: la U límite de su zona, y el factor solar de un doble bajo emisivo
    con rotura de puente térmico de más de 12 mm;
  - nave de panel sándwich: la U del panel, y huecos dobles con rotura de 4–12 mm;
  - nave de chapa sin aislar: solo las resistencias superficiales, con vidrio sencillo y
    marco metálico;
  - edificio anterior a la NBE-CT-79: muros y cubierta de 2,5 y huecos de 5,7, según el
    TFM de la Universidad de Zaragoza (2021),
    <https://zaguan.unizar.es/record/112232/files/TAZ-TFM-2021-1559_ANE.pdf>.
- **Solera sobre el terreno**: UNE-EN ISO 13370, con la dimensión característica
  B' = A/(0,5·P) y λ del terreno = 2,0 W/mK (el valor de la norma cuando no se conoce el
  terreno). En una nave de 50 × 100 m da U ≈ 0,19 W/m²K.
- **Zona climática a partir de la guía del IDAE**: los nombres de provincia de la guía se
  traducen a los del CTE (Vizcaya → Bizkaia, Baleares → Illes Balears…).

### Método de cálculo (`engines/solar.py`, `engines/cargas.py`)
- **Invierno**: transmisión U·A·ΔT, ventilación e infiltración; sin descontar ganancias.
  La solera se calcula con la temperatura exterior de proyecto, del lado de la seguridad.
- **Verano**: por componentes, hora a hora (horas solares 1–24) del día 21 del mes de
  proyecto, por defecto julio. La **hora punta** de cada espacio es la de mayor carga
  total; la del edificio sale de la suma simultánea.
  - Temperatura exterior: T(h) = T_max − f(h)·OMDR.
    - f(h) son las fracciones de ASHRAE 2009, cap. 14, tabla 6, tal como las incorpora
      EnergyPlus (`WeatherManager.cc`, «DefaultTempRangeMult»).
    - OMDR es la oscilación media diaria de la guía del IDAE.
  - Radiación: cielo despejado de ASHRAE, I_DN = A·exp(−B/sen β), con A, B y C el día 21
    de cada mes.
    - La tabla se contrastó con la serie ajustada de EnergyPlus: diferencias de menos del
      0,2 %.
    - Geometría solar de Duffie y Beckman; difusa isótropa; reflectancia del suelo 0,2.
    - Comprobación a mano: 40° N, 21 de julio, mediodía, horizontal ≈ 939 W/m².
  - Opacos: temperatura sol-aire de ASHRAE.
    - α/h_o = 0,026 m²K/W en superficie clara y 0,052 en oscura (por defecto).
    - ε·ΔR/h_o = 3,9 K en cubiertas y 0 en fachadas.
  - Huecos: conducción U·A·ΔT más radiación A·F_H·F_S·I.
  - Personas, iluminación, equipos y proceso: instantáneos.
  - Aire exterior: sensible m·c_p·ΔT y latente m·h_fg·ΔW, con el aire húmedo de ASHRAE,
    cap. 1. La humedad interior de verano es el 50 % (RITE 45–60 %).
  - Declarado en las notas del resultado: régimen permanente, sin inercia. Es del lado de
    la seguridad, sobre todo en cerramientos pesados; en naves ligeras apenas se aparta.
- **Aire exterior más seco que el interior** (clima seco de interior peninsular): no se
  descuenta su efecto deshumectante; el latente de ventilación no baja de 0.
- **Cámaras frigoríficas**:
  - sin aire exterior de ventilación (la tabla del RITE es de locales para personas); las
    entradas de aire por puertas se meten como proceso;
  - personas con q = 272 − 6·t W, de ASHRAE Handbook – Refrigeration, cap. 24, recogida
    en apuntes universitarios
    (<https://uomus.edu.iq/img/lectures21/MUCLecture_2022_8182410.pdf>);
  - fuera de la refrigeración simultánea de climatización, porque su frío es otra
    instalación.
- **Sala de manipulación a 12 °C**: Reglamento (CE) 853/2004, anexo III, sección I,
  cap. V (salas de despiece).
- **RITE IT 1.1.4.2.2** (revisado contra el BOE): salones de actos y salas de ordenadores
  son **IDA 3**.
- **Recuperador**: eficiencia sensible sobre la ventilación (RITE IT 1.2.4.5.2 lo exige
  con más de 0,5 m³/s de extracción).
- **Infiltración**:
  - n50 = 0,629·(Co·Ao + Ch·Ah)/V, según el CTE DB HE, Anejo H.
    - Co = 16 m³/h·m² en edificio nuevo y 29 en existente.
    - Ch según la clase de ventana (UNE-EN 12207): 50 / 27 / 9 / 3. El CTE exige clase 2
      en las zonas α, A y B y clase 3 en las C, D y E.
  - V_inf = 2·V·n50·e·ε, según la UNE-EN 12831, anexo D, tomada de AixLib (documentación
    DIN 12831) y de la ayuda de DesignBuilder.
    - e, con protección moderada: 0,02 con una fachada expuesta y 0,03 con más de una.
    - ε: 1,0 hasta 10 m de altura, 1,2 hasta 30 m y 1,5 por encima.
- **Aire exterior por uso** (`usos.caudal_exterior_m3h`):
  - por persona según el IDA;
  - por superficie según el IDA;
  - 50 m³/h por trabajador (RD 486);
  - caudal fijo en quirófano;
  - 2,5 dm³/s·m² de lámina en piscinas, tomando la superficie del espacio.

### En el proyecto (`app/cargas.py`, paso «Cargas y ventilación»)
- **Qué se guarda** (esquema V5): el clima y la obra (`cargas_proyecto`) y, por espacio, el
  uso, lo que el usuario cambia y sus correcciones de fachada (`cargas_espacio`).
  - Lo propuesto no se guarda: sale del catálogo con su fuente cada vez que se calcula.
  - Así, una mejora del catálogo llega a todos los proyectos, y lo que el usuario fijó no
    cambia.
  - El cálculo es determinista a partir de lo guardado; los resultados se recalculan al
    abrir el paso y no se almacenan como propiedades. Los pasos siguientes (redes,
    equipos) llamarán a `Proyecto.calcular_cargas()`.
- **Uso propuesto por el nombre** del espacio, con palabras clave en `PALABRAS_USO`:
  - se compara por inicio de palabra, no por «contiene»: «distribución» contenía «uci»;
  - lo específico va antes que lo general, y una prueba lo vigila;
  - sin coincidencia, el espacio sale «sin uso» y no se calcula hasta elegirlo.
- **Fachadas** (`engines/envolvente.py`):
  - un lado es fachada si no tiene enfrente, a menos de 0,6 m (un grueso de muro), un
    lado paralelo de otro espacio del mismo nivel;
  - las orientaciones se agrupan en 8 sectores de 45°, con el norte del plano indicado
    una vez;
  - **cubierta**: la parte de la planta de cada espacio sin otro espacio encima, medida
    con una rejilla de 30 × 30 puntos. Cuenta como «encima» un espacio cuya cota está a
    menos de 0,5 m de su techo, o uno más bajo cuyo volumen lo envuelve (un altillo dentro
    de una nave);
  - **solera**: los espacios de la cota más baja, con la U de la losa entera (ISO 13370,
    B' de toda la planta en contacto con el terreno, no de cada local);
  - la superficie de fachada es la longitud por la altura del espacio, con los huecos
    según el % del uso.
- **Color de los cerramientos**: por defecto oscuro (α/h_o = 0,052, el máximo de ASHRAE).
  El exterior estándar del panel de cubierta de catálogo es **rojo teja (RAL 8004)**, un
  color medio-oscuro: cara exterior rojo teja y cara interior blanca en Perfimur, y
  «rojo/blanco» en los paneles de tres grecas de Obramat. El usuario elige «claro» si lo es.
- **Permeabilidad de ventanas** supuesta por tipo de construcción:
  - en obra nueva, la clase que exige el CTE;
  - en nave de panel, clase 2;
  - en chapa y edificio antiguo, clase 1.
- **Coeficiente de caudal de la parte opaca** (Co) del CTE: «nuevo» en CTE y en panel;
  «existente» en el resto.
- **Informe**:
  - Excel con las hojas Resumen, Espacios, Partidas, Datos y fuentes, Cerramientos e
    Hipótesis;
  - PDF con los datos de partida, las cargas por espacio, el desglose de verano y las
    hipótesis con sus fuentes.

- **Límites declarados**:
  - la rejilla de la cubierta puede no ver un espacio muy estrecho y girado;
  - los espacios de un mismo nivel se suponen dibujados con el mismo origen de
    coordenadas, también si vienen de planos distintos;
  - la sala de manipulación a 12 °C va con las cámaras, fuera de la simultánea de
    climatización: se enfría con la instalación de frío.

## Pendiente
- Validar con la guía del IDAE real y un proyecto del usuario.
- Cargas de producto en cámaras y de evaporación en piscinas: hoy se meten como proceso.
