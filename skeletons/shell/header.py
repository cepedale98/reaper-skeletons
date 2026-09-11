from __future__ import annotations

from skeletons.gi_init import Gtk

from skeletons.gtkutil import add_class
from skeletons.widgets.knob import Knob
from skeletons.widgets.meter import Meter


class Header(Gtk.Box):
    def __init__(self, title: str):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_margin_top(8)
        self.set_margin_bottom(8)
        add_class(self, "section-header")

        self.in_meter = Meter()
        self.in_knob = Knob("INPUT", " dB", -24, 12, 0, size=56)
        self.gate_knob = Knob("GATE", " dB", -80, 0, -60, size=56)
        self.out_knob = Knob("OUTPUT", " dB", -24, 12, 0, size=56)
        self.out_meter = Meter()

        self.preset = Gtk.ComboBoxText()
        self.preset.set_size_request(220, -1)
        self.prev = Gtk.Button(label="◄")
        self.next = Gtk.Button(label="►")
        self.save = Gtk.Button(label="SAVE")

        preset_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        preset_box.append(self.prev)
        preset_box.append(self.preset)
        preset_box.append(self.next)
        preset_box.append(self.save)

        title_lbl = Gtk.Label(label=title.upper())
        add_class(title_lbl, "app-title")

        self.append(self.in_meter)
        self.append(self.in_knob)
        self.append(self.gate_knob)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        self.append(spacer)
        self.append(title_lbl)
        self.append(preset_box)
        spacer2 = Gtk.Box()
        spacer2.set_hexpand(True)
        self.append(spacer2)
        self.append(self.out_knob)
        self.append(self.out_meter)

    def fill_presets(self, presets: list[dict], current: str | None) -> None:
        self.preset.remove_all()
        active = 0
        for i, p in enumerate(presets):
            label = p.get("label") or p.get("id") or "?"
            if p.get("error"):
                label += " (error)"
            self.preset.append(p.get("id"), label)
            if p.get("id") == current:
                active = i
        if presets:
            self.preset.set_active(active)
