from __future__ import annotations

from skeletons.gi_init import Gtk

from skeletons.gtkutil import add_class
from skeletons.widgets.knob import Knob
from skeletons.widgets.meter import Meter


class SideRail(Gtk.Box):
    """Vertical input/output strip: meter + level knob, 88px column."""

    def __init__(self, title: str):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        add_class(self, "side-rail")
        add_class(self, "card")
        self.set_valign(Gtk.Align.FILL)
        self.set_halign(Gtk.Align.CENTER)
        self.set_hexpand(False)
        self.set_size_request(88, -1)
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(8)
        self.set_margin_bottom(8)

        label = Gtk.Label(label=title)
        add_class(label, "rail-title")
        label.set_halign(Gtk.Align.CENTER)
        self.append(label)

        self.meter = Meter(width=16)
        self.meter.set_content_height(168)
        self.meter.set_size_request(16, 168)
        self.meter.set_halign(Gtk.Align.CENTER)
        self.meter.set_vexpand(True)
        self.append(self.meter)

        self.level = Knob("LEVEL", " dB", -24, 12, 0, size=48)
        self.level.set_halign(Gtk.Align.CENTER)
        self.append(self.level)
        self.extra = None
