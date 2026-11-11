# Módulo: control de la instalación

Estado: **parte 1 implementada** (propuesta de categorías, puntos y comprobaciones). Parte 2
pendiente: esquemas de control en DXF.

## Decisiones del usuario (11-11-2026)

| Pregunta | Decisión |
|---|---|
| ¿Control dentro del alcance? | «El control sí es importante». |
| Qué debe hacer | «Debe proponer cosas en caso de no existir y, en caso de que sí, sacar esquemas si no hay (hay el qué pero no el cómo)». |

Por tanto:
- **Parte 1 (hecha)**: sin control definido, TRAZA lo **propone** desde lo diseñado.
- **Parte 2 (pendiente)**: con un listado de puntos (el propuesto o uno que el usuario ya
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
Hay dos clases de fila (revisión del 11-11-2026: al principio todas salían CUMPLE, y la
mayoría no podía fallar porque comprobaban la propia propuesta).

**Se calcula: CUMPLE / NO CUMPLE**
- Válvulas de control (IT .5). La pérdida de la válvula abierta al caudal de proyecto se
  calcula con su Kv, Δp = 10⁵·(q/Kv)², que es la definición del Kv. Se divide entre la
  pérdida de la unidad y la relación debe estar entre 0,6 y 1,3.
- Con el Kv del sistema hidráulico la relación sale 1. Una unidad sin pérdida (Kv 0) sale
  NO CUMPLE.

**«Incluida en la propuesta»**: exigencias del RITE que la propuesta ya recoge con su
sonda, su categoría o su punto. Sirven para justificar; no se cuentan como CUMPLE.
- Sonda de temperatura en cada espacio (IT .1).
- IDA-C6 en los locales de ocupación variable (IT 1.2.4.3.3.4).
- Nunca C2, C3 o C4 con ocupación permanente (IT 1.2.4.3.3.3).
- PICV por encima de 70 kW (IT .5).
- Medición de caudal en ventiladores de más de 5 m³/s (IT .10).

**«No aplica»**: el proyecto no tiene ese caso.

La pantalla resume solo lo calculado y cuenta aparte las exigencias incluidas.

## En el proyecto
- `app/control.py` y `Proyecto.propuesta_control()`: toman las cargas, las redes y los
  sistemas hidráulicos calculados. Lo que no se calcula se dice en un aviso.
- No se guarda nada: se recalcula con el proyecto y nunca está desactualizado.
- Paso **«Control»** (menú **Control**):
  - el resumen muestra los puntos por tipo y el resultado del RITE;
  - las pestañas son Comprobaciones, Categorías por espacio y Puntos.
- La página se calcula solo cuando está a la vista, porque la ventana refresca todas las
  páginas a cada cambio.
- **Excel**: hojas Resumen, Categorías, Puntos, Comprobaciones e Hipótesis. También sale en
  **Entregables** si hay redes o sistemas hidráulicos.
- Estado del paso: pendiente mientras no haya ninguna red ni sistema hidráulico.

## Validación
- Las categorías se comprueban contra el texto del RITE.
- La relación de las válvulas se comprueba con Kv calculados a mano (CUMPLE, límite de 1,3,
  0,5 fuera de rango y unidad sin pérdida).
- Los recuentos de puntos se cuentan a mano en `tests/unit/test_control.py`.
- Los umbrales de 5 m³/s y de 70 kW se prueban en el límite.
- Un test ata los usos del control al catálogo de usos.
- No hay un ejemplo resuelto publicado de listado de puntos: el listado es una propuesta,
  no un cálculo.
