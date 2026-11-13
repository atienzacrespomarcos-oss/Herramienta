# Guía de prueba de TRAZA

Esta guía acompaña al paquete **TRAZA-windows.zip**. En una tarde te deja probada la
herramienta con ficheros inventados y, después, con un proyecto tuyo ya terminado.

Los ficheros de la carpeta «Ejemplos de prueba» son inventados y ningún dato es de un
proyecto real. Lo que esta guía manda hacer con ellos lo repiten las pruebas automáticas de
TRAZA antes de publicar cada versión.

## 1. Instalar

1. Descarga el paquete desde el enlace fijo, que siempre tiene la última versión:
   https://github.com/atienzacrespomarcos-oss/Herramienta/releases/latest/download/TRAZA-windows.zip
2. Descomprímelo entero en una carpeta tuya, por ejemplo «Documentos\TRAZA». No lo abras desde
   dentro del ZIP: Windows no deja escribir ahí.
3. Abre «TRAZA\TRAZA.exe».
   - Windows avisará con SmartScreen, porque el ejecutable no está firmado. Pulsa «Más
     información» y luego «Ejecutar de todas formas». Solo te lo pide la primera vez.
4. Para actualizar, descarga otra vez el ZIP y sustituye la carpeta TRAZA. Tus proyectos no
   se tocan, porque cada proyecto es una carpeta «.traza» aparte.

## 2. Antes de empezar

1. Descarga la guía climática del IDAE, que TRAZA lee para el clima de la obra. Es la «Guía
   técnica de condiciones climáticas exteriores de proyecto» (2010):
   https://www.idae.es/uploads/documentos/documentos_12_Guia_tecnica_condiciones_climaticas_exteriores_de_proyecto_e4e5b769.pdf
   - TRAZA la lee entera: 104 estaciones.
2. Si vas a leer **PDF o Excel con la IA**, instala Claude Code una sola vez:
   - Abre PowerShell y escribe: irm https://claude.ai/install.ps1 | iex
   - Cierra y abre PowerShell, escribe claude e inicia sesión con tu suscripción.
   - Los BC3, DXF y Excel de obra con títulos reconocibles no la necesitan.
3. Ten a mano la plantilla de Word de Aliter para la justificación de cálculos.

## 3. Recorrido A: diseño con el plano de ejemplo (unos 30 minutos)

Usa la carpeta «Ejemplos de prueba\1 Diseño». Es una nave con un ALMACÉN de 1.000 m² y unas
OFICINAS de 78 m², con dos difusores y una UTA en las oficinas.

1. **Archivo → Nuevo proyecto…**: nombre «Nave ejemplo», tipo «Diseño (plano del
   cliente)» y la carpeta donde guardarlo.
2. **Documentos → Incorporar documento…**: «Nave ejemplo.dxf». Repite con la guía del IDAE
   que descargaste.
3. Paso **Planos y espacios → Planos → Leer plano DXF…**:
   - unidad del dibujo, mm;
   - capa de espacios, A-ESPACIOS;
   - capa de textos, A-TEXTOS.
4. **Planos → Nuevo nivel…**: «Planta baja», cota 0, altura libre 6 m.
5. Elige cada espacio propuesto y **Planos → Confirmar propuesta…**: primero ALMACÉN y
   luego OFICINAS. Salen con su superficie y un código: ESP-001 el ALMACÉN y ESP-002 las
   OFICINAS. El código se ve en la columna «Código» de la tabla de espacios, y es lo que
   piden los circuitos del sistema hidráulico.
6. Paso **Cargas y ventilación → Cargas → Clima y obra…**:
   - la guía del IDAE;
   - estación «Madrid — Madrid (Barajas)» de la lista;
   - provincia Madrid;
   - altitud de la obra, 650 m;
   - tipo de construcción, el que corresponda.
   Pulsa el botón **Calcular**. Orden de magnitud con la construcción del CTE, a revisar con tu
   criterio:
   - ALMACÉN: unos 37 kW de calefacción y 54 kW de refrigeración;
   - OFICINAS: unos 7,6 y 13,5 kW.
7. Paso **Redes de aire → Redes → Nueva red…**:
   - nombre «Impulsión oficinas», tipo impulsión;
   - el plano y el nivel;
   - capa de ejes M-IMPULSION;
   - bloque de difusores DIFUSOR y bloque del equipo UTA.
   Sale unos 4.100 m³/h. Es normal que avise de que el ALMACÉN no tiene difusores en esta
   red: el ejemplo solo los tiene en oficinas.
8. Paso **Sistema hidráulico → Agua → Nuevo sistema…**, de 2 tubos, con dos circuitos. En
   la columna «Espacios (códigos)» va el código del espacio, no su nombre:
   - «Oficinas»: espacios ESP-002, 4 unidades, 30 m, 15 kPa;
   - «Nave»: espacios ESP-001, 6 unidades, 60 m, 20 kPa.
   Sale un generador de unos 68 kW con primario DN65, más la lista de elementos y el
   esquema.
