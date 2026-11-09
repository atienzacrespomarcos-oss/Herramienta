# Flujo de trabajo de la herramienta

Estado: **decidido** (09-11-2026); se construye por bloques. **Bloque 1 implementado** (09-11-2026).

## Decisiones del usuario (09-11-2026)

| Pregunta | Decisión |
|---|---|
| Pedidos | **Fuera**: «Ya te dije que olvidaras pedidos». |
| Cómo llegan los encargos | **Plano del cliente y diseño yo**, **proyecto ajeno a ofertar** y **ampliación de una instalación existente**. «Solo ejecución», no. |
| Tipos de encargo | **Diseño · Oferta · Ampliación** (sustituyen a «diseño + presupuesto + instalación», «presupuesto + instalación» y «solo instalación»). |
| Recorrido | **Pasos con estado**: cada paso marca hecho / pendiente / desactualizado (si cambia algo de un paso anterior, avisa de lo que hay que revisar) y dice qué falta para el siguiente. |
| Ampliación | **Diseñar la parte nueva** sobre el plano existente. |
| Oferta | **También recalcular**: además de leer y revisar el presupuesto, rehacer cargas, redes o cuadros para detectar errores del proyecto antes de ofertar. |
| Planos nuevos | «Quiero poder yo **proponer planos de ampliación o modificación y que se recalcule todo**»: en cualquier encargo se carga un plano revisado (o uno de ampliación) y todo lo que depende de él se recalcula y se marca para revisar. |
| Orden de los bloques | **1 → 2 → 3** (encargos y estado; entregables y memoria; oferta con recálculo). |
| Tabla de pasos por encargo | **Así** (la de abajo). |
| Entregables de un diseño | **Planos DXF/LISP**, **Excel de cálculo** y **memoria técnica en Word editable** (.docx). Presupuesto/BC3 del diseño, no. |

## Pasos por tipo de encargo

| Paso | Diseño | Oferta | Ampliación |
|---|---|---|---|
| Documentación | ✓ | ✓ | ✓ |
| Planos y espacios | ✓ | ✓ (para recalcular) | ✓ (zonas nuevas marcadas) |
| Cargas y ventilación | ✓ | ✓ | ✓ (zonas nuevas) |
| Redes de aire | ✓ | ✓ | ✓ |
| Sistema hidráulico | ✓ | ✓ | ✓ |
| Subcuadros de clima | ✓ | ✓ | ✓ |
| Mediciones y ofertas | — | ✓ | — |
| Modificados | — | ✓ | — |
| Equipos | ✓ | ✓ | ✓ |
| Entregables (DXF/LISP, Excel, memoria) | ✓ | — | ✓ |

## Estado de cada paso
- **Pendiente**: le falta lo que necesita (p. ej. Cargas sin espacios confirmados), y lo
  dice: «Falta: confirmar espacios en Planos».
- **Hecho**: tiene datos y calcula sin error.
- **Desactualizado**: algo de un paso del que depende ha cambiado después (cargas →
  redes, hidráulica, cuadros); se marca hasta que se revise.
- Dependencias: Planos → Cargas → Redes de aire y Sistema hidráulico → Subcuadros →
  Entregables.

## Plan de entrega (por bloques)
1. **Encargos y pasos con estado**: los tres tipos nuevos (los proyectos existentes se
   pasan al más parecido), los pasos de cada tipo, el estado y «qué falta»; en ampliación,
   espacios marcados como existentes o nuevos; **plano revisado o de ampliación**: se
   carga y se recalcula todo lo que depende de él (espacios, cargas, redes, hidráulica,
   cuadros), con lo que cambia marcado para revisar.
2. **Entregables y memoria técnica**: un paso que saca de una vez los DXF/LISP y Excel de
   todo el diseño a una carpeta, y la memoria en Word con cada cálculo justificado por su
   norma.
3. **Oferta con recálculo**: comparar lo que dice el proyecto ajeno (mediciones,
   secciones, potencias) con lo que calcula la herramienta y listar las diferencias.

## Cómo está hecho el bloque 1 (decisiones de método, 09-11-2026)

