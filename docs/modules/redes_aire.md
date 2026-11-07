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
- Coeficientes del **manual Climaver, pp. 53–55**, que son los de ASHRAE para chapa:
  - codo de radio uniforme (C′, K_Re y K_θ);
  - reducción;
  - Y simétrica;
  - codo achaflanado;
  - codo a bisel;
  - piezas en Z;
  - bordeo de obstáculo;
  - derivación con radio;
  - derivación a bisel (C_d y C_s).
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
  Se toman como pérdida por defecto de difusores y rejillas.
- **RITE IT 1.2.4.2.5**, potencia específica de ventiladores (SFP, tabla 2.4.2.7):
  - en impulsión, SFP 4 (≤ 2000 W/(m³/s)) en climatización y SFP 3 en ventilación;
  - en extracción, SFP 3 en climatización y SFP 2 en ventilación.
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
  - ΔT de impulsión = 10 K, el salto típico: ASHRAE impulsa a unos 13 °C con el local a
    24 °C, es decir, unos 11 K. Se toma algo menos, del lado de más caudal.
- **Retorno** de un espacio: su impulsión menos su aire exterior.
- **Extracción**: el aire exterior del espacio.
- **Reparto**: a partes iguales entre los terminales del espacio. El atributo CAUDAL del
  bloque, si lo tiene, manda.
