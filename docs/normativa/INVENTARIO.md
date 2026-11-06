# Inventario normativo

> Origen: especificación de Etapa 0 (`docs/ETAPA0_ESPECIFICACION.md`, 05-11-2026).
> Marcas de rigor: **[V]** verificado con fuente · **[V2]** solo fuentes secundarias · **[C]** conocimiento sin verificar aún · **[P]** propuesta · **[?]** dato pendiente.

## 5. Marco normativo inicial

Se cargará como **datos** en `normativa/`, con versión y fuente. Esta tabla es el inventario, **no** el contenido.

| Norma | Disciplina | Estado comprobado hoy | Uso previsto |
|---|---|---|---|
| RITE — RD 1027/2007; última modificación de fondo RD 178/2021 | Clima / ventilación (bienestar) | [V2] Vigente con modificaciones. Hay un proyecto de reforma en tramitación; **no he podido confirmar** si se ha publicado. Confirmar en BOE antes de Etapa 3. | Calidad de aire, eficiencia, aislamiento, ámbito. |
| REBT — RD 842/2002 e ITC-BT | Electricidad | [V2] Vigente con modificaciones; listado de normas de la ITC-BT-02 actualizado por resoluciones; proyecto de modificación de varias ITC notificado a la UE. | Previsión, secciones, ΔU, protecciones, tierras. |
| **RSCIEI — RD 164/2025** (deroga RD 2267/2004) | PCI en establecimientos industriales | [V2] Publicado BOE 10-04-2025; en vigor 10-05-2025. | Caracterización, sectorización, requisitos de instalaciones PCI en naves. |
| RIPCI — RD 513/2017 | PCI (instalaciones) | [C] Vigente; según COAM, modificado por el RD 164/2025 [V2]. | Diseño/instalación de equipos PCI. |
| CTE — RD 314/2006 (DB SI, HS, HE, SE…) | Varias | [C] Vigente con modificaciones; confirmar texto consolidado. | Fontanería (HS4), saneamiento (HS5), ventilación (HS3 en su ámbito), acciones (SE-AE). |
| Código Estructural — RD 470/2021 | Estructura | [V2] En vigor desde 10-11-2021; deroga EHE-08 y EAE; el DB SE-A sigue aplicándose en edificación según colegios profesionales. | Etapa 7 (si se decide). |
| Eurocódigos (UNE-EN 1990–1999 + Anejos Nacionales) | Estructura | [C] | Etapa 7. |
| NCSE-02 — RD 997/2002 | Sismo | [C] | Etapa 7. |
| RSIF — RD 552/2019 | Refrigeración | [C] | Carga de refrigerante, clasificación de sistemas, documentación. |
| REP — RD 809/2021 | Equipos a presión | [C] | Cuando corresponda. |
| RD 486/1997 (lugares de trabajo) | Ventilación de naves | [C] | Caudal mínimo por trabajador y condiciones ambientales en locales de trabajo. |
| Reglamento (UE) 2024/573 (gases fluorados) | Refrigeración | [C] | Restricciones de refrigerantes. |
| Normas UNE / UNE-EN citadas por los reglamentos | Todas | Derechos de autor (AENOR). | **Solo** con tu ejemplar (C-03). |
| Guía IDAE «Condiciones climáticas exteriores de proyecto» | Cargas térmicas | [C] | Datos climáticos de proyecto con fuente. |

Estructura de cada entrada normativa [P]:

```yaml
id: REBT.ITC-BT-19.2.2.2
norma: REBT (RD 842/2002)
version: "texto consolidado BOE, fecha ..."
tipo: obligatorio | recomendacion | hipotesis | criterio_fabricante
ambito: "instalaciones interiores o receptoras"
contenido: { ...parámetros... }
fuente: { documento: "BOE-A-2002-18099", localizador: "ITC-BT-19 apdo. 2.2.2", url: ... }
verificado_por: usuario | pendiente
fecha_verificacion: 2026-..-..
```

Una entrada con `verificado_por: pendiente` **no** puede emitir un «CUMPLE»; solo «no evaluable: criterio sin verificar».

---

## 13. Fuentes consultadas en esta sesión

- Autodesk — AutoLISP en AutoCAD LT 2024 (novedades y limitaciones): https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-LT-WhatsNew/files/GUID-5FB57480-C9BE-4E3D-BEDF-D86035928FFA.htm ; https://www.autodesk.com/blogs/autocad/autocad-lt-2024-autolisp/
- PyMuPDF — doble licencia AGPL/comercial: https://pypi.org/project/PyMuPDF/1.19.0/
- ezdxf — licencia MIT, sin conversión a DWG, recomienda ODA File Converter: https://ezdxf.readthedocs.io/en/stable/introduction.html
- Open Design Alliance — ODA File Converter, uso no comercial salvo miembros: https://www.opendesign.com/node/3218
- Qt for Python — licencias LGPLv3/GPLv3/comercial: https://doc.qt.io/qtforpython/
- OCCT — LGPL-2.1 con excepción: https://dev.opencascade.org/doc/overview/html/occt_public_license.html
- IfcOpenShell — LGPL-3.0: https://www.github.com/IfcOpenShell/IfcOpenShell
- CoolProp — MIT: https://salsa.debian.org/kkremitzki/coolprop/-/blob/master/LICENSE
- Código Estructural RD 470/2021: https://www.boe.es/eli/es/rd/2021/06/29/470 ; coexistencia con DB SE-A: https://arquitectes.cat/es/printpdf/36268 ; https://www.ietcc.csic.es/wp-content/uploads/2021/11/jornada_codigo_estructural_24nov.pdf
- RSCIEI RD 164/2025: https://www.coam.org/actualidad-noticias-nuevo-reglamento-seguridad-contra-incendios-establecimientos/ ; https://www.tecnifuego.org/comunicacion/rsciei-2025-vs-2004-que-cambia-y-como-afecta-los-establecimientos-industriales ; https://www.coial.org/publicado-el-nuevo-reglamento-de-seguridad-contra-incendios-en-los-establecimientos-industriales/
- RITE, estado y reforma en tramitación: https://www.activatie.org/noticia?2601-Consulta-p%C3%BAblica-sobre-el-el-proyecto-de-RD-que-modifica-el-RITE= ; https://www.caloryfrio.com/noticias/normativas/nuevo-rite.html
- REBT, texto consolidado y modificaciones: https://www.boe.es/buscar/pdf/2002/BOE-A-2002-18099-consolidado.pdf ; https://www.coeib.com/noticia/real-decreto-por-el-que-se-modifican-el-reglamento-electrotecnico-para-baja-tension-y-el-reglamento-sobre-condiciones-tecnicas-y-garantias-de-seguridad-en-instalaciones-electricas-de-alta-tension-e-itcs ; https://www.boe.es/diario_boe/txt.php?id=BOE-A-2020-612

---

**Nota 05-11-2026:** por decisión del usuario la estructura se limita a geometría. El Código
Estructural, los Eurocódigos y la NCSE-02 quedan fuera del alcance de cálculo; se mantienen
en el inventario solo como referencia.
