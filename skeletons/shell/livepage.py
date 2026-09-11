from __future__ import annotations

from skeletons.gi_init import Gtk

from skeletons.gtkutil import add_class, bind_horizontal_wheel, clear
from skeletons.widgets.pedal import Pedal


TAB_LABELS = {
    "guitar.input": "IN",
    "guitar.pedals": "PEDALS",
    "guitar.amp": "AMP",
    "guitar.cabinet": "CAB",
    "guitar.fx": "FX",
}

EMPTY_HINT = (
    "Add JS: Skeletons Pedal to this track. Param-link Wet / On / knobs / switches. "
    "Optional JSON layout goes in the FX Comments field (title, color, discrete ticks)."
)


class LivePage(Gtk.Box):
    """Pedalboard for Skeletons Pedal JSFX instances on the current tab track."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        add_class(self, "live-stage")
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.on_param = None
        self.on_hover = None
        self._role = ""
        self._slots: tuple = ()
        self._pedals: list[Pedal] = []

        badge = Gtk.Label(label="LIVE")
        add_class(badge, "live-badge")
        badge.set_halign(Gtk.Align.CENTER)
        self.sub = Gtk.Label(label="Pedal panels on the current tab")
        self.sub.set_wrap(True)
        self.sub.set_halign(Gtk.Align.CENTER)
        add_class(self.sub, "card-sub")

        self.board = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self.board.set_halign(Gtk.Align.CENTER)
        self.board.set_valign(Gtk.Align.CENTER)
        self.board.set_hexpand(False)

        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.scroll.set_hexpand(True)
        self.scroll.set_vexpand(True)
        self.scroll.set_propagate_natural_height(True)
        self.scroll.set_child(self.board)
        bind_horizontal_wheel(self.scroll)

        self.empty = Gtk.Label(label=EMPTY_HINT)
        add_class(self.empty, "empty-hint")
        self.empty.set_wrap(True)
        self.empty.set_justify(Gtk.Justification.CENTER)
        self.empty.set_halign(Gtk.Align.CENTER)
        self.empty.set_valign(Gtk.Align.CENTER)
        self.empty.set_hexpand(True)
        self.empty.set_vexpand(True)

        self.append(badge)
        self.append(self.sub)
        self.append(self.scroll)
        self.append(self.empty)

    def bind(self, pedals: list[dict] | None, role: str = "") -> None:
        items = list(pedals or [])
        self._role = role
        label = TAB_LABELS.get(role, role.split(".")[-1].upper() if role else "TAB")
        if not items:
            self.empty.set_visible(True)
            self.scroll.set_visible(False)
            self.sub.set_text(f"{label} · no pedal panels")
            if self._slots:
                clear(self.board)
                self._pedals.clear()
                self._slots = ()
            return
        self.empty.set_visible(False)
        self.scroll.set_visible(True)
        self.sub.set_text(f"{label} · {len(items)} pedal{'s' if len(items) != 1 else ''}")
        slots = tuple(fx.get("slot", i) for i, fx in enumerate(items))
        if slots != self._slots:
            self._rebuild(items)
            self._slots = slots
        for fx, widget in zip(items, self._pedals):
            widget.bind(fx, role)

    def _rebuild(self, items: list[dict]) -> None:
        clear(self.board)
        self._pedals.clear()
        for fx in items:
            pedal = Pedal()
            pedal.on_param = self._param
            pedal.on_hover = self._hover
            pedal.bind(fx, self._role)
            self.board.append(pedal)
            self._pedals.append(pedal)

    def _hover(self, text: str) -> None:
        if self.on_hover:
            self.on_hover(text)

    def _param(self, role: str, fx: int, index: int, value: float) -> None:
        if self.on_param is None:
            return
        self.on_param(role, fx, index, value)
