# Módulo: control de la instalación

Estado: **implementado**. Parte 1: propuesta de categorías, puntos y comprobaciones. Parte 2:
esquemas de control en DXF con su secuencia de funcionamiento.

## Decisiones del usuario (11-11-2026)

| Pregunta | Decisión |
|---|---|
| ¿Control dentro del alcance? | «El control sí es importante». |
| Qué debe hacer | «Debe proponer cosas en caso de no existir y, en caso de que sí, sacar esquemas si no hay (hay el qué pero no el cómo)». |

Por tanto:
- **Parte 1 (hecha)**: sin control definido, TRAZA lo **propone** desde lo diseñado.
- **Parte 2 (hecha)**: con un listado de puntos (el propuesto o uno que el usuario ya
  tenga), TRAZA dibuja los **esquemas de control** («el cómo»).

## Fuente normativa
**RITE** (RD 1027/2007), texto consolidado del BOE, **IT 1.2.4.3** (leída el 11-11-2026):
- **IT 1.2.4.3.1** (control de las instalaciones de climatización):
  - **.1**: regulación separada de la temperatura en cada espacio (edificios nuevos);
  - **.2**: control todo-nada solo en casos tasados;
  - **.5**: válvulas de control con pérdida de 0,6 a 1,3 veces la del elemento controlado;
    con caudal variable y **más de 70 kW** de generación total, presión diferencial
    estabilizada sobre la válvula;
  - **.6**: temperatura del agua de calor según el exterior;
  - **.7**: impulsión de frío constante;
  - **.10**: ventiladores de **más de 5 m³/s**, medición y control del caudal de aire.
- **IT 1.2.4.3.2, tabla 2.4.3.1**: categorías **THM-C0 a C5**; equipamiento mínimo en el
  apartado 3.
- **IT 1.2.4.3.3, tabla 2.4.3.2**: categorías **IDA-C1 a C6**. El apartado 3 dice que
  IDA-C2, C3 y C4 se emplean en locales **no** diseñados para ocupación humana permanente.
  El apartado 4 dice que IDA-C6 se emplea en locales de **ocupación variable** («teatros,
  cines, salones de actos, aulas, recintos para el deporte y similares»).

## Método (decisiones de TRAZA, `engines/control.py` y `rules/control.py`)

### Categoría THM-C por espacio
- **THM-C3** si la instalación da frío y calor.
- **THM-C1** si solo da calor.
- **THM-C5** en el quirófano: la UNE 100713 fija la humedad relativa del local (45–55 %).
- Las cámaras frigoríficas (uso sin temperatura de invierno) no llevan categoría: las
  regula su equipo frigorífico.
- Sin sistema hidráulico, TRAZA no sabe con qué se climatiza (la expansión directa queda
  fuera de su diseño). En ese caso supone frío y calor (THM-C3) y lo dice en un aviso.

### Categoría IDA-C por espacio, según la ocupación del uso
| Ocupación | Usos | Propuesta | Por qué |
|---|---|---|---|
| Variable | reuniones, salón de eventos, gimnasio, comedor, restaurante, sala de espera, piscina | **IDA-C6** | Obligatorio (apartado 4). Estos usos son los «similares» del catálogo: elección de TRAZA. |
| No permanente | los de ventilación por superficie (pasillos, aseos, almacenes sin personal, salas técnicas) | **IDA-C3** (horario) | Valen C2, C3 o C4 (apartado 3). |
| Permanente, con IDA por persona | oficinas, despachos, comercio, sanitario… | **IDA-C6** (CO₂) | C2, C3 y C4 no valen; entre C1, C5 y C6, la sonda de CO₂ ajusta el aire exterior a la ocupación real. |
| Permanente, por trabajador o fijo | producción, almacenes con personal, quirófano | **IDA-C1** | Continuo durante la actividad; C5 o C6 también valen. |

### Puntos de control (E/S)
- Tipos: **ED** (entrada digital), **SD** (salida digital), **EA** (entrada analógica) y
  **SA** (salida analógica).
- Lo que exige el RITE lleva su artículo. El resto se marca «Propuesta (práctica
  habitual)» y se confirma con el integrador.

**Zonas**
- Temperatura ambiente EA (IT .1).
- Humedad EA si la categoría es THM-C2, C4 o C5.
- CO₂ EA si la categoría es IDA-C6.

