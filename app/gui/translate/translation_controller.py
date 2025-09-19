import os
import threading
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QMessageBox
from app.core import libretranslate_manager
from app.gui.translate.translation_worker import TranslationWorker

class TranslationController:
    def __init__(self, widget):
        self.widget = widget
        self.widget.request_translation.connect(self.start_translation)
        self.widget.cancel_translation.connect(self.cancel_translation)
        self.cancel_flag = threading.Event()
        self.thread = None
        self.worker = None

    def start_translation(self, file_path, src_lang, tgt_lang, engine):
        if engine == "libre_offline":
            vendors_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vendors"))
            if not libretranslate_manager.ensure_libretranslate(vendors_path):
                QMessageBox.critical(self.widget, "Error", "No se pudo iniciar LibreTranslate Offline.")
                return

        self.cancel_flag.clear()
        self.thread = QThread()
        self.worker = TranslationWorker(file_path, src_lang, tgt_lang, self.cancel_flag, engine)
        self.worker.moveToThread(self.thread)

        # Conexiones
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.widget.update_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)

        # Limpieza
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.worker.deleteLater)

        self.thread.start()

    def cancel_translation(self):
        self.cancel_flag.set()
        # Opcional: resetear barra de progreso
        # self.widget.update_progress(0)

    def _on_finished(self, output_file):
        QMessageBox.information(self.widget, "Completado", f"Traducción finalizada: {output_file}")
        self.worker = None

    def _on_error(self, message):
        QMessageBox.critical(self.widget, "Error", message)
        self.worker = None
