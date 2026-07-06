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
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

import create_webapp as cw  # noqa: E402
import config  # noqa: E402
import edge_launcher  # noqa: E402
import sgdb_client as sgdb  # noqa: E402
import steam_paths  # noqa: E402
import steam_restart  # noqa: E402

SGDB_KEY_URL = "https://steamgriddb.com/profile/preferences/api"
DONATE_URL = "https://example.com/donate"  # TODO: replace with the real donate link

# Only a close button -- no minimize/maximize -- on every window in the app.
NO_MINMAX_DECORATION_LAYOUT = ":close"


def guess_name_from_url(url):
    if "://" not in url:
        url = f"https://{url}"
    host = urlparse(url).netloc
    host = host.removeprefix("www.")
    base = host.split(".")[0]
    return base.replace("-", " ").title()


class OnboardingWindow(Adw.ApplicationWindow):
    """First-run setup: Steam installed, Edge installed, SGDB key set.
    Once all three pass, saves onboarding_complete and hands off to
    on_complete() to open the main window."""

    def __init__(self, app, on_complete):
        super().__init__(application=app, title="Set Up Steam Webapp Creator")
        self.set_default_size(480, -1)
        self.on_complete = on_complete
        self.edge_ok = False
        self.sgdb_ok = False
        self._key_debounce_id = None

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_decoration_layout(NO_MINMAX_DECORATION_LAYOUT)
        toolbar.add_top_bar(header)

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
        self.steam_status = Gtk.Image(icon_name="dialog-warning-symbolic")
        self.steam_row.add_suffix(self.steam_status)
        group.add(self.steam_row)

        self.edge_row = Adw.ActionRow(title="Microsoft Edge")
        self.edge_status = Gtk.Image(icon_name="dialog-warning-symbolic")
        self.edge_install_button = Gtk.Button(label="Install Microsoft Edge (Flatpak)", valign=Gtk.Align.CENTER)
        self.edge_install_button.connect("clicked", self._on_install_edge)
        self.edge_row.add_suffix(self.edge_status)
        self.edge_row.add_suffix(self.edge_install_button)
        group.add(self.edge_row)

        self.key_row = Adw.PasswordEntryRow(title="SteamGridDB API key")
        self.sgdb_status = Gtk.Image(icon_name="dialog-warning-symbolic")
        self.key_row.add_suffix(self.sgdb_status)
        self.key_row.connect("changed", self._on_key_changed)
        self.key_row.connect("entry-activated", self._on_key_activated)
        group.add(self.key_row)

        content.append(group)

        link = Gtk.LinkButton(uri=SGDB_KEY_URL, label="Get a free key at steamgriddb.com", halign=Gtk.Align.START)
        content.append(link)

        self.status_label = Gtk.Label(wrap=True)
        content.append(self.status_label)

        self.continue_button = Gtk.Button(
            label="Continue", css_classes=["suggested-action", "pill"], halign=Gtk.Align.CENTER, sensitive=False
        )
        self.continue_button.connect("clicked", self._on_continue)
        content.append(self.continue_button)

        scrolled = Gtk.ScrolledWindow(
            child=content, vexpand=True, propagate_natural_height=True, propagate_natural_width=True
        )
        toolbar.set_content(scrolled)
        self.set_content(toolbar)

        self._check_steam()
        self._check_edge()
        if config.get_sgdb_api_key():
            self.key_row.set_text(config.get_sgdb_api_key())
            self._check_key()

    def _set_status(self, image, ok):
        image.set_from_icon_name("emblem-ok-symbolic" if ok else "dialog-warning-symbolic")
        image.remove_css_class("success")
        if ok:
            image.add_css_class("success")

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
        # A system-wide `flatpak install` needs polkit authorization that
        # regular user accounts often don't have -- confirmed failing
        # outright, no auth prompt, on both a Fedora desktop and a real
        # Steam Deck (SteamOS blocks system-scope changes while its
        # read-only OS protection is enabled, which it is by default).
        # Opening the system software center hits the exact same wall,
        # since it goes through the same system D-Bus service either way.
        # A --user install sidesteps all of this entirely (confirmed
        # working on a real Deck) -- just needs a user-level flathub
        # remote to exist first, since most systems only have it
        # registered system-wide by default.
        self.edge_install_button.set_sensitive(False)
        self.status_label.set_label("Installing Microsoft Edge...")

        def work():
            subprocess.run(
                ["flatpak", "remote-add", "--user", "--if-not-exists", "flathub",
                 "https://flathub.org/repo/flathub.flatpakrepo"],
                capture_output=True,
            )
            result = subprocess.run(
                ["flatpak", "install", "--user", "-y", "flathub", "com.microsoft.Edge"],
                capture_output=True,
                text=True,
            )
            GLib.idle_add(self._install_edge_done, result.returncode == 0, result.stderr)

        threading.Thread(target=work, daemon=True).start()

    def _install_edge_done(self, ok, error_output):
        self.edge_install_button.set_sensitive(True)
        if ok:
            self.status_label.set_label("")
            self._check_edge()
        else:
            self.status_label.set_label(f"Install failed: {error_output.strip()}")

    def _on_key_changed(self, _entry):
        if self._key_debounce_id:
            GLib.source_remove(self._key_debounce_id)
        self._key_debounce_id = GLib.timeout_add(600, self._debounced_check_key)

    def _on_key_activated(self, *_args):
        if self._key_debounce_id:
            GLib.source_remove(self._key_debounce_id)
            self._key_debounce_id = None
        self._check_key()

    def _debounced_check_key(self):
        self._key_debounce_id = None
        self._check_key()
        return False

    def _check_key(self):
        key = self.key_row.get_text().strip()
        if not key:
            self.sgdb_ok = False
            self._set_status(self.sgdb_status, False)
            self.status_label.set_label("")
            self._update_continue_button()
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
        self.set_default_size(480, -1)

        self.match = None
        self._search_debounce_id = None
        self.pending_shortcuts_count = 0

        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.set_decoration_layout(NO_MINMAX_DECORATION_LAYOUT)

        donate_action = Gio.SimpleAction.new("donate", None)
        donate_action.connect("activate", self._on_donate)
        self.add_action(donate_action)

        preferences_action = Gio.SimpleAction.new("preferences", None)
        preferences_action.connect("activate", self._on_preferences)
        self.add_action(preferences_action)

        menu = Gio.Menu()
        menu.append("Donate", "win.donate")
        menu.append("Preferences", "win.preferences")
        menu_button = Gtk.MenuButton(icon_name="emblem-system-symbolic", tooltip_text="Menu", menu_model=menu)
        header.pack_end(menu_button)
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
        self.url_entry.connect("changed", self._on_url_changed)
        self.url_entry.connect("entry-activated", self._on_url_activated)
        clear_button = Gtk.Button(icon_name="edit-clear-symbolic", tooltip_text="Clear", valign=Gtk.Align.CENTER)
        clear_button.add_css_class("flat")
        clear_button.connect("clicked", self._on_clear_url)
        self.url_entry.add_suffix(clear_button)
        entries_group = Adw.PreferencesGroup()
        entries_group.add(self.url_entry)
        content.append(entries_group)

        self.results_group = Adw.PreferencesGroup(title="Matches", visible=False)
        self.results_list = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.SINGLE)
        self.results_list.connect("row-selected", self._on_row_selected)
        self.results_group.add(self.results_list)
        content.append(self.results_group)

        buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.CENTER)
        self.create_button = Gtk.Button(
            label="Create Steam Shortcut", css_classes=["suggested-action"], sensitive=False
        )
        self.create_button.connect("clicked", self._on_create)
        buttons_box.append(self.create_button)

        self.restart_steam_button = Gtk.Button(label="Restart Steam")
        self.restart_steam_button.connect("clicked", self._on_restart_steam)
        buttons_box.append(self.restart_steam_button)
        content.append(buttons_box)

        self.spinner = Gtk.Spinner()
        content.append(self.spinner)

        self.status_label = Gtk.Label(wrap=True)
        content.append(self.status_label)

        self.pending_label = Gtk.Label(wrap=True, css_classes=["dim-label"])
        content.append(self.pending_label)

        scrolled = Gtk.ScrolledWindow(
            child=content, vexpand=True, propagate_natural_height=True, propagate_natural_width=True
        )
        toolbar.set_content(scrolled)
        self.set_content(toolbar)

    def _on_donate(self, _action, _param):
        Gtk.show_uri(self, DONATE_URL, 0)

    def _on_preferences(self, _action, _param):
        OnboardingWindow(self.get_application(), on_complete=lambda: None).present()

    def _set_busy(self, busy, message=""):
        self.spinner.set_spinning(busy)
        self.create_button.set_sensitive(not busy and self.match is not None)
        self.status_label.set_label(message)

    def _clear_results(self):
        row = self.results_list.get_row_at_index(0)
        while row:
            self.results_list.remove(row)
            row = self.results_list.get_row_at_index(0)
        self.results_group.set_visible(False)

    def _on_url_changed(self, _entry):
        if self._search_debounce_id:
            GLib.source_remove(self._search_debounce_id)
        self._search_debounce_id = GLib.timeout_add(600, self._debounced_search)

    def _on_url_activated(self, *_args):
        if self._search_debounce_id:
            GLib.source_remove(self._search_debounce_id)
            self._search_debounce_id = None
        self._do_search()

    def _debounced_search(self):
        self._search_debounce_id = None
        self._do_search()
        return False

    def _do_search(self):
        url = self.url_entry.get_text().strip()
        self.match = None
        self.create_button.set_sensitive(False)
        self._clear_results()

        if not url:
            self._set_busy(False, "")
            return

        name = guess_name_from_url(url)
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
            m["name"] = cw.clean_shortcut_name(m["name"])
            row = Adw.ActionRow(title=m["name"])
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
        self._set_busy(False, f"Created '{name}' (appid {appid}).")
        self.pending_shortcuts_count += 1
        self._update_pending_label()

    def _create_failed(self, message):
        self._set_busy(False, f"Error: {message}")

    def _update_pending_label(self):
        n = self.pending_shortcuts_count
        if n == 0:
            self.pending_label.set_label("")
        else:
            self.pending_label.set_label(f"{n} shortcut{'s' if n != 1 else ''} to be added after Steam restart")

    def _on_clear_url(self, _button):
        self.url_entry.set_text("")
        if self._search_debounce_id:
            GLib.source_remove(self._search_debounce_id)
            self._search_debounce_id = None
        self.match = None
        self.create_button.set_sensitive(False)
        self._clear_results()
        self._set_busy(False, "")

    def _on_restart_steam(self, _button):
        self.restart_steam_button.set_sensitive(False)
        self.status_label.set_label("Restarting Steam...")

        def work():
            steam_restart.restart_steam()
            GLib.idle_add(self._restart_steam_done)

        threading.Thread(target=work, daemon=True).start()

    def _restart_steam_done(self):
        self.restart_steam_button.set_sensitive(True)
        self.status_label.set_label("")
        self.pending_shortcuts_count = 0
        self._update_pending_label()


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
