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
        return

    # Prefer the launcher script at its known absolute path within the
    # detected root over a PATH-based `steam` lookup: the script lives on
    # the shared host filesystem either way, but the launcher binary
    # normally installed to /usr/bin isn't visible from inside a
    # distrobox/toolbox container (separate root filesystem, only home
    # is shared) -- confirmed this is exactly why shutil.which("steam")
    # found nothing there even though native Steam is genuinely installed.
    launcher = os.path.join(root, "steam.sh")
    if os.path.exists(launcher):
        subprocess.Popen([launcher, "-silent"])
    elif shutil.which("steam"):
        subprocess.Popen(["steam", "-silent"])