**Redes de aire**
- Ventilador: marcha SD, estado ED, fallo ED y velocidad SA.
- Impulsión: colmatación de filtros ED; con climatización, además temperatura de
  impulsión EA.
- Con más de 18 000 m³/h, medición del caudal EA (IT .10; el umbral es estricto).

**Hidráulica, por servicio**
- Generador: marcha SD, estado ED, alarma ED, consigna de impulsión SA, y temperaturas de
  impulsión y retorno EA.
  - En frío, la consigna constante es exigencia (IT .7).
  - En calor, la curva según el exterior es propuesta: el .6 obliga con generadores
    estándar, de baja temperatura y de condensación, y TRAZA no sabe el tipo (suele ser una
    bomba de calor).
- Bomba de primario: marcha SD, estado ED y fallo ED.

**Hidráulica, por circuito**
- Bomba: marcha SD, estado ED, fallo ED y velocidad SA (secundarios de caudal variable,
  como en `hidronica.md`).
- Presión diferencial EA, para el mando de la bomba.
- Temperatura de impulsión EA.
- Una válvula de control SA por unidad: de 2 vías, o PICV si el **sistema** pasa de 70 kW.
  Con 4 tubos cuenta frío + calor, el mismo umbral que el esquema hidráulico.

**General**
- Temperatura exterior EA (propuesta: curvas de calor y secuencias).

### Comprobaciones
Dos revisiones del 11-11-2026 encontraron que todas las filas salían CUMPLE sin poder
fallar: comprobaban la propia propuesta. Incluso la de válvulas era circular, porque el Kv
del sistema hidráulico se dimensiona con la pérdida de la unidad. Ahora cada fila dice lo
que es:

- **«Incluida en la propuesta»**: exigencia del RITE que la propuesta ya recoge con su
  sonda, su categoría, su punto o su Kv. Sirve para justificar y no es una verificación.
  - Sonda de temperatura en cada espacio (IT .1).
  - IDA-C6 en los locales de ocupación variable (IT 1.2.4.3.3.4).
  - Nunca C2, C3 o C4 con ocupación permanente (IT 1.2.4.3.3.3).
  - Válvulas de control con relación 1 entre 0,6 y 1,3 (IT .5). La relación se recalcula
    con el Kv, Δp = 10⁵·(q/Kv)².
  - PICV por encima de 70 kW (IT .5).
  - Medición de caudal en ventiladores de más de 5 m³/s (IT .10).
- **NO CUMPLE**: un dato del proyecto impide la exigencia. Por ejemplo, una unidad con
  0 kPa de pérdida, que el sistema hidráulico admite: su válvula no se puede dimensionar.
- **CUMPLE**: queda para cuando haya un dato independiente que verificar, como un Kv
  comercial elegido. Hoy no lo hay.
- **«No aplica»**: el proyecto no tiene ese caso.

En pantalla se ve lo que NO CUMPLE y cuántas exigencias del RITE recoge la propuesta.

### Esquemas de control (parte 2; `io/esquema_control_dxf.py`)
DXF R2013 (AutoCAD 2013), sin escala, en mm de papel, como el esquema hidráulico y el
unifilar. Una banda por sistema (zonas, cada red de aire, cada servicio hidráulico):
- **Equipos**: cada uno en un recuadro, con sus señales.
- **Señales**: cada una con su símbolo, su texto y una línea de trazos hasta el
  controlador del sistema, rotulada con su tipo (y «×n» si son varias).
  - Las entradas van en círculo y las salidas en cuadrado.
  - El rótulo (T, HR, CO₂, ΔP, Q, P, E, F; C, VF, V, M) sale del texto de la señal y de
    su tipo (`engines/control.simbolo`), con lo específico antes que lo general.
  - En las entradas digitales, el fallo va antes que la magnitud («Alarma temperatura
    alta» es F). En las salidas digitales, la marcha va antes que el equipo («Orden de
    marcha del variador» es M).
  - La señal larga va en dos líneas y el recuadro del equipo crece hasta que cabe su
    nombre. El controlador tiene altura mínima para su recuento.
  - Se explica en la leyenda del propio dibujo: no se usan letras ISA, para no atribuir
    a la norma un código que no se ha comprobado.
