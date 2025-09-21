# app/gui/translate/translation_service.py
from app.core.translators import GoogleFreeTranslator, MyMemoryTranslator

class TranslationService:
    def __init__(self, engine="google_free"):
        self.engine = engine
        self.translators = {
            "google_free": GoogleFreeTranslator(),
            "mymemory": MyMemoryTranslator(),
        }

    def _resolve_src(self, lines, src_lang, tgt_lang):
        if self.engine == "mymemory" and (src_lang == "auto" or not src_lang):
            # detectar fuente a partir de muestra (rápido y suficiente)
            try:
                from deep_translator import GoogleTranslator
                sample = next((l for l in lines if l.strip()), "")[:200]
                if sample:
                    det = GoogleTranslator(source="auto", target=tgt_lang)
                    # deep_translator no expone 'detected language' estándar; aproximamos
                    # estrategia: traducir una muestra al mismo idioma destino y confiar en 'auto'
                    # si falla, forzamos 'en' como último recurso
                    # Si dispones de otro detector (langid), cámbialo aquí.
                    # En práctica, MyMemory funciona bien si no le pasamos 'auto'.
                    return "en"  # reemplaza por tu detector preferido si lo tienes disponible
            except Exception:
                pass
            return "en"
        return src_lang or "auto"

    def translate_lines(self, lines, src_lang, tgt_lang):
        src = self._resolve_src(lines, src_lang, tgt_lang)
        try:
            return self.translators[self.engine].translate_lines(lines, src, tgt_lang)
        except Exception as e:
            print(f"[WARN] {self.engine} falló: {e}")
            return lines

    def translate_text(self, text, src_lang, tgt_lang):
        return self.translate_lines([text], src_lang, tgt_lang)[0]
