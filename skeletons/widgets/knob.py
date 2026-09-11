from __future__ import annotations

import math

import cairo
from skeletons.gi_init import Gdk, Gtk


class Knob(Gtk.DrawingArea):
    """Vertical click-drag knob. Double-click resets. Ctrl for fine adjust."""

    def __init__(self, label: str = "", unit: str = "", minimum: float = 0.0, maximum: float = 1.0,
                 default: float = 0.0, size: int = 64):
        super().__init__()
        self.label = label
        self.unit = unit
        self.minimum = minimum
        self.maximum = maximum
        self.default = default
        self._value = default
        self._drag_start = 0.0
        self.on_change = None
        self.on_hover = None
        self.address = ""
        self.set_content_width(size)
        self.set_content_height(size + 28)
        self.set_size_request(size, size + 28)
        self.set_draw_func(self._draw)
        self.set_property("has-tooltip", True)
        self.connect("query-tooltip", self._tooltip)

        click = Gtk.GestureClick()
        click.connect("pressed", self._pressed)
        self.add_controller(click)

        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._drag_begin)
        drag.connect("drag-update", self._drag_update)
        self.add_controller(drag)

        scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", self._scroll)
        self.add_controller(scroll)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self._enter)
        self.add_controller(motion)

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float) -> None:
        v = max(self.minimum, min(self.maximum, v))
        if abs(v - self._value) > 1e-9:
            self._value = v
            self.queue_draw()

    def _norm(self) -> float:
        span = self.maximum - self.minimum
        if span <= 0:
            return 0.0
        return (self._value - self.minimum) / span

    def _format(self) -> str:
        if abs(self.maximum - self.minimum) > 20:
            return f"{self._value:.1f}{self.unit}"
        return f"{self._value:.2f}{self.unit}"

    def _draw(self, _area, cr: cairo.Context, w: int, h: int) -> None:
        from skeletons.gtkutil import theme_rgb

        dim = theme_rgb(self, ("theme_unfocused_fg_color",), (0.45, 0.45, 0.48))
        fg = theme_rgb(self, ("theme_fg_color", "window_fg_color"), (0.9, 0.9, 0.92))
        acc = theme_rgb(self, ("theme_selected_bg_color", "accent_color", "accent_bg_color"), (0.91, 0.54, 0.62))
        face = theme_rgb(self, ("theme_bg_color", "view_bg_color"), (0.18, 0.18, 0.2))
        cx, cy = w / 2, (h - 16) / 2 + 4
        radius = min(cx, cy) - 10
        start = math.pi * 0.75
        end = math.pi * 2.25

        ticks = 11
        for i in range(ticks):
            t = i / (ticks - 1)
            ang = start + (end - start) * t
            inner = radius + 3
            outer = radius + 6
            cr.set_source_rgba(*acc, 0.9 if t <= self._norm() + 0.02 else 0.25)
            cr.set_line_width(2)
            cr.move_to(cx + math.cos(ang) * inner, cy + math.sin(ang) * inner)
            cr.line_to(cx + math.cos(ang) * outer, cy + math.sin(ang) * outer)
            cr.stroke()

        cr.set_source_rgb(max(0, face[0] - 0.06), max(0, face[1] - 0.06), max(0, face[2] - 0.06))
        cr.arc(cx, cy + 1.5, radius, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgb(min(1, face[0] + 0.12), min(1, face[1] + 0.12), min(1, face[2] + 0.12))
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.fill()
        highlight = cairo.RadialGradient(cx - radius * 0.3, cy - radius * 0.35, 1, cx, cy, radius)
        highlight.add_color_stop_rgba(0, 1, 1, 1, 0.18)
        highlight.add_color_stop_rgba(1, 0, 0, 0, 0.08)
        cr.set_source(highlight)
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.fill()

        cr.set_line_width(3.2)
        cr.set_source_rgb(*dim)
        cr.arc(cx, cy, radius - 3, start, end)
        cr.stroke()
        cr.set_source_rgb(*acc)
        cr.arc(cx, cy, radius - 3, start, start + (end - start) * self._norm())
        cr.stroke()

        angle = start + (end - start) * self._norm()
        cr.set_source_rgb(*fg)
        cr.set_line_width(2.4)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(cx + math.cos(angle) * 4, cy + math.sin(angle) * 4)
        cr.line_to(cx + math.cos(angle) * (radius - 9), cy + math.sin(angle) * (radius - 9))
        cr.stroke()
        cr.arc(cx, cy, 3.2, 0, 2 * math.pi)
        cr.fill()

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_source_rgb(*fg)
        cr.set_font_size(11)
        text = self.label.upper()
        tw = cr.text_extents(text).width
        cr.move_to(cx - tw / 2, 13)
        cr.show_text(text)
        cr.set_font_size(10)
        cr.set_source_rgb(*dim)
        val = self._format()
        tw = cr.text_extents(val).width
        cr.move_to(cx - tw / 2, h - 3)
        cr.show_text(val)

    def _pressed(self, _g, n_press: int, _x: float, _y: float) -> None:
        if n_press >= 2:
            self._commit(self.default)

    def _drag_begin(self, _g, _x: float, _y: float) -> None:
        self._drag_start = self._value

    def _drag_update(self, gesture: Gtk.GestureDrag, _dx: float, dy: float) -> None:
        span = self.maximum - self.minimum
        state = gesture.get_current_event_state()
        scale = 0.002 if state & Gdk.ModifierType.CONTROL_MASK else 0.01
        self._commit(self._drag_start + (-dy) * span * scale)

    def _scroll(self, controller: Gtk.EventControllerScroll, _dx: float, dy: float) -> bool:
        state = controller.get_current_event_state()
        step = (self.maximum - self.minimum) * (0.005 if state & Gdk.ModifierType.CONTROL_MASK else 0.03)
        self._commit(self._value + (-step if dy > 0 else step))
        return True

    def _enter(self, _c, _x: float, _y: float) -> None:
        if self.on_hover:
            self.on_hover(self.address)

    def _commit(self, value: float) -> None:
        self.value = value
        if self.on_change:
            self.on_change(self._value)

    def _tooltip(self, _w, _x, _y, _kb, tooltip) -> bool:
        tooltip.set_text(self.address or f"{self.label} = {self._format()}")
        return True
