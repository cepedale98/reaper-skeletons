"""Gtk.Application runner shared by every launcher."""

from __future__ import annotations

from collections.abc import Callable

from skeletons.gi_init import Gio, Gtk


def run_app(application_id: str, build: Callable[[Gtk.Application], Gtk.Window]) -> int:
    app = Gtk.Application(
        application_id=application_id,
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )

    def activate(gtk_app: Gtk.Application) -> None:
        win = build(gtk_app)
        gtk_app.add_window(win)
        win.present()

    app.connect("activate", activate)
    return app.run(None)
