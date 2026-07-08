# Gridge

Type a URL or the name of a streaming/cloud-gaming service, and Gridge finds matching artwork on [SteamGridDB](https://www.steamgriddb.com/) and creates a non-Steam shortcut for it -- so it shows up as a native-looking tile in Steam's Game Mode, launching borderless in a kiosk browser window instead of a regular tab. Built with Steam hardware in mind.

## Requirements
1. Steam installed, either native OS package or Flatpak
2. Microsoft Edge
3. SteamGridDB API key 

## What it does

1. Type a URL (`netflix.com`) or a recognized service name (`Netflix`, `Disney+`, `GeForce NOW`, ...) into the URL bar.
2. Gridge searches SteamGridDB for matching artwork and shows a picker: Vertical Grid, Horizontal Grid, Hero, Logo, and Icon, each with several candidates to choose from (or just go with the defaults).
3. Click Create Steam Shortcut. Restart Steam, and the new shortcut appears in your library, ready to launch straight into the site in a clean, chromeless window.

A shortcut can be created even for services that don't have SteamGridDB artwork at all, and even for services not on Gridge's built-in name list (just type the full URL instead).

## Why Microsoft Edge

Every shortcut Gridge creates launches through Microsoft Edge, not a regular system browser or a bundled Electron window. That's a deliberate choice, not a default: **Edge is the only browser on Linux licensed to decode Dolby Digital Plus and Dolby Atmos audio.** Google never licensed those codecs into open-source Chromium, so every other Chromium-based browser (Chrome, Brave, Vivaldi, or a bundled Electron build) inherits the same gap.

This isn't a hypothetical edge case -- plenty of mainstream streaming catalogs use Dolby Atmos/Plus tracks by default for supported titles (a large chunk of Disney+'s Marvel/Star Wars library, for instance). When a browser without codec support hits one of these tracks, it typically doesn't show an error at all: video keeps playing, but the audio silently fails or drops out, which is a much worse experience than a browser refusing to load the page. Edge is the one browser that avoids this entirely, so it's the only one Gridge shells out to.

Edge shares one profile across every shortcut Gridge creates, so logins and saved sessions from one streaming service carry over to the others automatically -- you only sign in once per service, not once per shortcut.

## Status

Gridge is early (v1.0.0). It's been tested on a Steam Deck (native Steam) and a regular Linux desktop (Flatpak Steam), both with Gridge itself packaged as a Flatpak.

## Building from source

Gridge ships as a Flatpak. To build it yourself:

```
flatpak install --user flathub org.gnome.Sdk//50 org.gnome.Platform//50 org.flatpak.Builder
git clone https://github.com/Scarlet-Pachyderm/Gridge.git
cd Gridge
flatpak run org.flatpak.Builder --user --install --force-clean build-dir packaging/io.github.ScarletPachyderm.Gridge.json
flatpak run io.github.ScarletPachyderm.Gridge
```

## Issues

Found a bug, or a streaming service that doesn't work right? [Open an issue](https://github.com/Scarlet-Pachyderm/Gridge/issues).

## Credits

Built by [Scarlet-Pachyderm](https://github.com/Scarlet-Pachyderm) and Claude Code. Artwork sourced from [SteamGridDB](https://www.steamgriddb.com/).
