"""Minimal SteamGridDB API v2 client (stdlib only, no third-party deps)."""
import json
import os
import urllib.request
import urllib.parse

import config

API_BASE = "https://www.steamgriddb.com/api/v2"

# Steam's non-Steam-shortcut grid folder wants these shapes:
VERTICAL_DIMENSIONS = "600x900,342x482,660x930"
HORIZONTAL_DIMENSIONS = "460x215,920x430"

_ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")


class SGDBError(RuntimeError):
    pass


def _load_dotenv():
    if not os.path.exists(_ENV_FILE):
        return
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def _api_key():
    _load_dotenv()
    key = os.environ.get("STEAMGRIDDB_API_KEY") or config.get_sgdb_api_key()
    if not key:
        raise SGDBError(
            "No SteamGridDB API key configured. Set it in the app's Settings, "
            "or set STEAMGRIDDB_API_KEY in your environment for CLI use "
            "(get a free key at steamgriddb.com/profile/preferences/api)"
        )
    return key


def _get(path, params=None):
    url = f"{API_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "User-Agent": "steam-webapp-creator/0.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        raise SGDBError(f"SGDB API error {e.code} for {path}: {e.read().decode(errors='replace')}")
    if not data.get("success"):
        raise SGDBError(f"SGDB API returned failure for {path}: {data}")
    return data["data"]


def search(term):
    """Return list of {id, name, verified} candidate matches for a query."""
    results = _get(f"/search/autocomplete/{urllib.parse.quote(term)}")
    return [{"id": r["id"], "name": r["name"], "verified": r.get("verified", False)} for r in results]


def get_vertical_grid(game_id):
    grids = _get(f"/grids/game/{game_id}", {"dimensions": VERTICAL_DIMENSIONS})
    return grids[0]["url"] if grids else None


def get_horizontal_grid(game_id):
    grids = _get(f"/grids/game/{game_id}", {"dimensions": HORIZONTAL_DIMENSIONS})
    return grids[0]["url"] if grids else None


def get_hero(game_id):
    heroes = _get(f"/heroes/game/{game_id}")
    return heroes[0]["url"] if heroes else None


def get_logo(game_id):
    logos = _get(f"/logos/game/{game_id}")
    return logos[0]["url"] if logos else None


def get_icon(game_id):
    icons = _get(f"/icons/game/{game_id}")
    if not icons:
        return None
    # Prefer a plain PNG/APNG over .ico -- .ico isn't part of the
    # freedesktop icon spec and renders blank in some app menus.
    for icon in icons:
        if icon["url"].lower().endswith(".png"):
            return icon["url"]
    return icons[0]["url"]


def extract_largest_png_from_ico(ico_bytes):
    """Modern .ico files embed PNG-compressed frames for larger sizes.
    Pull out the biggest one so we can save a real .png (no image lib needed).
    Returns None if the .ico only contains legacy BMP/DIB frames."""
    count = int.from_bytes(ico_bytes[4:6], "little")
    best = None
    for i in range(count):
        entry = ico_bytes[6 + i * 16 : 6 + i * 16 + 16]
        width = entry[0] or 256
        height = entry[1] or 256
        size = int.from_bytes(entry[8:12], "little")
        offset = int.from_bytes(entry[12:16], "little")
        data = ico_bytes[offset : offset + size]
        if data[:8] == b"\x89PNG\r\n\x1a\n" and (best is None or width * height > best[0]):
            best = (width * height, data)
    return best[1] if best else None


def download(url, dest_path):
    req = urllib.request.Request(url, headers={"User-Agent": "steam-webapp-creator/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    with open(dest_path, "wb") as f:
        f.write(data)
    return dest_path
