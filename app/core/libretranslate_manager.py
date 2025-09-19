import os
import sys
import time
import signal
import subprocess
from typing import Iterable, Optional
import requests

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
_DEFAULT_WAIT_SECONDS = 20

# Mantenemos una referencia al proceso lanzado para permitir stop()
_LT_PROCESS: Optional[subprocess.Popen] = None


def _abs(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def _is_alive(proc: Optional[subprocess.Popen]) -> bool:
    return proc is not None and proc.poll() is None


def _creationflags_for_platform() -> int:
    # Oculta consola en Windows
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def is_libretranslate_running(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 1.0) -> bool:
    try:
        r = requests.get(f"http://{host}:{port}/languages", timeout=timeout)
        return r.status_code == 200
    except requests.RequestException:
        return False


def _build_cmd(host: str, port: int, languages: Iterable[str]) -> list[str]:
    langs = ",".join(languages) if languages else ""
    cmd = [
        sys.executable,
        "-m",
        "libretranslate",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if langs:
        cmd += ["--load-only", langs]
    return cmd


def start_libretranslate(
    vendors_path: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    languages: Iterable[str] = ("en", "es", "fr"),
    wait_seconds: int = _DEFAULT_WAIT_SECONDS,
) -> bool:
    """
    Arranca LibreTranslate en segundo plano.
    1) Intenta usar instalación vía pip (python -m libretranslate)
    2) Fallback: cwd en vendors/LibreTranslate si existe
    Espera hasta 'wait_seconds' a que /languages responda. Devuelve True si queda listo.
    """
    global _LT_PROCESS

    # Si ya está respondiendo, no hacemos nada.
    if is_libretranslate_running(host, port):
        return True

    cmd = _build_cmd(host, port, languages)
    creationflags = _creationflags_for_platform()

    # Intento 1: instalación pip
    try:
        _LT_PROCESS = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except Exception:
        _LT_PROCESS = None

    # Intento 2: vendors/LibreTranslate (si el intento 1 falló)
    if not _is_alive(_LT_PROCESS):
        lt_dir = os.path.join(_abs(vendors_path), "LibreTranslate")
        cwd = lt_dir if os.path.isdir(lt_dir) else None
        try:
            _LT_PROCESS = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except Exception:
            _LT_PROCESS = None

    # Espera con backoff suave a que responda
    deadline = time.time() + max(2, wait_seconds)
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        if is_libretranslate_running(host, port, timeout=1.0):
            return True
        # Si el proceso murió, no seguimos esperando
        if _LT_PROCESS is not None and _LT_PROCESS.poll() is not None:
            break
        time.sleep(min(0.25 * attempt, 2.0))

    return is_libretranslate_running(host, port, timeout=1.0)


def ensure_libretranslate(
    vendors_path: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    languages: Iterable[str] = ("en", "es", "fr"),
    wait_seconds: int = _DEFAULT_WAIT_SECONDS,
) -> bool:
    """
    Garantiza que LibreTranslate esté corriendo.
    Devuelve True si está listo, False si no se pudo iniciar.
    """
    if is_libretranslate_running(host, port):
        return True
    return start_libretranslate(vendors_path, host, port, languages, wait_seconds)


def stop_libretranslate(grace_seconds: float = 3.0) -> None:
    """
    Intenta parar el proceso lanzado por este módulo de forma limpia.
    No mata instancias que no hayamos lanzado (si otro LT ya estaba corriendo, no lo tocamos).
    """
    global _LT_PROCESS
    if not _is_alive(_LT_PROCESS):
        _LT_PROCESS = None
        return

    proc = _LT_PROCESS
    _LT_PROCESS = None

    try:
        if os.name == "nt":
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
        # Pequeña espera para cierre limpio
        deadline = time.time() + max(0.5, grace_seconds)
        while time.time() < deadline:
            if proc.poll() is not None:
                return
            time.sleep(0.1)
        # Forzar kill si no cerró
        proc.kill()
    except Exception:
        pass
