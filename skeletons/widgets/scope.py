from __future__ import annotations

import cairo

from skeletons.gi_init import Gtk
from skeletons.gtkutil import theme_rgb


class Oscilloscope(Gtk.DrawingArea):
    """Waveform from RappScope gmem."""

    def __init__(self):
        super().__init__()
        self.samples: list[float] = []
        self.peak = 0.0
        self.set_content_width(640)
        self.set_content_height(220)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_draw_func(self._draw)

    def update(self, samples: list[float], peak: float = 0.0) -> None:
        self.samples = samples
        self.peak = peak
        self.queue_draw()

    def _draw(self, _area, cr: cairo.Context, w: int, h: int) -> None:
        bg = theme_rgb(self, ("view_bg_color", "theme_bg_color"), (0.12, 0.12, 0.14))
        fg = theme_rgb(self, ("theme_fg_color", "window_fg_color"), (0.85, 0.85, 0.88))
        acc = theme_rgb(self, ("theme_selected_bg_color", "accent_color", "accent_bg_color"), (0.25, 0.75, 0.55))
        cr.set_source_rgb(*bg)
        cr.paint()
        mid = h / 2
        cr.set_source_rgba(fg[0], fg[1], fg[2], 0.25)
        cr.set_line_width(1)
        cr.move_to(16, mid)
        cr.line_to(w - 16, mid)
        cr.stroke()
        data = self.samples
        if len(data) < 2:
            cr.set_source_rgb(*fg)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(14)
            msg = "play a note"
            tw = cr.text_extents(msg).width
            cr.move_to(w / 2 - tw / 2, mid - 12)
            cr.show_text(msg)
            return
        cr.set_source_rgb(*acc)
        cr.set_line_width(2)
        left, right = 16, w - 16
        span = max(1, len(data) - 1)
        for i, s in enumerate(data):
            x = left + i / span * (right - left)
            y = mid - max(-1.0, min(1.0, s)) * (h * 0.4)
            if i == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.stroke()
        cr.set_source_rgb(*fg)
        cr.set_font_size(11)
        cr.move_to(16, h - 12)
        cr.show_text(f"peak {self.peak:.2f}")
