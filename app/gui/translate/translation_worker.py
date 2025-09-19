from PySide6.QtCore import QObject, Signal
from app.gui.translate.translation_service import TranslationService
from app.core import subtitles
import os

class TranslationWorker(QObject):
    progress = Signal(int)
    finished = Signal(str)
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
            total = len(texts)

            translated_texts = []
            batch_size = 10

            for i in range(0, total, batch_size):
                if self.cancel_flag.is_set():
                    return
                batch = texts[i:i+batch_size]
                translated_batch = self.service.translate_lines(batch, self.src_lang, self.tgt_lang)
                translated_texts.extend(translated_batch)
                self.progress.emit(int((len(translated_texts) / total) * 100))

            for e, t in zip(entries, translated_texts):
                e.translated = t

            output_file = self.file_path.replace(".srt", "_translated.srt")
            subtitles.save_srt(entries, output_file)
            self.finished.emit(output_file)

        except Exception as e:
            self.error.emit(str(e))
