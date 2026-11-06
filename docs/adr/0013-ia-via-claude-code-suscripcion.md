# ADR-0013 · IA mediante Claude Code con la suscripción del usuario; entra directo si cuadra

Estado: **Aceptado** (decisiones del usuario, 06-11-2026)

## Contexto

Leer ofertas y mediciones en PDF y Excel exige interpretar documentos de formato libre.
El usuario no tiene clave de API y pregunta si puede usar su suscripción de Claude.

Documentación oficial consultada el 06-11-2026:
- Un usuario final puede iniciar sesión en el binario de Claude Code sin modificar con su
  propia suscripción; lo prohibido es ofrecer ese login a terceros o enrutar peticiones en
  nombre de otros usuarios (https://code.claude.com/docs/en/legal-and-compliance.md,
  https://code.claude.com/docs/en/agent-sdk/overview.md).
- **No hay frase expresa** sobre programas propios de uso personal que llamen a `claude -p`.
  Se interpreta como «usuario final con su propia suscripción». Riesgo aceptado por el usuario.
- `claude -p` admite `--output-format json` y `--json-schema` (resultado en
  `structured_output`); la herramienta Read lee PDF e imágenes, no `.xlsx`
  (https://code.claude.com/docs/en/headless.md, https://code.claude.com/docs/en/tools-reference.md).
- Con `--bare` o con `ANTHROPIC_API_KEY` definida **no** se usa la suscripción
  (https://code.claude.com/docs/en/authentication.md).
- Consume los límites del plan; Anthropic no publica cifras absolutas.

## Decisión

1. TRAZA llama a **Claude Code instalado en el equipo del usuario** (`claude -p`), sin `--bare`
   y quitando `ANTHROPIC_API_KEY` del entorno del proceso hijo. Solo la herramienta `Read`,
   en modo que deniega todo lo demás. Salida con esquema JSON.
2. El Excel se convierte a texto con coordenadas de celda antes de enviarlo.
3. **Lo que lee la IA entra directo si pasa todas las comprobaciones** (decisión del usuario);
   lo que no, entra marcado «a revisar» con el motivo.
4. Comprobaciones deterministas (no las hace la IA):
   - La IA devuelve, además del número, **el texto literal** de cantidad y precio. TRAZA lo
     interpreta con su propia regla española (`core/numeros.py`) y debe coincidir con el
     número de la IA. Así se caza «2.400» leído como 2,4.
   - Ese texto literal debe **aparecer en la página citada** del PDF (o en la celda citada del
     Excel). Si no aparece, la línea no se da por buena.
   - Si el documento da importe, cantidad × precio debe coincidir al céntimo.
   - Si el documento da total, la suma de importes debe coincidir al céntimo.
   - Un PDF escaneado (sin texto) no permite la segunda comprobación: sus líneas entran
     «a revisar».
5. Cada partida guarda el lector (`ia-claude-code`), la página/celda y el resultado de las
   comprobaciones. El envío de un documento a la IA lo inicia siempre el usuario.

## Consecuencias

- Sin coste extra para el usuario; depende de tener Claude Code instalado y con sesión.
- Si Claude Code no está o no hay sesión, la lectura con IA no está disponible y se dice;
  el BC3 sigue leyéndose sin IA.
- La línea roja 7 («la IA solo propone») se matiza **para la lectura de documentos**: la IA
  propone y son las comprobaciones deterministas, no la IA, las que dan la línea por buena.
