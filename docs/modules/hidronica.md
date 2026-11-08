# Módulo: sistema hidráulico de climatización (Etapa 7, hoja de ruta 3.6)

Estado: **en desarrollo**.

## Decisiones del usuario (08-11-2026)

| Pregunta | Decisión |
|---|---|
| Siguiente bloque | **Hidrónico** (tras ventilación sencilla). |
| Qué se quiere | «Me interesa más que los conductos que **se dimensione un sistema hidráulico en condiciones**. Recomendando picajes, tuberías y diámetros, tamaño de colectores, válvulas, etc. Propón **esquemas hidráulicos de calidad y completos. Sin omitir ninguna clase de elemento**». |
| Sistemas | **2 tubos frío/calor** y **4 tubos**. |
| Configuración por defecto | **Primario-secundario**: generador con bomba de primario y depósito de inercia (o separador), colector con un circuito secundario por grupo de unidades, cada uno con su bomba y valvulería. |
| Circuitos | **De las cargas + longitud estimada**: unidades y potencias de las cargas de los espacios; el usuario agrupa en circuitos y da la longitud aproximada de cada uno. |
| Salidas | **Esquema de principio en DXF** (simbología normalizada, diámetros y referencias) y **listado de elementos en Excel** (diámetro, caudal, presión, cantidad) para pedidos. |
| Fuera | Diseño de VRF y selección de ventiladores: «cada fabricante tiene su software». |

