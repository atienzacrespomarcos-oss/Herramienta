"""Esquema de la base de datos del proyecto y sus migraciones (ADR-0003).

Migraciones propias con `PRAGMA user_version`: cada entrada de MIGRACIONES lleva la base
de la versión N-1 a la N. Nunca se edita una migración ya publicada; se añade otra.

Las restricciones CHECK repiten las reglas de `core.procedencia` a propósito: son la
segunda capa. Si un error de programación saltara la primera, la base de datos se niega
a guardar un valor sin procedencia.
"""

from __future__ import annotations

V1 = """
CREATE TABLE meta (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE documento (
    id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    nombre_original TEXT NOT NULL,
    extension TEXT NOT NULL,
    tamano INTEGER NOT NULL CHECK (tamano >= 0),
    paginas INTEGER,
    clasificacion TEXT,
    incorporado TEXT NOT NULL
);

CREATE TABLE registro_calculo (
    id TEXT PRIMARY KEY,
    motor TEXT NOT NULL,
    version TEXT NOT NULL,
    fecha TEXT NOT NULL,
    hash_entradas TEXT NOT NULL,
    contenido TEXT NOT NULL,
    obsoleto INTEGER NOT NULL DEFAULT 0 CHECK (obsoleto IN (0, 1))
);

CREATE TABLE elemento (
    id TEXT PRIMARY KEY,
    codigo TEXT NOT NULL UNIQUE CHECK (length(trim(codigo)) > 0),
    tipo TEXT NOT NULL,
    tipo_version INTEGER NOT NULL,
    disciplina TEXT NOT NULL,
    estado TEXT NOT NULL CHECK (estado IN
        ('borrador','propuesto','calculado','comprobado','aprobado')),
    padre_id TEXT REFERENCES elemento(id),
    creado TEXT NOT NULL,
    modificado TEXT NOT NULL
);

CREATE TABLE propiedad (
    elemento_id TEXT NOT NULL REFERENCES elemento(id) ON DELETE CASCADE,
    clave TEXT NOT NULL,
    valor TEXT NOT NULL,
    unidad TEXT,
    origen TEXT NOT NULL CHECK (origen IN
        ('usuario','documento','calculo','catalogo','hipotesis','ia_propuesta')),
    documento_id TEXT REFERENCES documento(id),
    localizador TEXT,
    registro_calculo_id TEXT REFERENCES registro_calculo(id),
    nota TEXT,
    confirmado INTEGER NOT NULL CHECK (confirmado IN (0, 1)),
    modificado TEXT NOT NULL,
    PRIMARY KEY (elemento_id, clave),
    CHECK (origen NOT IN ('documento','catalogo')
           OR (documento_id IS NOT NULL AND length(trim(coalesce(localizador,''))) > 0)),
    CHECK (origen IN ('documento','catalogo','ia_propuesta')
           OR (documento_id IS NULL AND localizador IS NULL)),
    CHECK ((documento_id IS NULL) = (localizador IS NULL)),
    CHECK ((origen = 'calculo') = (registro_calculo_id IS NOT NULL)),
    CHECK (origen <> 'hipotesis' OR length(trim(coalesce(nota,''))) > 0),
    CHECK (origen <> 'ia_propuesta' OR confirmado = 0),
    CHECK (origen = 'ia_propuesta' OR confirmado = 1)
);

CREATE TABLE decision (
    id TEXT PRIMARY KEY,
    elemento_id TEXT NOT NULL REFERENCES elemento(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('aprobar','reabrir')),
    motivo TEXT NOT NULL CHECK (length(trim(motivo)) > 0),
    fecha TEXT NOT NULL
);

CREATE TABLE pendiente (
    id TEXT PRIMARY KEY,
    elemento_id TEXT REFERENCES elemento(id),
    descripcion TEXT NOT NULL CHECK (length(trim(descripcion)) > 0),
    estado TEXT NOT NULL CHECK (estado IN ('abierto','resuelto')),
    resolucion TEXT,
    creado TEXT NOT NULL,
    CHECK (estado = 'abierto' OR length(trim(coalesce(resolucion,''))) > 0)
);

-- Registro de cambios: solo se añade. Los triggers impiden editarlo o borrarlo.
CREATE TABLE cambio (
    n INTEGER PRIMARY KEY AUTOINCREMENT,
    orden_id TEXT NOT NULL,
    orden TEXT NOT NULL,
    autor TEXT NOT NULL CHECK (autor IN
        ('usuario','motor','ia','importacion','deshacer','rehacer')),
    fecha TEXT NOT NULL,
    entidad TEXT NOT NULL,
    entidad_id TEXT NOT NULL,
    campo TEXT,
    antes TEXT,
    despues TEXT
);
CREATE TRIGGER cambio_sin_update BEFORE UPDATE ON cambio
BEGIN SELECT RAISE(ABORT, 'El registro de cambios no se modifica'); END;
CREATE TRIGGER cambio_sin_delete BEFORE DELETE ON cambio
BEGIN SELECT RAISE(ABORT, 'El registro de cambios no se borra'); END;

CREATE INDEX propiedad_documento ON propiedad(documento_id);
CREATE INDEX cambio_entidad ON cambio(entidad, entidad_id);
"""