- **Controlador**: un recuadro por sistema con el recuento ED/SD/EA/SA.
- **Secuencia de funcionamiento** («el cómo»), debajo de cada banda: lo que exige el RITE
  lleva su artículo y lo demás termina en «(propuesta)».
  - Zonas: temperatura por espacio (IT .1; la válvula de la unidad, propuesta); cada zona
    fuera de servicio por horario (IT .4); IDA-C6 con CO₂ o COV (tabla 2.4.3.2); humedad,
    con el equipamiento mínimo de la categoría (IT 1.2.4.3.2.3). Cómo actúa la sonda sobre
    la humectación es propuesta.
  - Redes: horario (IT .4), variador, filtros y caudal por encima de 5 m³/s (IT .10).
  - Hidráulica: impulsión de frío constante (IT .7), curva de calor (propuesta; IT .6
    con calderas), cambio de temporada con 2 tubos, primario con el generador, bombas de
    circuito a presión diferencial, presión diferencial estabilizada por encima de 70 kW
    (IT .5; con PICV, propuesta: el RITE no fija la tecnología) y circuitos fuera de
    servicio por horario (IT .4).
  - Revisión del 11-11-2026: al RITE solo se le atribuye lo que dice su texto; el medio
    (válvula, variador, PICV) es propuesta.

**Desde un listado del usuario** («hay el qué pero no el cómo»; `io/puntos_control.py`):
- Formato: Excel, .xls o CSV, sin plantilla.
- Columnas por su título: señal y tipo, obligatorias; equipo, sistema y cantidad.
  - Entre dos columnas para el mismo dato gana el sinónimo más específico («Señal» antes
    que «Descripción»).
  - «Tipo de equipo» no es el tipo de la señal.
  - «Nº» no es la cantidad: numerar las filas falseaba los recuentos.
  - Los saltos de línea de una celda se quedan en una sola línea.
- Tipos aceptados: ED/SD/EA/SA y DI/DO/AI/AO, BI/BO (BACnet).
- Lo que no se entiende (un tipo desconocido, una cantidad que no es un entero) **no se
  adivina**: la fila no entra y se dice cuál es.
- El esquema sale sin secuencia, porque TRAZA no sabe qué equipos son. El listado no se
  guarda en el proyecto.

## En el proyecto
- `app/control.py` y `Proyecto.propuesta_control()`: toman las cargas, las redes y los
  sistemas hidráulicos calculados. Lo que no se calcula se dice en un aviso.
- No se guarda nada: se recalcula con el proyecto y nunca está desactualizado.
- Paso **«Control»** (menú **Control**):
  - el resumen muestra los puntos por tipo y el resultado del RITE;
  - las pestañas son Comprobaciones, Categorías por espacio y Puntos.
- La página se calcula solo cuando está a la vista, porque la ventana refresca todas las
  páginas a cada cambio.
- **Excel**: hojas Resumen, Categorías, Puntos, Comprobaciones e Hipótesis.
- **Esquema de control (DXF)**, desde el menú Control. Entregables genera el Excel y el
  esquema si hay redes o sistemas hidráulicos.
- **«Esquema desde un listado de puntos…»**: se elige el fichero y el destino; lo que no
  entra se lista al terminar.
- Estado del paso: pendiente mientras no haya ninguna red ni sistema hidráulico.

## Validación
- Las categorías se comprueban contra el texto del RITE.
- La relación de las válvulas se comprueba con Kv calculados a mano: dentro del rango,
  límite de 1,3, 0,5 fuera de rango y unidad sin pérdida. En el proyecto real, la unidad
  sin pérdida sale NO CUMPLE (`tests/ui/test_paso_control.py`).
- Los recuentos de puntos se cuentan a mano en `tests/unit/test_control.py`.
- Los umbrales de 5 m³/s y de 70 kW se prueban en el límite.
- Un test ata los usos del control al catálogo de usos.
- Esquemas (`tests/unit/test_esquema_control.py`):
  - toda señal de la propuesta tiene un símbolo propio;
  - cada frase de la secuencia cita el RITE o dice «(propuesta)»;
  - el lector toma títulos bajo un encabezado, siglas inglesas y CSV, y rechaza con
    aviso lo que no entiende;
  - el DXF es R2013, con un círculo por entrada, una línea de trazos por señal y el
    recuento del controlador.
- No hay un ejemplo resuelto publicado de listado de puntos: el listado es una propuesta,
  no un cálculo.
