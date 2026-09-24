"""Fused chrome: old 8px nested frames joined by circular fillets.

Thin bars at the sides, expanded rounded plates on the tab strip and
footer cluster. Radii follow the grid: inner 8, outer 16.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import cairo
from skeletons.gi_init import GLib, Gtk

from skeletons.gtkutil import theme_rgb

M = 8.0
INNER = M
OUTER = 2 * M
PAD = M


def _mix(a: tuple[float, ...], b: tuple[float, ...], t: float) -> tuple[float, ...]:
    return tuple(a[i] * (1.0 - t) + b[i] * t for i in range(len(a)))


def _widget_rect(widget: Gtk.Widget | None, target: Gtk.Widget) -> tuple[float, float, float, float] | None:
    if widget is None or not widget.get_mapped():
        return None
    try:
        result = widget.compute_bounds(target)
    except Exception:
        return None
    if result is None:
        return None
    if isinstance(result, tuple):
        ok, rect = result
        if not ok or rect is None:
            return None
    else:
        rect = result
    if hasattr(rect, "get_x"):
        return (rect.get_x(), rect.get_y(), rect.get_width(), rect.get_height())
    origin = rect.origin
    size = rect.size
    return (origin.x, origin.y, size.width, size.height)


def _q(cr: cairo.Context, cx: float, cy: float, r: float, a0: float, da: float) -> None:
    if r <= 0.5:
        return
    a1 = a0 + da
    if da >= 0:
        cr.arc(cx, cy, r, a0, a1)
    else:
        cr.arc_negative(cx, cy, r, a0, a1)


def _radii(drop: float, gap_left: float, gap_right: float) -> tuple[float, float]:
    gap = max(0.0, min(gap_left, gap_right))
    r_out = min(OUTER, max(0.0, drop), gap)
    r_in = min(INNER, max(0.0, drop - r_out), max(0.0, gap - r_out))
    return r_in, r_out


class Chassis(Gtk.DrawingArea):
    """Background plates behind status/tabs and the footer cluster."""

    def __init__(self):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_halign(Gtk.Align.FILL)
        self.set_valign(Gtk.Align.FILL)
        self.set_can_target(False)
        self.set_draw_func(self._draw)
        self._lookup: dict[str, Callable[[], Gtk.Widget | None]] = {}
        self.connect("map", self._on_map)
        self.connect("notify::width", self._invalidate)
        self.connect("notify::height", self._invalidate)

    def watch(self, **getters: Callable[[], Gtk.Widget | None] | Gtk.Widget) -> None:
        resolved: dict[str, Callable[[], Gtk.Widget | None]] = {}
        for name, item in getters.items():
            if callable(item):
                resolved[name] = item
            else:
                resolved[name] = lambda widget=item: widget
        self._lookup = resolved
        for item in getters.values():
            widget = item() if callable(item) else item
            if widget is None:
                continue
            widget.connect("notify::width", self._invalidate)
            widget.connect("notify::height", self._invalidate)

    def _on_map(self, *_args) -> None:
        self.queue_draw()
        GLib.timeout_add(40, self._redraw_once)
        GLib.timeout_add(180, self._redraw_once)

    def _redraw_once(self, *_args) -> bool:
        self.queue_draw()
        return False

    def _invalidate(self, *_args) -> None:
        self.queue_draw()

    def _ref(self, name: str) -> Gtk.Widget | None:
        getter = self._lookup.get(name)
        return getter() if getter else None

    def _rect(self, name: str) -> tuple[float, float, float, float] | None:
        return _widget_rect(self._ref(name), self)

    def _draw(self, _area, cr: cairo.Context, w: int, h: int) -> None:
        if w < 8 or h < 8:
            return
        cr.set_antialias(cairo.ANTIALIAS_DEFAULT)
        bg = theme_rgb(self, ("view_bg_color", "theme_bg_color"), (0.12, 0.12, 0.14))
        acc = theme_rgb(self, ("theme_selected_bg_color", "accent_color"), (0.55, 0.72, 0.96))
        cr.set_source_rgb(*_mix(bg, (0.0, 0.0, 0.0), 0.08))
        cr.paint()

        menu_face = (*_mix(bg, acc, 0.18), 0.78)
        menu_rim = (*acc, 0.28)
        tab_face = (*_mix(bg, acc, 0.28), 0.82)
        tab_rim = (*acc, 0.38)

        status = self._rect("status")
        pill = self._rect("pill")
        cluster = self._rect("cluster")
        footer = self._rect("footer")

        thin_top = 40.0
        if status:
            thin_top = status[1] + status[3]
        self._fill_top(cr, w, thin_top, pill, menu_face, menu_rim, tab_face, tab_rim)

        thin_bot = 16.0
        if footer:
            thin_bot = max(M, min(2 * M, footer[3] * 0.22))
        self._fill_bottom(cr, w, h, thin_bot, cluster, menu_face, menu_rim)

    def _stamp(self, cr: cairo.Context, face, rim) -> None:
        cr.save()
        cr.translate(0, 3)
        cr.set_source_rgba(0, 0, 0, 0.16)
        cr.fill_preserve()
        cr.restore()
        cr.set_source_rgba(*face)
        cr.fill_preserve()
        cr.set_source_rgba(*rim)
        cr.set_line_width(1.0)
        cr.stroke()

    def _fill_top(self, cr, w, thin, pill, menu_face, menu_rim, tab_face, tab_rim) -> None:
        cr.new_path()
        cr.rectangle(0, 0, w, thin)
        self._stamp(cr, menu_face, menu_rim)
        if not pill:
            return
        x, y, bw, bh = pill
        left = x - PAD
        right = x + bw + PAD
        bottom = max(thin, y + bh + PAD)
        drop = max(0.0, bottom - thin)
        r_in, r_out = _radii(drop, max(0.0, left), max(0.0, w - right))
        cr.new_path()
        cr.move_to(max(0.0, left - r_in), thin)
        if r_in > 0.5:
            _q(cr, left - r_in, thin + r_in, r_in, -math.pi / 2, math.pi / 2)
        else:
            cr.line_to(left, thin)
        if bottom - r_out > thin + r_in + 0.5:
            cr.line_to(left, bottom - r_out)
        if r_out > 0.5:
            _q(cr, left + r_out, bottom - r_out, r_out, math.pi, -math.pi / 2)
        else:
            cr.line_to(left, bottom)
        cr.line_to(right - r_out, bottom)
        if r_out > 0.5:
            _q(cr, right - r_out, bottom - r_out, r_out, math.pi / 2, -math.pi / 2)
        else:
            cr.line_to(right, bottom)
        if bottom - r_out > thin + r_in + 0.5:
            cr.line_to(right, thin + r_in)
        if r_in > 0.5:
            _q(cr, right + r_in, thin + r_in, r_in, math.pi, math.pi / 2)
        else:
            cr.line_to(right, thin)
        cr.close_path()
        self._stamp(cr, tab_face, tab_rim)

    def _fill_bottom(self, cr, w, h, thin, cluster, face, rim) -> None:
        y_thin = h - thin
        cr.new_path()
        cr.move_to(0, h)
        cr.line_to(0, y_thin)
        if cluster:
            x, y, bw, bh = cluster
            left = x - PAD
            right = x + bw + PAD
            top = min(y_thin, y - PAD)
            drop = max(0.0, y_thin - top)
            r_in, r_out = _radii(drop, max(0.0, left), max(0.0, w - right))
            cr.line_to(max(0.0, left - r_in), y_thin)
            if r_in > 0.5:
                _q(cr, left - r_in, y_thin - r_in, r_in, math.pi / 2, -math.pi / 2)
            else:
                cr.line_to(left, y_thin)
            if top + r_out < y_thin - r_in - 0.5:
                cr.line_to(left, top + r_out)
            if r_out > 0.5:
                _q(cr, left + r_out, top + r_out, r_out, math.pi, math.pi / 2)
            else:
                cr.line_to(left, top)
            cr.line_to(right - r_out, top)
            if r_out > 0.5:
                _q(cr, right - r_out, top + r_out, r_out, -math.pi / 2, math.pi / 2)
            else:
                cr.line_to(right, top)
            if top + r_out < y_thin - r_in - 0.5:
                cr.line_to(right, y_thin - r_in)
            if r_in > 0.5:
                _q(cr, right + r_in, y_thin - r_in, r_in, math.pi, -math.pi / 2)
            else:
                cr.line_to(right, y_thin)
        cr.line_to(w, y_thin)
        cr.line_to(w, h)
        cr.close_path()
        self._stamp(cr, face, rim)
