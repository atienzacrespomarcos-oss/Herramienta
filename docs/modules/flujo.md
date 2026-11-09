# Flujo de trabajo de la herramienta

Estado: **decidido** (09-11-2026); se construye por bloques.

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

## Estado de cada paso (propuesta)
- **Pendiente**: le falta lo que necesita (p. ej. Cargas sin espacios confirmados), y lo
  dice: «Falta: confirmar espacios en Planos».
- **Hecho**: tiene datos y calcula sin error.
- **Desactualizado**: algo de un paso del que depende ha cambiado después (cargas →
  redes, hidráulica, cuadros); se marca hasta que se revise.
- Dependencias: Planos → Cargas → Redes de aire y Sistema hidráulico → Subcuadros →
  Entregables.

## Plan de entrega (propuesta, por bloques)
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
