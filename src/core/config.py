"""Application configuration loaded from config.yaml + environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Config:
    """Read-only view over the parsed config.yaml with dotted-path access."""

    def __init__(self, data: dict[str, Any]):
        self._data = data

    def get(self, path: str, default: Any = None) -> Any:
        node: Any = self._data
        for key in path.split("."):
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def __getitem__(self, path: str) -> Any:
        value = self.get(path, _MISSING)
        if value is _MISSING:
            raise KeyError(f"Missing config key: {path}")
        return value

    @property
    def data(self) -> dict[str, Any]:
        return self._data


_MISSING = object()


@lru_cache(maxsize=1)
def get_config(config_path: str | None = None) -> Config:
    load_dotenv(PROJECT_ROOT / ".env")
    path = Path(config_path) if config_path else PROJECT_ROOT / "config.yaml"
    with open(path) as f:
        return Config(yaml.safe_load(f))


def get_api_key(env_var: str) -> str | None:
    return os.environ.get(env_var) or None
