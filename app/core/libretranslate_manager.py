import subprocess
import sys
import os
import time
import requests

DEFAULT_PORT = 5000

def is_libretranslate_running(port=DEFAULT_PORT):
    """Comprueba si LibreTranslate responde en el puerto indicado."""
    try:
        r = requests.get(f"http://localhost:{port}/languages", timeout=1)
        return r.status_code == 200
    except requests.RequestException:
        return False

def start_libretranslate(vendors_path, port=DEFAULT_PORT, languages=("en", "es", "fr")):
    """
    Arranca LibreTranslate en segundo plano.
    1. Intenta usar instalación vía pip.
    2. Si no, intenta desde vendors/LibreTranslate.
    """
    # Comando base
    cmd = [sys.executable, "-m", "libretranslate", "--load-only", ",".join(languages), "--port", str(port)]

    try:
        # Intentar arranque usando instalación pip
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        # Si falla, intentar desde vendors
        libre_path = os.path.join(vendors_path, "LibreTranslate")
        process = subprocess.Popen(cmd, cwd=libre_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Esperar a que arranque
    for _ in range(20):
        if is_libretranslate_running(port):
            return True
        time.sleep(1)

    return False

def ensure_libretranslate(vendors_path, port=DEFAULT_PORT, languages=("en", "es", "fr")):
    """
    Garantiza que LibreTranslate esté corriendo.
    Devuelve True si está listo, False si no se pudo iniciar.
    """
    if is_libretranslate_running(port):
        return True
    return start_libretranslate(vendors_path, port, languages)
