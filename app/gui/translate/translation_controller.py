import threading
from PySide6.QtCore import QThread, QObject, Signal

from app.gui.translate.translation_worker import TranslationWorker

class TranslationController(QObject):
    all_started = Signal()
    all_finished = Signal()
    file_progress = Signal(str, int)   # path, %
    file_finished = Signal(str)        # path
    file_error = Signal(str, str)      # path, error

    def __init__(self, widget):
        super().__init__(widget)
        self.widget = widget
        self.widget.request_translation.connect(self.start_translations)  # ahora lista de paths
        self.widget.cancel_translation.connect(self.cancel_all)

        self.cancel_flag = threading.Event()
        self.threads = []
        self.workers = []
        self.active = 0

    def start_translations(self, file_paths, src_lang, tgt_lang, engine, max_concurrency=2):
        if not file_paths:
            return
        self.cancel_flag.clear()
        self.all_started.emit()
        self.active = 0
        self._queue = list(file_paths)
        self._src = src_lang
        self._dst = tgt_lang
        self._engine = engine
        self._max = max_concurrency
        self._start_next_batch()

    def _start_next_batch(self):
        while self._queue and len(self.threads) < self._max:
            fp = self._queue.pop(0)
            th = QThread()
            wk = TranslationWorker(fp, self._src, self._dst, self.cancel_flag, self._engine)
            wk.moveToThread(th)

            th.started.connect(wk.run)
            wk.progress.connect(lambda v, fp=fp: self.file_progress.emit(fp, v))
            wk.finished.connect(lambda out, fp=fp: self._on_file_finished(fp, out))
            wk.error.connect(lambda msg, fp=fp: self._on_file_error(fp, msg))

            wk.finished.connect(th.quit); wk.error.connect(th.quit)
            th.finished.connect(th.deleteLater); th.finished.connect(wk.deleteLater)

            self.threads.append(th); self.workers.append(wk)
            th.start()
            self.active += 1

    def _on_file_finished(self, fp, out):
        self.file_finished.emit(out)
        self._cleanup(fp)
        self._start_next_batch()
        self._maybe_all_done()

    def _on_file_error(self, fp, msg):
        self.file_error.emit(fp, msg)
        self._cleanup(fp)
        self._start_next_batch()
        self._maybe_all_done()

    def _cleanup(self, fp):
        # retirar hilo terminado
        self.threads = [t for t in self.threads if t.isRunning()]
        self.workers = [w for w in self.workers if w is not None]

    def _maybe_all_done(self):
        if not self._queue and not self.threads:
            self.all_finished.emit()

    def cancel_all(self):
        self.cancel_flag.set()
