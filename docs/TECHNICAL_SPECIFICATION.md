# Especificación técnica

> Origen: especificación de Etapa 0 (`docs/ETAPA0_ESPECIFICACION.md`, 05-11-2026).
> Marcas de rigor: **[V]** verificado con fuente · **[V2]** solo fuentes secundarias · **[C]** conocimiento sin verificar aún · **[P]** propuesta · **[?]** dato pendiente.

## 3. Investigación tecnológica

Criterios de evaluación: adecuación, mantenimiento activo, licencia, rendimiento, integración con Python/Qt, riesgo. Las versiones exactas se fijarán al crear el entorno (Etapa 1), comprobando ruedas (*wheels*) disponibles para Windows.

### 3.1 Tabla de evaluación

| Área | Candidata | Licencia | Veredicto [P] | Notas |
|---|---|---|---|---|
| Lenguaje | Python 3.12/3.13 | PSF | **Adoptar** | Ecosistema científico y CAD (ezdxf, NumPy, SciPy, CoolProp). La versión concreta la decide la disponibilidad de ruedas de PySide6, CoolProp e IfcOpenShell. |
| Interfaz | **PySide6 (Qt Widgets)** | LGPLv3 / GPLv3 / comercial [V] | **Adoptar** | Binding oficial de Qt. Widgets (no QML): docks, árboles, tablas densas, `QUndoStack`. Alternativas descartadas: PyQt6 (GPL), web/Electron (doble pila, peor integración con el cálculo en Python). |
| Persistencia | **SQLite** | Dominio público [C] | **Adoptar** | Un fichero por proyecto, transaccional, sin servidor. **Precaución**: no abrir el proyecto directamente desde carpetas sincronizadas (OneDrive/Dropbox) o de red — riesgo de corrupción documentado por SQLite [C]; se trabaja en local y la copia de seguridad va a la carpeta sincronizada. |
| Acceso a datos / migraciones | SQLAlchemy 2 + Alembic | MIT [C] | **Adoptar (ADR)** | Alembic tiene «modo batch» para las limitaciones de `ALTER TABLE` de SQLite [C]. Alternativa más simple: `sqlite3` + migraciones propias con `PRAGMA user_version`. |
| Validación de datos | Pydantic 2 | MIT [C] | **Adoptar** | Esquemas de propiedades por tipo de elemento, con versión. |
| Unidades | **pint** | BSD [C] | **Adoptar en fronteras** | SI internamente (float), `pint` en entradas/salidas de motores y en la interfaz; tests de análisis dimensional. |
| Numérico | NumPy, SciPy | BSD [C] | **Adoptar** | Resolución de redes (sistemas no lineales), interpolación de curvas de ventiladores/bombas. |
| Hidráulica / mecánica de fluidos | **fluids** (C. Bell) | MIT [C, verificar] | **Evaluar en Etapa 3** | Incluye correlaciones de fricción y coeficientes de accesorios **con cita a la fuente original** en su documentación; encaja con la trazabilidad. Cada función usada se contrasta con la fuente primaria antes de adoptarla. |
| Propiedades de fluidos | **CoolProp** | MIT [V] | **Adoptar (Etapa 5)** | Refrigerantes, agua, aire húmedo (`HumidAirProp`). |
| Grafos | NetworkX | BSD [C] | **Adoptar** | Redes, caminos críticos, búsqueda de rutas (A*). |
| Geometría 2D | Shapely (GEOS) | BSD [C] | **Adoptar** | Polígonos de espacios, intersecciones, offsets. |
| Geometría 3D / B-Rep | Open CASCADE (OCCT) | LGPL-2.1 + excepción [V] | **Aplazar** | Pesado y complejo. Para interferencias de conductos/tuberías/bandejas bastan cajas orientadas y cilindros. Se reevalúa en Etapa 7 (estructura) o si IFC lo exige. |
| DXF | **ezdxf** | MIT [V] | **Adoptar** | Lectura/escritura DXF, XDATA/diccionarios de extensión para incrustar ids, bloques, cotas, tablas. No convierte a DWG [V]. |
| DWG | ODA File Converter | Uso no comercial salvo miembros ODA [V] | **Descartar** | Ver C-05. |
| IFC | IfcOpenShell | LGPL-3.0 (partes GPL-3.0 a revisar) [V] | **Aplazar (Etapa 9)** | Útil para recibir modelos BIM de arquitectura/estructura. |
| PDF (texto, vectores) | PyMuPDF | AGPL-3.0 o comercial [V] | **Candidata principal** | La mejor extracción de trazados vectoriales de PDF (`get_drawings`) [C]. La AGPL impone obligaciones al *distribuir* o *ofrecer por red*; para uso estrictamente personal y local no hay conflicto práctico, pero si se reparte el programa (A-06) sí. No es asesoramiento jurídico. |
| PDF (alternativa permisiva) | pypdfium2 / pdfplumber | Apache-2.0·BSD-3 / MIT [C] | **Alternativa** | Si A-06 = «se distribuirá». |
| OCR | Tesseract | Apache-2.0 [C] | **Etapa 8** | Para escaneados; calidad limitada en planos. |
| XLSX | openpyxl | MIT [C] | **Adoptar** | Lectura de mediciones y escritura de listados. |
| DOCX | python-docx (+ docxtpl) | MIT (docxtpl LGPL) [C] | **Adoptar** | Memorias sobre **tu** plantilla Word. |
| PDF de salida | Desde DOCX (Word/LibreOffice) o WeasyPrint | BSD [C] | **Decidir en Etapa 3** | Recomiendo DOCX como fuente única y PDF derivado. |
| Visor 2D | QGraphicsView (Qt) | (Qt) | **Adoptar** | Suficiente para planta de referencia con miles de entidades. |
| Visor 3D | pyqtgraph.opengl / VTK (PyVista + pyvistaqt) | MIT / BSD [C] | **Prototipo comparativo en Etapa 6** | Solo consulta e interferencias. |
| IA local | Ollama / llama.cpp | MIT [C] | **Opcional (Etapa 8)** | Depende del hardware (pregunta nº 2). |
| IA externa | API de proveedor (p. ej. Anthropic) | Servicio de pago por uso | **Opcional, nunca obligatoria** | Solo con autorización por envío (RF-303). |
| Pruebas | pytest, pytest-qt, hypothesis | MIT/MPL [C] | **Adoptar** | `hypothesis` para propiedades físicas (monotonía, conservación). |
| Calidad | ruff, mypy, import-linter | MIT/BSD [C] | **Adoptar** | `import-linter` impide que los motores importen Qt o la base de datos. |
| Entorno | uv | MIT/Apache [C] | **Adoptar** | Entorno reproducible con `uv.lock`. Para uso personal **no hace falta instalador**: se ejecuta desde el entorno. Empaquetado (PyInstaller/Nuitka) solo si se pide. |

