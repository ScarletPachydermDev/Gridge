# Project recap / handoff

Written for continuing this project with Claude Code on the x86_64 laptop
(this repo was started on an aarch64 machine that can't run Steam).

## Goal

A Flatpak GTK4 app for Steam Deck / Bazzite / CachyOS: user types a URL
(e.g. netflix.com), app searches SteamGridDB for matching artwork, user
confirms the match, and the app creates a non-Steam shortcut so the site
shows up as a native-looking tile in Steam Game Mode — opened in a
borderless/kiosk browser window instead of a normal browser tab.

Stretch goal: bundle a Steam Input controller config so the d-pad acts
like Tab (navigate), A = Enter/Play-Pause, B = Back/Escape.

## Stack decisions (already made, don't re-litigate)

- **GTK4 + libadwaita**, Python via PyGObject. UI should stay minimal,
  styled like [unrud/video-downloader](https://github.com/unrud/video-downloader)
  — single window, no bells and whistles.
- **No third-party Python deps for the SGDB client** — stdlib `urllib`
  only, to keep the Flatpak runtime light. Keep this going unless there's
  a strong reason to add `requests`.
- **Flatpak target: x86_64 only** (changed from an earlier x64+arm64
  plan — see kiosk launcher decision below for why).
- Plan: publish to GitHub (done) for issues, then submit to **Flathub**
  for auto-updates.

## Repo

https://github.com/Scarlet-Pachyderm/steam-webapp-creator

(Transferred from a personal account into the `Scarlet-Pachyderm` org.
Repo name `steam-webapp-creator` is a placeholder — renaming later is
fine, GitHub redirects the old URL/remote automatically.)

## Stage 1 — done

`sgdb_client.py` + `create_webapp.py`: CLI that searches SGDB, lets the
user confirm a match, downloads the 5 asset categories, and (since Steam
isn't installed on the dev machine) registers a `.desktop` file in the
local app menu as a stand-in test for "does the icon actually render."
Confirmed working end-to-end for Netflix.

Non-obvious things learned along the way:

- SGDB API requests need a real `User-Agent` header or Cloudflare 403s
  them (error code 1010) — the auth header alone isn't enough.
- The `/icons` endpoint returns both `.ico` and plain `.png` entries for
  the same game. **Prefer `.png`**; `.ico` isn't part of the freedesktop
  icon spec and can render blank in app menus. `sgdb_client.py` already
  filters for `.png` first.
- As a fallback for the rare case where only `.ico` exists,
  `sgdb_client.extract_largest_png_from_ico()` pulls the largest embedded
  PNG frame straight out of the ICO container (modern ICOs embed real
  PNGs for big sizes) — no image library needed.
- Always derive the saved file extension from the actual URL, not a
  hardcoded `.png` — SGDB's "grid" assets are sometimes JPEGs.
- Grid dimensions used: vertical `600x900,342x482,660x930`, horizontal
  `460x215,920x430` (matches what Steam's non-Steam-shortcut grid folder
  expects for portrait/landscape tiles).
- `.env` (gitignored) holds `STEAMGRIDDB_API_KEY` — get a free key at
  steamgriddb.com/profile/preferences/api. Needs to be recreated on each
  machine, it's not in git.
- `assets/` (gitignored) holds test-downloaded images, also not in git.

## Stage 2 — items 1-4 done, confirmed working on real Steam

1. **`shortcuts.vdf` writer** — done, `shortcuts_vdf.py`. Binary VDF
   read/write (type-tagged tree: 0x00 map / 0x01 string / 0x02 int32,
   0x08 closes a map). `load()`/`save()` round-trip preserves existing
   entries and auto-backs up to `.bak` before overwriting.
   `add_shortcut()` updates in place by matching `appname` instead of
   duplicating.
2. **App ID calculation** — done, `shortcuts_vdf.generate_appid(exe,
   appname)`: CRC32 of the **quoted** exe path concatenated with the app
   name, OR'd with `0x80000000`. Same value is used for the vdf's
   `appid` field and every grid asset filename — confirmed they must all
   agree or Steam won't associate the artwork.
3. **Artwork placement** — done, in `create_webapp.py:register_steam_shortcut()`.
   Saves into `<userdata>/<id>/config/grid/` as `<appid>p.ext` (vertical),
   `<appid>.ext` (horizontal), `<appid>_hero.ext`, `<appid>_logo.ext`,
   `<appid>_icon.ext` — extension taken from the real downloaded file,
   not hardcoded.
4. **Steam install path detection** — done, `steam_paths.py`. Checks
   native `~/.local/share/Steam` / `~/.steam/steam` first, then Flatpak
   `~/.var/app/com.valvesoftware.Steam/.local/share/Steam`. Confirmed
   correct on both: picks native on the Steam Deck (SteamOS, `holo`),
   picks Flatpak on the x86_64 dev box. Multiple userdata user IDs
   aren't auto-resolved — raises and expects `--steam-user`.

**Confirmed end-to-end on real Steam for Disney+, on two different
machines:**
- **x86_64 desktop, Steam as Flatpak** — shortcut appeared with full
  artwork after a full Steam restart, and the tile launched the URL via
  `exe=/usr/bin/xdg-open` (a **host** binary path) with no
  `flatpak-spawn --host` wrapper needed — Steam's own Flatpak sandbox
  permissions were broad enough to exec it directly.
- **Steam Deck (SteamOS, native Steam)** — same code, same generated
  appid (`4039713046`, confirming the calc is deterministic across
  machines), shortcut appeared with artwork and launched correctly.
  Reached over SSH (SteamOS ships `sshd` but it's off by default —
  enabled via Desktop Mode: `passwd` then `sudo systemctl enable --now
  sshd`; unit is named `sshd`, not `ssh`). `killall steam` is enough to
  force a restart that picks up new shortcuts; it auto-relaunches.

Not yet tested: Bazzite, CachyOS, a userdata dir with multiple Steam
user IDs.

5. Steam needs a full restart (fully quit, not just close the window)
   to pick up new/changed shortcuts — confirmed, no known way around
   this.

## Later stages (not started)

- **Kiosk-mode browser launch — REVISED decision: bundle a Widevine-enabled
  Electron, don't shell out to an installed browser.** (Superseded the
  original "shell out to Brave/Chrome" plan below — kept struck through
  for context in case this needs revisiting.)
  - Using [castLabs' Electron fork](https://github.com/castlabs/electron-releases)
    ("Electron for Content Security", tag suffix `+wvcus`), which bundles
    Widevine CDM support via an official `components` API
    (`await components.whenReady()` before creating the `BrowserWindow`).
    Install via `npm install "https://github.com/castlabs/electron-releases#vXX.X.X+wvcus" --save-dev`
    (not published to the npm registry, GitHub tag pinning only).
  - Scaffolded in `kiosk-launcher/` (see below).
  - **x86_64 only** — confirmed by checking release assets across
    v41–v44: castLabs publishes `linux-x64` builds only, no `linux-arm64`,
    on every recent release. Since Steam Deck itself is x86_64, this
    doesn't hurt the main target, but it's why the arm64 Flatpak target
    was dropped (decided over the original x64+arm64 plan — user
    explicitly doesn't care about Flatpak size, so bundling Electron
    instead of shelling out was preferred).
  - Linux support in this fork is officially "partial": no persistent
    license storage (VMP limitation on Linux). Shouldn't matter here —
    that only affects offline-download DRM, not regular streaming
    playback.
  - Dev-signed builds (the default, no castLabs EVS subscription) may cap
    playback quality similarly to how Linux browsers already cap Netflix
    at ~720p without hardware-backed Widevine L1 — expected to be a wash
    against the browser-based approach, not a regression, but not yet
    verified against real playback.
  - ~~Original plan: shell out to an installed Chromium-based browser with
    `--app=<url>`, avoid embedding a browser engine at all, accept that
    users need Brave/Chrome/Edge already installed.~~
- Steam Input controller config bundling (dpad → Tab/Arrows, A → Enter,
  B → Escape) so sites are navigable without a mouse/keyboard. This is a
  Steam feature (works on any non-Steam shortcut), not something the app
  renders itself — quality depends on how keyboard-navigable the actual
  site is.
- Wrap the CLI logic in a GTK4/libadwaita UI.
- **SGDB API key distribution** (decision made, not yet implemented):
  the shipped app must have each user supply their own free SGDB key via
  a settings screen (stored locally), not embed the developer's key.
  SGDB's terms expect per-user keys; a key baked into a distributed app
  would get rate-limited across installs and risks revocation, breaking
  the app for everyone. The current `.env` (gitignored, recreated per
  dev machine) is only a stand-in for this until the UI exists.
- Flatpak manifest (x86_64 + aarch64), needs broad filesystem permission
  to reach Steam's userdata dir outside the sandbox.
- Flathub submission.

## Constraints to keep in mind

- Keep it a small utility app: no premature abstractions, no deps beyond
  what's needed, no error handling for cases that can't happen.
- Don't commit `.env` or `assets/` — already gitignored.
