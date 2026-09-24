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

        self.agent_pill = Gtk.Label(label="AGENT")
        add_class(self.agent_pill, "status-pill")
        add_class(self.agent_pill, "bad")
        self.agent_pill.set_valign(Gtk.Align.CENTER)

        self.preset_pill = Gtk.Label(label="—")
        add_class(self.preset_pill, "status-pill")
        self.preset_pill.set_valign(Gtk.Align.CENTER)
        self.preset_pill.set_ellipsize(Pango.EllipsizeMode.END)
        self.preset_pill.set_max_width_chars(22)

        self.settings_btn = icon_button("preferences-system-symbolic", "Open environment settings")
        add_class(self.settings_btn, "tactile")
        self.settings_btn.set_valign(Gtk.Align.CENTER)
        self.settings_btn.set_halign(Gtk.Align.END)
        self.settings_btn.connect("clicked", lambda *_: open_settings())

        end = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        end.set_halign(Gtk.Align.END)
        end.set_valign(Gtk.Align.CENTER)
        end.append(self.agent_pill)
        end.append(self.preset_pill)
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

    def set_agent(self, up: bool) -> None:
        ctx = self.agent_pill.get_style_context()
        ctx.remove_class("ok" if not up else "bad")
        add_class(self.agent_pill, "ok" if up else "bad")

    def set_preset(self, name: str | None) -> None:
        self.preset_pill.set_text(name or "—")
