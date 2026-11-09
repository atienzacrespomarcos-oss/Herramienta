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

# V4 (07-11-2026): geometría desde planos DXF (docs/modules/geometria.md, ADR-0014).
# - `plano`: cómo se lee un DXF del proyecto. Lo decide el usuario: unidad confirmada y
#   qué capas son espacios, obstáculos y nombres. `descartados`: propuestas que el usuario
#   ha rechazado (handles), para no volver a proponerlas.
# - `geometria`: el contorno (en metros, coordenadas del dibujo) de un elemento confirmado,
#   con la entidad DXF de la que sale: la procedencia de la geometría.
V4 = """
CREATE TABLE plano (
    id TEXT PRIMARY KEY,
    documento_id TEXT NOT NULL UNIQUE REFERENCES documento(id),
    unidad TEXT NOT NULL CHECK (unidad IN ('mm','cm','dm','m')),
    capas_espacios TEXT NOT NULL,
    capas_obstaculos TEXT NOT NULL,
    capas_textos TEXT NOT NULL,
    descartados TEXT NOT NULL,
    lector TEXT NOT NULL,
    version_lector TEXT NOT NULL,
    leido TEXT NOT NULL
);

CREATE TABLE geometria (
    elemento_id TEXT PRIMARY KEY REFERENCES elemento(id),
    plano_id TEXT NOT NULL REFERENCES plano(id),
    handle TEXT NOT NULL CHECK (length(trim(handle)) > 0),
    capa TEXT NOT NULL,
    contorno TEXT NOT NULL,
    UNIQUE (plano_id, handle)
);
"""

# V5 (07-11-2026): cargas y ventilación (docs/modules/cargas.md).
# - `cargas_proyecto` (una sola fila): de dónde sale el clima (la guía del IDAE incorporada
#   como documento y la página de su estación), la obra (provincia, altitud) y las
#   hipótesis de conjunto (tipo de construcción, norte del plano, mes, color, recuperador).
# - `cargas_espacio`: el uso de cada espacio, lo que el usuario cambia de la propuesta de
#   su uso (`ajustes`) y sus correcciones de fachada por sector (`fachadas`).
# Lo propuesto no se guarda: sale del catálogo con su fuente cada vez que se calcula.
V5 = """
CREATE TABLE cargas_proyecto (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    guia_documento_id TEXT NOT NULL REFERENCES documento(id),
    estacion_pagina INTEGER NOT NULL CHECK (estacion_pagina >= 1),
    provincia TEXT NOT NULL CHECK (length(trim(provincia)) > 0),
    altitud_obra REAL NOT NULL,
    tipo_construccion TEXT NOT NULL,
    norte REAL NOT NULL,
    mes INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    color TEXT NOT NULL CHECK (color IN ('claro', 'oscuro')),
    recuperacion REAL NOT NULL CHECK (recuperacion >= 0 AND recuperacion < 1)
);

CREATE TABLE cargas_espacio (
    elemento_id TEXT PRIMARY KEY REFERENCES elemento(id),
    uso TEXT NOT NULL CHECK (length(trim(uso)) > 0),
    ajustes TEXT NOT NULL,
    fachadas TEXT NOT NULL
);

UPDATE elemento SET tipo_version = 2 WHERE tipo = 'espacio';
"""

# V6 (07-11-2026): redes de aire (docs/modules/redes_aire.md). Cómo se lee una red del DXF
# (capa de ejes, bloques de terminales y de equipo) y sus criterios de dimensionado. Los
# tramos y resultados se calculan del dibujo cada vez: no se guardan.
V6 = """
CREATE TABLE red_aire (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL CHECK (length(trim(nombre)) > 0),
    tipo TEXT NOT NULL CHECK (tipo IN ('impulsion', 'retorno', 'extraccion')),
    plano_id TEXT NOT NULL REFERENCES plano(id),
    nivel_id TEXT REFERENCES elemento(id),
    capa_ejes TEXT NOT NULL CHECK (length(trim(capa_ejes)) > 0),
    bloques_terminales TEXT NOT NULL,
    bloque_equipo TEXT,
    climatizacion INTEGER NOT NULL CHECK (climatizacion IN (0, 1)),
    friccion_objetivo REAL NOT NULL CHECK (friccion_objetivo > 0),
    alto_maximo REAL CHECK (alto_maximo IS NULL OR alto_maximo > 0),
    forma TEXT NOT NULL CHECK (forma IN ('rectangular', 'circular')),
    salto_impulsion REAL NOT NULL CHECK (salto_impulsion > 0),
    creado TEXT NOT NULL,
    UNIQUE (nombre)
);
"""

