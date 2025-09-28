# app/services/style_manager.py
import os, sys
from pathlib import Path
from app.services.settings import get_settings, save_config

# Rutas relativas dentro del bundle/proyecto
STYLE_REL = {
    "dark": "app/assets/styles/style_dark.qss",
    "light": "app/assets/styles/style_light.qss",
}

def resource_path(relative_path: str) -> str:
    """Devuelve la ruta absoluta al recurso, compatible con PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def apply_theme(app, theme: str):
    """Carga el QSS según el tema, en dev y en exe."""
    rel = STYLE_REL.get(theme)
    if not rel:
        app.setStyleSheet("")
        return

    abs_path = resource_path(rel)
    try:
        if os.path.exists(abs_path):
            with open(abs_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
        else:
            # Fallback en dev por si trabajas fuera de raíz
            p = Path(rel)
            if p.exists():
                app.setStyleSheet(p.read_text(encoding="utf-8"))
            else:
                app.setStyleSheet("")
    except Exception:
        app.setStyleSheet("")

def set_theme(app, theme: str):
    """Persiste y aplica tema de forma centralizada."""
    S = get_settings()
    S.config["ui_theme"] = theme
    save_config(S.config)
    apply_theme(app, theme)
