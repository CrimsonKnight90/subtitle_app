from PySide6.QtCore import QObject, Signal
from app.gui.translate.translation_service import TranslationService
from app.core import subtitles
from pathlib import Path

class TranslationWorker(QObject):
    progress = Signal(int)        # 0..100 por archivo
    finished = Signal(str)        # ruta de salida
    error = Signal(str)

    def __init__(self, file_path, src_lang, tgt_lang, cancel_flag, engine):
        super().__init__()
        self.file_path = file_path
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.cancel_flag = cancel_flag
        self.service = TranslationService(engine)

    def run(self):
        try:
            entries = subtitles.load_srt(self.file_path)
            texts = [e.original for e in entries]
            total = max(1, len(texts))
            translated_texts = []

            batch_size = 25  # un poco más grande tras dedup
            for i in range(0, total, batch_size):
                if self.cancel_flag.is_set():
                    return
                batch = texts[i:i+batch_size]
                translated_batch = self.service.translate_lines(batch, self.src_lang, self.tgt_lang)
                translated_texts.extend(translated_batch)
                self.progress.emit(int((len(translated_texts) / total) * 100))

            for e, t in zip(entries, translated_texts):
                e.translated = t

            out = self._build_output_path(self.file_path)
            subtitles.save_srt(entries, out)
            self.finished.emit(out)
        except Exception as e:
            self.error.emit(str(e))

    def _build_output_path(self, path: str) -> str:
        p = Path(path)
        return str(p.with_name(p.stem + "_translated" + p.suffix))
