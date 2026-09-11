from __future__ import annotations

from skeletons.gi_init import Gtk, Pango

from skeletons.gtkutil import add_class, icon_button
from skeletons.open_settings import open_settings


class StatusBar(Gtk.CenterBox):
    """40px top bar: centered title + REAPER status, settings on the end."""

    def __init__(self, title: str = "Guitar"):
        super().__init__()
        add_class(self, "section-status")
        self.set_hexpand(True)

        cluster = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        cluster.set_halign(Gtk.Align.CENTER)
        cluster.set_valign(Gtk.Align.CENTER)

        self.title = Gtk.Label(label=title.upper())
        add_class(self.title, "app-title")
        self.title.set_halign(Gtk.Align.CENTER)

        self.status = Gtk.Label(label="REAPER: …")
        add_class(self.status, "status-label")
        self.status.set_halign(Gtk.Align.CENTER)

        self.warning = Gtk.Label(label="")
        add_class(self.warning, "hint")
        self.warning.set_halign(Gtk.Align.CENTER)
        self.warning.set_ellipsize(Pango.EllipsizeMode.END)
        self.warning.set_visible(False)

        self.address = Gtk.Label(label="")
        add_class(self.address, "address-line")
        self.address.set_halign(Gtk.Align.CENTER)
        self.address.set_ellipsize(Pango.EllipsizeMode.END)
        self.address.set_visible(False)

        cluster.append(self.title)
        cluster.append(self.status)
        cluster.append(self.warning)
        cluster.append(self.address)

        self.settings_btn = icon_button("preferences-system-symbolic", "Open environment settings")
        add_class(self.settings_btn, "tactile")
        self.settings_btn.set_valign(Gtk.Align.CENTER)
        self.settings_btn.set_halign(Gtk.Align.END)
        self.settings_btn.connect("clicked", lambda *_: open_settings())

        end = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        end.set_halign(Gtk.Align.END)
        end.set_valign(Gtk.Align.CENTER)
        end.append(self.settings_btn)

        self.set_center_widget(cluster)
        self.set_end_widget(end)

    def set_status(self, text: str, ok: bool) -> None:
        self.status.set_text(text)
        ctx = self.status.get_style_context()
        ctx.remove_class("ok" if not ok else "bad")
        add_class(self.status, "ok" if ok else "bad")

    def set_warning(self, text: str | None) -> None:
        if text:
            self.warning.set_text(text)
            self.warning.set_visible(True)
        else:
            self.warning.set_text("")
            self.warning.set_visible(False)

    def set_address(self, text: str) -> None:
        self.address.set_text(text or "")
