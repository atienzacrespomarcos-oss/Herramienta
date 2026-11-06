# ADR-0006 · Motores de cálculo puros y versionados
Estado: Propuesto · 05-11-2026
**Decisión:** cada motor es una función sin efectos laterales, con id y versión, que
devuelve un registro de cálculo completo. No importa Qt, base de datos ni IA
(import-linter). Resultados obsoletos detectados por hash de entradas.
