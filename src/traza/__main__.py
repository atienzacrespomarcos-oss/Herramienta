"""Arranque de TRAZA: `python -m traza [carpeta.traza]` o el ejecutable TRAZA.exe.

`--autoprueba` recorre el escenario de aceptación de la Etapa 1 sin ventana visible y
termina con código 0 si todo funciona. Sirve para comprobar que el ejecutable generado
en GitHub funciona de verdad, no solo que se ha compilado.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


def _autoprueba() -> int:
    import pymupdf

    from traza.app.ordenes import Aprobar, CrearElemento, FijarPropiedad
    from traza.app.proyecto import ElementoBloqueado, Proyecto
    from traza.core.procedencia import Origen, Procedencia

    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "prueba.pdf"
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), "autoprueba")
        doc.save(pdf)
        doc.close()
        p = Proyecto.crear(Path(tmp) / "Autoprueba", "Autoprueba")
        try:
            doc_id = p.incorporar_documento(pdf)
            o = CrearElemento("equipo", "EQ-1")
            p.ejecutar(o)
            usuario = Procedencia(Origen.USUARIO)
            p.ejecutar(FijarPropiedad(o.id, "fabricante", "F", None, usuario))
            p.ejecutar(FijarPropiedad(o.id, "modelo", "M", None, usuario))
            cita = Procedencia(Origen.DOCUMENTO, documento_id=doc_id, localizador="p. 1")
            p.ejecutar(FijarPropiedad(o.id, "caudal_aire", 2400, "m³/h", cita))
            p.ejecutar(Aprobar(o.id, "autoprueba"))
            try:
                p.ejecutar(FijarPropiedad(o.id, "caudal_aire", 1, "m³/h", usuario))
                raise AssertionError("se modificó un elemento aprobado")
            except ElementoBloqueado:
                pass  # solo vale el rechazo POR estar aprobado, no cualquier otro
            if p.deshacer() != "Aprobar" or p.elemento(o.id)["estado"] != "borrador":
                raise AssertionError("deshacer no revirtió la aprobación")
            if p.rehacer() != "Aprobar" or p.elemento(o.id)["estado"] != "aprobado":
                raise AssertionError("rehacer no repuso la aprobación")
            # La justificación en Word: python-docx necesita su plantilla interna, que
            # PyInstaller solo empaqueta con --collect-data docx.
            word = p.exportar_memoria(Path(tmp) / "autoprueba")
            if not word.exists() or word.stat().st_size == 0:
                raise AssertionError("no se generó la justificación en Word")
        finally:
            p.cerrar()
        _autoprueba_dxf(Path(tmp))
    return 0


def _autoprueba_dxf(carpeta: Path) -> None:
    """El lector DXF dentro del .exe: un ezdxf empaquetado a medias falla aquí, no en un
    plano del usuario."""
    import ezdxf

    from traza.io.dxf import leer_dxf

    doc = ezdxf.new("R2013")
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_lwpolyline([(0, 0), (40000, 0), (40000, 25000), (0, 25000)], close=True)
    ruta = carpeta / "autoprueba.dxf"
    doc.saveas(ruta)
    plano = leer_dxf(ruta)
    area = plano.contornos[0].contorno.escalado(0.001).area
    if plano.unidad_propuesta != "mm" or abs(area - 1000) > 1e-9:
        raise AssertionError(f"lector DXF: unidad {plano.unidad_propuesta}, superficie {area}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="traza")
    parser.add_argument("proyecto", nargs="?", help="carpeta .traza a abrir")
    parser.add_argument("--autoprueba", action="store_true")
    parser.add_argument(
        "--informe",
        help="fichero donde escribir el resultado de la autoprueba (TRAZA.exe no tiene consola)",
    )
    args = parser.parse_args(argv)

    if args.autoprueba:
        from PySide6.QtWidgets import QApplication

        from traza.ui.ventana import VentanaPrincipal

        # Cualquier excepción se convierte en código 1 y en texto: si escapara, el .exe sin
        # consola mostraría un cuadro modal y el CI esperaría a que alguien lo cerrara.
        try:
            app = QApplication.instance() or QApplication(sys.argv[:1])
            VentanaPrincipal()  # la interfaz también tiene que poder construirse
            codigo, texto = _autoprueba(), "Autoprueba correcta"
            app.quit()
        except BaseException:  # noqa: BLE001
            import traceback

            codigo, texto = 1, "Autoprueba FALLIDA\n" + traceback.format_exc()
        if args.informe:
            Path(args.informe).write_text(texto, encoding="utf-8")
        if sys.stdout is not None:  # None en el .exe con ventana
            print(texto)
        return codigo

    from PySide6.QtWidgets import QApplication

    from traza.ui.ventana import VentanaPrincipal

    app = QApplication(sys.argv[:1])
    app.setApplicationName("TRAZA")
    app.setOrganizationName("TRAZA")
    ventana = VentanaPrincipal()
    if args.proyecto:
        ventana.abrir(Path(args.proyecto))
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
