"""Configuration management — env vars + config file."""

import json
import os
from pathlib import Path


def get_data_dir() -> Path:
    """Return the data directory, configurable via DATA_DIR env var."""
    data_dir = Path(os.environ.get("DATA_DIR", Path.home() / ".plex-suggester"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_config_path() -> Path:
    return get_data_dir() / "config.json"


def load_config() -> dict:
    """Load config from file, overlaid with env vars."""
    config = {}
    config_path = get_config_path()
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))

    # Env vars override config file
    if token := os.environ.get("PLEX_TOKEN"):
        config["plex_token"] = token
    if server_url := os.environ.get("PLEX_SERVER_URL"):
        config["plex_server_url"] = server_url

    return config


def save_config(config: dict) -> None:
    """Save config to file. Only stores non-env-var settings."""
    config_path = get_config_path()
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
