# 📄 Archivo: settings.py

from dataclasses import dataclass
from pathlib import Path
import json
import sys

# ------------------ Configuración general ------------------
CONFIG_NAME = "config.json"

def get_install_dir() -> Path:
    """
    Devuelve la carpeta de instalación de la aplicación.
    - Si está empaquetado con PyInstaller, usa la carpeta del ejecutable.
    - En desarrollo, sube hasta la raíz del proyecto.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]

# ------------------ Carga y guardado de configuración ------------------
def load_config() -> dict:
    """
    Carga el archivo config.json y asegura que tenga todas las claves necesarias.
    Si no existe o está corrupto, devuelve un diccionario con valores por defecto.
    """
    cfg_path = get_install_dir() / CONFIG_NAME
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}

    # Defaults y migración
    data.setdefault("output_mode", "default")  # default | same | same_subdir | custom
    data.setdefault("custom_output_base", "")
    data.setdefault("same_subdir_name", "subtitulos extraidos")
    data.setdefault("auto_select", True)
    # 🔹 Nuevo: idioma preferido
    data.setdefault("preferred_lang", None)
    # en load_config()
    data.setdefault("ui_language", "es")
    data.setdefault("ui_theme", "dark")  # dark | light

    return data

def save_config(cfg: dict):
    """
    Guarda el diccionario de configuración en config.json con formato legible.
    """
    cfg_path = get_install_dir() / CONFIG_NAME
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

# ------------------ Objeto Settings ------------------
@dataclass
class Settings:
    install_dir: Path
    ffmpeg_dir: Path
    ffmpeg_exe: Path
    ffprobe_exe: Path
    ffplay_exe: Path
    config: dict

    def save(self):
        """Guarda la configuración actual en disco."""
        save_config(self.config)

def get_settings() -> Settings:
    """
    Devuelve un objeto Settings con rutas y configuración cargada.
    """
    install_dir = get_install_dir()
    ffmpeg_dir = install_dir / "app" / "vendors" / "ffmpeg"
    cfg = load_config()
    return Settings(
        install_dir=install_dir,
        ffmpeg_dir=ffmpeg_dir,
        ffmpeg_exe=ffmpeg_dir / "ffmpeg.exe",
        ffprobe_exe=ffmpeg_dir / "ffprobe.exe",
        ffplay_exe=ffmpeg_dir / "ffplay.exe",
        config=cfg
    )
