import threading
from PySide6.QtCore import QObject, QTimer, QThread, Signal
from shiboken6 import isValid
from .translation_worker import TranslationWorker
from .translation_service import TranslationService
from app.core import subtitles


class TranslationController(QObject):
    # Señales
    all_finished = Signal()
    all_result = Signal(bool)
    file_finished = Signal(str)
    file_error = Signal(str, str)
    file_progress = Signal(str, int)
    processing_started = Signal()
    processing_finished = Signal()

    def __init__(self, widget):
        super().__init__(widget)
        self.widget = widget

        # Conectar señales del widget
        self.widget.request_translation.connect(self.start_translations)
        self.widget.cancel_translation.connect(self.cancel_all)

        # Estado
        self.service = None  # se inicializa por motor en cada worker si usas motor por worker
        self.threads = []
        self.workers = []
        self._queue = []
        self._max = 1
        self.active = 0
        self.is_processing = False
        self.cancel_flag = threading.Event()
        self._engine = "google_free"

        # Timer de limpieza
        self.cleanup_timer = QTimer()
        self.cleanup_timer.setInterval(2000)
        self.cleanup_timer.timeout.connect(self._cleanup_finished_threads)

    def start_translations(self, files, src_lang, tgt_lang, engine, max_concurrency=1):
        """Inicia la traducción de múltiples archivos"""
        if self.is_processing:
            print("[CONTROLLER] Ya hay un proceso en ejecución")
            return

        self._queue = list(files)
        self._max = 1  # serial por archivo, como pediste
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self._engine = engine  # ✅ guardar motor
        self.cancel_flag.clear()
        self.is_processing = True
        self.active = 0

        print(f"[CONTROLLER] Iniciando traducción de {len(files)} archivos")
        self.processing_started.emit()
        self.cleanup_timer.start()
        self._start_next()

    def _start_next(self):
        """Inicia el siguiente archivo en la cola y prepara la vista previa."""
        if not self._queue or self.active >= self._max:
            return

        file_path = self._queue.pop(0)

        # Cargar preview del archivo en la UI (lado izquierdo)
        try:
            entries = subtitles.load_srt(file_path)
            if entries:
                self.widget.load_file_preview(entries)
            else:
                print(f"[CONTROLLER] Archivo vacío o inválido para preview: {file_path}")
        except Exception as e:
            print(f"[CONTROLLER] Error cargando preview: {e}")

        # Crear hilo y worker con parámetros correctos
        thread = QThread()
        worker = TranslationWorker(file_path, self.src_lang, self.tgt_lang, self.cancel_flag, self._engine)
        worker.moveToThread(thread)

        # Conectar señales
        worker.progress.connect(lambda v, path=file_path: self._on_worker_progress(path, v))
        worker.line_translated.connect(self.widget.on_line_translated)  # << NUEVO
        worker.finished.connect(lambda out_path: self._on_worker_finished(out_path))
        worker.error.connect(lambda msg, path=file_path: self._on_worker_error(path, msg))
        thread.started.connect(worker.run)

        # Limpieza al finalizar
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(lambda: self._remove_thread(thread))
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(worker.deleteLater)

        # Guardar referencias y arrancar
        self.threads.append(thread)
        self.workers.append(worker)
        self.active += 1
        print(f"[CONTROLLER] Iniciado worker para: {file_path}, activos: {self.active}")
        thread.start()

    def _remove_thread(self, thread):
        """Elimina un hilo terminado de la lista de forma segura"""
        try:
            if thread in self.threads:
                self.threads.remove(thread)
            if isValid(thread):
                thread.deleteLater()
        except Exception as e:
            print(f"[CONTROLLER] Error removiendo thread: {e}")

    def _cleanup_finished_threads(self):
        """Limpia hilos terminados de forma segura"""
        try:
            active_threads = []
            for t in self.threads:
                if not isValid(t):
                    continue  # ya destruido por Qt
                if t.isRunning():
                    active_threads.append(t)
                else:
                    try:
                        t.deleteLater()
                    except Exception:
                        pass
            self.threads = active_threads
        except Exception as e:
            print(f"[CONTROLLER] Error en cleanup threads: {e}")

    def _on_worker_finished(self, out_path):
        # Limpiar vista de preview para el próximo archivo
        self.widget.clear_preview()
        print(f"[CONTROLLER] Archivo terminado: {out_path}")
        self.file_finished.emit(out_path)
        self.active -= 1
        if not self._queue and self.active == 0:
            self._finish_all()
        else:
            self._start_next()

    def _on_worker_error(self, file_path, error_msg):
        print(f"[CONTROLLER] Error en {file_path}: {error_msg}")
        self.file_error.emit(file_path, error_msg)
        self.active -= 1
        if not self._queue and self.active == 0:
            self._finish_all()
        else:
            self._start_next()

    def _on_worker_progress(self, file_path, progress):
        self.file_progress.emit(file_path, progress)

    def _finish_all(self, canceled=False):
        """Finaliza el proceso de traducción"""
        try:
            if self.cleanup_timer.isActive():
                self.cleanup_timer.stop()
        except Exception:
            pass

        self.is_processing = False
        self.processing_finished.emit()
        self.all_result.emit(canceled)  # ✅ True si cancelado, False si completado
        self.all_finished.emit()
        print("[CONTROLLER] Todas las traducciones finalizadas" + (" (canceladas)" if canceled else ""))

    def cleanup_on_shutdown(self):
        """Apaga de forma segura todos los hilos y limpia recursos"""
        try:
            if self.cleanup_timer.isActive():
                self.cleanup_timer.stop()

            for th in list(self.threads):
                try:
                    if isValid(th) and th.isRunning():
                        th.quit()
                        th.wait(2000)
                except Exception as e:
                    print(f"[WARN] Error terminando hilo en shutdown: {e}")
                finally:
                    try:
                        if isValid(th):
                            th.deleteLater()
                    except Exception:
                        pass

            for wk in list(self.workers):
                try:
                    wk.deleteLater()
                except Exception:
                    pass

            self.threads.clear()
            self.workers.clear()
            self.is_processing = False
            self.active = 0
            self._queue = []

            print("[CONTROLLER] Cleanup on shutdown completado")
        except Exception as e:
            print(f"[CONTROLLER] Cleanup on shutdown error: {e}")

    def cancel_all(self):
        """Cancela todas las traducciones de manera segura"""
        if not self.is_processing:
            print("[CONTROLLER] No hay proceso activo para cancelar")
            return

        print("[CONTROLLER] Iniciando cancelación...")
        self.cancel_flag.set()

        if self.cleanup_timer.isActive():
            self.cleanup_timer.stop()

        for th in list(self.threads):
            try:
                if isValid(th) and th.isRunning():
                    th.quit()
                    th.wait(2000)
            except Exception as e:
                print(f"[WARN] Error terminando hilo: {e}")
            finally:
                try:
                    if isValid(th):
                        th.deleteLater()
                except Exception:
                    pass

        self._queue = []
        self.active = 0
        self._finish_all(canceled=True)

