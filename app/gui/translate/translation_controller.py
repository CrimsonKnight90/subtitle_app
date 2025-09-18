from PySide6.QtCore import QThread
import threading
from .translation_worker import TranslationWorker

class TranslationController:
    def __init__(self, widget):
        self.widget = widget
        self.widget.request_translation.connect(self.start_translation)
        self.widget.cancel_translation.connect(self.cancel_translation)
        self.cancel_flag = threading.Event()

    def start_translation(self, file_path, src_lang, tgt_lang):
        self.cancel_flag.clear()
        self.thread = QThread()
        self.worker = TranslationWorker(file_path, src_lang, tgt_lang, self.cancel_flag)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.widget.update_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)

        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def cancel_translation(self):
        self.cancel_flag.set()

    def _on_finished(self, output_file):
        self.widget.update_progress(100)
        print(f"Traducción completada: {output_file}")

    def _on_error(self, message):
        print(f"Error: {message}")
