"""Stub launcher for instrument apps that are not built yet."""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skeletons.gi_init import Gtk

from skeletons.open_settings import open_settings
from skeletons.shell.application import run_app
from skeletons.shell.window import load_css


def _app_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "", name.lower())
    return f"org.skeletons.{slug or 'stub'}"


def run_stub(name: str, accent_note: str = "") -> None:
    holder: dict[str, Gtk.Window] = {}

    def build(gtk_app: Gtk.Application) -> Gtk.Window:
        load_css()
        win = Gtk.ApplicationWindow(application=gtk_app, title=name)
        win.set_default_size(640, 360)
        win.set_name("skeletons")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        box.set_margin_start(40)
        box.set_margin_end(40)
        title = Gtk.Label(label=name.upper())
        title.get_style_context().add_class("app-title")
        body = Gtk.Label(
            label=f"{name} will share skeletons and the same REAPER instance as Guitar.\n"
            "v1 ships this stub so the launcher and ExtState command key already exist.\n\n"
            f"Start Guitar for the working surface. {accent_note}"
        )
        body.set_wrap(True)
        body.set_justify(Gtk.Justification.CENTER)
        settings_btn = Gtk.Button(label="SETTINGS")
        settings_btn.set_tooltip_text("Open the environment folder settings")
        settings_btn.get_style_context().add_class("settings-btn")
        settings_btn.set_halign(Gtk.Align.CENTER)
        settings_btn.connect("clicked", lambda *_: open_settings())
        box.append(title)
        box.append(body)
        box.append(settings_btn)
        win.set_child(box)
        holder["win"] = win
        return win

    raise SystemExit(run_app(_app_id(name), build))
