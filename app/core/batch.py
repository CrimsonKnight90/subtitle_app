# app\core\batch.py
# 📄 Archivo: app/core/batch.py

from pathlib import Path
from typing import Callable, Iterable, Tuple, Optional
from app.core.ffmpeg_utils import ffprobe_subs, extract_subtitle_stream, BITMAP_CODECS
from app.services.settings import get_settings
from app.services.logging_config import get_logger

# ------------------ Logger ------------------
log = get_logger(__name__)

# ------------------ Extensiones de video soportadas ------------------
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".m4v"}

# ------------------ Iterador de videos ------------------
def iter_videos(root: Path) -> Iterable[Path]:
    """
    Recorre recursivamente la carpeta raíz y devuelve todos los videos soportados.
    """
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in VIDEO_EXT:
            yield p

# ------------------ Resolución de ruta de salida ------------------
def resolve_output_path(input_root: Path, video_path: Path) -> Path:
    """
    Devuelve la ruta de salida para el archivo de subtítulos según la configuración.
    Si el video no está dentro de input_root, usa solo el nombre para evitar ValueError.
    """
    S = get_settings()
    mode = S.config.get("output_mode", "default")
    custom_base = S.config.get("custom_output_base", "")
    subdir_name = S.config.get("same_subdir_name", "subtitulos extraidos")

    try:
        rel = video_path.relative_to(input_root).with_suffix(".srt")
    except ValueError:
        # Si no está dentro de input_root, usar solo el nombre
        rel = Path(video_path.name).with_suffix(".srt")

    if mode == "same":
        return video_path.with_suffix(".srt")
    if mode == "same_subdir":
        return video_path.parent / subdir_name / video_path.with_suffix(".srt").name
    if mode == "custom":
        return Path(custom_base) / rel
    return S.install_dir / "subtitulos" / rel

# ------------------ Procesar un solo video/pista ------------------
def process_one(
    video: Path,
    input_root: Path,
    sel_index: int,
    suffix: str = ""
) -> Tuple[bool, str, Optional[Path]]:
    """
    Extrae una pista de subtítulos específica de un video.
    - video: ruta del archivo de video
    - input_root: carpeta raíz de entrada
    - sel_index: índice de pista a extraer
    - suffix: sufijo opcional para el nombre de salida (evita sobrescrituras)
    """
    try:
        tracks = ffprobe_subs(video)
    except Exception as e:
        return False, f"ffprobe falló: {e}", None

    supported = [t for t in tracks if t["codec_name"] not in BITMAP_CODECS]
    track = next((t for t in supported if t["index"] == sel_index), None)
    if track is None:
        return False, "Índice de pista inválido. Saltado.", None

    # 🔹 Construir nombre de salida con idioma y sufijo único
    lang = track.get("language", "und") or "und"

    try:
        base_out = resolve_output_path(input_root=input_root, video_path=video)
    except Exception as e:
        return False, f"Error al resolver ruta de salida: {e}", None

    # Incluir idioma y sufijo (por ejemplo: _track3) para evitar sobrescrituras
    out_path = base_out.with_name(f"{base_out.stem} [{lang}]{suffix}.srt")

    try:
        ok = extract_subtitle_stream(video, track_index=track["index"], out_srt=out_path)
    except Exception as e:
        return False, f"Error al extraer subtítulos: {e}", None

    if not ok:
        return False, "ffmpeg no pudo extraer/convertir la pista seleccionada.", None

    return True, f"Extraído: idioma={lang} codec={track['codec_name']} default={track['default']}", out_path

# ------------------ Procesar carpeta completa ------------------
def process_folder(input_root: Path, progress_cb: Callable[[int, int, str], None], ask_track_cb) -> None:
    """
    Procesa todos los videos de una carpeta usando un callback de progreso.
    """
    vids = list(iter_videos(input_root))
    total = len(vids)
    done = 0
    for v in vids:
        try:
            ok, msg, outp = process_one(v, input_root, ask_track_cb)
        except Exception as e:
            ok, msg, outp = False, f"Error procesando {v.name}: {e}", None

        done += 1
        info = f"[{done}/{total}] {v.name} → {outp if outp else ''} | {msg}"
        log.info(info)
        progress_cb(done, total, info)
