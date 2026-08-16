from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger as _logger

def setup_logger(log_path: str | None = None):
    from loguru import logger

    if log_path is None:
        log_path = str(Path.home() / ".openmanus" / "logs" / "openmanus.log")

    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    logger.remove()

    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
               "<level>{message}</level>",
        level="INFO",
    )

    logger.add(
        log_path,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    return logger

setup_logger()
