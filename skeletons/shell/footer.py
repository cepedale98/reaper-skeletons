from __future__ import annotations

from skeletons.gi_init import Gtk

from skeletons.gtkutil import add_class, icon_toggle
from skeletons.widgets.tuner import TunerStrip


def _nav_cell(btn: Gtk.ToggleButton, caption: str) -> Gtk.Box:
    cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    add_class(cell, "nav-cell")
    cell.set_halign(Gtk.Align.CENTER)
    cell.set_valign(Gtk.Align.CENTER)
    btn.set_halign(Gtk.Align.CENTER)
    btn.set_valign(Gtk.Align.CENTER)
    label = Gtk.Label(label=caption)
    add_class(label, "nav-label")
    label.set_halign(Gtk.Align.CENTER)
    cell.append(btn)
    cell.append(label)
    return cell


class Footer(Gtk.Box):
    """Centered navbar: TUNER, SCOPE, tuner strip, MODE, INFO."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        add_class(self, "section-footer")
        self.set_hexpand(True)

        cluster = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        cluster.set_halign(Gtk.Align.CENTER)
        cluster.set_valign(Gtk.Align.CENTER)
        add_class(cluster, "nav-cluster")

        self.tuner_btn = icon_toggle("audio-input-microphone-symbolic", "Tuner")
        self.scope_btn = icon_toggle("utilities-system-monitor-symbolic", "Oscilloscope")
        self.mode_btn = icon_toggle("view-grid-symbolic", "Live performance mode")
        self.info_btn = icon_toggle("dialog-information-symbolic", "Info")
        add_class(self.mode_btn, "nav-primary")
        self.mode_btn.set_size_request(56, 56)

        self.tuner_strip = TunerStrip()
        self.tuner_strip.set_valign(Gtk.Align.CENTER)
        self.tuner_strip.set_halign(Gtk.Align.CENTER)

        cluster.append(_nav_cell(self.tuner_btn, "TUNER"))
        cluster.append(_nav_cell(self.scope_btn, "SCOPE"))
        cluster.append(self.tuner_strip)
        cluster.append(_nav_cell(self.mode_btn, "MODE"))
        cluster.append(_nav_cell(self.info_btn, "INFO"))

        lead = Gtk.Box()
        lead.set_hexpand(True)
        trail = Gtk.Box()
        trail.set_hexpand(True)
        self.append(lead)
        self.append(cluster)
        self.append(trail)

        self.info_btn.connect("toggled", self._on_info)
        self._on_address = None

    def _on_info(self, btn: Gtk.ToggleButton) -> None:
        if self._on_address:
            self._on_address(btn.get_active())
