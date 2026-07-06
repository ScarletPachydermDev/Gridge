"""Export/import this tool's own Steam shortcuts (identified by exe ==
LAUNCH_WRAPPER, so a user's own unrelated non-Steam shortcuts are never
touched) as a portable zip archive. Bundles each shortcut's already-
downloaded SGDB artwork so import doesn't need network access or a
configured API key at all.
"""
import json
import os
import re
import shutil
import tempfile
import zipfile

import create_webapp as cw
import shortcuts_vdf
import steam_paths

MANIFEST_NAME = "manifest.json"


def _extract_url(launch_options):
    match = re.search(r"--app=(\S+)", launch_options or "")
    return match.group(1) if match else None


def export_shortcuts(zip_path, user_id=None):
    """Write a zip of all this tool's shortcuts (name, URL, and grid
    artwork) to zip_path. Returns the number exported."""
    userdata_dir = steam_paths.find_userdata_dir(user_id)
    vdf_path = os.path.join(userdata_dir, "config", "shortcuts.vdf")
    grid_dir = os.path.join(userdata_dir, "config", "grid")
    root = shortcuts_vdf.load(vdf_path)

    entries = []
    for v in root.get("shortcuts", {}).values():
        exe = v.get("exe") or v.get("Exe")
        if exe != cw.LAUNCH_WRAPPER:
            continue
        appname = v.get("appname") or v.get("AppName")
        url = _extract_url(v.get("LaunchOptions"))
        appid = v.get("appid")
        if appname and url and appid:
            entries.append({"appname": appname, "url": url, "appid": appid})

    with tempfile.TemporaryDirectory() as tmp:
        manifest = []
        for entry in entries:
            slug = cw.slugify(entry["appname"])
            asset_dir = os.path.join(tmp, "assets", slug)
            os.makedirs(asset_dir, exist_ok=True)
            asset_files = {}
            for basename, pattern in cw.GRID_FILENAMES.items():
                for ext in (".png", ".jpg", ".jpeg", ".ico"):
                    candidate = os.path.join(grid_dir, pattern.format(appid=entry["appid"], ext=ext))
                    if os.path.exists(candidate):
                        dest_name = f"{basename}{ext}"
                        shutil.copy2(candidate, os.path.join(asset_dir, dest_name))
                        asset_files[basename] = f"assets/{slug}/{dest_name}"
                        break
            manifest.append({"appname": entry["appname"], "url": entry["url"], "assets": asset_files})

        with open(os.path.join(tmp, MANIFEST_NAME), "w") as f:
            json.dump(manifest, f, indent=2)

        if os.path.exists(zip_path):
            os.remove(zip_path)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for dirpath, _dirs, filenames in os.walk(tmp):
                for filename in filenames:
                    full = os.path.join(dirpath, filename)
                    zf.write(full, os.path.relpath(full, tmp))

    return len(manifest)


def import_shortcuts(zip_path, user_id=None):
    """Read a zip written by export_shortcuts() and register each
    shortcut on this machine, reusing the bundled artwork directly
    (no SGDB re-fetch needed). Returns the number imported."""
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)

        with open(os.path.join(tmp, MANIFEST_NAME)) as f:
            manifest = json.load(f)

        count = 0
        for entry in manifest:
            asset_paths = {basename: os.path.join(tmp, rel_path) for basename, rel_path in entry["assets"].items()}
            cw.register_steam_shortcut(entry["appname"], entry["url"], asset_paths, user_id)
            count += 1

    return count