# V2 (06-11-2026): mediciones, ofertas y presupuestos leídos de documentos, y sus partidas.
# Cada partida guarda DÓNDE está en su documento (localizador): sin eso no se guarda.
V2 = """
CREATE TABLE medicion (
    id TEXT PRIMARY KEY,
    documento_id TEXT NOT NULL REFERENCES documento(id),
    nombre TEXT NOT NULL CHECK (length(trim(nombre)) > 0),
    clase TEXT NOT NULL CHECK (clase IN ('medicion','oferta','presupuesto')),
    proveedor TEXT,
    lector TEXT NOT NULL,
    version_lector TEXT NOT NULL,
    leido TEXT NOT NULL,
    avisos TEXT NOT NULL,
    -- Líneas del documento que no se han podido convertir en partida (porcentajes, códigos
    -- sin concepto…). Si > 0, los totales de esta medición son parciales.
    omitidas INTEGER NOT NULL DEFAULT 0 CHECK (omitidas >= 0),
    -- Total que declara el propio documento (si lo declara), para contrastar la suma.
    total_documento REAL
);

CREATE TABLE partida (
    id TEXT PRIMARY KEY,
    medicion_id TEXT NOT NULL REFERENCES medicion(id),
    orden INTEGER NOT NULL,
    capitulo TEXT NOT NULL,
    codigo TEXT,
    etiqueta TEXT,
    unidad TEXT,
    resumen TEXT,
    texto TEXT,
    cantidad REAL,
    precio REAL,
    localizador TEXT NOT NULL CHECK (length(trim(localizador)) > 0),
    estado TEXT NOT NULL DEFAULT 'exacta'
        CHECK (estado IN ('exacta','comprobada','a_revisar','confirmada')),
    motivos TEXT NOT NULL DEFAULT '[]',
    -- Una partida «a revisar» tiene que decir por qué.
    CHECK (estado <> 'a_revisar' OR motivos <> '[]'),
    UNIQUE (medicion_id, orden)
);

CREATE INDEX partida_medicion ON partida(medicion_id);
"""

# V3 (06-11-2026): ampliaciones y modificaciones sobre una medición leída.
# Un cambio es una VARIACIÓN (nueva cantidad de una partida de la base) o una partida NUEVA
# tomada de una oferta leída. Motivo y justificación obligatorios (decisión del usuario).
V3 = """
CREATE TABLE modificado (
    id TEXT PRIMARY KEY,
    medicion_id TEXT NOT NULL REFERENCES medicion(id),
    numero INTEGER NOT NULL CHECK (numero >= 1),
    titulo TEXT NOT NULL CHECK (length(trim(titulo)) > 0),
    creado TEXT NOT NULL,
    UNIQUE (medicion_id, numero)
);

CREATE TABLE cambio_modificado (
    id TEXT PRIMARY KEY,
    modificado_id TEXT NOT NULL REFERENCES modificado(id),
    orden INTEGER NOT NULL CHECK (orden >= 1),
    tipo TEXT NOT NULL CHECK (tipo IN ('variacion','nueva')),
    partida_id TEXT NOT NULL REFERENCES partida(id),
    cantidad REAL NOT NULL CHECK (cantidad >= 0),
    motivo TEXT NOT NULL CHECK (motivo IN ('medicion','diseno','economica','otro')),
    justificacion TEXT NOT NULL CHECK (length(trim(justificacion)) > 0),
    creado TEXT NOT NULL,
    UNIQUE (modificado_id, orden),
    UNIQUE (modificado_id, tipo, partida_id)
);

CREATE INDEX cambio_modificado_partida ON cambio_modificado(partida_id);
"""

MIGRACIONES: tuple[str, ...] = (V1, V2, V3)
VERSION_ACTUAL = len(MIGRACIONES)
