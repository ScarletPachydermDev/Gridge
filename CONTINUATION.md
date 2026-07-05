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
   `~/.var/app/com.valvesoftware.Steam/.local/share/Steam`. Only tested
   against the Flatpak path so far (dev machine runs Steam as a
   Flatpak); native path is unverified. Multiple userdata user IDs
   aren't auto-resolved — raises and expects `--steam-user`.

**Confirmed end-to-end on real Steam (Flatpak) for Disney+:** shortcut
appeared in Steam's library with full artwork after a full Steam
restart, and clicking the tile launched the URL correctly via
`exe=/usr/bin/xdg-open` (a **host** binary path) with no
`flatpak-spawn --host` wrapper needed — Steam's own Flatpak sandbox
permissions were broad enough to exec it directly. Worth re-checking
on a different Bazzite/CachyOS box before assuming this always holds.

5. Steam needs a full restart (fully quit, not just close the window)
   to pick up new/changed shortcuts — confirmed, no known way around
   this.

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