9. Paso **Subcuadros de clima → Electricidad → Nuevo subcuadro… → Proponer desde los
   equipos**. Pon la potencia eléctrica de cada equipo, la de la ficha del modelo elegido.
   En el ejemplo no hay fichas: pon 2 kW donde salga vacía. Luego acepta.
10. Paso **Control**: mira las pestañas Comprobaciones, Categorías por espacio y Puntos.
    - **Control → Exportar esquema de control (DXF)…**.
    - **Control → Esquema desde un listado de puntos…** con «Listado de puntos
      ejemplo.csv».
11. Paso **Entregables**: **Entregables → Plantilla de Word…**, elige la de Aliter, y luego
    **Entregables → Generar entregables…**. Crea una carpeta nueva con todo:
    - DXF, LISP y Excel;
    - PDF de cargas;
    - justificación en Word.
12. **Archivo → Emitir revisión…** con el nombre «Para oferta».
    - Cambia el uso de OFICINAS: **Cargas → Datos del espacio…**
    - Haz **Archivo → Comparar con una revisión…**: verás qué cambia en cargas, caudales y
      potencias.

**Comprueba fuera de TRAZA** (es lo que más importa):
- Abre cada DXF en tu AutoCAD (2013–2017): unidades, capas, textos legibles y escala.
- En tu plano, **APPLOAD** del fichero .lsp y el comando **TRAZA_RED**: dibuja la red dentro
  de tu dibujo, en sus coordenadas.
- Abre la justificación en Word: que tu plantilla de Aliter se respete.
- Abre los Excel: que los números salgan con coma decimal y se puedan usar.

## 4. Recorrido B: oferta y modificado (unos 10 minutos)

1. **Archivo → Nuevo proyecto…**, tipo «Oferta de un proyecto ajeno».
2. **Documentos → Incorporar documento…** con «2 Oferta\Oferta climatización ejemplo.bc3».
3. **Mediciones → Leer medición u oferta…**: elige el documento, «oferta» y un proveedor.
   - Mira el árbol de capítulos y partidas, y los avisos.
   - **Mediciones → Exportar Excel con todo…**.
4. **Modificados → Nuevo modificado…**, y después **Modificados → Cambiar cantidad de una
   partida…** con su motivo. Luego:
   - **Modificados → Exportar modificado a Excel…**;
   - **Modificados → Exportar presupuesto actualizado a BC3…**.
5. **Comprueba fuera de TRAZA**: importa ese BC3 en Presto, o en Arquímedes si lo usas.

## 5. Recorrido C: obra (unos 15 minutos)

1. **Archivo → Nueva obra desde documentos…**: nombre y carpeta, y elige **todos** los
   ficheros de «3 Obra».
   - TRAZA propone qué es cada uno: presupuesto, coste objetivo, certificación o facturas.
   - Confírmalo en la tabla y monta la obra en orden.
2. Recorre los pasos:
   - Venta (presupuesto contratado);
   - Coste objetivo, con sus paquetes;
   - Certificaciones;
   - Coste real, con las facturas del ERP;
   - Previsión: **Obra → Actualizar mi previsión…**;
   - Futuribles: **Obra → Nuevo futurible…** y **Obra → Sí / no en el escenario**.
3. **Obra → Exportar Excel de control…**.

## 6. Recorrido D: un proyecto tuyo ya terminado (lo que de verdad valida)

Repite el recorrido A con el DXF de una nave que ya hayas calculado a mano. Tus documentos
se quedan en tu ordenador. Para cada resultado, apunta en una tabla tu valor, el de TRAZA y
la diferencia:
- cargas por espacio y totales;
- caudales de aire y presión del ventilador;
- diámetros, bombas e inercia;
- secciones de cable y protecciones.

Lo mismo con el BC3 o el Excel de una oferta y con el Excel de Presto de una obra cerrada.

## 7. Cómo me cuentas lo que falle

Por cada cosa que falle o sobre, apunta:
- el paso en que estabas;
- qué hiciste;
- qué esperabas y qué salió;
- una captura de pantalla si se puede.

**No me envíes documentos reales.** Descríbeme el caso: si hace falta, lo reproduzco con
un fichero inventado de la misma forma.

## 8. Si algo va mal

- **Edición → Deshacer** deshace cualquier cambio del proyecto.
- TRAZA guarda una copia de seguridad cada vez que abres un proyecto. Para volver a una:
  **Archivo → Restaurar copia de seguridad…**.
- Un error inesperado sale en un aviso con su texto: haz una captura y me la pasas.
