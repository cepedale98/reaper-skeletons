"""Settings launcher — folders the environment needs."""

from __future__ import annotations

import os
import sys
from functools import partial

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from skeletons.gi_init import Gio, Gtk

from skeletons.config import (
    FIELDS,
    NETWORK_FIELDS,
    ensure_layout,
    list_rigs,
    list_track_templates,
    load,
    push_to_agent,
    save,
)
from skeletons.shell.application import run_app
from skeletons.shell.window import load_css


class SettingsApp:
    def __init__(self, gtk_app: Gtk.Application):
        load_css()
        self.cfg = load()
        self.win = Gtk.ApplicationWindow(application=gtk_app, title="Skeletons Settings")
        self.win.set_default_size(760, 640)
        self.win.set_name("skeletons")
        self.entries: dict[str, Gtk.Entry] = {}

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        intro = Gtk.Label(
            label="The GTK apps are an interface onto one REAPER instance. "
            "Track groups load as .RTrackTemplate files; each tab then receives "
            "a .RfxChain. Knobs come from the Skeletons Control JSFX you design "
            "and Param-link in REAPER — the apps never host plugins themselves."
        )
        intro.set_wrap(True)
        intro.set_xalign(0)
        box.append(intro)

        box.append(self._section("Folders", FIELDS, browse=True))
        box.append(self._section("REAPER control surface", NETWORK_FIELDS, browse=False))

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        save_btn = Gtk.Button(label="Save")
        save_btn.connect("clicked", self._save)
        push_btn = Gtk.Button(label="Push paths to REAPER")
        push_btn.connect("clicked", self._push)
        row.append(save_btn)
        row.append(push_btn)
        box.append(row)

        self.status = Gtk.Label(label="")
        self.status.set_xalign(0)
        self.status.set_wrap(True)
        box.append(self.status)

        self.summary = Gtk.Label(label="")
        self.summary.set_xalign(0)
        self.summary.set_wrap(True)
        box.append(self.summary)

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(box)
        self.win.set_child(scroll)
        self._refresh_summary()
        ensure_layout(self.cfg)

    def _section(self, title: str, fields, browse: bool) -> Gtk.Frame:
        frame = Gtk.Frame(label=title)
        grid = Gtk.Grid()
        grid.set_column_spacing(8)
        grid.set_row_spacing(8)
        grid.set_margin_top(8)
        grid.set_margin_bottom(8)
        grid.set_margin_start(8)
        grid.set_margin_end(8)
        for i, (key, label, hint) in enumerate(fields):
            lbl = Gtk.Label(label=label)
            lbl.set_xalign(0)
            entry = Gtk.Entry()
            entry.set_text(str(self.cfg.get(key, "")))
            entry.set_hexpand(True)
            entry.set_tooltip_text(hint)
            grid.attach(lbl, 0, i * 2, 3, 1)
            grid.attach(entry, 0, i * 2 + 1, 2 if browse else 3, 1)
            if browse:
                btn = Gtk.Button(label="Browse")
                btn.connect("clicked", self._browse, key)
                grid.attach(btn, 2, i * 2 + 1, 1, 1)
            self.entries[key] = entry
        frame.set_child(grid)
        return frame

    def _collect(self) -> dict:
        data = dict(self.cfg)
        for k, e in self.entries.items():
            text = e.get_text().strip()
            if k.endswith("_port"):
                try:
                    data[k] = int(text)
                except ValueError:
                    data[k] = text
            else:
                data[k] = text
        return data

    def _browse(self, _btn, key: str) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title("Choose folder")
        current = self.entries[key].get_text()
        if current and os.path.isdir(current):
            dialog.set_initial_folder(Gio.File.new_for_path(current))
        dialog.select_folder(self.win, None, partial(self._on_folder, key=key))

    def _on_folder(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, key: str) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except Exception:
            return
        path = folder.get_path() if folder is not None else None
        if path:
            self.entries[key].set_text(path)

    def _save(self, _btn) -> None:
        data = self._collect()
        save(data)
        ensure_layout(data)
        self.cfg = data
        self._refresh_summary()
        err = push_to_agent(data)
        if err:
            self.status.set_text(f"Saved to ~/.config/Skeletons/config.json — REAPER not reached ({err})")
        else:
            self.status.set_text("Saved and pushed folder paths to the running REAPER agent.")

    def _push(self, _btn) -> None:
        data = self._collect()
        err = push_to_agent(data)
        if err:
            self.status.set_text(err)
        else:
            self.status.set_text("Folder paths published to ExtState (Skeletons).")

    def _refresh_summary(self) -> None:
        data = self._collect()
        lines = []
        for key, title, _hint in FIELDS:
            path = data.get(key, "")
            mark = "ok" if path and os.path.exists(str(path)) else "missing"
            lines.append(f"{title}: {path}  [{mark}]")
        rigs = list_rigs("guitar", data)
        templates = list_track_templates(data)
        lines.append(f"Guitar rigs: {', '.join(rigs) or '(none yet)'}")
        lines.append(f"Track templates: {len(templates)} .RTrackTemplate file(s)")
        self.summary.set_text("\n".join(lines))


def main() -> None:
    holder: dict[str, SettingsApp] = {}

    def build(gtk_app: Gtk.Application) -> Gtk.Window:
        holder["app"] = SettingsApp(gtk_app)
        return holder["app"].win

    raise SystemExit(run_app("org.skeletons.settings", build))


if __name__ == "__main__":
    main()
