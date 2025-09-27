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
        time_str = time_str.strip().replace(',', '.')
        h, m, s = time_str.split(':')
        return int(h) * 3600 + int(m) * 60 + float(s)
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
    Parser robusto que maneja CUALQUIER formato SRT correctamente.
    Especialmente diseñado para manejar entradas multi-línea.
    """
    entries = []
    try:
        path_obj = Path(path)
        if not path_obj.exists():
            print(f"[ERROR] Archivo no encontrado: {path}")
            return []

        # Leer archivo con múltiples encodings
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

        # Normalizar contenido
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        content = re.sub(r'\n{3,}', '\n\n', content)  # Normalizar separadores múltiples

        # MÉTODO 1: Parser por bloques (más robusto)
        entries = _parse_by_blocks(content)

        if not entries:
            # MÉTODO 2: Parser por regex como fallback
            print("[SUBTITLES] Intentando parser alternativo...")
            entries = _parse_by_regex(content)

        print(f"[SUBTITLES] Cargadas {len(entries)} entradas exitosamente")
        return entries

    except Exception as e:
        print(f"[ERROR] Error crítico cargando SRT: {e}")
        return []


def _parse_by_blocks(content: str) -> list[SubtitleEntry]:
    """Parser principal por bloques de texto"""
    entries = []

    # Dividir por bloques separados por líneas vacías
    blocks = [block.strip() for block in content.split('\n\n') if block.strip()]

    for block in blocks:
        lines = [line.strip() for line in block.split('\n') if line.strip()]

        if len(lines) < 3:  # Necesitamos al menos: número, tiempo, texto
            continue

        try:
            # Línea 1: Número
            index = int(lines[0])

            # Línea 2: Timestamps
            timestamp_line = lines[1]
            if '-->' not in timestamp_line:
                continue

            start_str, end_str = timestamp_line.split('-->')
            start_time = _parse_time(start_str.strip())
            end_time = _parse_time(end_str.strip())

            # Línea 3+: Todo el texto (preservando líneas múltiples)
            text_lines = lines[2:]

            # CRÍTICO: Preservar saltos de línea originales
            text = '\n'.join(text_lines)

            if text:
                entry = SubtitleEntry(
                    id=index,
                    start=start_time,
                    end=end_time,
                    original=text
                )
                entries.append(entry)

                # Debug para primeras 3 entradas
                if len(entries) <= 3:
                    print(f"[SUBTITLES] Bloque {index}: {start_time:.3f}-{end_time:.3f}")
                    print(f"[SUBTITLES] Líneas de texto: {len(text_lines)}")
                    print(f"[SUBTITLES] Contenido: '{text[:80]}...'")

        except Exception as e:
            print(f"[ERROR] Error procesando bloque: {e}")
            continue

    return entries


def _parse_by_regex(content: str) -> list[SubtitleEntry]:
    """Parser alternativo usando regex para casos complejos"""
    entries = []

    # Regex más permisivo que captura bloques completos
    pattern = r'(\d+)\s*\n(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*\n((?:.*\n?)*?)(?=\n\d+\s*\n\d{2}:\d{2}:\d{2}|\Z)'

    matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)

    for match in matches:
        try:
            index = int(match[0])
            start_time = _parse_time(match[1])
            end_time = _parse_time(match[2])
            text = match[3].strip()

            if text:
                entry = SubtitleEntry(
                    id=index,
                    start=start_time,
                    end=end_time,
                    original=text
                )
                entries.append(entry)

        except Exception as e:
            print(f"[ERROR] Error en regex match: {e}")
            continue

    return entries


def save_srt(entries: list[SubtitleEntry], path: str):
    """
    Guarda entradas SRT preservando exactamente la estructura original.
    """
    try:
        if not entries:
            print("[ERROR] No hay entradas para guardar")
            return

        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            for i, entry in enumerate(entries, 1):
                # Usar traducción si existe, sino original
                text_to_save = entry.translated if entry.translated.strip() else entry.original

                # CRÍTICO: No alterar la estructura de líneas del texto
                # Solo limpiar espacios extremos, pero preservar saltos de línea internos
                text_to_save = text_to_save.strip()

                # Formatear tiempos
                start_time = _format_time(entry.start)
                end_time = _format_time(entry.end)

                # Escribir entrada completa
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text_to_save}\n\n")

                # Debug para primeras 3 entradas
                if i <= 3:
                    num_lines = text_to_save.count('\n') + 1
                    print(f"[SUBTITLES] Guardando {i}: {start_time}-{end_time}")
                    print(f"[SUBTITLES] Líneas de texto: {num_lines}")
                    print(f"[SUBTITLES] Preview: '{text_to_save[:60]}...'")

        print(f"[SUBTITLES] Guardado exitoso: {path} ({len(entries)} entradas)")

    except Exception as e:
        print(f"[ERROR] Error guardando SRT: {e}")
        raise


def load_srt_fallback(path: str) -> list[SubtitleEntry]:
    """
    Fallback usando pysrt para casos donde el parser manual falla.
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


def sync_entries_from_original(original_path: str, translated_entries: list[SubtitleEntry]) -> list[SubtitleEntry]:
    """
    Sincroniza las entradas traducidas con la estructura del archivo original.
    """
    try:
        original_entries = load_srt(original_path)

        if len(original_entries) != len(translated_entries):
            print(f"[SYNC] Discrepancia: original={len(original_entries)}, traducido={len(translated_entries)}")

            # Si el traducido tiene más entradas, intentar reagrupar
            if len(translated_entries) > len(original_entries):
                return _regroup_translated_entries(original_entries, translated_entries)

        # Aplicar timestamps del original al traducido
        synchronized = []
        for i, (orig, trans) in enumerate(zip(original_entries, translated_entries)):
            synced_entry = SubtitleEntry(
                id=orig.id,
                start=orig.start,  # USAR TIEMPOS DEL ORIGINAL
                end=orig.end,  # USAR TIEMPOS DEL ORIGINAL
                original=orig.original,
                translated=trans.translated or trans.original
            )
            synchronized.append(synced_entry)

        print(f"[SYNC] Sincronizadas {len(synchronized)} entradas")
        return synchronized

    except Exception as e:
        print(f"[ERROR] Error sincronizando: {e}")
        return translated_entries


def _regroup_translated_entries(original_entries: list[SubtitleEntry], translated_entries: list[SubtitleEntry]) -> list[
    SubtitleEntry]:
    """
    Reagrupa entradas traducidas que se dividieron incorrectamente.
    """
    regrouped = []
    trans_idx = 0

    for orig in original_entries:
        # Calcular cuántas líneas tiene el original
        orig_lines = orig.original.count('\n') + 1

        # Recopilar las siguientes N entradas traducidas
        collected_text = []
        for _ in range(orig_lines):
            if trans_idx < len(translated_entries):
                text = translated_entries[trans_idx].translated or translated_entries[trans_idx].original
                collected_text.append(text.strip())
                trans_idx += 1

        # Crear entrada reagrupada
        regrouped_text = '\n'.join(collected_text)
        regrouped_entry = SubtitleEntry(
            id=orig.id,
            start=orig.start,
            end=orig.end,
            original=orig.original,
            translated=regrouped_text
        )
        regrouped.append(regrouped_entry)

    print(f"[REGROUP] Reagrupadas {len(regrouped)} entradas de {len(translated_entries)} originales")
    return regrouped