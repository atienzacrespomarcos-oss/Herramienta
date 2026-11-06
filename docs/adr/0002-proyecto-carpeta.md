# ADR-0002 · Un proyecto = una carpeta
Estado: Propuesto · 05-11-2026
**Decisión:** `Proyecto.traza/` con `proyecto.db` (SQLite), `documentos/<sha256>`,
`exportaciones/`, `copias/`.
**Motivos:** documentos originales intactos y deduplicados; copias simples; la base de datos
no crece con PDF pesados.
**Consecuencia:** trabajar en disco local; la copia de seguridad puede ir a una carpeta
sincronizada, el proyecto abierto no (riesgo de corrupción de SQLite en carpetas
sincronizadas o de red [C]).
