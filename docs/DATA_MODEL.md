# Modelo de datos

> Origen: especificación de Etapa 0 (`docs/ETAPA0_ESPECIFICACION.md`, 05-11-2026).
> Marcas de rigor: **[V]** verificado con fuente · **[V2]** solo fuentes secundarias · **[C]** conocimiento sin verificar aún · **[P]** propuesta · **[?]** dato pendiente.

## 7. Modelo central de datos (borrador)

### 7.1 Entidades

| Entidad | Contenido | Comentario |
|---|---|---|
| `proyecto` | Metadatos, ubicación, perfil normativo (qué versión de cada norma), unidades de visualización. | |
| `revision` | Instantáneas con nombre (Rev. 0, Rev. A…) y comparación. | RF-009 |
| `documento` | Fichero (sha256), tipo, origen, fecha de incorporación, clasificación (oferta, plano, ficha…). | Ficheros en `documentos/<sha256>`; nunca se modifican. |
| `referencia_origen` | documento + página/hoja/celda/región + texto extraído + método (manual/determinista/IA) + confianza. | Base de la trazabilidad (RF-021). |
| `nivel`, `espacio`, `obstaculo` | Geometría de edificio: polígono, cotas, alturas, uso, ocupación. | Planta libre (RF-040). |
| `sistema` | Disciplina, tipo, medio (aire, agua, R-32…), parámetros de diseño, clasificación bienestar/proceso. | |
| `elemento` | id (UUID), disciplina, tipo, código visible (UTA-01, T-12…), sistema, espacio, estado, bloqueado. | Núcleo. |
| `propiedad` | elemento, clave, valor, unidad, **origen** (usuario / documento / cálculo / catálogo / hipótesis / IA-propuesta), ref_origen, registro_calculo, confirmado. | Procedencia por valor (ADR-0005). Validada contra el esquema del tipo. |
| `geometria_elemento` | Polilínea 3D (lineales), punto+rotación+caja (equipos), sección. | |
| `puerto` | elemento, nombre, medio, sentido (entrada/salida/bidireccional), posición. | Inspirado en el concepto de puertos de distribución de IFC. |
| `conexion` | puerto_a ↔ puerto_b. | Hace la red computable (RF-004). |
| `catalogo_*` | Biblioteca de fabricantes **fuera** del proyecto, con documento origen. Al usarse, se copia una instantánea al proyecto. | Un cambio de catálogo no altera un proyecto en silencio. |
| `entrada_normativa` | Ver §5. Biblioteca fuera del proyecto; el proyecto fija versiones. | |
| `registro_calculo` | Ver §6.2. | RN-04 |
| `comprobacion` | regla, elementos, valor, límite, resultado, margen, registro_calculo. | |
| `conflicto` | elementos, localización, tipo, gravedad, criterio, soluciones, estado (abierto/aceptado/rechazado/resuelto). | RF-043 |
| `decision` | Aprobaciones/reaperturas con motivo y fecha. | RF-006/007 |
| `pendiente` | Información por confirmar, con origen y elemento afectado. | RF-012 |
| `cambio` | Registro solo-añadir: orden, entidad, campo, antes, después, autor (usuario/motor/IA/importación), fecha. | RF-008 |
| `exportacion` | Formato, fecha, versión, hash, mapa elemento ↔ handle DXF. | RF-203 |

### 7.2 Ejemplo: tramo de conducto

```
elemento  T-IMP-012  tipo=conducto_rectangular  sistema=IMP-UTA-01  estado=calculado
  puertos: entrada ← T-IMP-011.salida ; salida → D-IMP-012A.entrada , T-IMP-013.entrada
  propiedades:
    caudal          2 400 m³/h   origen=cálculo (suma aguas abajo)   reg=calc#88
    ancho×alto      500×300 mm   origen=propuesta motor               reg=calc#91
    velocidad       4,44 m/s     origen=cálculo                       reg=calc#91
    material        chapa galv.  origen=documento (pliego p.14)       ref=doc#3/p14
    rugosidad       [valor]      origen=hipótesis declarada + fuente   ref=bib#…
    Δp/L, Δp tramo  …            origen=cálculo                       reg=calc#92
  geometría: polilínea 3D, cota inferior +4,20 m
  comprobaciones: velocidad ≤ criterio de diseño (hipótesis del proyecto, no norma)
```
(Los valores del ejemplo ilustran el formato; no son un cálculo.)

### 7.3 Estados

```
borrador ──► propuesto ──► calculado ──► comprobado ──► APROBADO (bloqueado)
   ▲              │             │              │              │
   └──────────────┴── cambio de entrada ⇒ «obsoleto» ◄────────┘ reabrir = decisión explícita registrada
```

---
