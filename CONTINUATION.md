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
- Flatpak targets: **x86_64 and aarch64**.
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

## Stage 2 — next up (the reason for switching to x86)

Real Steam integration, testable now that Steam actually runs:

1. **`shortcuts.vdf` writer** — binary VDF format Steam uses for non-Steam
   games, lives at
   `<userdata>/<steam_user_id>/config/shortcuts.vdf`.
2. **App ID calculation** — Steam derives a shortcut's app ID from a CRC32
   of the exe path + app name; grid asset filenames must use this ID.
3. **Artwork placement** — save the 5 fetched assets into
   `<userdata>/<steam_user_id>/config/grid/` as:
   - `<appid>p.png` — vertical grid (portrait box art)
   - `<appid>.png` — horizontal grid (landscape box art)
   - `<appid>_hero.png` — hero banner
   - `<appid>_logo.png` — logo
   - `<appid>_icon.png` — icon
4. **Steam install path detection** — must handle both native Steam
   (`~/.local/share/Steam` or `~/.steam/steam`) *and* Steam installed as a
   Flatpak itself (`~/.var/app/com.valvesoftware.Steam/.local/share/Steam`),
   since Bazzite and some CachyOS setups use the latter. Not yet
   implemented — this is the main portability risk across distros.
5. Steam needs a restart (or Big Picture/Game Mode refresh) to pick up
   new shortcuts — no known way around this.

## Later stages (not started)

- Kiosk-mode browser launch (`chromium --app=<url>` or similar) as the
  shortcut's actual `Exec` target. Prefer Chromium-based browsers —
  Netflix/Disney+ need Widevine DRM, which vanilla Firefox doesn't
  support well. (Dev machine only has Zen/Firefox installed, no
  Chromium — another reason x86 testing matters.)
- Steam Input controller config bundling (dpad → Tab/Arrows, A → Enter,
  B → Escape) so sites are navigable without a mouse/keyboard. This is a
  Steam feature (works on any non-Steam shortcut), not something the app
  renders itself — quality depends on how keyboard-navigable the actual
  site is.
- Wrap the CLI logic in a GTK4/libadwaita UI.
- Flatpak manifest (x86_64 + aarch64), needs broad filesystem permission
  to reach Steam's userdata dir outside the sandbox.
- Flathub submission.

## Constraints to keep in mind

- Keep it a small utility app: no premature abstractions, no deps beyond
  what's needed, no error handling for cases that can't happen.
- Don't commit `.env` or `assets/` — already gitignored.
