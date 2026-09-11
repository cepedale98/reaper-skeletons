from __future__ import annotations

from skeletons.gi_init import Gtk


class Stomp(Gtk.ToggleButton):
    """Pedal stomp switch bound to FX enabled (pressed = engaged)."""

    def __init__(self, label: str = "ON"):
        super().__init__(label=label)
        self.get_style_context().add_class("stomp")
        self.get_style_context().add_class("tactile")
        self.set_size_request(56, 32)
        self.on_toggle = None
        self.connect("toggled", self._toggled)

    def _toggled(self, _btn) -> None:
        if self.on_toggle:
            self.on_toggle(self.get_active())
