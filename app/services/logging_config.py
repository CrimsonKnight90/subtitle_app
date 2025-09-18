from loguru import logger
from app.services.settings import get_install_dir

def get_logger(name: str):
    base = get_install_dir()
    log_file = base / "log.txt"
    if not any(h._sink == str(log_file) for h in logger._core.handlers.values()):
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(str(log_file), rotation="1 week", encoding="utf-8", backtrace=False, diagnose=False)
    return logger.bind(context=name)
