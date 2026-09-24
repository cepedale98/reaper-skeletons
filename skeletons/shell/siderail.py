from __future__ import annotations

from skeletons.gi_init import Gtk

from skeletons.gtkutil import add_class
from skeletons.widgets.knob import Knob
from skeletons.widgets.meter import Meter


class SideRail(Gtk.Box):
    """I/O strip: title, then meter with the level knob beside it."""

    def __init__(self, title: str, knob_side: str = "start"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        add_class(self, "side-rail")
        self.set_valign(Gtk.Align.FILL)
        self.set_halign(Gtk.Align.CENTER)
        self.set_hexpand(False)
        self.set_vexpand(True)
        self.set_size_request(96, -1)
        self.set_margin_start(4)
        self.set_margin_end(4)
        self.set_margin_top(4)
        self.set_margin_bottom(2)

        label = Gtk.Label(label=title)
        add_class(label, "rail-title")
        label.set_halign(Gtk.Align.CENTER)
        self.append(label)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_vexpand(True)
        row.set_hexpand(False)
        row.set_halign(Gtk.Align.CENTER)

        self.meter = Meter(width=26)
        self.meter.set_content_height(80)
        self.meter.set_size_request(26, 80)
        self.meter.set_hexpand(False)
        self.meter.set_vexpand(True)
        self.meter.set_valign(Gtk.Align.FILL)
        self.meter.set_halign(Gtk.Align.CENTER)

        self.level = Knob("LEVEL", " dB", -24, 12, 0, size=40)
        self.level.set_halign(Gtk.Align.CENTER)
        self.level.set_valign(Gtk.Align.START)
        self.level.set_vexpand(False)

        if knob_side == "end":
            row.append(self.meter)
            row.append(self.level)
        else:
            row.append(self.level)
            row.append(self.meter)
        self.append(row)
        self.extra = None
