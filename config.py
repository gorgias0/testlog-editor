"""Configuration management for TestLog Editor."""

import json
import os


class Config:
    """Manages application configuration and state persistence."""

    CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".testlog_editor_config.json")

    @staticmethod
    def load_last_workspace():
        """Load the last opened workspace path from config."""
        if not os.path.exists(Config.CONFIG_FILE):
            return None

        try:
            with open(Config.CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            path = cfg.get("last_workspace")
            if path and os.path.isdir(path):
                return path
        except Exception:
            pass
        return None

    @staticmethod
    def save_last_workspace(path):
        """Save the workspace path to config."""
        try:
            cfg = {"last_workspace": path}
            with open(Config.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f)
        except Exception:
            pass
