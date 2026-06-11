"""Centralized logging setup."""

from __future__ import annotations

import logging
import sys

_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    from src.core.config import get_config

    level = get_config().get("logging.level", "INFO")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger("fin_expert")
    root.setLevel(level)
    root.addHandler(handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    return logging.getLogger(f"fin_expert.{name}")
