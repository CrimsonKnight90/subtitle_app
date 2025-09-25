# app\core\translators.py
# app/core/translators.py
from abc import ABC, abstractmethod
from time import sleep
from typing import List, Dict
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

# Concurrencia interna por lote (ajusta según servicio)
MAX_PARALLEL = 6
# Timeouts razonables por request
REQ_TIMEOUT = 6

class ITranslator(ABC):
    @abstractmethod
    def translate_lines(self, lines: List[str], src: str, dst: str, cancel_flag=None) -> List[str]:
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
        self._cache: Dict[tuple, str] = {}  # (src, dst, text) -> translation

    def _translate_one(self, tr, text: str, src: str, dst: str) -> str:
        # reintentos con jitter
        for attempt in range(3):
            try:
                return tr.translate(text)
            except Exception:
                sleep(0.12 * (2 ** attempt) + random.random() * 0.08)
        return text  # fallback seguro

    def translate_lines(self, lines, src="auto", dst="es", cancel_flag=None):
        tr = self.GoogleTranslator(source=src, target=dst)
        unique, index_map = _dedup(lines)
        out = [""] * len(unique)

        # pre-llenar cache y tareas
        tasks = {}
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
            for i, text in enumerate(unique):
                if cancel_flag and cancel_flag.is_set():
                    break
                if not text:
                    out[i] = ""
                    continue
                key = (src, dst, text)
                if key in self._cache:
                    out[i] = self._cache[key]
                    continue
                # schedule
                tasks[pool.submit(self._translate_one, tr, text, src, dst)] = (i, key)

            for future in as_completed(tasks):
                if cancel_flag and cancel_flag.is_set():
                    break
                i, key = tasks[future]
                try:
                    res = future.result()
                    out[i] = res
                    self._cache[key] = res
                except Exception:
                    out[i] = key[2]  # fallback al original

        # rellena los que queden vacíos si se canceló a mitad
        for i, text in enumerate(unique):
            if out[i] == "":
                out[i] = text if text else ""

        return _recompose(unique, out, index_map)

class MyMemoryTranslator(ITranslator):
    def __init__(self):
        import requests
        self.session = requests.Session()
        self._cache: Dict[tuple, str] = {}  # (src, dst, text) -> translation

    def _translate_one(self, text: str, src: str, dst: str) -> str:
        import requests
        for attempt in range(3):
            try:
                r = self.session.get(
                    "https://api.mymemory.translated.net/get",
                    params={"q": text, "langpair": f"{src}|{dst}"},
                    timeout=REQ_TIMEOUT,
                )
                r.raise_for_status()
                data = r.json()
                return data.get("responseData", {}).get("translatedText", text)
            except requests.RequestException:
                sleep(0.12 * (2 ** attempt) + random.random() * 0.08)
        return text

    def translate_lines(self, lines, src="auto", dst="es", cancel_flag=None):
        unique, index_map = _dedup(lines)
        out = [""] * len(unique)

        tasks = {}
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
            for i, text in enumerate(unique):
                if cancel_flag and cancel_flag.is_set():
                    break
                if not text:
                    out[i] = ""
                    continue
                key = (src, dst, text)
                if key in self._cache:
                    out[i] = self._cache[key]
                    continue
                tasks[pool.submit(self._translate_one, text, src, dst)] = (i, key)

            for future in as_completed(tasks):
                if cancel_flag and cancel_flag.is_set():
                    break
                i, key = tasks[future]
                try:
                    res = future.result()
                    out[i] = res
                    self._cache[key] = res
                except Exception:
                    out[i] = key[2]

        for i, text in enumerate(unique):
            if out[i] == "":
                out[i] = text if text else ""

        return _recompose(unique, out, index_map)
