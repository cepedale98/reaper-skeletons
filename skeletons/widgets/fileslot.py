from __future__ import annotations

from skeletons.gi_init import Gtk, Pango


class FileSlot(Gtk.Box):
    """Ratatouille-style file row: type icon, normalize, filename, erase."""

    def __init__(self, title: str, kind: str = "nam"):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.set_margin_top(4)
        self.set_margin_bottom(4)
        self.kind = kind
        self.on_normalize = None
        self.on_erase = None

        icon = Gtk.Label(label="NAM" if kind == "nam" else "IR")
        icon.get_style_context().add_class("slot-title")
        icon.set_size_request(36, -1)

        self._title = Gtk.Label(label=title)
        self._title.get_style_context().add_class("slot-title")
        self._title.set_xalign(0)
        self._title.set_size_request(72, -1)

        self.normalize = Gtk.ToggleButton(label="N")
        self.normalize.set_tooltip_text("Normalize")
        self.normalize.get_style_context().add_class("header-btn")
        self.normalize.connect("toggled", self._norm)

        self._name = Gtk.Label(label="—")
        self._name.set_xalign(0)
        self._name.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self._name.set_hexpand(True)

        self.erase = Gtk.Button(label="✕")
        self.erase.set_tooltip_text("Erase slot")
        self.erase.get_style_context().add_class("header-btn")
        self.erase.connect("clicked", self._erase)

        self.append(icon)
        self.append(self._title)
        self.append(self.normalize)
        self.append(self._name)
        self.append(self.erase)

    def set_path(self, path: str | None) -> None:
        if not path or path == "None":
            self._name.set_text("empty")
            self._name.set_tooltip_text("")
        else:
            self._name.set_text(path.rsplit("/", 1)[-1])
            self._name.set_tooltip_text(path)

    def set_normalized(self, on: bool) -> None:
        self.normalize.handler_block_by_func(self._norm)
        self.normalize.set_active(bool(on))
        self.normalize.handler_unblock_by_func(self._norm)

    def _norm(self, btn: Gtk.ToggleButton) -> None:
        if self.on_normalize:
            self.on_normalize(btn.get_active())

    def _erase(self, _btn) -> None:
        if self.on_erase:
            self.on_erase()
