import logging
from pathlib import Path

from config.settings import config

_configured = False


def setup_logging():
    """Configure root logging once, shared by main.py and web/app.py."""
    global _configured
    if _configured:
        return logging.getLogger("soc")

    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    level_name = config.get("logging.level", "INFO")
    level = getattr(logging, level_name, logging.INFO)
    fmt = config.get("logging.format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[
            logging.FileHandler(log_dir / "soc_automation.log"),
            logging.StreamHandler(),
        ],
    )
    _configured = True
    return logging.getLogger("soc")
