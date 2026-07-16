"""Config loader — reads ~/.config/inboxguard/config.yaml"""

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "inboxguard" / "config.yaml"


class Config:
    def __init__(self, config_path: str = None):
        self.path = Path(config_path).expanduser() if config_path else DEFAULT_CONFIG_PATH
        self._data: dict = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            raise FileNotFoundError(
                f"Config file not found at {self.path}.\n"
                f"Run:  cp config.example.yaml {self.path}\n"
                f"Then edit it with your email credentials."
            )
        with open(self.path, "r") as fh:
            data = yaml.safe_load(fh)
        # Expand env vars inside string values
        return self._expand_env(data)

    def _expand_env(self, obj):
        if isinstance(obj, dict):
            return {k: self._expand_env(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._expand_env(i) for i in obj]
        if isinstance(obj, str):
            return os.path.expandvars(obj)
        return obj

    def get(self, key: str, default: Any = None) -> Any:
        """Dot-notation access: config.get('email.imap_server')"""
        parts = key.split(".")
        node = self._data
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node if node is not None else default

    def reload(self):
        self._data = self._load()

    @property
    def raw(self) -> dict:
        return self._data
