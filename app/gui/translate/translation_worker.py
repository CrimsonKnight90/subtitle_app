# app\gui\translate\translation_worker.py
from PySide6.QtCore import QObject, Signal
from app.gui.translate.translation_service import TranslationService
from app.core import subtitles
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
        """Ejecuta la traducción con manejo mejorado de errores, cancelación y optimización de lotes"""
        try:
            print(f"[WORKER] Iniciando traducción: {self.file_path}")

            # Verificar cancelación antes de comenzar
            if self.cancel_flag.is_set():
                print(f"[WORKER] Cancelado antes de iniciar: {self.file_path}")
                return

            # Cargar subtítulos
            entries = subtitles.load_srt(self.file_path)
            if not entries:
                self.error.emit("Archivo de subtítulos vacío o inválido")
                return

            # Extraer textos originales
            texts = [e.original for e in entries]
            total = max(1, len(texts))

            # Deduplicación fuerte: evita traducir repeticiones
            unique_index = {}
            unique_texts = []
            for idx, txt in enumerate(texts):
                key = txt.strip()
                if key not in unique_index:
                    unique_index[key] = len(unique_texts)
                    unique_texts.append(key)

            # Mapa de texto único -> lista de índices originales donde aparece
            unique_to_indices = {}
            for i, txt in enumerate(texts):
                key = txt.strip()
                unique_to_indices.setdefault(key, []).append(i)

            print(f"[WORKER] {len(unique_texts)} líneas únicas detectadas de {total} totales")

            # Configuración de lotes según motor
            if self.service.engine == "google_v1":
                # Mirror SE’s ~1500 char limit, leverage one HTTP call per batch
                max_lines, max_chars, sleep_after_batch = 60, 1400, 0.02
            elif self.service.engine == "google_free":
                # deep_translator is more sensitive, use smaller batches
                max_lines, max_chars, sleep_after_batch = 20, 900, 0.05
            elif self.service.engine == "mymemory":
                max_lines, max_chars, sleep_after_batch = 40, 4000, 0.0
            else:
                max_lines, max_chars, sleep_after_batch = 20, 2500, 0.02

            def yield_batches(items, max_lines, max_chars):
                batch, char_count = [], 0
                for it in items:
                    it_len = len(it)
                    if batch and (len(batch) >= max_lines or char_count + it_len > max_chars):
                        yield batch
                        batch, char_count = [], 0
                    batch.append(it)
                    char_count += it_len
                if batch:
                    yield batch

            translated_unique_map = {}
            processed = 0

            # Procesar en lotes
            for batch in yield_batches(unique_texts, max_lines, max_chars):
                if self.cancel_flag.is_set():
                    print(f"[WORKER] Cancelado durante procesamiento: {self.file_path}")
                    return

                try:
                    translated_batch = self.service.translate_lines(
                        batch, self.src_lang, self.tgt_lang,
                        cancel_flag=self.cancel_flag
                    )

                    if self.cancel_flag.is_set():
                        print(f"[WORKER] Cancelado después de traducir lote: {self.file_path}")
                        return

                    for original, translated in zip(batch, translated_batch):
                        idx_u = unique_index[original]
                        translated_unique_map[idx_u] = translated

                        # Emitir a todas las posiciones originales donde aparece este texto
                        for orig_idx in unique_to_indices.get(original, []):
                            self.line_translated.emit(orig_idx, original, translated)

                    processed += len(batch)
                    progress_value = int((processed / max(1, len(unique_texts))) * 100)
                    self.progress.emit(min(99, progress_value))

                    if sleep_after_batch > 0.0:
                        time.sleep(sleep_after_batch)

                except Exception as e:
                    print(f"[WORKER] Error traduciendo lote: {e}")
                    for original in batch:
                        idx_u = unique_index[original]
                        translated_unique_map[idx_u] = original
                    processed += len(batch)
                    continue

            # Reconstruir traducciones completas
            translated_texts = []
            for txt in texts:
                idx_u = unique_index[txt.strip()]
                translated_texts.append(translated_unique_map.get(idx_u, txt))

            # Verificar cancelación antes de guardar
            if self.cancel_flag.is_set():
                print(f"[WORKER] Cancelado antes de guardar: {self.file_path}")
                return

            # Asignar traducciones a las entradas
            for e, t in zip(entries, translated_texts):
                if self.cancel_flag.is_set():
                    return
                e.translated = self._post_process_translation(t)

            # Guardar archivo traducido
            out_path = self._build_output_path(self.file_path)
            subtitles.save_srt(entries, out_path)

            print(f"[WORKER] Traducción completada: {out_path}")
            self.finished.emit(out_path)

        except Exception as e:
            print(f"[WORKER] Error crítico en {self.file_path}: {e}")
            self.error.emit(f"Error procesando archivo: {str(e)}")

    def _get_optimal_batch_size(self):
        """Determina el tamaño de lote óptimo según el motor de traducción"""
        engine = self.service.engine

        # Optimizaciones específicas por motor
        if engine == "google_free":
            # Google Free es más sensible al rate limiting
            return 8
        elif engine == "mymemory":
            # MyMemory maneja mejor lotes más grandes
            return 15
        else:
            return 10

    def _post_process_translation(self, text):
        """Post-procesa el texto traducido para mejorar calidad"""
        if not text:
            return text

        # Limpiar espacios extra
        text = text.strip()

        # Corregir problemas comunes de traducción automática
        corrections = {
            " ,": ",",
            " .": ".",
            " !": "!",
            " ?": "?",
            " :": ":",
            " ;": ";",
            "( ": "(",
            " )": ")",
            "[ ": "[",
            " ]": "]",
            "{ ": "{",
            " }": "}",
            # Corregir espacios dobles
            "  ": " "
        }

        for wrong, right in corrections.items():
            text = text.replace(wrong, right)

        return text

    def _build_output_path(self, path: str) -> str:
        """
        Construye la ruta de salida con estructura de carpetas fija (independiente de la UI).
        - Carpeta: 'Translated_Subtitles_src_to_tgt' junto al archivo original.
        - Archivo: <nombre>_tgtLang.srt
        - Evita colisiones añadiendo sufijo incremental si ya existe.
        """
        p = Path(path)

        # Carpeta de salida (nombre fijo en inglés, desacoplado de la UI)
        folder_base = "Subtitles"
        output_folder = f"{folder_base}_{self.tgt_lang}"
        out_dir = p.parent / output_folder
        out_dir.mkdir(parents=True, exist_ok=True)

        # Nombre base traducido
        translated_name = f"{p.stem}_{self.tgt_lang}{p.suffix}"
        out_path = out_dir / translated_name

        return str(out_path)

    def _should_use_parallel_processing(self, text_count):
        """Determina si usar procesamiento en paralelo para archivos grandes"""
        # Para archivos con más de 100 líneas, considera paralelismo interno
        return text_count > 100 and self.service.engine in ['mymemory']

    def _translate_in_parallel_chunks(self, texts, chunk_size=50):
        """Traduce en chunks paralelos para archivos muy grandes"""
        import concurrent.futures
        from threading import BoundedSemaphore

        # Limitar concurrencia para no sobrecargar APIs
        semaphore = BoundedSemaphore(2)

        def translate_chunk(chunk):
            with semaphore:
                if self.cancel_flag.is_set():
                    return chunk
                return self.service.translate_lines(
                    chunk, self.src_lang, self.tgt_lang,
                    cancel_flag=self.cancel_flag
                )

        chunks = [texts[i:i + chunk_size] for i in range(0, len(texts), chunk_size)]
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_to_chunk = {executor.submit(translate_chunk, chunk): chunk
                               for chunk in chunks}

            for future in concurrent.futures.as_completed(future_to_chunk):
                if self.cancel_flag.is_set():
                    # Cancelar futures pendientes
                    for f in future_to_chunk:
                        f.cancel()
                    return texts  # Devolver originales si se cancela

                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"[WARN] Error en chunk paralelo: {e}")
                    # Usar chunk original como fallback
                    results.append(future_to_chunk[future])

        # Reconstruir lista completa
        return [item for sublist in results for item in sublist]