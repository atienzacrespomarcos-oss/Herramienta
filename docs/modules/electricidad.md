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
- **GUÍA-BT Anexo 2 «Cálculo de las caídas de tensión»** (sep. 2003, rev. 1),
  <https://www.plcmadrid.es/wp-content/uploads/guia_bt_anexo_2_sep03R1.pdf>:
  - trifásico e = P·L/(γ·S·U), monofásico e = 2·P·L/(γ·S·U) (U = 400 V o 230 V),
    despreciando la reactancia hasta 120 mm²; por encima, X ≈ 0,15 R (150), 0,20 R (185) y
    0,25 R (240): ΔU = (R + X·tg φ)·P/U;
  - conductividad del cobre γ = 56 / 48 / 44 m/(Ω·mm²) a 20 / 70 / 90 °C.
- **GUÍA-BT-22** (oct. 2005, rev. 1),
  <https://www.plcmadrid.es/wp-content/uploads/rebt/itc22/guia_bt_22_oct05R1.pdf>:
  protección contra sobrecargas con **Ib ≤ In ≤ Iz** e **I2 ≤ 1,45·Iz**; con interruptores
  UNE-EN 60898 o 61009, I2 = 1,45·In (la segunda condición se cumple sola). Curvas B
  (3–5 In), **C (5–10 In)** y **D (10–20 In, arranque de motores)**.
- **Calibres de interruptores automáticos**: catálogo de aparamenta modular de General
  Electric (ElfaPlus EP60/EP100/EP250)
  (<https://documentacion.generadordeprecios.info/documentaciontecnica/generalelectric/ge_aparam_modular.pdf>):
  6, 10, 13, 16, 20, 25, 32, 40, 50, 63, 80, 100 y 125 A (modular), 160 A (caja moldeada).

## Criterios elegidos
- **Cable** por defecto RZ1-K 0,6/1 kV (XLPE) multipolar en **bandeja perforada** (método
  E), con el factor de agrupamiento de la tabla E por el número de líneas de la bandeja;
  también tubo en superficie (B2) o sobre pared (C).
- **Caída de tensión** con γ del cobre a 90 °C (XLPE) o 70 °C (PVC), del lado de la
  seguridad; límite del 5 % (6,5 % con transformador propio) **sumando la de la línea que
  alimenta el subcuadro**.
- **Sección**: la menor normalizada que cumple Iz·factor ≥ In (que ya es ≥ Ib) y la caída
  de tensión; motores con Ib al 125 % (ITC-BT-47).
- **Protección**: magnetotérmico de la serie de calibres, curva D en motores (bombas,
  ventiladores, compresores) y C en el resto; diferencial por salida.
