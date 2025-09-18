from deep_translator import GoogleTranslator as GoogleFreeTranslator
from deep_translator import MyMemoryTranslator

class TranslationService:
    def __init__(self):
        pass

    def translate_text(self, text, src_lang, tgt_lang):
        """
        Traduce texto usando GoogleFreeTranslator y MyMemory como fallback.
        """
        # 1️⃣ GoogleFreeTranslator
        try:
            return GoogleFreeTranslator(source=src_lang, target=tgt_lang).translate(text)
        except Exception as e:
            print(f"[WARN] GoogleFreeTranslator falló: {e}")

        # 2️⃣ MyMemoryTranslator
        try:
            return MyMemoryTranslator(source=src_lang, target=tgt_lang).translate(text)
        except Exception as e:
            print(f"[WARN] MyMemoryTranslator falló: {e}")

        # 3️⃣ Fallback final: devolver texto original
        return text
