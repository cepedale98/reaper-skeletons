from __future__ import annotations

from skeletons.gi_init import Gtk

from skeletons.gtkutil import add_class


class Slider(Gtk.Box):
    """Horizontal slider for continuous FX parameters (normalized 0–1)."""

    def __init__(self, label: str = "", width: int = 160):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        add_class(self, "param-slider")
        self.set_valign(Gtk.Align.CENTER)
        self.set_size_request(width, 56)
        self.on_change = None
        self.on_hover = None
        self.address = ""
        self._text = ""
        self._building = False

        self._name = Gtk.Label(label=(label or "").upper())
        add_class(self._name, "ctrl-name")
        self._name.set_xalign(0)

        self._scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 1.0, 0.001)
        self._scale.set_draw_value(False)
        self._scale.set_hexpand(True)
        self._scale.connect("value-changed", self._changed)

        self._value = Gtk.Label(label="0.00")
        add_class(self._value, "ctrl-caption")
        self._value.set_xalign(1)

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        head.append(self._name)
        self._name.set_hexpand(True)
        head.append(self._value)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self._enter)
        self.add_controller(motion)

        self.append(head)
        self.append(self._scale)

    def set_label(self, text: str) -> None:
        self._name.set_text((text or "").upper())

    def set_text(self, text: str) -> None:
        self._text = text or ""
        self._value.set_text(self._text or f"{self._scale.get_value():.2f}")

    @property
    def value(self) -> float:
        return float(self._scale.get_value())

    @value.setter
    def value(self, v: float) -> None:
        v = max(0.0, min(1.0, float(v or 0)))
        if abs(v - self._scale.get_value()) < 1e-6:
            return
        self._building = True
        self._scale.set_value(v)
        self._building = False
        if not self._text:
            self._value.set_text(f"{v:.2f}")

    def _changed(self, *_args) -> None:
        if not self._text:
            self._value.set_text(f"{self.value:.2f}")
        if self._building or self.on_change is None:
            return
        self.on_change(self.value)

    def _enter(self, _c, _x: float, _y: float) -> None:
        if self.on_hover:
            self.on_hover(self.address)
