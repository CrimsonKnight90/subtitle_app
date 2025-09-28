# main.py
import sys, os
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon
from app.gui.main_window import MainWindow
from app.services.settings import get_settings
from app.services.style_manager import apply_theme

def resource_path(relative_path: str) -> str:
    """Devuelve la ruta absoluta al recurso, compatible con PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def show_fatal_error(message):
    """Muestra un mensaje de error fatal antes de cerrar."""
    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.critical(None, "Error fatal", f"❌ El programa encontró un error inesperado:\n\n{message}")
    sys.exit(1)

def main():
    try:
        app = QApplication(sys.argv)
        S = get_settings()

        # 🔹 Aplica el tema guardado en config.json (dark/light)
        apply_theme(app, S.config.get("ui_theme", "dark"))

        # 🔹 Establecer icono global de la aplicación
        icon_path = resource_path("app/assets/icons/exe.ico")
        app.setWindowIcon(QIcon(icon_path))

        win = MainWindow()
        # Opcional: también puedes fijar el icono en la ventana principal
        win.setWindowIcon(QIcon(icon_path))

        win.show()
        sys.exit(app.exec())

    except Exception as e:
        show_fatal_error(str(e))


if __name__ == "__main__":
    main()
