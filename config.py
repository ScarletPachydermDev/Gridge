"""Persistent app settings (SGDB API key, etc.), stored as JSON under
XDG_CONFIG_HOME. This is the real, user-facing settings storage the
GUI reads/writes -- separate from the .env file, which stays a
dev-only convenience for running the CLI directly.
"""
import json
import os

CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "steam-webapp-creator")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def load():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save(**updates):
    data = load()
    data.update(updates)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_sgdb_api_key():
    return load().get("sgdb_api_key")


def set_sgdb_api_key(key):
    save(sgdb_api_key=key)