# V7 (08-11-2026): ventilación sencilla (docs/modules/redes_aire.md, «Ventilación»). El caudal
# de cada espacio puede salir de las cargas (lo de antes), de renovaciones por hora según su
# volumen (tabla 3.6 del manual de S&P) o de unas renovaciones fijas.
V7 = """
ALTER TABLE red_aire ADD COLUMN criterio_caudal TEXT NOT NULL DEFAULT 'cargas'
    CHECK (criterio_caudal IN ('cargas', 'volumen', 'renovaciones'));
ALTER TABLE red_aire ADD COLUMN renovaciones REAL
    CHECK (renovaciones IS NULL OR renovaciones > 0);
"""

# V8 (08-11-2026): sistema hidráulico primario-secundario (docs/modules/hidronica.md). Los
# circuitos van en JSON dentro del sistema (nombre, espacios, unidades, longitud, pérdida de
# la unidad, exterior): se definen y cambian juntos. Los resultados se calculan cada vez.
V8 = """
CREATE TABLE sistema_hidraulico (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL CHECK (length(trim(nombre)) > 0),
    tipo TEXT NOT NULL CHECK (tipo IN ('2_tubos', '4_tubos')),
    material TEXT NOT NULL CHECK (material IN ('acero', 'cobre', 'plastico')),
    frio_impulsion REAL NOT NULL,
    frio_retorno REAL NOT NULL,
    calor_impulsion REAL NOT NULL,
    calor_retorno REAL NOT NULL,
    altura_m REAL NOT NULL CHECK (altura_m >= 0),
    longitud_primario_m REAL NOT NULL CHECK (longitud_primario_m >= 0),
    volumen_minimo_l_kw REAL NOT NULL CHECK (volumen_minimo_l_kw > 0),
    circuitos TEXT NOT NULL,
    creado TEXT NOT NULL,
    UNIQUE (nombre)
);
"""

# V9 (09-11-2026): subcuadros eléctricos de clima (docs/modules/electricidad.md). Las
# salidas van en JSON dentro del subcuadro; los resultados se calculan cada vez.
V9 = """
CREATE TABLE subcuadro (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL CHECK (length(trim(nombre)) > 0),
    suministro TEXT NOT NULL CHECK (suministro IN ('compania', 'ct')),
    longitud_alimentacion_m REAL NOT NULL CHECK (longitud_alimentacion_m > 0),
    metodo_alimentacion TEXT NOT NULL CHECK (metodo_alimentacion IN ('E', 'B2', 'C')),
    salidas TEXT NOT NULL,
    creado TEXT NOT NULL,
    UNIQUE (nombre)
);
"""

# V10 (09-11-2026): tipos de encargo Diseño · Oferta · Ampliación (docs/modules/flujo.md).
# «Presupuesto + instalación» y «solo instalación» pasan a Oferta, el más parecido.
# También: «dar por revisado» un paso desactualizado (marca que cambia en cada revisión).
V10 = """
UPDATE meta SET valor = 'oferta'
    WHERE clave = 'encargo' AND valor IN ('presupuesto', 'instalacion');
CREATE TABLE paso_revisado (
    paso TEXT PRIMARY KEY,
    marca TEXT NOT NULL
);
"""

MIGRACIONES: tuple[str, ...] = (V1, V2, V3, V4, V5, V6, V7, V8, V9, V10)
VERSION_ACTUAL = len(MIGRACIONES)
