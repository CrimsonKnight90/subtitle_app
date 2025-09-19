from deep_translator import GoogleTranslator as GoogleFreeTranslator
from deep_translator import MyMemoryTranslator
from app.core.translators import GoogleFreeTranslator, MyMemoryTranslator, LibreTranslateTranslator

class TranslationService:
    def __init__(self, engine="google_free"):
        self.engine = engine
        self.translators = {
            "google_free": GoogleFreeTranslator(),
            "mymemory": MyMemoryTranslator(),
            "libre_online": LibreTranslateTranslator("https://libretranslate.com"),
            "libre_offline": LibreTranslateTranslator("http://localhost:5000")
        }

    def translate_lines(self, lines, src_lang, tgt_lang):
        try:
            return self.translators[self.engine].translate_lines(lines, src_lang, tgt_lang)
        except Exception as e:
            print(f"[WARN] {self.engine} falló: {e}")
            return lines


    def translate_text(self, text, src_lang, tgt_lang):
        try:
            return self.translators[self.engine].translate_lines([text], src_lang, tgt_lang)[0]
        except Exception as e:
            print(f"[WARN] {self.engine} falló: {e}")
            return text

