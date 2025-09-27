from pathlib import Path
import shutil, platform

def ffmpeg_available() -> bool:
    exe = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"

    # 1. Buscar en PATH
    if shutil.which(exe):
        return True

    # 2. Buscar en vendors/ffmpeg
    vendor_dir = Path("app/vendors/ffmpeg")
    vendor_exec = vendor_dir / exe
    if vendor_exec.exists():
        return True

    return False

def ffmpeg_path() -> Path | None:
    """Devuelve la ruta al ejecutable de ffmpeg si existe, None si no"""
    exe = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"

    # PATH
    path = shutil.which(exe)
    if path:
        return Path(path)

    # vendors
    vendor_exec = Path("app/vendors/ffmpeg") / exe
    if vendor_exec.exists():
        return vendor_exec

    return None
