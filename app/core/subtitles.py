# app\core\subtitles.py
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SubtitleEntry:
    id: int
    start: float
    end: float
    original: str
    translated: str = ""


def _parse_time(time_str: str) -> float:
    """Convierte formato SRT time a segundos (ej: 00:00:03,430 -> 3.43)"""
    try:
        # Formato: HH:MM:SS,mmm
        time_str = time_str.strip()
        if ',' in time_str:
            main_part, ms_part = time_str.split(',')
        elif '.' in time_str:
            main_part, ms_part = time_str.split('.')
        else:
            main_part, ms_part = time_str, '000'

        h, m, s = map(int, main_part.split(':'))
        ms = int(ms_part.ljust(3, '0')[:3])  # Asegurar 3 dígitos

        total_seconds = h * 3600 + m * 60 + s + ms / 1000.0
        return total_seconds
    except Exception as e:
        print(f"[ERROR] Error parsing time '{time_str}': {e}")
        return 0.0


def _format_time(seconds: float) -> str:
    """Convierte segundos a formato SRT time"""
    try:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
    except Exception:
        return "00:00:00,000"


def load_srt(path: str) -> list[SubtitleEntry]:
    """
    Carga un archivo SRT con parser manual robusto.
    Maneja archivos complejos con etiquetas HTML y múltiples líneas.
    """
    try:
        path_obj = Path(path)
        if not path_obj.exists():
            print(f"[ERROR] Archivo no encontrado: {path}")
            return []

        # Leer archivo con múltiples encodings como fallback
        content = None
        for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
            try:
                with open(path, 'r', encoding=encoding) as f:
                    content = f.read()
                print(f"[SUBTITLES] Archivo leído con encoding: {encoding}")
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            print(f"[ERROR] No se pudo leer el archivo con ningún encoding")
            return []

        # Normalizar saltos de línea
        content = content.replace('\r\n', '\n').replace('\r', '\n')

        # Patrón regex para capturar entradas SRT completas
        # Captura: número, timestamp, y todo el texto hasta el próximo número o final
        pattern = r'(\d+)\s*\n(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*\n(.*?)(?=\n\d+\s*\n\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}|\n*$)'

        entries = []
        matches = re.findall(pattern, content, re.DOTALL)

        print(f"[SUBTITLES] Parser regex encontró {len(matches)} entradas")

        for match in matches:
            try:
                index = int(match[0])
                start_time = _parse_time(match[1].replace(',', '.'))
                end_time = _parse_time(match[2].replace(',', '.'))
                text = match[3]

                # ✅ Normalizar multilíneas sin colapsarlas
                # - strip solo al inicio y final del bloque
                # - preservar saltos internos
                text = text.replace("\r\n", "\n").replace("\r", "\n")
                text_lines = [line.rstrip() for line in text.split("\n")]
                clean_text = "\n".join(text_lines).strip()

                if clean_text:  # Solo agregar si hay contenido
                    entry = SubtitleEntry(
                        id=index,
                        start=start_time,
                        end=end_time,
                        original=clean_text
                    )
                    entries.append(entry)

                    # Debug para primeras 3 entradas
                    if len(entries) <= 3:
                        print(f"[SUBTITLES] Entrada {index}: {start_time:.3f}-{end_time:.3f} -> '{clean_text[:50]}...'")


            except Exception as e:
                print(f"[ERROR] Error procesando entrada SRT: {e}")
                continue

        print(f"[SUBTITLES] Cargadas {len(entries)} entradas exitosamente")
        return entries

    except Exception as e:
        print(f"[ERROR] Error crítico cargando SRT: {e}")
        return []


def save_srt(entries: list[SubtitleEntry], path: str):
    """
    Guarda entradas como archivo SRT con formato correcto.
    Maneja etiquetas HTML y múltiples líneas correctamente.
    """
    try:
        if not entries:
            print("[ERROR] No hay entradas para guardar")
            return

        # Crear directorio si no existe
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        lines = []

        for i, entry in enumerate(entries, 1):
            # Usar texto traducido si existe, sino usar original
            text_to_save = entry.translated if entry.translated.strip() else entry.original

            # Formatear entrada SRT
            start_time = _format_time(entry.start)
            end_time = _format_time(entry.end)

            # Estructura estándar SRT
            lines.append(str(i))
            lines.append(f"{start_time} --> {end_time}")

            # ✅ CORRECCIÓN: dividir multilíneas y guardarlas una por una
            for line in text_to_save.splitlines():
                lines.append(line)

            lines.append("")  # Línea vacía entre entradas

            # Debug para primeras 3 entradas
            if i <= 3:
                print(f"[SUBTITLES] Guardando {i}: {start_time}-{end_time} -> '{text_to_save[:50]}...'")

        # Escribir archivo
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"[SUBTITLES] Guardado exitoso: {path} ({len(entries)} entradas)")

    except Exception as e:
        print(f"[ERROR] Error guardando SRT: {e}")
        raise


def load_srt_fallback(path: str) -> list[SubtitleEntry]:
    """
    Fallback usando pysrt para compatibilidad con archivos simples.
    """
    try:
        import pysrt
        subs = pysrt.open(path, encoding="utf-8")
        entries = []

        for s in subs:
            start = s.start.ordinal / 1000.0
            end = s.end.ordinal / 1000.0
            entry = SubtitleEntry(
                id=s.index,
                start=start,
                end=end,
                original=s.text
            )
            entries.append(entry)

        print(f"[SUBTITLES] Fallback pysrt cargó {len(entries)} entradas")
        return entries

    except Exception as e:
        print(f"[ERROR] Fallback pysrt también falló: {e}")
        return []