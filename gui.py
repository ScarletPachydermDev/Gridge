#!/usr/bin/env python3
"""Minimal GTK4/libadwaita UI: type an app name + URL, pick the right
SteamGridDB match, create the Steam shortcut. Styled like
github.com/unrud/video-downloader -- single window, no bells and
whistles.
"""
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

import create_webapp as cw  # noqa: E402
import config  # noqa: E402
import edge_launcher  # noqa: E402
import sgdb_client as sgdb  # noqa: E402
import steam_paths  # noqa: E402


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

        self.name_entry = Adw.EntryRow(title="App name (e.g. Netflix)")
        self.url_entry = Adw.EntryRow(title="URL (e.g. https://netflix.com)")
        entries_group = Adw.PreferencesGroup()
        entries_group.add(self.name_entry)
        entries_group.add(self.url_entry)
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
        name = self.name_entry.get_text().strip()
        if not name:
            self.status_label.set_label("Enter an app name first.")
            return

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
        if not win:
            win = MainWindow(self)
        win.present()


def main():
    Application().run()


if __name__ == "__main__":
    main()
