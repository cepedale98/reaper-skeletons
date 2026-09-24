from __future__ import annotations

from skeletons.gi_init import Gtk, Pango

from skeletons.gtkutil import add_class, bind_horizontal_wheel, clear
from skeletons.widgets.pedal import Pedal


TAB_LABELS = {
    "guitar.input": "IN",
    "guitar.pedals": "PEDALS",
    "guitar.amp": "AMP",
    "guitar.cabinet": "CAB",
    "guitar.fx": "FX",
}

LETTERS = ("A", "B", "C", "D")

EMPTY_HINT = (
    "Add JS: Skeletons Pedal to this track. Param-link Wet / On / knobs / switches. "
    "Optional JSON layout goes in the FX Comments field (title, color, discrete ticks)."
)


class _Tile(Gtk.Button):
    """Letter over a name, the floor-unit scribble strip."""

    def __init__(self, key: str):
        super().__init__()
        add_class(self, "perf-tile")
        self.set_can_focus(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.key_lbl = Gtk.Label(label=key)
        add_class(self.key_lbl, "perf-key")
        self.name_lbl = Gtk.Label(label="")
        add_class(self.name_lbl, "perf-name")
        self.name_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.name_lbl.set_max_width_chars(16)
        box.append(self.key_lbl)
        box.append(self.name_lbl)
        self.set_child(box)

    def show_slot(self, name: str, *, active: bool, empty: bool, accent: int) -> None:
        self.name_lbl.set_text(name)
        for cls in ("perf-tile-active", "perf-tile-empty", "perf-tile-unsaved"):
            self.remove_css_class(cls)
        for i in range(12):
            self.remove_css_class(f"pedal-c{i}")
        if empty:
            add_class(self, "perf-tile-empty")
            self.set_sensitive(False)
            return
        self.set_sensitive(True)
        if active:
            add_class(self, "perf-tile-active")
            add_class(self, f"pedal-c{accent % 12}")


class LivePage(Gtk.Box):
    """MODE: floor-unit strip above the pedalboard."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        add_class(self, "live-stage")
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.on_param = None
        self.on_hover = None
        self.on_preset = None
        self._role = ""
        self._slots: tuple = ()
        self._pedals: list[Pedal] = []
        self._pages: list[dict] = [{"slots": [None, None, None, None]}]
        self._page = 0
        self._current_id: str | None = None
        self._followed_id: str | None = None
        self._labels: dict[str, str] = {}

        self.strip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        add_class(self.strip, "perf-strip")
        self.strip.set_halign(Gtk.Align.CENTER)

        self.bank_prev = Gtk.Button(label="◄")
        self.bank_next = Gtk.Button(label="►")
        add_class(self.bank_prev, "icon-btn")
        add_class(self.bank_next, "icon-btn")
        self.bank_label = Gtk.Label(label="01")
        add_class(self.bank_label, "perf-bank")
        self.bank_label.set_width_chars(3)
        self.bank_prev.connect("clicked", lambda *_: self._step_page(-1))
        self.bank_next.connect("clicked", lambda *_: self._step_page(1))

        bank = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        bank.append(self.bank_prev)
        bank.append(self.bank_label)
        bank.append(self.bank_next)
        self.strip.append(bank)

        self.tiles: list[_Tile] = []
        for letter in LETTERS:
            tile = _Tile(letter)
            tile.connect("clicked", self._on_tile, letter)
            self.tiles.append(tile)
            self.strip.append(tile)

        divider = Gtk.Box()
        add_class(divider, "perf-divider")
        self.strip.append(divider)

        self.scene = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        add_class(self.scene, "perf-tile")
        add_class(self.scene, "perf-scene")
        self.scene_key = Gtk.Label(label="1")
        add_class(self.scene_key, "perf-key")
        self.scene_name = Gtk.Label(label="—")
        add_class(self.scene_name, "perf-name")
        self.scene_name.set_ellipsize(Pango.EllipsizeMode.END)
        self.scene_name.set_max_width_chars(16)
        self.scene.append(self.scene_key)
        self.scene.append(self.scene_name)
        self.strip.append(self.scene)

        self.caption_meta = Gtk.Label(label="01")
        add_class(self.caption_meta, "perf-caption-meta")
        self.caption_meta.set_halign(Gtk.Align.CENTER)
        self.caption_name = Gtk.Label(label="—")
        add_class(self.caption_name, "perf-caption-name")
        self.caption_name.set_halign(Gtk.Align.CENTER)
        self.caption_name.set_ellipsize(Pango.EllipsizeMode.END)

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

        self.append(self.strip)
        self.append(self.caption_meta)
        self.append(self.caption_name)
        self.append(self.sub)
        self.append(self.scroll)
        self.append(self.empty)
        self._paint()

    def show_set(self, pages: list[dict] | None, current_id: str | None, presets: list[dict] | None = None) -> None:
        self._pages = list(pages) if pages else [{"slots": [None, None, None, None]}]
        self._labels = {}
        for preset in presets or []:
            pid = preset.get("id")
            if pid:
                self._labels[pid] = preset.get("label") or pid
        self._current_id = current_id or None
        if self._page >= len(self._pages):
            self._page = 0
        if current_id != self._followed_id:
            self._followed_id = current_id
            for index, page in enumerate(self._pages):
                if current_id and current_id in (page.get("slots") or []):
                    self._page = index
                    break
        self._paint()

    def _step_page(self, delta: int) -> None:
        count = len(self._pages)
        if count < 1:
            return
        self._page = (self._page + delta) % count
        self._paint()

    def _on_tile(self, _btn: Gtk.Button, letter: str) -> None:
        index = LETTERS.index(letter)
        slots = (self._pages[self._page].get("slots") or []) if self._pages else []
        preset_id = slots[index] if index < len(slots) else None
        if preset_id and self.on_preset:
            self.on_preset(preset_id)

    def _paint(self) -> None:
        page = self._pages[self._page] if self._pages else {"slots": [None] * 4}
        slots = list(page.get("slots") or [])
        while len(slots) < 4:
            slots.append(None)
        self.bank_label.set_text(f"{self._page + 1:02d}")
        single = len(self._pages) <= 1
        self.bank_prev.set_sensitive(not single)
        self.bank_next.set_sensitive(not single)

        active_letter = None
        active_name = "—"
        for index, tile in enumerate(self.tiles):
            preset_id = slots[index]
            empty = not preset_id
            name = "—" if empty else self._labels.get(preset_id, preset_id)
            active = bool(preset_id) and preset_id == self._current_id
            tile.show_slot(name, active=active, empty=empty, accent=index)
            if active:
                active_letter = LETTERS[index]
                active_name = name

        if self._current_id and active_letter is None:
            active_name = self._labels.get(self._current_id, self._current_id)
        loaded = bool(self._current_id)
        self.scene_name.set_text(active_name if loaded else "—")
        for i in range(12):
            self.scene.remove_css_class(f"pedal-c{i}")
        self.scene.remove_css_class("perf-tile-active")
        if loaded:
            add_class(self.scene, "perf-tile-active")
            add_class(self.scene, "pedal-c0")

        if active_letter:
            self.caption_meta.set_text(f"{self._page + 1:02d}{active_letter} · 1")
            self.caption_name.set_text(active_name)
        elif loaded:
            self.caption_meta.set_text(f"{self._page + 1:02d} · 1")
            self.caption_name.set_text(active_name)
        else:
            self.caption_meta.set_text(f"{self._page + 1:02d}")
            self.caption_name.set_text("—")

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
