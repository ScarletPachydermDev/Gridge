"""Restart Steam so it picks up new/changed non-Steam shortcuts."""
import os
import shutil
import subprocess
import time

import steam_paths


def restart_steam():
    """Kill Steam and relaunch it (Flatpak or native, whichever is
    present). Fire-and-forget -- Steam takes a while to fully start on
    its own regardless of how it's launched.

    Uses steam_paths' filesystem-based detection rather than asking the
    `flatpak` CLI whether Steam is installed -- that CLI's view can be
    isolated from the host's actual installs (e.g. from inside a
    distrobox/toolbox container used for dev testing), even though the
    filesystem paths themselves are shared and visible."""
    subprocess.run(["killall", "steam"], capture_output=True)
    time.sleep(1)

    try:
        root = steam_paths.find_steam_root()
    except steam_paths.SteamNotFoundError:
        return

    if root == os.path.expanduser(steam_paths.FLATPAK_ROOT):
        flatpak = shutil.which("flatpak")
        if flatpak:
            subprocess.Popen([flatpak, "run", "com.valvesoftware.Steam"])
    elif shutil.which("steam"):
        subprocess.Popen(["steam", "-silent"])
