# ADR-0003 · SQLite con migraciones propias

Estado: **Aceptado** · 06-11-2026 (sustituye la propuesta inicial SQLAlchemy + Alembic)

**Decisión:** módulo `sqlite3` de la biblioteca estándar y migraciones propias numeradas
con `PRAGMA user_version` (`src/traza/persistence/esquema.py`).

**Motivos:**
- El modelo tiene pocas tablas genéricas (elemento, propiedad, documento, decisión,
  pendiente, cambio). Un ORM no aporta y añade una capa más que entender y mantener.
- Cada migración se aplica en una transacción explícita: o entra entera o no entra.
- Las reglas de procedencia se expresan como restricciones CHECK del propio SQL.

**Consecuencias:**
- Nunca se edita una migración publicada; se añade la siguiente.
- Un proyecto creado por una versión más nueva del programa no se abre (no se arriesga a
  estropearlo).
- Diario `DELETE` y `synchronous=FULL`: un único fichero de base de datos, sin `-wal`/`-shm`.