### Encargos
- Tres tipos: `diseno`, `oferta`, `ampliacion`. Los proyectos anteriores con «presupuesto +
  instalación» o «solo instalación» pasan a **Oferta** (migración V10).
- Pasos visibles: la tabla de arriba. «Entregables» llega en el bloque 2.

### Estado de cada paso (`app/flujo.py`)
- Marca en la lista de pasos: **✓** hecho, **○** pendiente, **⚠** desactualizado; al
  pasar el ratón, lo que falta o lo que ha cambiado. Equipos no tiene estado.
- **Pendiente**: le faltan datos («Falta: leer el plano DXF», «Falta: el clima y la obra»,
  «Falta: definir un sistema hidráulico»…) o un elemento no se calcula (««Nave» no se
  calcula: …»).
- **Desactualizado**: un paso del que depende (Planos → Cargas → Redes de aire y Sistema
  hidráulico → Subcuadros) ha cambiado después del último cambio propio o de la última
  revisión. Se quita cambiando el paso o con **Ver → Dar por revisado este paso** (se
  puede deshacer).
- Lo que cuenta como «cambio» sale del registro de cambios. Un cambio hecho por la misma
  orden que cambió un paso anterior no cuenta como revisión del paso (al revisar el plano,
  la red pasa al plano nuevo, pero nadie ha revisado la red).
- Deshacer un cambio también es un cambio: lo que dependía sigue marcado hasta revisarlo
  (preferible a darlo por bueno sin mirar).
- El estado **no lee la guía del IDAE** (tarda segundos y la lista se refresca a cada
  cambio): hasta pulsar «Calcular» en Cargas, Cargas, Redes e Hidráulica se dan por hechos
  si tienen sus datos; después, además, tienen que calcular.

### Plano revisado o de ampliación (Planos → «Plano revisado o de ampliación…»)
- Se elige el DXF nuevo (incorporado antes en Documentación). Tiene que tener las mismas
  capas que el plano al que sustituye; se lee con la misma unidad.
- **Emparejamiento** (`app/planos.emparejar`): un espacio u obstáculo confirmado es «el
  mismo» que el contorno del revisado del mismo papel que contiene un punto interior suyo
  y cuyo punto interior está dentro de él (se solapan de verdad); entre varios, el de
  superficie más parecida. Punto interior: el centroide o, si cae fuera (L, U), el centro
  del primer tramo interior de una horizontal. Los handles no sirven: AutoCAD u otro
  programa los renumera al guardar.
- Antes de aplicar se enseña el resumen: sin cambios, los que **cambian** (superficie antes
  → después), los que **ya no están** (se quitan) y cuántos **contornos nuevos** hay para
  confirmar. Tolerancia de «sin cambios»: 0,01 m² y 0,01 m.
- Al aceptar, una sola orden (se deshace entera): plano nuevo con las mismas capas; cada
  elemento conserva su identidad (cargas, circuitos y redes siguen apuntándole) con su
  contorno nuevo, y su superficie y perímetro recalculados con registro nuevo (el anterior
  queda obsoleto); los que ya no están se quitan; las redes de aire pasan al plano nuevo;
  los descartes del plano anterior que siguen en el revisado se mantienen descartados.
- Todo lo demás se recalcula solo (las cargas, redes, hidráulica y cuadros se calculan
  siempre de lo guardado) y queda **⚠ desactualizado** para revisarlo.
- Se rechaza: si ningún elemento coincide (dibujo desplazado a otro punto base o en otra
  unidad); si un elemento **aprobado** cambia o desaparece (hay que reabrirlo con motivo);
  si uno que ya no está tiene decisiones o pendientes registrados; si un contorno revisado
  se corta a sí mismo.
- El plano sustituido sigue en la base por la historia, pero ya no se ve ni se trabaja.

### Ampliación: zonas nuevas
- Se diseña la parte nueva: en el plano de la ampliación (o el existente con la ampliación
  dibujada) **solo se confirman los espacios nuevos**; lo existente se queda sin confirmar
  (en gris, como el resto del dibujo) o se descarta. Así cargas, redes, hidráulica y
  cuadros se calculan solo para la ampliación, sin una marca más que mantener. La pantalla
  lo dice («Confirmados (ampliación)», «Falta: confirmar los espacios de la ampliación»).
