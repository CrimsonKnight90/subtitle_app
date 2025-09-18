from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox
from PySide6.QtGui import QAction, QIcon
from app.gui.extract.extract_widget import ExtractWidget
from app.services.settings import get_settings, save_config
from PySide6.QtCore import Signal
from app.services.i18n import get_translator

# 🔹 NUEVOS IMPORTS
from app.gui.translate.translation_widget import TranslationWidget
from app.gui.translate.translation_controller import TranslationController


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

        # 🔹 NUEVA SECCIÓN DE TRADUCCIÓN DE SUBTÍTULOS
        self.translation_widget = TranslationWidget(self)
        self.translation_controller = TranslationController(self.translation_widget)

        # Conectar widgets a la señal de cambio de idioma
        self.language_changed.connect(self.extract_widget.retranslate_ui)
        # Si quieres que TranslationWidget soporte cambio de idioma, implementa retranslate_ui en él y descomenta:
        # self.language_changed.connect(self.translation_widget.retranslate_ui)

        # Conectar señales para bloquear menú durante extracción
        self.extract_widget.processing_started.connect(lambda: self.menuBar().setEnabled(False))
        self.extract_widget.processing_finished.connect(lambda: self.menuBar().setEnabled(True))

        # Conectar señales para bloquear menú durante traducción de subtítulos
        if hasattr(self.translation_widget, "processing_started"):
            self.translation_widget.processing_started.connect(lambda: self.menuBar().setEnabled(False))
        if hasattr(self.translation_widget, "processing_finished"):
            self.translation_widget.processing_finished.connect(lambda: self.menuBar().setEnabled(True))

        # Añadir widgets al stack
        self.stack.addWidget(self.extract_widget)       # índice 0
        self.stack.addWidget(self.translation_widget)   # índice 1

        # Conectar señales de ExtractWidget
        self.extract_widget.request_menu_rebuild.connect(self._rebuild_menubar)
        self.extract_widget.request_title_change.connect(self.setWindowTitle)

        # Construir menú inicial
        self._rebuild_menubar()

    def _rebuild_menubar(self):
        self.menuBar().clear()

        # Menú principal de subtítulos
        menu_subs = self.menuBar().addMenu(self.t("subtitles_menu"))
        act_extract = QAction(self.t("menu_extract"), self)
        act_subs_translate = QAction(self.t("menu_subtitles_translate"), self)

        act_extract.triggered.connect(lambda: self.stack.setCurrentWidget(self.extract_widget))
        act_subs_translate.triggered.connect(lambda: self.stack.setCurrentWidget(self.translation_widget))

        menu_subs.addAction(act_extract)
        menu_subs.addAction(act_subs_translate)

        # Menú de configuración
        menu_config = self.menuBar().addMenu(self.t("preferences"))
        menu_lang = menu_config.addMenu(self.t("interface_language"))
        for code in ["es", "en", "fr"]:
            act = menu_lang.addAction(self.t({"es": "spanish", "en": "english", "fr": "french"}[code]))
            act.triggered.connect(lambda _, c=code: self._cambiar_idioma(c))

        # Menú de ayuda
        menu_help = self.menuBar().addMenu(self.t("help"))
        act_manual = menu_help.addAction(self.t("manual"))
        act_manual.triggered.connect(self._mostrar_manual)

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

        self.t = get_translator()
        self.extract_widget.t = get_translator()
        self.extract_widget.tree.set_ui_language(lang_code)
        self.extract_widget._apply_translations()

        # Emitir señal global para refrescar todos los widgets conectados
        self.language_changed.emit()

        # Reconstruir menús con el nuevo idioma
        self._rebuild_menubar()
