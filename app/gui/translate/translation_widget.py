from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QComboBox, QProgressBar, QGroupBox, QFormLayout, QSizePolicy
)
from PySide6.QtCore import Signal
from app.services.i18n import get_translator

class TranslationWidget(QWidget):
    # Señal con 4 parámetros: archivo, idioma origen, idioma destino, motor
    request_translation = Signal(str, str, str, str)
    cancel_translation = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_file = None
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # --- Sección archivo ---
        file_group = QGroupBox("Archivo de subtítulos")
        file_layout = QHBoxLayout()
        self.lbl_file = QLabel("Ninguno seleccionado")
        btn_select = QPushButton("Seleccionar...")
        btn_select.clicked.connect(self._select_file)
        file_layout.addWidget(self.lbl_file, stretch=1)
        file_layout.addWidget(btn_select)
        file_group.setLayout(file_layout)

        # --- Sección configuración ---
        config_group = QGroupBox("Configuración de traducción")
        form_layout = QFormLayout()
        self.cmb_source = QComboBox()
        self.cmb_source.addItems(["auto", "en", "es", "fr", "de"])
        self.cmb_target = QComboBox()
        self.cmb_target.addItems(["es", "en", "fr", "de"])
        self.cmb_engine = QComboBox()
        self.cmb_engine.addItems(["google_free", "mymemory", "libre_online", "libre_offline"])
        form_layout.addRow("Idioma origen:", self.cmb_source)
        form_layout.addRow("Idioma destino:", self.cmb_target)
        form_layout.addRow("Motor:", self.cmb_engine)
        config_group.setLayout(form_layout)

        # --- Barra de progreso ---
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # --- Botones ---
        btn_layout = QHBoxLayout()
        btn_translate = QPushButton("Traducir")
        btn_translate.setObjectName("PrimaryButton")  # Usa estilo del QSS
        btn_translate.clicked.connect(self._start_translation)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setObjectName("DangerButton")  # Usa estilo del QSS
        btn_cancel.clicked.connect(self.cancel_translation.emit)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_translate)
        btn_layout.addWidget(btn_cancel)

        # --- Añadir todo al layout principal ---
        main_layout.addWidget(file_group)
        main_layout.addWidget(config_group)
        main_layout.addWidget(self.progress)
        main_layout.addLayout(btn_layout)

    def _select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar subtítulo", "", "Subtítulos (*.srt *.vtt)"
        )
        if file_path:
            self.lbl_file.setText(file_path)
            self.selected_file = file_path

    def _start_translation(self):
        if self.selected_file:
            self.request_translation.emit(
                self.selected_file,
                self.cmb_source.currentText(),
                self.cmb_target.currentText(),
                self.cmb_engine.currentText()
            )

    def update_progress(self, value: int):
        self.progress.setValue(value)

    def retranslate_ui(self):
        """Actualiza todos los textos visibles según el idioma actual."""
        self.t = get_translator()
        self.lbl_file.setText(self.t("no_subtitle_file_selected"))
        # Aquí actualizarías textos de botones y etiquetas si usas i18n
