#!/usr/bin/env python3
"""Minimal GTK4/libadwaita UI: type a URL, pick the right SteamGridDB
match, create the Steam shortcut. Styled like
github.com/unrud/video-downloader -- single window, no bells and
whistles. First run shows a 3-step onboarding check (Steam, Edge,
SGDB key) before the main window.
"""
import subprocess
import threading
from urllib.parse import urlparse

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

import create_webapp as cw  # noqa: E402
import config  # noqa: E402
import edge_launcher  # noqa: E402
import sgdb_client as sgdb  # noqa: E402
import steam_paths  # noqa: E402

SGDB_KEY_URL = "https://steamgriddb.com/profile/preferences/api"


def guess_name_from_url(url):
    if "://" not in url:
        url = f"https://{url}"
    host = urlparse(url).netloc
    host = host.removeprefix("www.")
    base = host.split(".")[0]
    return base.replace("-", " ").title()


class SettingsDialog(Adw.Window):
    def __init__(self, parent):
        super().__init__(transient_for=parent, modal=True, title="Settings", default_width=420, default_height=220)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())

        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(
            title="SteamGridDB",
            description="Get a free key at steamgriddb.com/profile/preferences/api",
        )
        self.key_row = Adw.PasswordEntryRow(title="API key")
        existing = config.get_sgdb_api_key()
        if existing:
            self.key_row.set_text(existing)
        self.key_row.connect("entry-activated", self._on_save)
        group.add(self.key_row)

        save_button = Gtk.Button(label="Save", css_classes=["suggested-action"], halign=Gtk.Align.END)
        save_button.connect("clicked", self._on_save)
        group.add(save_button)

        page.add(group)
        toolbar.set_content(page)
        self.set_content(toolbar)

    def _on_save(self, *_args):
        config.set_sgdb_api_key(self.key_row.get_text().strip())
        self.close()


