from __future__ import annotations

from pathlib import Path

from skeletons.gi_init import Gtk

from skeletons.config import find_icon
from skeletons.gtkutil import add_class


ICON_STEMS = {
    "guitar.input": ("in", "input", "mic"),
    "guitar.pedals": ("pedals", "fx"),
    "guitar.amp": ("amp", "guitar"),
    "guitar.cabinet": ("cab", "speaker"),
    "guitar.fx": ("fx", "reverb"),
    "keys.input": ("in", "input"),
    "keys.inst": ("keys", "piano"),
    "keys.fx": ("fx",),
    "mic.input": ("mic", "in"),
    "mic.fx": ("fx",),
    "sidefx.reverb": ("reverb", "fx"),
    "sidefx.delay": ("delay", "fx"),
}


def icon_for_role(role: str) -> Path | None:
    for stem in ICON_STEMS.get(role, (role.split(".")[-1],)):
        hit = find_icon(stem)
        if hit:
            return hit
    return None


class TabRow(Gtk.Box):
    """Centered pill nav: IN → PEDALS → AMP → CAB → FX."""

    def __init__(self, tabs: list[tuple[str, str]]):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.set_halign(Gtk.Align.CENTER)
        self.set_hexpand(True)
        self.set_margin_top(4)
        self.set_margin_bottom(4)
        self.on_select = None
        self._buttons: dict[str, Gtk.ToggleButton] = {}
        self._notes: dict[str, Gtk.Label] = {}
        self._active: str | None = None

        pill = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        add_class(pill, "nav-pill")
        pill.set_halign(Gtk.Align.CENTER)

        for i, (role, label) in enumerate(tabs):
            if i:
                arrow = Gtk.Label(label="→")
                add_class(arrow, "tab-arrow")
                pill.append(arrow)
            btn = Gtk.ToggleButton()
            add_class(btn, "tab-icon")
            btn.set_has_frame(False)
            btn.set_tooltip_text(label)
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            col.set_halign(Gtk.Align.CENTER)
            icon = icon_for_role(role)
            badge = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            add_class(badge, "tab-badge")
            badge.set_halign(Gtk.Align.CENTER)
            if icon:
                img = Gtk.Image.new_from_file(str(icon))
                img.set_pixel_size(32)
                img.set_halign(Gtk.Align.CENTER)
                badge.append(img)
            else:
                mark = Gtk.Label(label=label[:1])
                add_class(mark, "tab-mark")
                badge.append(mark)
            col.append(badge)
            name = Gtk.Label(label=label)
            add_class(name, "tab-label")
            note = Gtk.Label(label="")
            add_class(note, "tab-note")
            col.append(name)
            col.append(note)
            btn.set_child(col)
            btn.connect("toggled", self._toggled, role)
            pill.append(btn)
            self._buttons[role] = btn
            self._notes[role] = note
        self.append(pill)
        fx_note = self._notes.get("guitar.fx")
        if fx_note:
            fx_note.set_text("send")

    def _toggled(self, btn: Gtk.ToggleButton, role: str) -> None:
        if not btn.get_active():
            if self._active == role:
                btn.handler_block_by_func(self._toggled)
                btn.set_active(True)
                btn.handler_unblock_by_func(self._toggled)
            return
        self.select(role, notify=True)

    def select(self, role: str, notify: bool = False) -> None:
        self._active = role
        for r, btn in self._buttons.items():
            btn.handler_block_by_func(self._toggled)
            btn.set_active(r == role)
            btn.handler_unblock_by_func(self._toggled)
        if notify and self.on_select:
            self.on_select(role)

    def set_dimmed(self, role: str, dimmed: bool) -> None:
        btn = self._buttons.get(role)
        if btn:
            btn.set_opacity(0.4 if dimmed else 1.0)

    def set_hidden(self, role: str, hidden: bool) -> None:
        btn = self._buttons.get(role)
        if btn:
            btn.set_visible(not hidden)

    def set_send(self, role: str, db: float | None) -> None:
        note = self._notes.get(role)
        if not note:
            return
        if db is None:
            note.set_text("send" if role == "guitar.fx" else "")
        else:
            note.set_text(f"{db:.0f} dB")

    @property
    def active(self) -> str | None:
        return self._active