## Fuentes (descargadas y leídas el 08-11-2026)
- **RITE** consolidado, BOE-A-2007-15820 (<https://www.boe.es/buscar/act.php?id=BOE-A-2007-15820>):
  - IT 1.3.4.2.1: flexibles en equipos con motor > 3 kW.
  - IT 1.3.4.2.2: llenado con válvula de corte, filtro, contador y desconector (en ese
    orden), llenado manual, presostato con alarma, válvula de alivio ≥ DN 20 tarada a la
    máxima de servicio + 0,2 a 0,3 bar. Tabla 3.4.2.2 (DN de alimentación: calor/frío
    15/20 hasta 70 kW; 20/25 hasta 150; 25/32 hasta 400; 32/40 más).
  - IT 1.3.4.2.3: vaciados parciales ≥ DN 20; vaciado total por el punto más bajo,
    tabla 3.4.2.3 (calor/frío 20/25 hasta 70 kW; 25/32 hasta 150; 32/40 hasta 400;
    40/50 más); purgadores ≥ DN 15 en los puntos altos.
  - IT 1.3.4.2.4: vaso de expansión cerrado (UNE 100155, cap. 9).
  - IT 1.3.4.2.5: válvulas de seguridad (además de la de alivio) con accionamiento manual;
    dispositivo que impida arrancar sin la presión de proyecto.
  - IT 1.3.4.2.6: dilatación (UNE 100156).
  - IT 1.3.4.2.7: mariposas con desmultiplicador desde DN 100; retención de clapeta solo
    hasta DN 32; de disco con muelle de DN 40 a DN 150; de disco o motorizada > DN 150.
  - IT 1.3.4.2.8: filtro de 1 mm por circuito (velocidad de paso ≤ la de la tubería);
    0,25 mm ante válvulas automáticas > DN 15 y contadores.
  - IT 1.3.4.2.12: cada unidad terminal con válvula de cierre a la entrada y a la salida,
    una de ellas de equilibrado, y un dispositivo de regulación.
  - IT 1.2.4.2.1: aislamiento, tablas 1.2.4.2.1 a 1.2.4.2.4 (calientes y fríos,
    interior y exterior); las redes que llevan alternativamente frío y calor, con la
    condición más exigente; > 70 kW, método alternativo con estas tablas como mínimo.
  - IT 1.2.4.2.7: equilibrado en diseño con válvulas de equilibrado.
  - IT 1.2.4.3.1.5: válvulas de control con pérdida entre 0,6 y 1,3 veces la del
    elemento controlado; con caudal variable y > 70 kW, presión diferencial estabilizada.
  - IT 1.3.4.4.5.6 (> 70 kW): termómetro en colectores; manómetro en vasos; termómetro en
    el retorno de cada secundario; manómetro diferencial en cada bomba; termómetros y
    manómetros a la entrada y salida de intercambiadores; termómetros a la entrada y
    salida del agua de cada batería.
- **IDAE, Guía técnica nº 18 «Instalaciones de climatización por agua»** (2012):
  <https://www.idae.es/sites/default/files/publications/documents/documentos_18_Guia_tecnica_instalaciones_de_climatizacion_por_agua_ed78f988.pdf>
  - Ap. B: Q = P/(cp·ΔT), cp 4,18 kJ/(kg·K); salto de diseño 5 °C en frío; pérdida máxima
    **40 mm c.a./m** (≈ 392 Pa/m) y **velocidad < 1,2 m/s** por ruido; tablas de cobre
    (UNE-EN 1057) y termoplástico a 10 y 40 °C.
  - Ejemplos 4.1 y 4.2: fancoils a 7/12 °C en verano y 45/40 °C en invierno; pérdida en
    tubos = 2 (ida y vuelta) × 1,3 × tramos (**30 % por accesorios**); fancoil de conductos
    1.500 mm c.a.; intercambiador de la máquina 1 a 2 m c.a.; válvulas de equilibrado en
    todos los fancoils menos el del camino crítico.
  - 3.1.2: presión mínima de llenado tal que haya ≈ 1 bar relativo en todo el circuito;
    presión inicial del vaso 0,2–0,3 bar por debajo de la de llenado; presión de prueba
    1,5 × la máxima de trabajo, mínimo 6 bar.
  - 3.1.3: Vu = Ce·V, Ce = (3,24·T² + 102,13·T − 2.708,3)·10⁻⁶ (tabla 27: 0,0105 a
    50 °C), Vt = Vu/(Pi/Pm − Pi/PM) con presiones absolutas (ejemplo: 260 l, 50 °C,
    Pi 1,7, Pm 2, PM 3 bar abs → 2,7/(0,85 − 0,567) = 9,5 l). Volumen de la instalación =
    depósito de inercia + baterías de generadores y terminales + tuberías (tabla 26).
  - 3.1.4: dilatación Ld = Cd·L·ΔT (acero 0,012; cobre 0,017 mm/(m·°C)).
  - 2.5: volumen mínimo de agua para limitar arranques: el del fabricante.
- **IDAE, «La bomba de calor en la rehabilitación energética de edificios»** (2023):
  volumen mínimo siempre disponible mediante **depósito de inercia en paralelo como
  compensador hidráulico** (o en serie con válvula de presión diferencial).
- **ASHRAE Fundamentals 1997 (SI), cap. 33**: 1,2 m/s hasta DN 50 y 400 Pa/m por encima;
  velocidades mayores aceptables en diámetros grandes.
- **Carrier**, manuales de enfriadoras: volumen mínimo = potencia × N; N = 3,5 l/kW en
  aire acondicionado (30RA), 3,25 (30RQS), 6,5 en procesos.
- **Caleffi, Idraulica 18** (separadores hidráulicos), p. 4–6
  (<https://www.caleffi.com/sites/default/files/media/external-file/Idraulica_18_IT_I%20separatori%20idraulici%20-%20I%20collettori%20a%20pressione%20controllata.pdf>):
  método de los tres diámetros, D = 3·d, válido con velocidad en las bocas ≤ 0,9 m/s.

## Criterios elegidos (se documentan aquí, no se preguntan)
- **Tuberías**: ≤ 392 Pa/m (40 mm c.a./m, IDAE) siempre, y ≤ 1,2 m/s hasta DN 50
  (IDAE y ASHRAE); por encima de DN 50 solo el límite de pérdida (ASHRAE).
- **Colectores**: como separador de baja pérdida (Caleffi): velocidad ≤ 0,9 m/s con el
  caudal total y nunca menor que la tubería general. No se encontró un criterio
  publicado específico para colectores; se usa el del separador porque cumplen la misma
  función (pérdida despreciable entre picajes).
- **Depósito de inercia** en paralelo, con 4 bocas (compensador): volumen = volumen
  mínimo del fabricante (por defecto 3,5 l/kW, Carrier 30RA) menos el agua del primario.
  Se da el volumen mínimo; el modelo comercial lo elige el usuario. Si el primario ya
  cubre el mínimo, el depósito sigue como separador y el listado lo dice. Bocas por el
  método de los tres diámetros.
- **Altura de bombas**: tuberías 2 × 1,3 × R·L (IDAE; el 30 % cubre accesorios, filtro
  incluido) + unidad terminal + válvula de control (autoridad 1, dentro de 0,6–1,3 del
  RITE). Temperatura de cálculo: la más fría de cada modo (impulsión en frío, retorno en
  calor), agua más viscosa, del lado de la seguridad.
- **Cobre y plástico no tienen DN**: los umbrales del RITE (tipo de válvula, retención,
  filtro de 0,25 mm) se comparan con su diámetro interior, que es lo que el DN aproxima; en
  el listado se piden por su medida («22×1»).
- **Llenado y vaciado**: el DN de alimentación, por la potencia de toda la instalación
  (la tabla 3.4.2.2 habla de la instalación); el de vaciado total, por la del circuito de
  cada generador (la 3.4.2.3 habla del circuito). Umbral de 70 kW (medida, PICV): potencia
  de toda la instalación (frío + calor en 4 tubos).
- **Bombas**: cada una con válvulas de corte para desmontarla, retención, manómetro
  diferencial y manguitos antivibratorios (RITE IT 1.3.4.2.1.2 los exige con motor > 3 kW;
  por debajo se ponen como recomendados y el listado lo dice).
- **Dilatación del plástico**: según el fabricante del tubo (la guía IDAE no da
  coeficiente; RITE IT 1.3.4.2.6.5, códigos del CTN 53).
- **Un espacio solo puede estar en un circuito** del sistema: si no, su carga se sumaría
  dos veces (la orden lo rechaza).
- **Aislamiento** (RITE, tablas transcritas del BOE; λ = 0,040 W/(m·K); diámetro exterior
  ≤ 35 / ≤ 60 / ≤ 90 / ≤ 140 / > 140 mm):

  | Tabla | Fluido | Espesores (mm) |
  |---|---|---|
  | 1.2.4.2.1 interior | caliente 40–60 °C | 25 / 30 / 30 / 30 / 35 |
  | 1.2.4.2.1 interior | caliente > 60–100 °C | 25 / 30 / 30 / 40 / 40 |
  | 1.2.4.2.2 exterior | caliente 40–60 °C | 35 / 40 / 40 / 40 / 45 |
  | 1.2.4.2.2 exterior | caliente > 60–100 °C | 35 / 40 / 40 / 50 / 50 |
  | 1.2.4.2.3 interior | frío > 0–10 °C | 25 / 30 / 30 / 40 / 40 |
  | 1.2.4.2.3 interior | frío > 10 °C | 20 / 20 / 30 / 30 / 30 |
  | 1.2.4.2.4 exterior | frío > 0–10 °C | 45 / 50 / 50 / 60 / 60 |
  | 1.2.4.2.4 exterior | frío > 10 °C | 40 / 40 / 50 / 50 / 50 |
- **Tubos** (diámetro exterior × espesor, mm):
  - **acero negro UNE-EN 10255 serie media M** (lo habitual en salas de máquinas y
    distribución), según la tabla de compatibilidad Megapress de Viega
    (<https://www.viega.it/content/dam/viegadm/en/temp/download_assets/it/tabelle_compatibilit_megapress.pdf>):
    DN15 21,3×2,6; DN20 26,9×2,6; DN25 33,7×3,2; DN32 42,4×3,2; DN40 48,3×3,2;
    DN50 60,3×3,6; DN65 76,1×3,6; DN80 88,9×4,0; DN100 114,3×4,5; DN125 139,7×5,0;
    DN150 165,1×5,0. Por encima de DN150 la herramienta avisa (tubo de la UNE-EN 10216/10217
    a definir con el suministrador).
  - **cobre UNE-EN 1057** (tablas de la guía IDAE nº 18): 12×1; 15×1; 18×1; 22×1;
    25×1,5; 28×1,5; 35×1,5; 42×1,5; 54×2.
  - **termoplástico** (tablas de la guía IDAE nº 18): 12×0,7; 16×0,9; 20×1,2; 25×1,5;
    32×1,9; 40×2,4; 50×2,9; 63×3,7.
- **Rugosidad**: cobre 0,002 mm y termoplástico 0,006 mm (guía IDAE nº 18, al pie de sus
  tablas); acero comercial 0,045 mm (diagrama de Moody, tablas usuales de rugosidad).
- **Comprobación del motor**: el ejemplo del Ap. B de la guía IDAE nº 18, fancoil de
  5 kW (0,238 l/s) en cobre 22×1 a 10 °C: v = 0,76 m/s y 44 mm c.a./m.
- **Volumen mínimo**: solo cuenta el agua del primario (tuberías del primario y depósito).
  Con válvulas de 2 vías cerradas, la de los secundarios no llega al generador, y la guía
  IDAE de la bomba de calor (2023) pide el volumen mínimo «cualquiera que sea el estado de
  los elementos terminales».
- **Presiones** (vaso en la sala, punto bajo): llenado = 1 bar + altura (1 bar en el punto
  alto); precarga del vaso 0,3 bar menos; máxima = llenado + 1 bar; válvula de seguridad =
  máxima + 0,5 bar (las relaciones de los tres ejemplos de la guía IDAE nº 18, 3.1.2);
  alivio = máxima + 0,3 bar (RITE IT 1.3.4.2.2; los ejemplos IDAE usan + 0,5, se sigue el
  RITE); prueba 1,5 × máxima, mínimo 6 bar; PN normalizado por encima de la seguridad.
- **Vaso**: temperaturas de 5 a 45 °C (IDAE nº 18, 3.1.4), o la de impulsión de calor si
  es mayor; volumen = tuberías + depósito de inercia (los equipos, del fabricante).
- **Válvulas**: de corte de bola hasta DN50 y de mariposa por encima (con desmultiplicador
  desde DN100, RITE); en las unidades, de control de 2 vías con Kv para autoridad 1 y, por
  encima de 70 kW (caudal variable), independientes de la presión (RITE IT 1.2.4.3.1.5).
- **Secundarios** de caudal variable: válvulas de 2 vías y bombas de velocidad variable.

## En el proyecto (`app/hidronica.py`, paso «Sistema hidráulico», menú «Agua»)
- **Qué se guarda** (esquema V8, tabla `sistema_hidraulico`): nombre, tipo (2 o 4 tubos),
  tubería, temperaturas, altura de la instalación sobre la sala, longitud del primario,
  volumen mínimo del generador (l/kW) y los circuitos en JSON (nombre, espacios, unidades,
  longitud de ida, pérdida de la unidad en kPa, exterior).
- **Potencias**: las cargas de los espacios de cada circuito (verano y invierno), sin
  simultaneidad. Sin cargas no hay sistema que calcular; un circuito sin potencia se deja
  fuera con aviso.
- **2 tubos**: un servicio frío/calor (bomba de calor reversible) dimensionado para el
  modo de más caudal. **4 tubos**: dos servicios independientes, cada uno con su
  generador, primario, inercia, vaso y circuitos.
- **En pantalla** (presentación limpia): «Sala de máquinas» (generador, primario,
  colectores, inercia, vaso, presiones), «Circuitos» y «Elementos».
- **Excel**: Resumen, Circuitos, Elementos (zona, elemento, especificación, medida, cantidad,
  norma o fuente) e Hipótesis.

## Pendiente
- **Esquema de principio en DXF** (decisión del usuario): siguiente entrega (7.B).
- Validar con un proyecto real del usuario.
- Volúmenes de agua de generador y unidades: hoy no se conocen y no entran en el vaso.
