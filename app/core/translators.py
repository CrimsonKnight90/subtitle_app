# app/core/translate.py
from abc import ABC, abstractmethod
from time import sleep
from typing import Iterable
import time
from deep_translator import GoogleTranslator


class ITranslator(ABC):
    @abstractmethod
    def translate_lines(self, lines: list[str], src: str, dst: str) -> list[str]:
        ...

class GoogleFreeTranslator(ITranslator):
    def __init__(self):
        from deep_translator import GoogleTranslator
        self._ctor = GoogleTranslator
    def translate_lines(self, lines, src="auto", dst="es"):
        tr = self._ctor(source=src, target=dst)
        result = []
        for line in lines:
            result.append(tr.translate(line) if line.strip() else line)
            sleep(0.05)  # micro-pausing para evitar rate-limit
        return result

class LibreTranslateTranslator(ITranslator):
    def __init__(self, base_url="https://libretranslate.com"):
        import requests
        self.base_url = base_url
        self.requests = requests
    def translate_lines(self, lines, src="auto", dst="es"):
        # Traducción línea a línea para ser amable con el servidor
        out = []
        for line in lines:
            if not line.strip():
                out.append(line); continue
            r = self.requests.post(f"{self.base_url}/translate",
                                   json={"q": line, "source": src, "target": dst, "format": "text"},
                                   timeout=15)
            r.raise_for_status()
            out.append(r.json().get("translatedText", line))
            sleep(0.1)
        return out

class MyMemoryTranslator(ITranslator):
    def __init__(self):
        import requests
        self.requests = requests
    def translate_lines(self, lines, src="auto", dst="es"):
        out=[]
        for line in lines:
            if not line.strip():
                out.append(line); continue
            r = self.requests.get("https://api.mymemory.translated.net/get",
                                  params={"q": line, "langpair": f"{src}|{dst}"}, timeout=15)
            r.raise_for_status()
            data = r.json()
            out.append(data.get("responseData", {}).get("translatedText", line))
            sleep(0.1)
        return out

class RouterTranslator(ITranslator):
    """
    Orquesta varios traductores con fallback.
    Incluye translate_lines_with_provider para devolver también el proveedor usado.
    """

    def __init__(self, providers):
        self.providers = providers

    def translate(self, text, src, dst):
        for provider in self.providers:
            try:
                result = provider.translate(text, src, dst)
                if result:
                    return result
            except Exception:
                continue
        return None

    def translate_lines(self, lines, src, dst):
        for provider in self.providers:
            try:
                result = provider.translate_lines(lines, src, dst)
                if result:
                    return result
            except Exception:
                continue
        return [None] * len(lines)

    def translate_lines_with_provider(self, lines, src, dst):
        """
        Traduce con fallback y devuelve (lista_traducida, nombre_proveedor).
        """
        for provider in self.providers:
            provider_name = provider.__class__.__name__
            try:
                result = provider.translate_lines(lines, src, dst)
                if result:
                    return result, provider_name
            except Exception:
                continue
        return [f"[ERROR] {line}" for line in lines], "None"



