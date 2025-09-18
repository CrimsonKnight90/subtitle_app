from PySide6.QtCore import QObject, Signal, Slot
import time
from .translation_service import TranslationService

class TranslationWorker(QObject):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, file_path, src_lang, tgt_lang, cancel_flag):
        super().__init__()
        self.file_path = file_path
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.cancel_flag = cancel_flag
        self.service = TranslationService()

    @Slot()
    def run(self):
        try:
            # Leer archivo de subtítulos
            with open(self.file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            total = len(lines)
            translated_lines = []

            for i, line in enumerate(lines):
                if self.cancel_flag.is_set():
                    self.error.emit("Traducción cancelada por el usuario.")
                    return

                # Solo traducir líneas que no sean números ni timestamps
                if not line.strip().isdigit() and "-->" not in line:
                    translated_line = self.service.translate_text(
                        line.strip(), self.src_lang, self.tgt_lang
                    )
                    translated_lines.append(translated_line + "\n")
                else:
                    translated_lines.append(line)

                # Emitir progreso
                self.progress.emit(int((i + 1) / total * 100))
                time.sleep(0.01)  # Simulación de carga

            # Guardar archivo traducido
            output_file = self.file_path.replace(".srt", "_translated.srt")
            with open(output_file, "w", encoding="utf-8") as f:
                f.writelines(translated_lines)

            self.finished.emit(output_file)

        except Exception as e:
            self.error.emit(str(e))
