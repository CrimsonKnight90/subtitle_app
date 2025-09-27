# app\core\translators.py
from abc import ABC, abstractmethod
from time import sleep
from typing import List, Dict
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import requests
import json
import unicodedata
from urllib.parse import quote_plus

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
        self.session = requests.Session()
        self.session.headers.update({
            "user-agent": "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36",
            "Content-Type": "application/json; charset=UTF-8",
        })
        self.base = "https://translate.googleapis.com/"

    def _build_url(self, src: str, dst: str, q: str) -> str:
        return (
            f"{self.base}translate_a/single?"
            f"client=gtx&sl={src}&tl={dst}&dt=t&q={quote_plus(q)}"
        )

    def _parse_google_v1(self, payload: str) -> list[str]:
        """Parsea la respuesta de Google Translate"""
        try:
            data = json.loads(payload)
        except Exception as e:
            print(f"Error parseando JSON: {e}")
            return []

        lines = []
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, list):
                for item in first:
                    if isinstance(item, list) and item:
                        s = item[0] or ""
                        if isinstance(s, str):
                            s = s.replace("\\n", "\n")
                            s = re.sub(r'\n{2,}', '\n', s)
                            s = unicodedata.normalize("NFC", s)
                            lines.append(s.strip())
                        else:
                            lines.append("")
                    else:
                        lines.append("")
        return lines

    def _post_process_translation(self, original: str, translated: str) -> str:
        """Post-procesamiento inteligente para mantener estructura"""
        if not translated or translated.isspace():
            return original

        # Preservar números al inicio
        original_match = re.match(r'^(\d+)\s*$', original.strip())
        if original_match:
            prefix = original_match.group(1)
            if not translated.startswith(prefix):
                return f"{prefix}\n{translated}"

        # Controlar saltos de línea excesivos
        original_line_count = original.count('\n') + 1
        translated_line_count = translated.count('\n') + 1

        if translated_line_count > original_line_count + 2:
            lines = translated.split('\n')
            if len(lines) > original_line_count + 1:
                merged_lines = []
                current_line = ""

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    if not current_line:
                        current_line = line
                    elif len(current_line) < 40 or len(line) < 25:
                        current_line += " " + line
                    else:
                        merged_lines.append(current_line)
                        current_line = line

                if current_line:
                    merged_lines.append(current_line)

                if 1 <= len(merged_lines) <= original_line_count + 2:
                    translated = '\n'.join(merged_lines)

        # Limpiar espacios extra
        translated = re.sub(r' +', ' ', translated)
        translated = re.sub(r'\n +', '\n', translated)

        return translated.strip()

    def translate_lines(self, lines: list[str], src="auto", dst="es", cancel_flag=None) -> list[str]:
        """Versión optimizada con procesamiento por lotes"""
        if not lines:
            return lines

        # Separar líneas a traducir de las que no se deben traducir
        to_translate = []
        translate_indices = []
        original_lines = lines.copy()

        for i, line in enumerate(lines):
            # No traducir: líneas vacías, números, formatos de tiempo
            if (not line.strip() or
                    line.strip().isdigit() or
                    re.search(r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', line)):
                continue

            to_translate.append(line)
            translate_indices.append(i)

        # Si no hay nada que traducir, retornar original
        if not to_translate:
            return lines

        # Procesar en lotes para mayor velocidad
        batch_size = 20  # Ajusta según necesidad
        results = []

        for batch_start in range(0, len(to_translate), batch_size):
            if cancel_flag and cancel_flag.is_set():
                return lines

            batch_end = min(batch_start + batch_size, len(to_translate))
            batch = to_translate[batch_start:batch_end]

            print(f"Traduciendo lote {batch_start // batch_size + 1}: {len(batch)} líneas")

            try:
                # Unir el lote con un delimitador especial
                delimiter = " ||| "
                batch_text = delimiter.join(batch)

                url = self._build_url(src, dst, batch_text)
                r = self.session.get(url, timeout=REQ_TIMEOUT)
                r.raise_for_status()

                # Parsear respuesta
                parsed = self._parse_google_v1(r.text)
                if parsed:
                    full_text = " ".join(parsed)
                    # Dividir usando el delimitador
                    translated_batch = full_text.split(delimiter)

                    # Ajustar longitud si es necesario
                    if len(translated_batch) < len(batch):
                        translated_batch += [""] * (len(batch) - len(translated_batch))
                    elif len(translated_batch) > len(batch):
                        translated_batch = translated_batch[:len(batch)]
                else:
                    translated_batch = batch  # Fallback

                results.extend(translated_batch)

            except Exception as e:
                print(f"Error en lote {batch_start // batch_size + 1}: {e}")
                results.extend(batch)  # Usar original en caso de error

        # Reconstruir las líneas finales con post-procesamiento
        final_lines = original_lines.copy()

        for i, translated_line in zip(translate_indices, results):
            if i < len(final_lines):
                final_lines[i] = self._post_process_translation(
                    original_lines[i],
                    translated_line
                )

        return final_lines