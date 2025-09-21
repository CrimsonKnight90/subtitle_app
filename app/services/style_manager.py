from pathlib import Path
from app.services.settings import get_settings, save_config

STYLES = {
    "dark": Path("app/assets/styles/style_dark.qss"),
    "light": Path("app/assets/styles/style_light.qss"),
}

def apply_theme(app, theme: str):
    path = STYLES.get(theme)
    if path and path.exists():
        app.setStyleSheet(path.read_text(encoding="utf-8"))
    else:
        app.setStyleSheet("")

def set_theme(app, theme: str):
    S = get_settings()
    S.config["ui_theme"] = theme
    save_config(S.config)
    apply_theme(app, theme)
