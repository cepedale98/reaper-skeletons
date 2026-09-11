from __future__ import annotations

from skeletons.gi_init import Gtk


class FlowStrip(Gtk.Box):
    """Read-only pictorial signal path. Nodes switch tabs when clicked."""

    def __init__(self, nodes: list[tuple[str, str]]):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.set_halign(Gtk.Align.CENTER)
        self.set_margin_bottom(8)
        self.on_click = None
        self._btns: dict[str, Gtk.Button] = {}
        self._notes: dict[str, Gtk.Label] = {}
        for i, (role, label) in enumerate(nodes):
            if i:
                arrow = Gtk.Label(label="→")
                arrow.get_style_context().add_class("flow-arrow")
                self.append(arrow)
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            btn = Gtk.Button(label=label)
            btn.get_style_context().add_class("flow-node")
            btn.connect("clicked", self._clicked, role)
            note = Gtk.Label(label="")
            note.get_style_context().add_class("flow-arrow")
            col.append(btn)
            col.append(note)
            self.append(col)
            self._btns[role] = btn
            self._notes[role] = note
        fx_note = self._notes.get("guitar.fx")
        if fx_note:
            fx_note.set_text("∥ send")

    def _clicked(self, _b, role: str) -> None:
        if self.on_click:
            self.on_click(role)

    def set_send(self, role: str, db: float | None) -> None:
        note = self._notes.get(role)
        if not note:
            return
        if db is None:
            note.set_text("∥ send")
        else:
            note.set_text(f"∥ {db:.0f} dB")
