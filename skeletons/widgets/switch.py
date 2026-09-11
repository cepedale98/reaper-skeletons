from __future__ import annotations

from skeletons.gi_init import Gtk, Pango

from skeletons.gtkutil import add_class


class Switch(Gtk.Box):
    """Labeled on/off control for toggle FX parameters."""

    def __init__(self, label: str = ""):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        add_class(self, "param-switch")
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.set_size_request(72, 56)
        self.on_change = None
        self.on_hover = None
        self.address = ""
        self._building = False

        self._name = Gtk.Label(label=(label or "").upper())
        add_class(self._name, "ctrl-name")
        self._name.set_ellipsize(Pango.EllipsizeMode.END)
        self._name.set_max_width_chars(10)

        self._sw = Gtk.Switch()
        self._sw.set_halign(Gtk.Align.CENTER)
        self._sw.set_valign(Gtk.Align.CENTER)
        self._sw.connect("notify::active", self._toggled)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self._enter)
        self.add_controller(motion)

        self.append(self._name)
        self.append(self._sw)

    def set_label(self, text: str) -> None:
        self._name.set_text((text or "").upper())

    @property
    def value(self) -> float:
        return 1.0 if self._sw.get_active() else 0.0

    @value.setter
    def value(self, v: float) -> None:
        on = float(v or 0) >= 0.5
        if self._sw.get_active() == on:
            return
        self._building = True
        self._sw.set_active(on)
        self._building = False

    def _toggled(self, *_args) -> None:
        if self._building or self.on_change is None:
            return
        self.on_change(self.value)

    def _enter(self, _c, _x: float, _y: float) -> None:
        if self.on_hover:
            self.on_hover(self.address)
