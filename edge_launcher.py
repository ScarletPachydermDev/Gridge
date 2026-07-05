"""Detect an installed Microsoft Edge, native or Flatpak.

Edge is the only Chromium-based browser with Dolby Digital Plus/Atmos audio
decoding built in on every platform it ships, including Linux -- Google
never licensed Dolby codecs into open-source Chromium, so no other
Chromium derivative (including a bundled Electron) can play that audio.
Rather than bundling a browser ourselves, we shell out to Edge if it's
already installed, and ask the user to install it otherwise.
"""
import shutil
import subprocess

NATIVE_BINARY_NAMES = ["microsoft-edge-stable", "microsoft-edge", "microsoft-edge-beta", "microsoft-edge-dev"]
FLATPAK_APP_ID = "com.microsoft.Edge"

INSTALL_INSTRUCTIONS = (
    "Microsoft Edge wasn't found. Install it from Flathub "
    "(flatpak install flathub com.microsoft.Edge) or from "
    "https://www.microsoft.com/en-us/edge/download?platform=linux "
    "(official .deb/.rpm), then try again."
)


class EdgeNotFoundError(RuntimeError):
    pass


def _flatpak_edge_installed():
    flatpak = shutil.which("flatpak")
    if not flatpak:
        return False
    result = subprocess.run(
        [flatpak, "info", FLATPAK_APP_ID],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def find_edge():
    """Returns (exe, prefix_args) for the installed Edge. prefix_args is
    empty for a native binary, or ["run", FLATPAK_APP_ID, "--"] when only
    the Flatpak is installed, so callers can just do
    [exe, *prefix_args, "--app=<url>", ...]."""
    for name in NATIVE_BINARY_NAMES:
        path = shutil.which(name)
        if path:
            return path, []

    if _flatpak_edge_installed():
        return shutil.which("flatpak"), ["run", FLATPAK_APP_ID, "--"]

    raise EdgeNotFoundError(INSTALL_INSTRUCTIONS)