### 3.2 Decisiones a documentar como ADR (Etapa 1)

| ADR | Decisión propuesta |
|---|---|
| 0001 | Python + PySide6 Widgets. |
| 0002 | Proyecto = carpeta (`proyecto.db` + `documentos/` por hash + `exportaciones/` + `copias/`). |
| 0003 | SQLite + SQLAlchemy/Alembic (o alternativa mínima). |
| 0004 | SI interno, pint en fronteras, unidades de visualización configurables. |
| 0005 | Procedencia por valor (tabla de propiedades con origen) frente a JSON opaco. |
| 0006 | Motores de cálculo puros, versionados, con registro de cálculo. |
| 0007 | Normativa como datos citados y versionados; nada de umbrales «en el código». |
| 0008 | DXF como intercambio principal; LISP complementario; DWG descartado. |
| 0009 | Ids del modelo incrustados en XDATA con APPID propio. |
| 0010 | Interfaz única de órdenes (*commands*) usada por UI, scripts y asistente IA. |
| 0011 | OCCT aplazado; interferencias con primitivas simples. |
| 0012 | Licencia de PDF (PyMuPDF vs. permisivas) según A-06. |

---

## 6. Arquitectura técnica propuesta

### 6.1 Capas

```
┌──────────────────────────────────────────────────────────────────────┐
│ ui/  PySide6: ventana principal, árbol, propiedades, tablas, visores, │
│      alertas, documentos, historial, asistente                       │
└───────────────▲──────────────────────────────────────────────────────┘
                │ solo llama a órdenes y consultas
┌───────────────┴──────────────────────────────────────────────────────┐
│ app/  Órdenes (commands) con deshacer, consultas, flujo de estados,  │
│       orquestación de cálculos, detección de resultados obsoletos    │
└──▲──────────▲───────────▲────────────▲─────────────▲─────────────────┘
   │          │           │            │             │
┌──┴───┐ ┌────┴─────┐ ┌───┴──────┐ ┌───┴────────┐ ┌──┴───────────────┐
│core/ │ │engines/  │ │rules/    │ │coordination│ │io/ dxf, lisp,    │
│modelo│ │cálculo   │ │normativa │ │conflictos  │ │ xlsx, docx, pdf, │
│puro, │ │puro, sin │ │como datos│ │geometría   │ │ ingesta docs     │
│unid. │ │Qt ni BD  │ │+ checks  │ │            │ │                  │
└──▲───┘ └──────────┘ └──────────┘ └────────────┘ └──────────────────┘
   │
┌──┴───────────────────────────────────────────────────────────────────┐
│ persistence/  SQLite, repositorios, migraciones, copias, revisiones  │
└──────────────────────────────────────────────────────────────────────┘
ai/  Proveedor (local/externo) → produce PROPUESTAS de órdenes, nunca escribe en el modelo
```

