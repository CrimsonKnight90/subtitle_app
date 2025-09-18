from app.services.settings import get_settings
from app.services.translations import TRANSLATIONS

def get_translator():
    S = get_settings()
    lang = S.config.get("ui_language", "es")
    return lambda key: TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)
