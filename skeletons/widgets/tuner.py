from __future__ import annotations

import math

import cairo
from skeletons.gi_init import Gtk

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


class Tuner(Gtk.DrawingArea):
    """Needle tuner. Green when within 5 cents."""

    def __init__(self):
        super().__init__()
        self.freq = 0.0
        self.cents = 0.0
        self.note = -1
        self.level = 0.0
        self.set_content_width(420)
        self.set_content_height(160)
        self.set_size_request(420, 160)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_draw_func(self._draw)

    def update(self, freq: float, cents: float, note: float, level: float) -> None:
        self.freq = freq
        self.cents = cents
        self.note = note
        self.level = level
        self.queue_draw()

    def _draw(self, _area, cr: cairo.Context, w: int, h: int) -> None:
        from skeletons.gtkutil import theme_rgb

        bg = theme_rgb(self, ("view_bg_color", "theme_bg_color"), (0.09, 0.09, 0.1))
        cr.set_source_rgb(*bg)
        cr.paint()
        in_tune = abs(self.cents) < 5 and self.freq > 0
        cr.set_source_rgb(0.25, 0.85, 0.4) if in_tune else cr.set_source_rgb(0.85, 0.85, 0.88)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(36)
        if self.note >= 0 and self.freq > 0:
            name = NOTE_NAMES[int(self.note) % 12] + str(int(self.note) // 12 - 1)
        else:
            name = "—"
        tw = cr.text_extents(name).width
        cr.move_to(w / 2 - tw / 2, 48)
        cr.show_text(name)
        y = 90
        cr.set_source_rgb(0.3, 0.3, 0.32)
        cr.set_line_width(2)
        cr.move_to(40, y)
        cr.line_to(w - 40, y)
        cr.stroke()
        cr.set_source_rgb(0.5, 0.5, 0.52)
        cr.set_font_size(10)
        for cents, label in ((-50, "-50"), (0, "0"), (50, "+50")):
            x = 40 + (cents + 50) / 100 * (w - 80)
            cr.move_to(x, y - 8)
            cr.line_to(x, y + 8)
            cr.stroke()
            tw = cr.text_extents(label).width
            cr.move_to(x - tw / 2, y + 22)
            cr.show_text(label)
        if self.freq > 0:
            x = 40 + max(0, min(1, (self.cents + 50) / 100)) * (w - 80)
            cr.set_source_rgb(0.25, 0.85, 0.4) if in_tune else cr.set_source_rgb(0.91, 0.54, 0.62)
            cr.arc(x, y, 8, 0, 2 * math.pi)
            cr.fill()
        cr.set_source_rgb(0.55, 0.55, 0.55)
        cr.set_font_size(11)
        info = f"{self.freq:.1f} Hz   {self.cents:+.0f} ¢" if self.freq > 0 else "play a note"
        tw = cr.text_extents(info).width
        cr.move_to(w / 2 - tw / 2, h - 16)
        cr.show_text(info)


class TunerStrip(Gtk.DrawingArea):
    """Compact always-on tuner for the footer."""

    def __init__(self):
        super().__init__()
        self.freq = 0.0
        self.cents = 0.0
        self.note = -1
        self.set_content_width(160)
        self.set_content_height(40)
        self.set_size_request(160, 40)
        self.set_draw_func(self._draw)

    def update(self, freq: float, cents: float, note: float, _level: float = 0) -> None:
        self.freq = freq
        self.cents = cents
        self.note = note
        self.queue_draw()

    def _draw(self, _area, cr: cairo.Context, w: int, h: int) -> None:
        cr.set_source_rgb(0.1, 0.1, 0.1)
        cr.paint()
        in_tune = abs(self.cents) < 5 and self.freq > 0
        cr.set_source_rgb(0.25, 0.85, 0.4) if in_tune else cr.set_source_rgb(0.7, 0.7, 0.72)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        if self.note >= 0 and self.freq > 0:
            name = NOTE_NAMES[int(self.note) % 12]
        else:
            name = "—"
        cr.move_to(8, h / 2 + 4)
        cr.show_text(name)
        y = h / 2
        cr.set_source_rgb(0.3, 0.3, 0.32)
        cr.set_line_width(2)
        cr.move_to(32, y)
        cr.line_to(w - 8, y)
        cr.stroke()
        if self.freq > 0:
            x = 32 + max(0, min(1, (self.cents + 50) / 100)) * (w - 48)
            cr.set_source_rgb(0.25, 0.85, 0.4) if in_tune else cr.set_source_rgb(0.91, 0.54, 0.62)
            cr.arc(x, y, 5, 0, 2 * math.pi)
            cr.fill()
