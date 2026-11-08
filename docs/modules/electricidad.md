# Módulo: subcuadros eléctricos de clima (Etapa 8)

Estado: **en desarrollo**.

## Decisiones del usuario (08-11-2026)

| Pregunta | Decisión |
|---|---|
| Siguiente bloque | **Electricidad BT** (tras el sistema hidráulico). |
| Alcance | «Yo solo funciono con **subcuadros de clima**. Lo de detrás me da igual»: el cuadro general y la acometida quedan fuera; la línea que alimenta el subcuadro es un dato. |
| Suministro | **Los dos, por proyecto**: BT de compañía o centro de transformación propio (cambia los límites de caída de tensión, REBT ITC-BT-19). |
| Salidas | **Esquema unifilar en DXF**. |

## Propuesta de funcionamiento (se documenta, no se pregunta)
- Un subcuadro por sistema de clima (o los que el usuario defina) con una salida por
  equipo: generadores, bombas, ventiladores/UTA/extractores y grupos de unidades
  terminales.
- Los receptores se proponen desde los equipos ya dimensionados en la herramienta; la
  potencia eléctrica la ajusta el usuario con la ficha del modelo elegido en el software
  del fabricante.
- Cálculo por línea: intensidad, sección por intensidad admisible y por caída de tensión,
  protección magnetotérmica y diferencial, con las reglas de motores (ITC-BT-47).

## Fuentes (descargadas y leídas el 08-11-2026)
- **REBT** (RD 842/2002), texto consolidado BOE-A-2002-18099
  (<https://www.boe.es/buscar/act.php?id=BOE-A-2002-18099>):
  - **ITC-BT-19 2.2.2**: caída de tensión máxima, en instalaciones no de vivienda, **3 %
    alumbrado y 5 % demás usos**; con **transformador propio**, desde su salida, **4,5 % y
    6,5 %**. Se calcula con todos los aparatos que puedan funcionar a la vez.
  - **ITC-BT-19 2.2.3**: intensidades admisibles según UNE 20460-5-523 y su anexo nacional.
  - **ITC-BT-19 tabla 2**: conductor de protección S ≤ 16 → S; 16 < S ≤ 35 → 16;
    S > 35 → S/2.
  - **ITC-BT-19 2.7**: dispositivo de corte en carga en cuadros secundarios y en cualquier
    receptor; corte omnipolar en cuadros y receptores de más de 1.000 W.
  - **ITC-BT-47**: conductores de un motor al 125 % de su intensidad a plena carga; de
    varios motores, 125 % del mayor más la plena carga de los demás.
- **Ministerio de Industria, Guía técnica de aplicación GUÍA-BT-19** (feb. 2009, rev. 2),
  reproducida en <https://www.plcmadrid.es/wp-content/uploads/guia_bt_19_feb09R2.pdf>:
  - **Tabla A**: intensidades admisibles de cables de cobre no enterrados, 40 °C, que repite
    la tabla A.52-1 bis de la UNE 20460-5-523:2004 (la guía recomienda esta edición frente a
    la tabla 1 del REBT, de 1994). Columnas 2 a 13 y su asignación por método (leída con la
    posición de cada celda en la página 10 del PDF):

    | Método | 3×PVC | 2×PVC | 3×XLPE | 2×XLPE |
    |---|---|---|---|---|
    | A1 | 3 | 4 | 6 | 7 |
    | A2 | 2 | 3 | 5 | 6 |
    | B1 | 5 | 6 | 8 | 10 |
    | B2 | 4 | 5 | 7 | 8 |
    | C | 6 | 8 | 9 | 11 |
    | E | 7 | 9 | 10 | 12 |
    | F | 8 | 10 | 11 | 13 |

  - **Tabla E** (A.52-3), agrupamiento de circuitos en capa única: en bandeja perforada
    1,00 / 0,90 / 0,80 / 0,75 / 0,75 / 0,70 para 1 / 2 / 3 / 4 / 6 / 9 circuitos (sin más
    reducción por encima de 9); sobre pared 1,00 / 0,85 / 0,80 / 0,75 / 0,70 / 0,70.
  - La tabla A da en 400 mm² columna 9 un valor (699 A) fuera de la serie (552 → 645): se
    toma como errata y la herramienta llega hasta 300 mm², más que suficiente para salidas
    de un subcuadro de clima.
