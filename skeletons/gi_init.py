"""Pin GTK 4 / Gdk 4 before any other gi.repository import."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

__all__ = ["Gdk", "Gio", "GLib", "Gtk", "Pango"]