Reglas de dependencia (comprobadas automáticamente con `import-linter`):

1. `engines/` y `rules/` no importan `ui/`, `persistence/` ni `ai/`. Reciben datos y devuelven resultados.
2. `ui/` no toca la base de datos: solo `app/`.
3. `ai/` solo puede emitir órdenes de `app/` marcadas como propuesta.
4. Toda modificación del modelo pasa por una orden ⇒ registro de cambios + deshacer garantizados por construcción.

### 6.2 Patrón de motor de cálculo

```python
# Esquema conceptual (no es código definitivo)
@engine(id="air.duct.friction", version="1.0.0")
def friccion_tramo(entrada: EntradaTramo) -> RegistroCalculo:
    ...
RegistroCalculo = {
  motor, version, fecha, hash_entradas,
  entradas (con unidades y procedencia), hipotesis[], metodo (+ecuaciones),
  referencias[] (id de entrada normativa o bibliográfica), resultados (con unidades),
  comprobaciones[] (regla, valor, límite, CUMPLE/NO CUMPLE/NO EVALUABLE),
  advertencias[], aproximaciones_declaradas[]
}
```

- Si cambian las entradas de un cálculo aprobado, su registro pasa a **obsoleto** (comparando `hash_entradas`) y aparece en alertas; no se recalcula ni se sobrescribe en silencio.
- Tres resultados posibles de una comprobación: **CUMPLE**, **NO CUMPLE**, **NO EVALUABLE** (falta dato, criterio no verificado o fuera de ámbito). Nunca un «CUMPLE» por defecto.

### 6.3 Asistente en lenguaje natural

`texto → (IA) plan de órdenes propuesto → comprobación de datos suficientes (determinista) → muestra el plan → el usuario acepta → ejecución por app/ → resultados revisables`. Si faltan datos, la respuesta es la lista de lo que falta, no una suposición.

---
