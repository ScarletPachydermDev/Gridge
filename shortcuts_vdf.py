"""Read/write Steam's binary shortcuts.vdf (non-Steam game shortcuts).

Binary VDF is a flat type-tagged tree: each entry is a type byte, a
null-terminated key, then a value (nested map / null-terminated string /
little-endian int32) depending on the type byte. A map is closed by 0x08.
"""
import os
import shutil
import zlib

TYPE_MAP = 0x00
TYPE_STRING = 0x01
TYPE_INT32 = 0x02
TYPE_MAP_END = 0x08


def generate_appid(exe, appname):
    """Steam's non-Steam-shortcut app ID: CRC32 of the quoted exe path
    concatenated with the app name, with the top bit forced on. This same
    value is both the vdf entry's 'appid' field and the number grid asset
    filenames are keyed on (<appid>p.png, <appid>_hero.png, ...)."""
    quoted_exe = exe if exe.startswith('"') else f'"{exe}"'
    key = (quoted_exe + appname).encode("utf-8")
    return zlib.crc32(key) | 0x80000000


def _read_cstring(data, i):
    end = data.index(b"\x00", i)
    return data[i:end].decode("utf-8", errors="replace"), end + 1


def _parse_map(data, i):
    result = {}
    n = len(data)
    while i < n:
        type_byte = data[i]
        i += 1
        if type_byte == TYPE_MAP_END:
            return result, i
        key, i = _read_cstring(data, i)
        if type_byte == TYPE_MAP:
            value, i = _parse_map(data, i)
        elif type_byte == TYPE_STRING:
            value, i = _read_cstring(data, i)
        elif type_byte == TYPE_INT32:
            value = int.from_bytes(data[i : i + 4], "little")
            i += 4
        else:
            raise ValueError(f"Unknown VDF type byte {type_byte:#x} at offset {i - 1}")
        result[key] = value
    return result, i


def parse(data):
    root, _ = _parse_map(data, 0)
    return root


def _write_cstring(s):
    return s.encode("utf-8") + b"\x00"


def serialize(obj):
    out = bytearray()
    for key, value in obj.items():
        if isinstance(value, dict):
            out += bytes([TYPE_MAP]) + _write_cstring(key) + serialize(value) + bytes([TYPE_MAP_END])
        elif isinstance(value, int):
            out += bytes([TYPE_INT32]) + _write_cstring(key) + value.to_bytes(4, "little")
        else:
            out += bytes([TYPE_STRING]) + _write_cstring(key) + _write_cstring(str(value))
    return bytes(out)


def load(path):
    if not os.path.exists(path):
        return {"shortcuts": {}}
    with open(path, "rb") as f:
        return parse(f.read())


def save(path, root):
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")
    data = serialize(root) + bytes([TYPE_MAP_END])
    with open(path, "wb") as f:
        f.write(data)


def add_shortcut(vdf_path, *, appname, exe, start_dir, icon, launch_options, tags=None):
    """Add or update (by appname) a non-Steam shortcut entry. Returns the
    generated appid. Backs up any existing shortcuts.vdf to .bak first."""
    root = load(vdf_path)
    shortcuts = root.setdefault("shortcuts", {})

    appid = generate_appid(exe, appname)
    entry = {
        "appid": appid,
        "appname": appname,
        "exe": exe,
        "StartDir": start_dir,
        "icon": icon,
        "ShortcutPath": "",
        "LaunchOptions": launch_options,
        "IsHidden": 0,
        "AllowDesktopConfig": 1,
        "AllowOverlay": 1,
        "OpenVR": 0,
        "Devkit": 0,
        "DevkitGameID": "",
        "DevkitOverrideAppID": 0,
        "LastPlayTime": 0,
        "FlatpakAppID": "",
        "tags": {str(i): t for i, t in enumerate(tags or [])},
    }

    existing_key = next((k for k, v in shortcuts.items() if v.get("appname") == appname), None)
    key = existing_key if existing_key is not None else str(len(shortcuts))
    shortcuts[key] = entry

    save(vdf_path, root)
    return appid
