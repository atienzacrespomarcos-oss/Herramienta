# ADR-0008 · DXF como intercambio principal; DWG fuera
Estado: Propuesto · 05-11-2026
**Decisión:** salida gráfica principal en DXF R2013 (AC1027) con ezdxf (MIT) [V];
AutoLISP como complemento para operar sobre dibujos abiertos.
**Motivos:** el DXF se verifica en tests automáticos; el LISP no sin AutoCAD. El usuario
tiene AutoCAD completo 2013–2017.
**DWG descartado:** ODA File Converter es de uso no comercial salvo miembros de ODA [V].
**Comprobado:** ezdxf 1.4.5 genera AC1027 sin errores de auditoría (05-11-2026).
