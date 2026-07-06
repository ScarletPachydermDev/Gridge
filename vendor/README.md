Vendored third-party code, committed as plain source (not a git submodule)
because the Steam Deck's host OS has no `pip` available for
`sync_gamescope_resolution.py` to depend on at runtime.

- `Xlib/` — [python-xlib](https://github.com/python-xlib/python-xlib) 0.33,
  pure Python, LGPL 2.1 (see `Xlib-LICENSE`). Downloaded as a wheel and
  extracted as-is, unmodified.
- `six.py` — [six](https://github.com/benjaminp/six) 1.17.0, MIT (see
  `six-LICENSE`). python-xlib's own Python 2/3 compat dependency.
