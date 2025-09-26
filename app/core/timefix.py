import re
from pathlib import Path

TIMECODE = r"(\d{2}:\d{2}:\d{2}[,.]\d{3})"
BLOCK_RE = re.compile(
    rf"^\s*(\d+)\s*\n{TIMECODE}\s*-->\s*{TIMECODE}\s*\n([\s\S]*?)(?=\n\n|\Z)",
    re.MULTILINE
)

def parse_srt(path: str):
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    blocks = []
    for m in BLOCK_RE.finditer(text):
        idx = int(m.group(1))
        start = m.group(2).replace(",", ".")
        end = m.group(3).replace(",", ".")
        body = m.group(4).rstrip()
        blocks.append({"index": idx, "start": start, "end": end, "text": body})
    return blocks

def format_srt(blocks):
    lines = []
    for b in blocks:
        start = b["start"].replace(".", ",")
        end = b["end"].replace(".", ",")
        lines.append(f"{b['index']}\n{start} --> {end}\n{b['text']}\n")
    return "\n".join(lines).strip() + "\n"

def compare_and_fix_times(original_path: str, translated_path: str, out_path: str):
    orig = parse_srt(original_path)
    trans = parse_srt(translated_path)

    if len(orig) != len(trans):
        print(f"[WARN] Diferente número de bloques: original={len(orig)} vs traducido={len(trans)}.")
        # Alinear por mínima longitud para evitar IndexError; reporta diferencias.
        n = min(len(orig), len(trans))
    else:
        n = len(orig)

    fixed = []
    mismatches = 0
    for i in range(n):
        o = orig[i]
        t = trans[i]
        # Clonar tiempos del original, preservar texto traducido
        if o["start"] != t["start"] or o["end"] != t["end"]:
            mismatches += 1
        fixed.append({
            "index": o["index"],     # mantener numeración del original
            "start": o["start"],     # SIEMPRE del original
            "end":   o["end"],       # SIEMPRE del original
            "text":  t["text"]       # texto traducido
        })

    # Si el traducido tenía más bloques, los ignoramos; si tenía menos, reportamos
    if len(trans) > n:
        print(f"[WARN] {len(trans)-n} bloques extra en traducido serán ignorados.")
    if len(trans) < len(orig):
        print(f"[WARN] {len(orig)-len(trans)} bloques faltantes en traducido; tiempos se preservan, texto no.")

    out_text = format_srt(fixed)
    Path(out_path).write_text(out_text, encoding="utf-8")
    print(f"[FIX] Guardado corregido en: {out_path} | desajustes corregidos: {mismatches}/{n}")
