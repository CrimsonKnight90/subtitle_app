# main.py
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from app.gui.main_window import MainWindow
from app.services.settings import get_settings
from app.services.style_manager import apply_theme

def show_fatal_error(message):
    """Muestra un mensaje de error fatal antes de cerrar."""
    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.critical(None, "Error fatal", f"❌ El programa encontró un error inesperado:\n\n{message}")
    sys.exit(1)

def main():
    try:
        app = QApplication(sys.argv)
        S = get_settings()
        apply_theme(app, S.config.get("ui_theme", "dark"))

        # Cargar estilos desde styles.qss si existe
        qss_path = Path("styles.qss")
        if qss_path.exists():
            try:
                with open(qss_path, "r", encoding="utf-8") as f:
                    app.setStyleSheet(f.read())
            except Exception as e:
                print(f"⚠ No se pudo cargar styles.qss: {e}")

        win = MainWindow()
        win.show()
        sys.exit(app.exec())

    except Exception as e:
        show_fatal_error(str(e))

if __name__ == "__main__":
    main()
