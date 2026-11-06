# ADR-0001 · Python + PySide6 (Qt Widgets)
Estado: Propuesto · 05-11-2026
**Contexto:** aplicación de escritorio local, cálculo científico, un desarrollador asistido.
**Decisión:** Python 3.12 + PySide6 con Qt Widgets (no QML).
**Motivos:** ecosistema técnico (ezdxf, NumPy, SciPy, CoolProp, fluids); PySide6 es el
binding oficial de Qt, licencia LGPLv3/GPL [V]; Widgets da docks, árboles, tablas densas y
QUndoStack.
**Descartado:** PyQt6 (GPL/comercial), Electron/Tauri (dos pilas), QML (orientado a táctil).
**Comprobado:** PySide6 6.12.0 instala en Python 3.12 y arranca sin pantalla (05-11-2026).
