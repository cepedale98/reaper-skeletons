from __future__ import annotations

import math

import cairo
from skeletons.gi_init import Gtk


class Meter(Gtk.DrawingArea):
    """Vertical peak meter. Input is dB, typically -60..6."""

    def __init__(self, minimum: float = -60.0, maximum: float = 6.0, width: int = 24):
        super().__init__()
        self.minimum = minimum
        self.maximum = maximum
        self._db = minimum
        self.set_content_width(width)
        self.set_content_height(80)
        self.set_size_request(width, 80)
        self.set_draw_func(self._draw)

    def set_db(self, db: float) -> None:
        self._db = db
        self.queue_draw()

    def _draw(self, _area, cr: cairo.Context, w: int, h: int) -> None:
        from skeletons.gtkutil import theme_rgb

        bg = theme_rgb(self, ("view_bg_color", "theme_bg_color"), (0.1, 0.1, 0.12))
        fg = theme_rgb(self, ("theme_unfocused_fg_color", "theme_fg_color"), (0.45, 0.45, 0.48))
        span = self.maximum - self.minimum
        norm = 0 if span <= 0 else max(0.0, min(1.0, (self._db - self.minimum) / span))
        fill_h = h * norm
        segs = max(20, min(40, int(h / 12)))
        gap = 1.6
        seg_h = h / segs
        radius = max(1.4, min(4.0, (w - 2) * 0.22))
        for i in range(segs):
            y = h - (i + 1) * seg_h
            filled = fill_h >= (i + 0.35) * seg_h
            seg_db = self.minimum + (i + 1) / segs * span
            if not filled:
                dim = tuple(bg[c] * 0.72 + fg[c] * 0.18 for c in range(3))
                cr.set_source_rgba(*dim, 0.55)
            elif seg_db >= 0:
                cr.set_source_rgb(0.86, 0.22, 0.24)
            elif seg_db >= -12:
                cr.set_source_rgb(0.92, 0.72, 0.18)
            else:
                cr.set_source_rgb(0.28, 0.76, 0.42)
            self._lever(cr, 0.5, y + gap * 0.5, w - 1.0, max(2.0, seg_h - gap), radius)
            cr.fill()

    def _lever(self, cr: cairo.Context, x: float, y: float, w: float, h: float, radius: float) -> None:
        radius = min(radius, w / 2, h / 2)
        cr.new_path()
        cr.arc(x + radius, y + radius, radius, math.pi, 1.5 * math.pi)
        cr.arc(x + w - radius, y + radius, radius, 1.5 * math.pi, 2 * math.pi)
        cr.arc(x + w - radius, y + h - radius, radius, 0, 0.5 * math.pi)
        cr.arc(x + radius, y + h - radius, radius, 0.5 * math.pi, math.pi)
        cr.close_path()