class OnboardingWindow(Adw.ApplicationWindow):
    """First-run setup: Steam installed, Edge installed, SGDB key set.
    Once all three pass, saves onboarding_complete and hands off to
    on_complete() to open the main window."""

    def __init__(self, app, on_complete):
        super().__init__(application=app, title="Set Up Steam Webapp Creator")
        self.set_default_size(480, 480)
        self.on_complete = on_complete
        self.edge_ok = False
        self.sgdb_ok = False

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=24,
            margin_bottom=24,
            margin_start=24,
            margin_end=24,
        )

        group = Adw.PreferencesGroup(title="Requirements")

        self.steam_row = Adw.ActionRow(title="Steam")
        self.steam_status = Gtk.Image(icon_name="dialog-question-symbolic")
        self.steam_row.add_suffix(self.steam_status)
        group.add(self.steam_row)

        self.edge_row = Adw.ActionRow(title="Microsoft Edge")
        self.edge_status = Gtk.Image(icon_name="dialog-question-symbolic")
        self.edge_install_button = Gtk.Button(label="Open Software Center to Install", valign=Gtk.Align.CENTER)
        self.edge_install_button.connect("clicked", self._on_install_edge)
        self.edge_row.add_suffix(self.edge_status)
        self.edge_row.add_suffix(self.edge_install_button)
        group.add(self.edge_row)

        content.append(group)

        key_group = Adw.PreferencesGroup(title="SteamGridDB API key")
        self.key_row = Adw.PasswordEntryRow(title="API key")
        self.key_row.connect("entry-activated", self._on_save_key)
        key_group.add(self.key_row)

        link = Gtk.LinkButton(uri=SGDB_KEY_URL, label="Get a free key at steamgriddb.com", halign=Gtk.Align.START)
        key_group.add(link)

        save_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.END)
        self.sgdb_status = Gtk.Image(icon_name="dialog-question-symbolic")
        save_button = Gtk.Button(label="Save", css_classes=["suggested-action"])
        save_button.connect("clicked", self._on_save_key)
        save_row.append(self.sgdb_status)
        save_row.append(save_button)
        key_group.add(save_row)

        content.append(key_group)

        self.status_label = Gtk.Label(wrap=True)
        content.append(self.status_label)

        self.continue_button = Gtk.Button(
            label="Continue", css_classes=["suggested-action", "pill"], halign=Gtk.Align.CENTER, sensitive=False
        )
        self.continue_button.connect("clicked", self._on_continue)
        content.append(self.continue_button)

        toolbar.set_content(Gtk.ScrolledWindow(child=content, vexpand=True))
        self.set_content(toolbar)

        self._check_steam()
        self._check_edge()
        if config.get_sgdb_api_key():
            self.key_row.set_text(config.get_sgdb_api_key())
            self._on_save_key()

    def _set_status(self, image, ok):
        image.set_from_icon_name("emblem-ok-symbolic" if ok else "dialog-warning-symbolic")

    def _update_continue_button(self):
        self.continue_button.set_sensitive(self.steam_ok and self.edge_ok and self.sgdb_ok)

    def _check_steam(self):
        try:
            root = steam_paths.find_steam_root()
            self.steam_ok = True
            self.steam_row.set_subtitle(root)
        except steam_paths.SteamNotFoundError as e:
            self.steam_ok = False
            self.steam_row.set_subtitle(str(e))
        self._set_status(self.steam_status, self.steam_ok)
        self._update_continue_button()

    def _check_edge(self):
        try:
            exe, _ = edge_launcher.find_edge()
            self.edge_ok = True
            self.edge_row.set_subtitle(exe)
            self.edge_install_button.set_visible(False)
        except edge_launcher.EdgeNotFoundError:
            self.edge_ok = False
            self.edge_row.set_subtitle("Not installed")
            self.edge_install_button.set_visible(True)
        self._set_status(self.edge_status, self.edge_ok)
        self._update_continue_button()

    def _on_install_edge(self, _button):
        # A direct `flatpak install` needs polkit authorization for a
        # system-wide deploy, which regular user accounts often don't have
        # (confirmed failing outright, no auth prompt, on both a Fedora
        # desktop and a real Steam Deck). Opening the system's own software
        # center instead goes through a path that's already properly
        # authorized, and works the same everywhere via the appstream: URI
        # scheme most software centers (Discover, GNOME Software) register.
        try:
            subprocess.Popen(["xdg-open", "appstream://com.microsoft.Edge"])
        except FileNotFoundError:
            self.status_label.set_label("Couldn't open a software center -- install Microsoft Edge manually.")
            return

        self.status_label.set_label("Waiting for Microsoft Edge to be installed...")
        GLib.timeout_add_seconds(3, self._poll_edge_installed)

    def _poll_edge_installed(self):
        self._check_edge()
        if self.edge_ok:
            self.status_label.set_label("")
            return False
        return True

    def _on_save_key(self, *_args):
        key = self.key_row.get_text().strip()
        if not key:
            self.status_label.set_label("Enter an API key first.")
            return
        self.status_label.set_label("Checking key...")

        def work():
            try:
                config.set_sgdb_api_key(key)
                sgdb.search("test")
            except sgdb.SGDBError as e:
                GLib.idle_add(self._key_check_failed, str(e))
                return
            GLib.idle_add(self._key_check_done)

        threading.Thread(target=work, daemon=True).start()

    def _key_check_done(self):
        self.sgdb_ok = True
        self._set_status(self.sgdb_status, True)
        self.status_label.set_label("")
        self._update_continue_button()

    def _key_check_failed(self, message):
        self.sgdb_ok = False
        self._set_status(self.sgdb_status, False)
        self.status_label.set_label(f"Error: {message}")
        self._update_continue_button()

    def _on_continue(self, _button):
        config.set_onboarding_complete()
        self.close()
        self.on_complete()


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Steam Webapp Creator")
        self.set_default_size(480, 560)

        self.match = None

        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        settings_button = Gtk.Button(icon_name="emblem-system-symbolic", tooltip_text="Settings")
        settings_button.connect("clicked", self._open_settings)
        header.pack_end(settings_button)
        toolbar.add_top_bar(header)

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=24,
            margin_bottom=24,
            margin_start=24,
            margin_end=24,
        )

        self.url_entry = Adw.EntryRow(title="URL (e.g. https://netflix.com)")
        self.name_entry = Adw.EntryRow(title="Search term (auto-filled from URL, editable)")
        entries_group = Adw.PreferencesGroup()
        entries_group.add(self.url_entry)
        entries_group.add(self.name_entry)
        content.append(entries_group)

        self.search_button = Gtk.Button(label="Find Artwork", css_classes=["suggested-action"], halign=Gtk.Align.CENTER)
        self.search_button.connect("clicked", self._on_search)
        content.append(self.search_button)

        self.results_group = Adw.PreferencesGroup(title="Matches", visible=False)
        self.results_list = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.SINGLE)
        self.results_list.connect("row-selected", self._on_row_selected)
        self.results_group.add(self.results_list)
        content.append(self.results_group)

        self.create_button = Gtk.Button(
            label="Create Steam Shortcut", css_classes=["suggested-action"], halign=Gtk.Align.CENTER, sensitive=False
        )
        self.create_button.connect("clicked", self._on_create)
        content.append(self.create_button)

        self.spinner = Gtk.Spinner()
        content.append(self.spinner)

        self.status_label = Gtk.Label(wrap=True)
        content.append(self.status_label)

        scrolled = Gtk.ScrolledWindow(child=content, vexpand=True)
        toolbar.set_content(scrolled)
        self.set_content(toolbar)

    def _open_settings(self, _button):
        SettingsDialog(self).present()

    def _set_busy(self, busy, message=""):
        self.spinner.set_spinning(busy)
        self.search_button.set_sensitive(not busy)
        self.create_button.set_sensitive(not busy and self.match is not None)
        self.status_label.set_label(message)

    def _clear_results(self):
        row = self.results_list.get_row_at_index(0)
        while row:
            self.results_list.remove(row)
            row = self.results_list.get_row_at_index(0)
        self.results_group.set_visible(False)

    def _on_search(self, _button):
        url = self.url_entry.get_text().strip()
        if not url:
            self.status_label.set_label("Enter a URL first.")
            return

        name = self.name_entry.get_text().strip()
        if not name:
            name = guess_name_from_url(url)
            self.name_entry.set_text(name)

        self.match = None
        self.create_button.set_sensitive(False)
        self._clear_results()
        self._set_busy(True, "Searching SteamGridDB...")

        def work():
            try:
                matches = sgdb.search(name)
            except Exception as e:
                GLib.idle_add(self._search_failed, str(e))
                return
            GLib.idle_add(self._search_done, matches)

        threading.Thread(target=work, daemon=True).start()

    def _search_failed(self, message):
        self._set_busy(False, f"Error: {message}")

    def _search_done(self, matches):
        self._set_busy(False, "" if matches else "No matches found.")
        if not matches:
            return
        for m in matches:
            row = Adw.ActionRow(title=m["name"], subtitle="Verified" if m["verified"] else "")
            row.match_data = m
            self.results_list.append(row)
        self.results_group.set_visible(True)
        self.results_list.select_row(self.results_list.get_row_at_index(0))

    def _on_row_selected(self, _listbox, row):
        self.match = row.match_data if row else None
        self.create_button.set_sensitive(self.match is not None)

    def _on_create(self, _button):
        if not self.match:
            return
        url = self.url_entry.get_text().strip()
        if not url:
            self.status_label.set_label("Enter a URL first.")
            return

        match = self.match
        self._set_busy(True, f"Fetching assets for {match['name']}...")

        def work():
            try:
                slug = cw.slugify(match["name"])
                paths = cw.fetch_assets(match["id"], slug)
                appid = cw.register_steam_shortcut(match["name"], url, paths)
                GLib.idle_add(self._create_done, match["name"], appid)
            except (steam_paths.SteamNotFoundError, edge_launcher.EdgeNotFoundError, sgdb.SGDBError) as e:
                GLib.idle_add(self._create_failed, str(e))
            except Exception as e:
                GLib.idle_add(self._create_failed, str(e))

        threading.Thread(target=work, daemon=True).start()

    def _create_done(self, name, appid):
        self._set_busy(False, f"Created '{name}' (appid {appid}). Restart Steam to see it.")

    def _create_failed(self, message):
        self._set_busy(False, f"Error: {message}")


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.ScarletPachyderm.SteamWebappCreator")

    def do_activate(self):
        win = self.props.active_window
        if win:
            win.present()
            return

        if config.is_onboarding_complete():
            MainWindow(self).present()
        else:
            OnboardingWindow(self, on_complete=lambda: MainWindow(self).present()).present()


def main():
    Application().run()


if __name__ == "__main__":
    main()
