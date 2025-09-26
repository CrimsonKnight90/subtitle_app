# app\gui\translate\translation_service.py
from app.core.translators import GoogleFreeTranslator, MyMemoryTranslator, GoogleV1Translator
import time
import threading


class TranslationService:
    def __init__(self, engine="google_free"):
        self.engine = engine
        self.translators = {
            "google_free": GoogleFreeTranslator(),
            "google_v1": GoogleV1Translator(),
            "mymemory": MyMemoryTranslator(),
        }

        # Cache simple para evitar re-traducir textos idénticos
        self._translation_cache = {}
        self._cache_lock = threading.RLock()

        # Rate limiting mejorado
        self._last_request_time = 0
        self._request_lock = threading.RLock()

    def _resolve_src(self, lines, src_lang, tgt_lang):
        """Resuelve el idioma fuente con detección mejorada"""
        if self.engine == "mymemory" and (src_lang == "auto" or not src_lang):
            try:
                # Usar langdetect para detección más precisa
                from langdetect import detect, LangDetectException

                sample_lines = [l for l in lines[:5] if l.strip()]
                if sample_lines:
                    sample = " ".join(sample_lines)[:200]
                    detected = detect(sample)

                    # Mapear códigos de langdetect a códigos de traducción
                    lang_mapping = {
                        'ca': 'ca', 'zh-cn': 'zh', 'zh-tw': 'zh',
                        'cs': 'cs', 'da': 'da', 'nl': 'nl',
                        'en': 'en', 'et': 'et', 'fi': 'fi',
                        'fr': 'fr', 'de': 'de', 'el': 'el',
                        'hu': 'hu', 'it': 'it', 'ja': 'ja',
                        'ko': 'ko', 'lv': 'lv', 'lt': 'lt',
                        'pl': 'pl', 'pt': 'pt', 'ro': 'ro',
                        'ru': 'ru', 'sk': 'sk', 'sl': 'sl',
                        'es': 'es', 'sv': 'sv'
                    }

                    return lang_mapping.get(detected, 'en')

            except (ImportError, LangDetectException, Exception) as e:
                print(f"[WARN] Error en detección con langdetect: {e}")
                # Fallback al método anterior...

        return src_lang or "auto"

    def _get_cache_key(self, text, src_lang, tgt_lang):
        """Genera clave de cache para el texto"""
        return f"{src_lang}_{tgt_lang}_{hash(text.strip().lower())}"

    def _clean_html_tags(self, text):
        """Elimina etiquetas HTML del texto antes de traducir"""
        import re
        if not text:
            return text

        # Patrón para etiquetas HTML comunes en subtítulos
        html_pattern = r'</?(?:font|b|i|u|strong|em)\s*[^>]*>'

        # Remover etiquetas HTML
        cleaned = re.sub(html_pattern, '', text, flags=re.IGNORECASE)

        # Limpiar espacios extra que quedan tras remover etiquetas
        # Colapsar solo espacios y tabs, pero preservar saltos de línea
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        # Normalizar espacios alrededor de saltos de línea
        cleaned = re.sub(r' *\n *', '\n', cleaned).strip()

        return cleaned

    def _restore_html_structure(self, original, translated):
        """Restaura la estructura HTML del texto original en el traducido"""
        import re

        if not original or not translated:
            return translated

        # Si el original no tiene etiquetas HTML, devolver traducción tal como está
        if '<' not in original:
            return translated

        # Extraer etiquetas de apertura del original
        opening_tags = re.findall(r'<(?:font|b|i|u|strong|em)\s*[^>]*>', original, re.IGNORECASE)

        # Extraer etiquetas de cierre del original
        closing_tags = re.findall(r'</(?:font|b|i|u|strong|em)>', original, re.IGNORECASE)

        # Aplicar etiquetas al texto traducido
        result = translated

        # Agregar etiquetas de apertura al inicio
        for tag in opening_tags:
            result = tag + ' ' + result

        # Agregar etiquetas de cierre al final
        for tag in reversed(closing_tags):
            result = result + ' ' + tag

        return result.strip()

    def _apply_rate_limiting(self):
        """Aplica rate limiting inteligente según el motor"""
        with self._request_lock:
            current_time = time.time()

            if self.engine == "google_free":
                # Google Free es más restrictivo
                min_interval = 0.5  # 500ms entre requests
            elif self.engine == "mymemory":
                # MyMemory es más permisivo
                min_interval = 0.1  # 100ms entre requests
            else:
                min_interval = 0.3

            elapsed = current_time - self._last_request_time
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                time.sleep(sleep_time)

            self._last_request_time = time.time()

    def translate_lines(self, lines, src_lang, tgt_lang, cancel_flag=None):
        """Traduce múltiples líneas con optimizaciones de velocidad"""
        if not lines:
            return []

        src = self._resolve_src(lines, src_lang, tgt_lang)

        # Filtrar líneas vacías y crear mapeo
        non_empty_lines = []
        line_mapping = {}  # índice original -> índice en non_empty_lines

        # Almacenar textos originales para restaurar estructura HTML
        original_lines_with_html = []
        cleaned_lines = []

        for i, line in enumerate(lines):
            if line.strip():
                line_mapping[i] = len(non_empty_lines)
                original_lines_with_html.append(line.strip())  # Guardar con HTML
                cleaned_line = self._clean_html_tags(line.strip())  # Limpiar para traducir
                non_empty_lines.append(cleaned_line)
                cleaned_lines.append(cleaned_line)

        if not non_empty_lines:
            return lines  # Solo líneas vacías

        # Verificar cancelación
        if cancel_flag and cancel_flag.is_set():
            return lines

        # Buscar en cache y preparar líneas para traducir
        cached_results = {}
        lines_to_translate = []
        translate_indices = []

        with self._cache_lock:
            for i, line in enumerate(non_empty_lines):
                if cancel_flag and cancel_flag.is_set():
                    return lines

                cache_key = self._get_cache_key(line, src, tgt_lang)
                if cache_key in self._translation_cache:
                    cached_results[i] = self._translation_cache[cache_key]
                else:
                    lines_to_translate.append(line)
                    translate_indices.append(i)

        print(f"[SERVICE] Cache hits: {len(cached_results)}, Nuevas traducciones: {len(lines_to_translate)}")

        # Traducir líneas no cacheadas
        translated_new = []
        if lines_to_translate:
            try:
                # Aplicar rate limiting antes de traducir
                self._apply_rate_limiting()

                # Verificar cancelación antes de API call
                if cancel_flag and cancel_flag.is_set():
                    return lines

                # Llamar al traductor
                translated_new = self.translators[self.engine].translate_lines(
                    lines_to_translate, src, tgt_lang, cancel_flag=cancel_flag
                )

                # Guardar en cache
                with self._cache_lock:
                    for original, translated in zip(lines_to_translate, translated_new):
                        cache_key = self._get_cache_key(original, src, tgt_lang)
                        self._translation_cache[cache_key] = translated

                        # Limitar tamaño de cache (mantener últimas 1000 traducciones)
                        if len(self._translation_cache) > 1000:
                            # Eliminar 20% más antiguas (aproximación simple)
                            keys_to_remove = list(self._translation_cache.keys())[:200]
                            for key in keys_to_remove:
                                del self._translation_cache[key]

            except Exception as e:
                print(f"[ERROR] {self.engine} falló: {e}")
                # En caso de error, devolver textos originales
                translated_new = lines_to_translate

        # Combinar resultados cacheados y nuevos
        final_translations = [''] * len(non_empty_lines)

        # Asignar resultados cacheados
        for i, translation in cached_results.items():
            final_translations[i] = translation

        # Asignar nuevas traducciones
        for translate_idx, translation in zip(translate_indices, translated_new):
            final_translations[translate_idx] = translation

        # Reconstruir resultado final manteniendo líneas vacías y restaurando HTML
        result = []
        translation_idx_counter = 0

        for i, original_line in enumerate(lines):
            if i in line_mapping:
                # Línea no vacía, usar traducción y restaurar HTML
                translation_idx = line_mapping[i]
                translated_text = final_translations[translation_idx]

                # Restaurar estructura HTML del original
                if translation_idx_counter < len(original_lines_with_html):
                    original_with_html = original_lines_with_html[translation_idx_counter]
                    restored_translation = self._restore_html_structure(original_with_html, translated_text)
                    result.append(restored_translation)
                    translation_idx_counter += 1
                else:
                    result.append(translated_text)
            else:
                # Línea vacía, mantener como está
                result.append(original_line)

        return result

    def translate_text(self, text, src_lang, tgt_lang, cancel_flag=None):
        """Traduce un texto individual"""
        return self.translate_lines([text], src_lang, tgt_lang, cancel_flag=cancel_flag)[0]

    def clear_cache(self):
        """Limpia el cache de traducciones"""
        with self._cache_lock:
            self._translation_cache.clear()
            print("[SERVICE] Cache de traducciones limpiado")

    def get_cache_stats(self):
        """Obtiene estadísticas del cache"""
        with self._cache_lock:
            return {
                'size': len(self._translation_cache),
                'engine': self.engine
            }