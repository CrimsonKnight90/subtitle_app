# app/core/translators.py
from abc import ABC, abstractmethod
from time import sleep
from typing import List, Dict
import random

class ITranslator(ABC):
    @abstractmethod
    def translate_lines(self, lines: List[str], src: str, dst: str) -> List[str]:
        ...

def _dedup(lines: List[str]) -> tuple[List[str], Dict[int, int]]:
    uniq = {}
    order = []
    for idx, line in enumerate(lines):
        key = line.strip()
        if key not in uniq:
            uniq[key] = len(order)
            order.append(key)
    index_map = {}
    for idx, line in enumerate(lines):
        index_map[idx] = uniq[line.strip()]
    return order, index_map

def _recompose(unique_in: List[str], unique_out: List[str], index_map: Dict[int, int]) -> List[str]:
    return [unique_out[index_map[i]] if unique_in[index_map[i]].strip() else "" for i in range(len(index_map))]

class GoogleFreeTranslator(ITranslator):
    def __init__(self):
        from deep_translator import GoogleTranslator
        self.GoogleTranslator = GoogleTranslator

    def translate_lines(self, lines, src="auto", dst="es"):
        # 1 traductor por lote, dedup y backoff suave
        tr = self.GoogleTranslator(source=src, target=dst)
        unique, index_map = _dedup(lines)
        out = [""] * len(unique)
        for i, text in enumerate(unique):
            if not text:
                out[i] = ""
                continue
            for attempt in range(4):
                try:
                    out[i] = tr.translate(text)
                    break
                except Exception:
                    sleep(0.25 * (2 ** attempt) + random.random() * 0.1)
            else:
                out[i] = text  # fallback
            sleep(0.02)  # micro pausa
        return _recompose(unique, out, index_map)

class MyMemoryTranslator(ITranslator):
    def __init__(self):
        import requests
        self.session = requests.Session()

    def translate_lines(self, lines, src="auto", dst="es"):
        # MyMemory no acepta 'auto': que alguien arriba fije 'src'
        unique, index_map = _dedup(lines)
        out = [""] * len(unique)
        for i, text in enumerate(unique):
            if not text:
                out[i] = ""
                continue
            for attempt in range(4):
                try:
                    r = self.session.get(
                        "https://api.mymemory.translated.net/get",
                        params={"q": text, "langpair": f"{src}|{dst}"},
                        timeout=10,
                    )
                    r.raise_for_status()
                    data = r.json()
                    out[i] = data.get("responseData", {}).get("translatedText", text)
                    break
                except Exception:
                    sleep(0.25 * (2 ** attempt) + random.random() * 0.1)
            else:
                out[i] = text
            sleep(0.03)
        return _recompose(unique, out, index_map)
