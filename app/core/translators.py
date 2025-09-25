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

        # deep_translator supports translate_batch; chunk to avoid overlong requests
        CHUNK_SIZE = 50
        chunks = [unique[i:i + CHUNK_SIZE] for i in range(0, len(unique), CHUNK_SIZE)]
        idx = 0
        for chunk in chunks:
            if cancel_flag and cancel_flag.is_set():
                break
            try:
                batch_res = tr.translate_batch(chunk)
            except Exception:
                batch_res = chunk  # fallback
            for j, text in enumerate(chunk):
                res = batch_res[j] if j < len(batch_res) else text
                key = (src, dst, text)
                self._cache[key] = res
                out[idx + j] = res
            idx += len(chunk)

        # Fill any remaining blanks if cancelled mid-way
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

class GoogleV1Translator(ITranslator):
    def __init__(self):
        import requests
        self.session = requests.Session()
        # Persistent headers like SE’s Initialize()
        self.session.headers.update({
            "user-agent": "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36",
            "Content-Type": "application/json; charset=UTF-8",
        })
        self.base = "https://translate.googleapis.com/"

    def _build_url(self, src: str, dst: str, q: str) -> str:
        from urllib.parse import quote_plus
        # Mirror SE: translate_a/single?client=gtx&sl=...&tl=...&dt=t&q=...
        return (
            f"{self.base}translate_a/single?"
            f"client=gtx&sl={src}&tl={dst}&dt=t&q={quote_plus(q)}"
        )

    def _parse_google_v1(self, payload: str) -> list[str]:
        # Lightweight parser that mirrors SE’s ConvertJsonObjectToStringLines
        import json, re
        try:
            data = json.loads(payload)
        except Exception:
            # Some responses are JS-like arrays; try eval-safe fallback
            # As last resort, return raw payload to avoid crashing
            return [payload]

        lines = []
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, list):
                for item in first:
                    if isinstance(item, list) and item:
                        s = item[0] or ""
                        if isinstance(s, str):
                            # Trim escaped CRLF y limpiar secuencias de nueva línea
                            if s.endswith("\\r\\n"):
                                s = s[:-4]
                            try:
                                # Reemplazar secuencias escapadas por saltos de línea reales
                                s = s.replace("\\n", "\n")
                                # Normalizar Unicode para acentos y ñ
                                import unicodedata
                                s = unicodedata.normalize("NFC", s)
                            except Exception:
                                pass
                            lines.append(s)
                        else:
                            lines.append("")
                    else:
                        lines.append("")
        # Limpiar espacios antes de saltos de línea (como hace Subtitle Edit)
        lines = [re.sub(r" +\n", "\n", ln).strip() for ln in lines]

        return lines

    def translate_lines(self, lines: list[str], src="auto", dst="es", cancel_flag=None) -> list[str]:
        # Join batch into one request, one payload
        # Use a delimiter unlikely to occur; choose explicit newline
        batch = [ln.strip() for ln in lines]
        joined = "\n".join(batch)

        if cancel_flag and cancel_flag.is_set():
            return lines

        url = self._build_url(src, dst, joined)
        try:
            r = self.session.get(url, timeout=REQ_TIMEOUT)
            r.raise_for_status()
            parsed = self._parse_google_v1(r.text)
            # Google sometimes returns fewer segments; pad safely
            if len(parsed) < len(batch):
                parsed += [""] * (len(batch) - len(parsed))
            return parsed[:len(batch)]
        except Exception:
            # Safe fallback: return originals to avoid blocking
            return lines
