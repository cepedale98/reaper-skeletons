"""GTK 4 helpers so callers do not use removed GTK 3 container APIs."""

from __future__ import annotations

from collections.abc import Iterator

from skeletons.gi_init import Gtk


def children(widget: Gtk.Widget) -> list[Gtk.Widget]:
    out: list[Gtk.Widget] = []
    child = widget.get_first_child()
    while child is not None:
        out.append(child)
        child = child.get_next_sibling()
    return out


def iter_children(widget: Gtk.Widget) -> Iterator[Gtk.Widget]:
    yield from children(widget)


def clear(widget: Gtk.Widget) -> None:
    for child in children(widget):
        widget.remove(child)


def load_css_data(provider: Gtk.CssProvider, css: str) -> None:
    if hasattr(provider, "load_from_string"):
        provider.load_from_string(css)
    else:
        provider.load_from_data(css.encode("utf-8"))


def add_class(widget: Gtk.Widget, name: str) -> None:
    if hasattr(widget, "add_css_class"):
        widget.add_css_class(name)
    else:
        widget.get_style_context().add_class(name)


def theme_rgb(widget: Gtk.Widget, names: tuple[str, ...], fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    ctx = widget.get_style_context()
    for name in names:
        try:
            ok, color = ctx.lookup_color(name)
        except Exception:
            continue
        if ok:
            return (color.red, color.green, color.blue)
    return fallback


def bind_horizontal_wheel(scroll: Gtk.ScrolledWindow, step: float = 48.0) -> None:
    """Vertical mouse wheel pans the horizontal scrollbar when the row overflows."""
    flags = Gtk.EventControllerScrollFlags.VERTICAL | Gtk.EventControllerScrollFlags.HORIZONTAL
    ctl = Gtk.EventControllerScroll.new(flags)
    ctl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

    def on_scroll(_c, dx: float, dy: float) -> bool:
        hadj = scroll.get_hadjustment()
        if hadj is None:
            return False
        overflow = hadj.get_upper() - hadj.get_page_size() > 1
        if overflow and abs(dy) >= abs(dx) and dy != 0:
            hadj.set_value(hadj.get_value() + dy * step)
            return True
        if dx:
            hadj.set_value(hadj.get_value() + dx * step)
            return True
        return False

    ctl.connect("scroll", on_scroll)
    scroll.add_controller(ctl)


def icon_toggle(icon_name: str, tooltip: str) -> Gtk.ToggleButton:
    btn = Gtk.ToggleButton()
    btn.set_tooltip_text(tooltip)
    add_class(btn, "icon-toggle")
    img = Gtk.Image.new_from_icon_name(icon_name)
    img.set_pixel_size(24)
    btn.set_child(img)
    return btn


def icon_button(icon_name: str, tooltip: str) -> Gtk.Button:
    btn = Gtk.Button()
    btn.set_tooltip_text(tooltip)
    add_class(btn, "icon-btn")
    img = Gtk.Image.new_from_icon_name(icon_name)
    img.set_pixel_size(24)
    btn.set_child(img)
    return btn
