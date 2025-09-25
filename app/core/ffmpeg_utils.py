# app\core\ffmpeg_utils.py
# 📄 Archivo: app/core/ffmpeg_utils.py

from pathlib import Path
import subprocess, json
from typing import List, Optional
from app.services.settings import get_settings
from app.services.logging_config import get_logger

# ------------------ Logger ------------------
log = get_logger(__name__)

# ------------------ Clase para representar pistas ------------------
class SubTrack(dict):
    """Representa una pista de subtítulos con sus metadatos."""
    pass

# ------------------ Verificación de binarios ------------------
def check_binaries() -> None:
    """
    Verifica que ffmpeg y ffprobe existan en la carpeta de instalación.
    Lanza FileNotFoundError si falta alguno.
    """
    S = get_settings()
    for exe in (S.ffmpeg_exe, S.ffprobe_exe):
        if not exe.exists():
            raise FileNotFoundError(f"No se encontró {exe}. Asegúrate de incluir /ffmpeg en la carpeta de instalación.")

# ------------------ Obtener pistas de subtítulos con ffprobe ------------------
def ffprobe_subs(video: Path) -> List[SubTrack]:
    """
    Ejecuta ffprobe para obtener información de las pistas de subtítulos.
    Devuelve una lista de SubTrack con datos de cada pista soportada.
    """
    S = get_settings()
    check_binaries()
    cmd = [
        str(S.ffprobe_exe), "-v", "error",
        "-select_streams", "s",
        "-show_entries", "stream=index,codec_name,disposition:stream_tags=language,title",
        "-of", "json",
        str(video)
    ]
    log.info(f"ffprobe: {' '.join(cmd)}")

    # 🔹 Forzar UTF-8 y reemplazar caracteres inválidos para evitar UnicodeDecodeError
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    if res.returncode != 0:
        raise RuntimeError(f"ffprobe falló: {res.stderr}")

    data = json.loads(res.stdout or "{}")
    tracks = []
    for s in data.get("streams", []):
        disp = s.get("disposition", {}) or {}
        tags = s.get("tags", {}) or {}
        tracks.append(SubTrack({
            "index": s.get("index"),
            "codec_name": s.get("codec_name", "").lower(),
            "language": (tags.get("language") or "und").lower(),
            "title": tags.get("title") or "",
            "default": bool(disp.get("default", 0)),
            "forced": bool(disp.get("forced", 0)),
        }))
    return tracks

# ------------------ Codecs de subtítulos basados en imagen ------------------
BITMAP_CODECS = {"hdmv_pgs_subtitle", "pgssub", "dvd_subtitle", "dvdsub", "xsub", "vobsub"}

# ------------------ Selección automática de pista ------------------
def choose_track(tracks: List[SubTrack], auto_select: bool) -> Optional[SubTrack]:
    """
    Devuelve la pista predeterminada si existe, o la primera pista disponible.
    """
    if not tracks:
        return None
    if auto_select:
        for t in tracks:
            if t.get("default"):
                return t
        return tracks[0]
    return None

# ------------------ Extracción de pista de subtítulos ------------------
def extract_subtitle_stream(video: Path, track_index: int, out_srt: Path) -> bool:
    """
    Extrae una pista de subtítulos específica a formato SRT usando ffmpeg.
    """
    S = get_settings()
    check_binaries()

    # Traducir índice global -> relativo en subtítulos
    all_subs = ffprobe_subs(video)
    sub_only = [t for t in all_subs if t["codec_name"]]
    relative_index = next((i for i, t in enumerate(sub_only) if t["index"] == track_index), 0)

    out_srt.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(S.ffmpeg_exe), "-y",
        "-i", str(video),
        "-map", f"0:s:{relative_index}",
        "-c:s", "srt",
        str(out_srt)
    ]
    log.info(f"ffmpeg: {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    if proc.returncode != 0:
        log.error(f"ffmpeg error: {proc.stderr.strip()}")
        return False
    return out_srt.exists() and out_srt.stat().st_size > 0
