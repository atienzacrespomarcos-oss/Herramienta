# Módulo: cargas térmicas y ventilación (Etapa 4)

Estado: **en desarrollo** (4.A datos de partida).

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
- **Ocupación**: CTE DB SI, tabla 2.1, en m²/persona (oficinas 10, hospitalización 15,
  alojamiento 20, comercial 2–5, restaurantes 1,5, almacenes 40…).
- **Iluminación**: CTE DB HE3, tabla 3.2: 10 W/m² con iluminancia ≤ 600 lux, 25 W/m² con
  > 600 lux y 5 W/m² en aparcamiento. Es potencia máxima: se toma como valor de cálculo.

## Pendiente de esta etapa
- 4.A Catálogo de usos con calor de las personas por actividad y equipos por uso, y
  catálogo de tipos constructivos.
- 4.B Motores de cargas de invierno y verano y de ventilación.
- 4.C Paso «Cargas y ventilación» en la ventana, con su informe.
