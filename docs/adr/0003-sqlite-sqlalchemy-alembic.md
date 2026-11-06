# ADR-0003 · SQLite + SQLAlchemy 2 + Alembic
Estado: Propuesto · 05-11-2026
**Decisión:** SQLite con SQLAlchemy 2 (Core/ORM) y migraciones Alembic en modo batch.
**Alternativa:** `sqlite3` + migraciones propias con `PRAGMA user_version` (más simple, menos
herramienta). Se confirma en la Etapa 1 con el primer esquema.
