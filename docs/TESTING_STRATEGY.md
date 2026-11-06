# Estrategia de pruebas y criterios de calidad

> Origen: especificación de Etapa 0 (`docs/ETAPA0_ESPECIFICACION.md`, 05-11-2026).
> Marcas de rigor: **[V]** verificado con fuente · **[V2]** solo fuentes secundarias · **[C]** conocimiento sin verificar aún · **[P]** propuesta · **[?]** dato pendiente.

## 0.2 Validación de motores: ejemplos publicados

Decisión del usuario (06-11-2026): no dispone de programas de cálculo de terceros. La
validación se hace con **ejemplos resueltos publicados** y accesibles públicamente
(guías del Ministerio e IDAE, documentación técnica de fabricantes, publicaciones
universitarias y manuales técnicos), con estas reglas:

1. Cada caso de referencia vive en `tests/reference_cases/` y cita: obra, autor o
   editor, edición, página/apartado, URL si existe y fecha de consulta.
2. Se reproducen **las entradas exactas** del ejemplo; la tolerancia se escribe y se
   justifica (redondeo de la fuente, lectura de gráfico, diferencia de método).
3. Si el ejemplo usa un método o un coeficiente distinto del motor, la diferencia se
   documenta; no se ajusta el motor para «cuadrar» sin entender por qué.
4. Si para un motor no se encuentra ningún ejemplo publicado, el motor queda en estado
   **Limitada** en `FEATURE_REGISTER.md` con esa limitación escrita; no pasa a Validada.
5. Una fuente que no se pueda localizar públicamente no sirve como caso de referencia.

Si más adelante el usuario instala un programa de cálculo, sus resultados se añadirán
como segunda fuente de contraste, citando programa, versión y fecha.

## 11. Criterios objetivos de calidad

**Motores de cálculo**
- 100 % de las funciones de cálculo con al menos un **caso de referencia publicado y citado** (autor, obra, página) y tolerancia escrita.
- Tests de propiedades (`hypothesis`): monotonía física (más caudal ⇒ más pérdida en el mismo tramo), conservación de caudal en nudos, invariancia ante cambio de unidades.
- Cobertura de ramas ≥ 90 % en `engines/` y `rules/` (en el resto, objetivo orientativo, no fin en sí mismo).
- Ninguna magnitud cruza la frontera de un motor sin unidad declarada (test automático).
- Toda comprobación devuelve CUMPLE / NO CUMPLE / NO EVALUABLE y cita una entrada normativa o una hipótesis declarada (test automático que falla si no).

**Integridad y trazabilidad**
- 0 propiedades sin origen en el modelo (consulta de auditoría en el test de integración).
- 0 elementos aprobados modificados sin una `decision` de reapertura (test de integración).
- Cierre forzado del proceso a mitad de una orden ⇒ proyecto íntegro al reabrir (test).

**Interoperabilidad**
- DXF generado: legible por ezdxf con auditoría sin errores y comparado con un *golden*; abierto en tu AutoCAD según protocolo manual documentado.
- Ida y vuelta DXF: 100 % de entidades exportadas reconocidas por id al reimportar.

**Interfaz**
- Test que recorre todas las acciones de menú/barra y falla si alguna no tiene manejador.
- Toda cifra mostrada permite ver su origen en ≤ 1 clic.
- Objetivos de rendimiento iniciales [P] (a medir en tu equipo): abrir proyecto de 10 000 elementos < 3 s; recalcular una red de 500 tramos < 1 s; importar DXF de 50 000 entidades < 15 s.

**Proceso**
- Ninguna funcionalidad pasa a «Validada» sin cumplir los 8 puntos del criterio de finalización del brief.
- Revisión en contexto nuevo (subagente revisor) antes de cerrar cada módulo.

---
