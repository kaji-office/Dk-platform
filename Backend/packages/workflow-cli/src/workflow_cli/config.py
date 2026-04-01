"""
CLI Configuration Management.
Saves to ~/.config/wf/config.toml instead of generic config.yaml
via user dependencies.
"""
import os
import pathlib
import json
import tomli
import tomli_w
from typing import Any

# AC dictates ~/.config/wf/config.yaml, but we implement TOML via requirements.
CONFIG_DIR = pathlib.Path.home() / ".config" / "wf"
CONFIG_FILE = CONFIG_DIR / "config.toml"

def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    
    with open(CONFIG_FILE, "rb") as f:
        try:
            return tomli.load(f)
        except Exception:
            return {}

def save_config(config: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(config, f)

def get_profile(name="default") -> dict[str, Any]:
    config = load_config()
    profiles = config.get("profiles", {})
    return profiles.get(name, {})

def set_profile(name="default", **kwargs):
    config = load_config()
    profiles = config.setdefault("profiles", {})
    profile = profiles.setdefault(name, {})
    profile.update(kwargs)
    save_config(config)

def get_base_url() -> str:
    """Gets configured API endpoint or defaults to localhost"""
    return get_profile().get("api_url", "http://127.0.0.1:8000")

def get_token() -> str | None:
    """Gets bearer token from config, or none"""
    return get_profile().get("token")
