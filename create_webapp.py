#!/usr/bin/env python3
"""Stage 1 CLI: search SGDB, confirm match, download the 5 asset categories,
and (for local testing without Steam) register a .desktop entry so the icon
shows up in the app menu.
"""
import argparse
import os
import re
import shutil
import sys
from urllib.parse import urlparse

import sgdb_client as sgdb
import shortcuts_vdf
import steam_paths

ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")
APPLICATIONS_DIR = os.path.expanduser("~/.local/share/applications")
KIOSK_LAUNCHER_DIR = os.path.join(os.path.dirname(__file__), "kiosk-launcher")
KIOSK_LAUNCHER_ELECTRON = os.path.join(KIOSK_LAUNCHER_DIR, "node_modules", "electron", "dist", "electron")
KIOSK_LAUNCHER_SCRIPT = os.path.join(KIOSK_LAUNCHER_DIR, "launch.sh")


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def pick_match(name):
    matches = sgdb.search(name)
    if not matches:
        sys.exit(f"No SGDB matches found for '{name}'")

    print(f"\nSGDB matches for '{name}':")
    for i, m in enumerate(matches):
        tag = " (verified)" if m["verified"] else ""
        print(f"  [{i}] {m['name']}{tag} - id {m['id']}")

    if len(matches) == 1:
        choice = 0
    else:
        raw = input(f"Pick a match [0-{len(matches) - 1}] (default 0): ").strip()
        choice = int(raw) if raw else 0
    return matches[choice]


def fetch_assets(game_id, slug):
    out_dir = os.path.join(ASSET_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)

    fetchers = {
        "grid_vertical": sgdb.get_vertical_grid,
        "grid_horizontal": sgdb.get_horizontal_grid,
        "hero": sgdb.get_hero,
        "logo": sgdb.get_logo,
        "icon": sgdb.get_icon,
    }

    paths = {}
    for basename, fetch in fetchers.items():
        url = fetch(game_id)
        if not url:
            print(f"  ! no {basename} available on SGDB, skipping")
            continue
        ext = os.path.splitext(urlparse(url).path)[1] or ".png"
        filename = f"{basename}{ext}"
        dest = os.path.join(out_dir, filename)
        sgdb.download(url, dest)

        if ext == ".ico":
            with open(dest, "rb") as f:
                png_data = sgdb.extract_largest_png_from_ico(f.read())
            if png_data:
                os.remove(dest)
                filename = f"{basename}.png"
                dest = os.path.join(out_dir, filename)
                with open(dest, "wb") as f:
                    f.write(png_data)

        print(f"  + {filename}  <-  {url}")
        paths[basename] = dest
    return paths


GRID_FILENAMES = {
    "grid_vertical": "{appid}p{ext}",
    "grid_horizontal": "{appid}{ext}",
    "hero": "{appid}_hero{ext}",
    "logo": "{appid}_logo{ext}",
    "icon": "{appid}_icon{ext}",
}


def register_steam_shortcut(name, url, asset_paths, user_id=None):
    """Copy fetched assets into Steam's grid folder and add/update a
    non-Steam shortcut entry in shortcuts.vdf. Returns the appid."""
    if not os.path.exists(KIOSK_LAUNCHER_ELECTRON):
        sys.exit(
            f"Kiosk launcher isn't built: {KIOSK_LAUNCHER_ELECTRON} not found.\n"
            f"Run: cd {KIOSK_LAUNCHER_DIR} && npm install"
        )

    userdata_dir = steam_paths.find_userdata_dir(user_id)
    grid_dir = os.path.join(userdata_dir, "config", "grid")
    os.makedirs(grid_dir, exist_ok=True)

    appid = shortcuts_vdf.generate_appid(KIOSK_LAUNCHER_SCRIPT, name)

    icon_dest = None
    for basename, src in asset_paths.items():
        if basename not in GRID_FILENAMES:
            continue
        ext = os.path.splitext(src)[1]
        dest = os.path.join(grid_dir, GRID_FILENAMES[basename].format(appid=appid, ext=ext))
        shutil.copy2(src, dest)
        print(f"  + {os.path.basename(dest)}  <-  {src}")
        if basename == "icon":
            icon_dest = dest

    vdf_path = os.path.join(userdata_dir, "config", "shortcuts.vdf")
    written_appid = shortcuts_vdf.add_shortcut(
        vdf_path,
        appname=name,
        exe=KIOSK_LAUNCHER_SCRIPT,
        start_dir=KIOSK_LAUNCHER_DIR + "/",
        icon=icon_dest or "",
        launch_options=f". {url}",
        allow_overlay=False,
    )
    assert written_appid == appid
    print(f"\nAdded/updated Steam shortcut '{name}' (appid {appid}) in {vdf_path}")
    print("Restart Steam (fully quit, not just close the window) to see it.")
    return appid


def register_test_desktop_entry(name, slug, url, icon_path):
    """Add a .desktop file to the app menu so we can visually confirm the
    icon/artwork pipeline without needing Steam installed."""
    os.makedirs(APPLICATIONS_DIR, exist_ok=True)
    desktop_path = os.path.join(APPLICATIONS_DIR, f"webapp-test-{slug}.desktop")
    icon_field = icon_path or ""
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={name} (webapp test)\n"
        f"Comment=Steam webapp creator test entry for {url}\n"
        f"Icon={icon_field}\n"
        f'Exec=xdg-open "{url}"\n'
        "Terminal=false\n"
        "Categories=Network;\n"
    )
    with open(desktop_path, "w") as f:
        f.write(content)
    os.chmod(desktop_path, 0o755)
    print(f"\nRegistered test app menu entry: {desktop_path}")

    update_db = "/usr/bin/update-desktop-database"
    if os.path.exists(update_db):
        os.system(f'"{update_db}" "{APPLICATIONS_DIR}" >/dev/null 2>&1')


def main():
    parser = argparse.ArgumentParser(description="Search SGDB, fetch assets, add a Steam shortcut")
    parser.add_argument("name", help="App name to search on SteamGridDB, e.g. Netflix")
    parser.add_argument("url", help="URL the webapp should open, e.g. https://netflix.com")
    parser.add_argument("--steam-user", help="Steam user id, only needed if you have more than one")
    parser.add_argument(
        "--desktop-only", action="store_true",
        help="Skip Steam integration and just register a test .desktop entry",
    )
    args = parser.parse_args()

    match = pick_match(args.name)
    slug = slugify(match["name"])
    print(f"\nFetching assets for '{match['name']}' (SGDB id {match['id']})...")
    paths = fetch_assets(match["id"], slug)

    if not args.desktop_only:
        try:
            register_steam_shortcut(match["name"], args.url, paths, args.steam_user)
            return
        except steam_paths.SteamNotFoundError as e:
            print(f"\n! Steam not found ({e}), falling back to test .desktop entry")

    icon_path = paths.get("icon") or paths.get("grid_vertical")
    register_test_desktop_entry(match["name"], slug, args.url, icon_path)


if __name__ == "__main__":
    main()
