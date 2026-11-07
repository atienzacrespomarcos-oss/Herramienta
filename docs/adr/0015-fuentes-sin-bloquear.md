# ADR-0015 · Fuentes: buscar, usar y citar; nunca bloquear
Estado: Aceptado · 07-11-2026 · Sustituye en parte a ADR-0007 (nivel y verificación de las
fuentes) y a las líneas rojas 1, 3 y 4 de su primera versión.

**Contexto:** el usuario (07-11-2026): «No siempre vas a encontrar fuentes 100 % fiables y a
mí me da exactamente igual. No quiero cosas como "no verificado", "no comprobado" o cosas
así. Quiero una herramienta que eleve mi nivel y me permita ser mucho más eficiente. Cuando
ocurran cosas así, busca y fíate de lo que encuentres». Y sobre los cerramientos: «Nunca me
dan esos datos. Presupón los típicos dependiendo del tipo de construcción».

**Decisión:**
1. Los datos de cálculo (clima, usos, cerramientos, coeficientes, caudales) viven como
   **datos citados** en `data/` (se mantiene la idea de ADR-0007: nada de cifras en el
   código). Cada valor lleva su **fuente** (documento, apartado, URL).
2. Se busca la mejor fuente publicada disponible y **se usa**. No hay niveles de
   verificación visibles ni etiquetas «fuente secundaria», «no verificado» o «no evaluable»
   en la herramienta.
3. Si un dato del proyecto no se conoce, se **presupone el típico** de su tipo (de
   construcción, de uso) con su fuente, y queda como **hipótesis** con procedencia: el
   usuario lo ve y lo puede cambiar, pero el cálculo sale siempre.
4. Si dos fuentes discrepan, se elige con criterio de ingeniería la más reconocida en el
   mercado español (RITE y CTE antes que manuales; manuales reconocidos antes que webs) y la
   elección se anota en la ficha del módulo.

**Lo que no cambia:** procedencia por valor (de dónde sale cada número), nada aprobado se
modifica en silencio, y la IA solo propone. Las comprobaciones de la lectura de documentos
con IA («a revisar», ADR-0013) siguen: comprueban que la lectura sea fiel al documento, no la
calidad de una fuente.

**Consecuencias:** la herramienta da siempre un resultado completo y presentable, con sus
hipótesis a la vista y sus fuentes citadas.
