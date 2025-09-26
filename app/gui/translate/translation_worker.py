# app\gui\translate\translation_worker.py
from PySide6.QtCore import QObject, Signal
from app.gui.translate.translation_service import TranslationService
from app.core import subtitles
from app.core.postprocess import postprocesar
from pathlib import Path
import time



class TranslationWorker(QObject):
    progress = Signal(int)  # 0..100 por archivo
    finished = Signal(str)  # ruta de salida
    error = Signal(str)
    line_translated = Signal(int, str, str)  # índice, original, traducido


    def __init__(self, file_path, src_lang, tgt_lang, cancel_flag, engine):
        super().__init__()
        self.file_path = file_path
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.cancel_flag = cancel_flag
        self.service = TranslationService(engine)

    def run(self):
        """Ejecuta la traducción SIN deduplicación para evitar problemas de mapeo"""
        try:
            print(f"[WORKER] Iniciando traducción: {self.file_path}")
            print(f"[WORKER] Configuración: {self.src_lang} -> {self.tgt_lang} usando {self.service.engine}")

            # Verificar cancelación antes de comenzar
            if self.cancel_flag.is_set():
                print(f"[WORKER] Cancelado antes de iniciar: {self.file_path}")
                return

            # Cargar subtítulos
            entries = subtitles.load_srt(self.file_path)
            if not entries:
                self.error.emit("Archivo de subtítulos vacío o inválido")
                return

            # Extraer textos originales MANTENIENDO EL ORDEN 1:1
            texts = [e.original for e in entries]
            total = len(texts)
            print(f"[WORKER] Cargadas {total} entradas de subtítulos")

            # Crear lista de traducciones del mismo tamaño
            translated_texts = [''] * total

            # Configuración de lotes según motor
            if self.service.engine == "google_v1":
                max_lines, max_chars, sleep_after_batch = 60, 1400, 0.02
            elif self.service.engine == "google_free":
                max_lines, max_chars, sleep_after_batch = 20, 900, 0.05
            elif self.service.engine == "mymemory":
                max_lines, max_chars, sleep_after_batch = 40, 4000, 0.0
            else:
                max_lines, max_chars, sleep_after_batch = 20, 2500, 0.02

            def create_batches_simple(items, max_lines, max_chars):
                """Crea lotes manteniendo índices originales"""
                batches = []
                current_batch = []
                current_indices = []
                char_count = 0

                for i, item in enumerate(items):
                    item_len = len(item)
                    if (current_batch and
                            (len(current_batch) >= max_lines or char_count + item_len > max_chars)):
                        batches.append((current_batch, current_indices))
                        current_batch = []
                        current_indices = []
                        char_count = 0

                    current_batch.append(item)
                    current_indices.append(i)
                    char_count += item_len

                if current_batch:
                    batches.append((current_batch, current_indices))

                return batches

            # Crear lotes preservando índices
            batches = create_batches_simple(texts, max_lines, max_chars)
            total_processed = 0

            print(f"[WORKER] Procesando {len(batches)} lotes, total items: {total}")

            # Procesar cada lote secuencialmente
            for batch_idx, (batch_texts, batch_indices) in enumerate(batches):
                if self.cancel_flag.is_set():
                    print(f"[WORKER] Cancelado durante procesamiento")
                    return

                print(f"[WORKER] Lote {batch_idx + 1}/{len(batches)}: {len(batch_texts)} elementos")
                print(f"[WORKER] Índices del lote: {batch_indices}")

                try:
                    # Traducir el lote completo
                    translated_batch = self.service.translate_lines(
                        batch_texts, self.src_lang, self.tgt_lang,
                        cancel_flag=self.cancel_flag
                    )
                    # Defensa adicional: si GoogleV1 colapsa todo en la primera línea
                    if (
                            self.service.engine == "google_v1"
                            and len(translated_batch) == len(batch_texts)
                            and translated_batch.count("") >= len(batch_texts) - 1
                            and translated_batch[0].count("\n") >= len(batch_texts) - 1
                    ):
                        split_lines = translated_batch[0].split("\n")
                        if len(split_lines) >= len(batch_texts):
                            translated_batch = split_lines[:len(batch_texts)]

                    if self.cancel_flag.is_set():
                        return

                    # Verificar que la traducción devolvió el número correcto de elementos
                    if len(translated_batch) != len(batch_texts):
                        print(
                            f"[ERROR] Discrepancia en lote {batch_idx}: esperaba {len(batch_texts)}, recibió {len(translated_batch)}")
                        # Usar originales como fallback
                        translated_batch = batch_texts

                    # Asignar traducciones DIRECTAMENTE por índice
                    for idx, (original_idx, original_text, translated_text) in enumerate(
                            zip(batch_indices, batch_texts, translated_batch)):
                        if self.cancel_flag.is_set():
                            return

                        # Asignación DIRECTA sin mapeos complejos
                        translated_texts[original_idx] = translated_text

                        # Logging detallado
                        print(
                            f"[WORKER] Asignando {original_idx}: '{original_text[:30]}...' -> '{translated_text[:30]}...'")

                        # Emitir señal para UI
                        self.line_translated.emit(original_idx, original_text, translated_text)

                    total_processed += len(batch_texts)
                    progress_value = int((total_processed / total) * 100)
                    self.progress.emit(min(99, progress_value))

                    # Sleep entre lotes
                    if sleep_after_batch > 0.0:
                        time.sleep(sleep_after_batch)

                except Exception as e:
                    print(f"[WORKER] Error en lote {batch_idx}: {e}")
                    # En caso de error, mantener textos originales para este lote
                    for original_idx, original_text in zip(batch_indices, batch_texts):
                        if translated_texts[original_idx] == '':
                            translated_texts[original_idx] = original_text
                            print(f"[WORKER] Fallback para índice {original_idx}: mantener original")

                    total_processed += len(batch_texts)
                    continue

            # Verificación final de integridad
            if self.cancel_flag.is_set():
                return

            print(f"[WORKER] Verificación final: {len(entries)} entradas, {len(translated_texts)} traducciones")

            if len(translated_texts) != len(entries):
                error_msg = f"Error crítico: {len(entries)} entradas vs {len(translated_texts)} traducciones"
                print(f"[ERROR] {error_msg}")
                self.error.emit(error_msg)
                return

            # Verificar que no hay traducciones vacías inesperadas
            empty_count = sum(1 for t in translated_texts if not t.strip())
            print(f"[WORKER] Traducciones vacías: {empty_count}/{len(translated_texts)}")

            # Asignar traducciones finales a entries
            for i, (entry, translation) in enumerate(zip(entries, translated_texts)):
                if self.cancel_flag.is_set():
                    return

                processed_translation = postprocesar(translation)
                entry.translated = processed_translation

                # Log de asignación final
                print(f"[WORKER] Final {i}: '{entry.original[:30]}...' -> '{processed_translation[:30]}...'")

                # Verificar traducciones vacías
                if entry.original.strip() and not processed_translation.strip():
                    print(f"[WARN] Traducción vacía para entrada {i}, usando original")
                    entry.translated = entry.original

            # Guardar archivo
            out_path = self._build_output_path(self.file_path)
            subtitles.save_srt(entries, out_path)

            print(f"[WORKER] Traducción completada: {out_path}")
            self.finished.emit(out_path)
            self.progress.emit(100)

        except Exception as e:
            print(f"[WORKER] Error crítico: {e}")
            import traceback
            traceback.print_exc()
            self.error.emit(f"Error procesando archivo: {str(e)}")

    def _build_output_path(self, path: str) -> str:
        """
        Construye la ruta de salida con estructura de carpetas fija.
        - Carpeta: 'Subtitles_<tgt_lang>' junto al archivo original.
        - Archivo: <nombre>_<tgtLang>.srt
        """
        p = Path(path)

        # Carpeta de salida
        folder_base = "Subtitles"
        output_folder = f"{folder_base}_{self.tgt_lang}"
        out_dir = p.parent / output_folder
        out_dir.mkdir(parents=True, exist_ok=True)

        # Nombre base traducido
        translated_name = f"{p.stem}_{self.tgt_lang}{p.suffix}"
        out_path = out_dir / translated_name

        return str(out_path)
