from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QComboBox, QProgressBar
)
from PySide6.QtCore import Signal

class TranslationWidget(QWidget):
    request_translation = Signal(str, str, str)  # ruta, idioma_origen, idioma_destino
    cancel_translation = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.lbl_file = QLabel("Archivo de subtítulos: Ninguno")
        btn_select = QPushButton("Seleccionar archivo")
        btn_select.clicked.connect(self._select_file)

        self.cmb_source = QComboBox()
        self.cmb_source.addItems(["auto", "en", "es", "fr", "de"])

        self.cmb_target = QComboBox()
        self.cmb_target.addItems(["es", "en", "fr", "de"])

        self.progress = QProgressBar()
        self.progress.setValue(0)

        btn_translate = QPushButton("Traducir")
        btn_translate.clicked.connect(self._start_translation)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.cancel_translation.emit)

        layout.addWidget(self.lbl_file)
        layout.addWidget(btn_select)
        layout.addWidget(QLabel("Idioma origen:"))
        layout.addWidget(self.cmb_source)
        layout.addWidget(QLabel("Idioma destino:"))
        layout.addWidget(self.cmb_target)
        layout.addWidget(self.progress)
        layout.addWidget(btn_translate)
        layout.addWidget(btn_cancel)

    def _select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar subtítulo", "", "Subtítulos (*.srt *.vtt)"
        )
        if file_path:
            self.lbl_file.setText(f"Archivo: {file_path}")
            self.selected_file = file_path

    def _start_translation(self):
        if hasattr(self, "selected_file"):
            self.request_translation.emit(
                self.selected_file,
                self.cmb_source.currentText(),
                self.cmb_target.currentText()
            )

    def update_progress(self, value: int):
        self.progress.setValue(value)

    def retranslate_ui(self):
        """Actualiza todos los textos visibles según el idioma actual."""
        self.t = get_translator()
        self.lbl_file.setText(self.t("no_subtitle_file_selected"))
        # Reasignar textos de botones y etiquetas
        # Nota: Si quieres que los QComboBox cambien idioma, aquí puedes regenerar sus items
        for widget in self.findChildren(QPushButton):
            if widget.text() in [self.t("select_file"), self.t("translate"), self.t("cancel")]:
                continue  # Ya están en el idioma correcto
        # También puedes actualizar etiquetas fijas:
        # self.some_label.setText(self.t("some_key"))
