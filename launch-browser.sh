#!/bin/sh
# Steam sets LD_PRELOAD for its overlay in every child process it launches,
# regardless of the shortcut's AllowOverlay setting (confirmed via
# coredumpctl during kiosk-launcher testing: it crashed a bundled Electron
# build hard). Stripping it here before exec'ing the real browser avoids
# that class of crash for any browser we shell out to.
unset LD_PRELOAD
exec "$@"
