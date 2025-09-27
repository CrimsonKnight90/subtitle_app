# app\gui\main_window.py
from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import Signal
from app.gui.extract.extract_widget import ExtractWidget
from app.services.settings import get_settings, save_config
from app.services.i18n import get_translator
from app.gui.translate.translation_widget import TranslationWidget
from app.gui.translate.translation_controller import TranslationController
from app.services.style_manager import set_theme
import atexit
class MainWindow(QMainWindow):
    language_changed = Signal()

    def __init__(self):
        super().__init__()

        # Ruta base de iconos
        self.icon_path = Path("app/assets/icons")

        self.t = get_translator()
        self.setWindowTitle(self.t("app_title"))
        self.setWindowIcon(QIcon(str(self.icon_path / "app.svg")))
        self.resize(1000, 700)

        # Contenedor central
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Instancias de las secciones existentes
        self.extract_widget = ExtractWidget(self)

        # Nueva sección de traducción
        self.translation_widget = TranslationWidget(self)
        self.translation_controller = TranslationController(self.translation_widget)
        # en __init__ luego de crear controller
        self.translation_controller.file_progress.connect(self.translation_widget.on_file_progress)
        self.translation_controller.file_finished.connect(self.translation_widget.on_file_finished)


        # Conectar widgets a la señal de cambio de idioma
        self.language_changed.connect(self.extract_widget.retranslate_ui)

        # Bloqueo de menú durante procesos (conexión única y segura)
        self.translation_widget.processing_started.connect(self._on_processing_started)
        self.translation_widget.processing_finished.connect(self._on_processing_finished)

        # Conectar señales de ExtractWidget
        self.extract_widget.processing_started.connect(self._on_processing_started)
        self.extract_widget.processing_finished.connect(self._on_processing_finished)

        # Conectar señales del controlador
        self.translation_controller.all_result.connect(self.translation_widget.on_all_finished)

        # Añadir widgets al stack
        self.stack.addWidget(self.extract_widget)       # índice 0
        self.stack.addWidget(self.translation_widget)   # índice 1

        # --- Toolbar de acciones rápidas ---
        from PySide6.QtWidgets import QToolBar, QWidget, QSizePolicy
        self.toolbar = QToolBar("Acciones")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        # Agregar spacer para empujar el botón de tema a la derecha
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)

        # Acción de toggle de tema (sol/luna) - AHORA A LA DERECHA
        self.act_theme_toggle = QAction(self)
        self.act_theme_toggle.setToolTip("Cambiar tema (Oscuro/Claro)")
        self.act_theme_toggle.triggered.connect(self._toggle_theme)
        self.toolbar.addAction(self.act_theme_toggle)

        # Inicializar icono según tema actual
        S = get_settings()
        current_theme = S.config.get("ui_theme", "dark")
        self._update_theme_icon(current_theme)

        # Conectar señales de ExtractWidget
        self.extract_widget.request_menu_rebuild.connect(self._rebuild_menubar)
        self.extract_widget.request_title_change.connect(self.setWindowTitle)

        # Construir menú inicial
        self._rebuild_menubar()

        # AÑADIR ESTAS LÍNEAS NUEVAS:
        # Cleanup al cerrar aplicación
        atexit.register(self.translation_controller.cleanup_on_shutdown)

    def _rebuild_menubar(self):
        self.menuBar().clear()

        # Menú principal
        menu_subs = self.menuBar().addMenu(self.t("subtitles_menu"))
        act_extract = QAction(self.t("menu_extract"), self)
        act_subs_translate = QAction(self.t("menu_translate"), self)

        act_extract.triggered.connect(lambda: self.stack.setCurrentWidget(self.extract_widget))
        act_subs_translate.triggered.connect(lambda: self.stack.setCurrentWidget(self.translation_widget))

        menu_subs.addAction(act_extract)
        menu_subs.addAction(act_subs_translate)

        # Menú de configuración
        menu_config = self.menuBar().addMenu(self.t("preferences"))

        # Idioma
        menu_lang = menu_config.addMenu(self.t("interface_language"))
        for code in ["es", "en", "fr"]:
            act = menu_lang.addAction(self.t({"es": "spanish", "en": "english", "fr": "french"}[code]))
            act.triggered.connect(lambda _, c=code: self._cambiar_idioma(c))

        # TEMA MOVIDO AQUÍ (segundo lugar)
        menu_theme = menu_config.addMenu(self.t("interface_theme") if hasattr(self.t, "__call__") else "Tema")
        act_dark = menu_theme.addAction("Oscuro")
        act_light = menu_theme.addAction("Claro")
        act_dark.triggered.connect(lambda: set_theme(self._app(), "dark"))
        act_light.triggered.connect(lambda: set_theme(self._app(), "light"))

        # Menú de ayuda (al final)
        menu_help = self.menuBar().addMenu(self.t("help"))
        act_manual = menu_help.addAction(self.t("manual"))
        act_manual.triggered.connect(self._mostrar_manual)

        act_ffmpeg = menu_help.addAction("Descargar FFmpeg")
        act_ffmpeg.triggered.connect(lambda: self._abrir_ffmpeg_web())

    def _abrir_ffmpeg_web(self):
        import webbrowser
        webbrowser.open("https://ffmpeg.org/download.html")

    def _toggle_theme(self):
        S = get_settings()
        current = S.config.get("ui_theme", "dark")
        new_theme = "light" if current == "dark" else "dark"
        # Persistir y aplicar
        set_theme(self._app(), new_theme)
        # Actualizar icono del botón
        self._update_theme_icon(new_theme)

    def _update_theme_icon(self, theme: str):
        # Usa tus SVG: sol para light, luna para dark
        icon_name = "sun.svg" if theme == "light" else "moon.svg"
        icon_path = self.icon_path / icon_name
        self.act_theme_toggle.setIcon(QIcon(str(icon_path)))
        # Texto accesible
        self.act_theme_toggle.setText("Claro" if theme == "light" else "Oscuro")

    def _app(self):
        from PySide6.QtWidgets import QApplication
        return QApplication.instance()

    def _mostrar_manual(self):
        QMessageBox.information(
            self,
            self.t("manual_title"),
            self.t("manual_message")
        )

    def _cambiar_idioma(self, lang_code):
        S = get_settings()
        S.config["ui_language"] = lang_code
        save_config(S.config)
        if hasattr(self.translation_widget, "retranslate_ui"):
            self.translation_widget.retranslate_ui()
        self.t = get_translator()
        self.extract_widget.t = get_translator()
        self.extract_widget.tree.set_ui_language(lang_code)
        self.extract_widget._apply_translations()

        self.language_changed.emit()
        self._rebuild_menubar()

    def _on_processing_started(self):
        """Maneja el inicio de procesamiento de manera segura"""
        try:
            self.menuBar().setEnabled(False)
        except Exception as e:
            print(f"[WARN] Error deshabilitando menú: {e}")

    def _on_processing_finished(self):
        """Maneja el fin de procesamiento de manera segura"""
        try:
            self.menuBar().setEnabled(True)
        except Exception as e:
            print(f"[WARN] Error habilitando menú: {e}")

    def closeEvent(self, event):
        """Maneja el cierre de la ventana de manera segura"""
        try:
            # Cleanup del controlador antes de cerrar
            if hasattr(self, 'translation_controller'):
                self.translation_controller.cleanup_on_shutdown()
            event.accept()
        except Exception as e:
            print(f"[MAIN] Error en closeEvent: {e}")
            event.accept()