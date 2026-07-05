#!/bin/sh
# Steam still sets LD_PRELOAD for its overlay in child processes (zygote,
# GPU, renderer) even with AllowOverlay=0 in shortcuts.vdf -- env vars are
# inherited regardless of that flag. Stripping it here is the reliable fix;
# Electron's multi-process zygote crashes hard when the overlay .so gets
# preloaded into it.
unset LD_PRELOAD
exec "$(dirname "$0")/node_modules/electron/dist/electron" "$@"
