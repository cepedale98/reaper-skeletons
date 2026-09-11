from __future__ import annotations

from skeletons.gi_init import Gtk, Pango

from skeletons.gtkutil import add_class


class Spin(Gtk.Box):
    """Number box for discrete / integer-looking FX parameters."""

    def __init__(self, label: str = "", minimum: float = 0.0, maximum: float = 1.0, step: float = 1.0):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        add_class(self, "param-spin")
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.set_size_request(88, 56)
        self.on_change = None
        self.on_hover = None
        self.address = ""
        self.minimum = minimum
        self.maximum = maximum
        self._building = False
        step = step if step and step > 0 else 1.0
        digits = 0 if abs(step - round(step)) < 1e-9 and abs(maximum - minimum) >= 1 else 2

        self._name = Gtk.Label(label=(label or "").upper())
        add_class(self._name, "ctrl-name")
        self._name.set_ellipsize(Pango.EllipsizeMode.END)

        adj = Gtk.Adjustment(
            value=minimum,
            lower=minimum,
            upper=maximum,
            step_increment=step,
            page_increment=max(step, (maximum - minimum) / 10.0),
        )
        self._spin = Gtk.SpinButton()
        self._spin.set_adjustment(adj)
        self._spin.set_digits(digits)
        self._spin.set_numeric(True)
        self._spin.set_halign(Gtk.Align.CENTER)
        self._spin.connect("value-changed", self._changed)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self._enter)
        self.add_controller(motion)

        self.append(self._name)
        self.append(self._spin)

    @property
    def value(self) -> float:
        span = self.maximum - self.minimum
        if span <= 0:
            return 0.0
        return (float(self._spin.get_value()) - self.minimum) / span

    @value.setter
    def value(self, norm: float) -> None:
        span = self.maximum - self.minimum
        raw = self.minimum + max(0.0, min(1.0, float(norm or 0))) * span
        if abs(raw - self._spin.get_value()) < 1e-9:
            return
        self._building = True
        self._spin.set_value(raw)
        self._building = False

    def _changed(self, *_args) -> None:
        if self._building or self.on_change is None:
            return
        self.on_change(self.value)

    def _enter(self, _c, _x: float, _y: float) -> None:
        if self.on_hover:
            self.on_hover(self.address)
