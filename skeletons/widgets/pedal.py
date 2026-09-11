"""One Live-view pedal bound to a Skeletons Pedal JSFX instance."""

from __future__ import annotations

import math
import re

import cairo

from skeletons.gi_init import Gdk, Gtk, Pango

from skeletons.gtkutil import add_class, clear, load_css_data, theme_rgb
from skeletons.widgets.knob import Knob
from skeletons.widgets.switch import Switch

# Fixed slider indices in skel_panel_pedal (JSFX slider1 = index 0).
IDX_WET = 0
IDX_ON = 1
IDX_KNOB0 = 2
N_KNOBS_MAX = 6
IDX_SW0 = 8
N_SW_MAX = 3
IDX_N_KNOBS = 11
IDX_N_SWITCHES = 12
IDX_COLOR = 13
IDX_TITLE = 14

COLOR_COUNT = 12
GENERIC_TITLES = frozenset({"", "title", "pedal", "skeletons pedal", "reaperapp pedal", "slider15", "parm15"})


def param_at(fx: dict, index: int) -> dict | None:
    for p in fx.get("params") or []:
        if p.get("index") == index:
            return p
    return None


def panel_cfg(fx: dict) -> dict | None:
    cfg = fx.get("panel_cfg")
    return cfg if isinstance(cfg, dict) else None


def _slider_int(fx: dict, index: int, lo: int, hi: int, default: int) -> int:
    p = param_at(fx, index)
    if not p:
        return default
    mn = float(p.get("min", lo))
    mx = float(p.get("max", hi))
    if mx <= mn:
        return default
    val = mn + float(p.get("norm") or 0) * (mx - mn)
    return max(lo, min(hi, int(round(val))))


def _ctrl_param(item: dict, default: int) -> int:
    for key in ("param", "index"):
        try:
            return int(item.get(key))
        except (TypeError, ValueError):
            continue
    return default


def _ticks(item: dict) -> list[str]:
    raw = item.get("ticks")
    if raw is None:
        raw = item.get("steps")
    return [str(s) for s in (raw or []) if str(s).strip()]


HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


def knob_specs(fx: dict) -> list[dict]:
    cfg = panel_cfg(fx)
    if cfg and cfg.get("knobs"):
        out = []
        for i, raw in enumerate(list(cfg["knobs"])[:N_KNOBS_MAX]):
            item = raw if isinstance(raw, dict) else {}
            steps = _ticks(item)
            typ = item.get("type") or "knob"
            if typ == "continuous":
                typ = "knob"
            if typ == "discrete" and len(steps) < 2:
                typ = "knob"
            out.append({
                "param": _ctrl_param(item, IDX_KNOB0 + i),
                "type": typ,
                "label": (item.get("label") or f"Knob {i + 1}").strip(),
                "steps": steps,
            })
        while len(out) < 2:
            i = len(out)
            out.append({"param": IDX_KNOB0 + i, "type": "knob", "label": f"Knob {i + 1}", "steps": []})
        return out
    n = _slider_int(fx, IDX_N_KNOBS, 2, N_KNOBS_MAX, 3)
    out = []
    for i in range(n):
        p = param_at(fx, IDX_KNOB0 + i)
        out.append({
            "param": IDX_KNOB0 + i,
            "type": "knob",
            "label": ((p or {}).get("name") or f"Knob {i + 1}").strip(),
            "steps": [],
        })
    return out


def switch_specs(fx: dict) -> list[dict]:
    cfg = panel_cfg(fx)
    if cfg and "switches" in cfg:
        out = []
        for i, raw in enumerate(list(cfg.get("switches") or [])[:N_SW_MAX]):
            item = raw if isinstance(raw, dict) else {}
            steps = _ticks(item)
            typ = item.get("type") or "toggle"
            if typ == "multi" and len(steps) < 2:
                typ = "toggle"
            out.append({
                "param": _ctrl_param(item, IDX_SW0 + i),
                "type": typ,
                "label": (item.get("label") or f"Switch {i + 1}").strip(),
                "steps": steps,
            })
        return out
    n = _slider_int(fx, IDX_N_SWITCHES, 0, N_SW_MAX, 0)
    out = []
    for i in range(n):
        p = param_at(fx, IDX_SW0 + i)
        out.append({
            "param": IDX_SW0 + i,
            "type": "toggle",
            "label": ((p or {}).get("name") or f"Switch {i + 1}").strip(),
            "steps": [],
        })
    return out


def knob_count(fx: dict) -> int:
    return max(2, min(N_KNOBS_MAX, len(knob_specs(fx))))


def switch_count(fx: dict) -> int:
    return max(0, min(N_SW_MAX, len(switch_specs(fx))))


def color_hex(fx: dict) -> str | None:
    cfg = panel_cfg(fx)
    if not cfg:
        return None
    raw = cfg.get("color_hex") or cfg.get("color")
    if not isinstance(raw, str) or not HEX_RE.match(raw.strip()):
        return None
    raw = raw.strip()
    return raw if raw.startswith("#") else f"#{raw}"


def color_index(fx: dict) -> int:
    cfg = panel_cfg(fx)
    if cfg and cfg.get("color") is not None and not isinstance(cfg.get("color"), str):
        try:
            return max(0, min(COLOR_COUNT - 1, int(cfg["color"])))
        except (TypeError, ValueError):
            pass
    return _slider_int(fx, IDX_COLOR, 0, COLOR_COUNT - 1, 0)


def title_of(fx: dict) -> str:
    cfg = panel_cfg(fx)
    if cfg:
        name = (cfg.get("title") or "").strip()
        if name.lower() not in GENERIC_TITLES:
            return name
    titled = ((param_at(fx, IDX_TITLE) or {}).get("name") or "").strip()
    if titled.lower() not in GENERIC_TITLES:
        return titled
    raw = (fx.get("name") or "").strip()
    raw = re.sub(r"^(JS|CLAP):\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*\(.*\)$", "", raw).strip()
    low = raw.lower()
    if "skel_panel_pedal" in low or "rapp_panel_pedal" in low or low in ("skeletons pedal", "reaperapp pedal", "pedal"):
        return "PEDAL"
    return raw or "PEDAL"


def wet_label(fx: dict) -> str:
    cfg = panel_cfg(fx)
    if cfg and (cfg.get("wet") or cfg.get("wet_label") or "").strip():
        return str(cfg.get("wet") or cfg.get("wet_label")).strip()
    p = param_at(fx, IDX_WET)
    return ((p or {}).get("name") or "Wet").strip() or "Wet"


def knob_row_sizes(n: int) -> tuple[int, int]:
    n = max(2, min(N_KNOBS_MAX, n))
    top = (n + 1) // 2
    return top, n - top


def layout_key(fx: dict) -> tuple:
    knobs = tuple((s["param"], s["type"], s["label"], tuple(s["steps"])) for s in knob_specs(fx))
    switches = tuple((s["param"], s["type"], s["label"], tuple(s["steps"])) for s in switch_specs(fx))
    return (title_of(fx), color_hex(fx) or color_index(fx), knobs, switches)


def _norm_index(norm: float, n: int) -> int:
    if n <= 1:
        return 0
    return max(0, min(n - 1, int(round(float(norm or 0) * (n - 1)))))


def _index_norm(index: int, n: int) -> float:
    if n <= 1:
        return 0.0
    return max(0, min(n - 1, index)) / (n - 1)


class DiscreteKnob(Knob):
    """Continuous 0–1 knob that snaps to named detents."""

    def __init__(self, label: str, steps: list[str], value: float = 0.0, size: int = 48):
        self.steps = [str(s) for s in steps if str(s)]
        if len(self.steps) < 2:
            self.steps = ["0", "1"]
        super().__init__(label, "", 0.0, 1.0, value, size)
        self._value = self._snap_norm(value)

    def _count(self) -> int:
        return max(1, len(self.steps))

    def _snap_norm(self, v: float) -> float:
        return _index_norm(_norm_index(v, self._count()), self._count())

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float) -> None:
        snapped = self._snap_norm(float(v or 0))
        if abs(snapped - self._value) > 1e-9:
            self._value = snapped
            self.queue_draw()

    def _format(self) -> str:
        i = _norm_index(self._value, self._count())
        return self.steps[i]

    def _commit(self, value: float) -> None:
        snapped = self._snap_norm(value)
        self._value = snapped
        self.queue_draw()
        if self.on_change:
            self.on_change(self._value)

    def _scroll(self, controller: Gtk.EventControllerScroll, _dx: float, dy: float) -> bool:
        n = self._count()
        if n <= 1:
            return True
        step = 1.0 / (n - 1)
        self._commit(self._value + (-step if dy > 0 else step))
        return True


class CycleSwitch(Gtk.Box):
    """Click-to-advance multi-state control."""

    def __init__(self, label: str, steps: list[str]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        add_class(self, "param-switch")
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.set_size_request(72, 56)
        self.on_change = None
        self.on_hover = None
        self.address = ""
        self.steps = [str(s) for s in steps if str(s)] or ["Off", "On"]
        self._index = 0
        self._building = False

        self._name = Gtk.Label(label=(label or "").upper())
        add_class(self._name, "ctrl-name")
        self._name.set_ellipsize(Pango.EllipsizeMode.END)
        self._name.set_max_width_chars(10)

        self._btn = Gtk.Button(label=self.steps[0])
        add_class(self._btn, "pedal-cycle")
        self._btn.set_halign(Gtk.Align.CENTER)
        self._btn.connect("clicked", self._cycle)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self._enter)
        self.add_controller(motion)

        self.append(self._name)
        self.append(self._btn)

    def set_label(self, text: str) -> None:
        self._name.set_text((text or "").upper())

    @property
    def value(self) -> float:
        return _index_norm(self._index, len(self.steps))

    @value.setter
    def value(self, v: float) -> None:
        i = _norm_index(float(v or 0), len(self.steps))
        if i == self._index:
            self._btn.set_label(self.steps[i])
            return
        self._building = True
        self._index = i
        self._btn.set_label(self.steps[i])
        self._building = False

    def _cycle(self, *_args) -> None:
        if self._building or not self.steps:
            return
        self._index = (self._index + 1) % len(self.steps)
        self._btn.set_label(self.steps[self._index])
        if self.on_change:
            self.on_change(self.value)

    def _enter(self, _c, _x: float, _y: float) -> None:
        if self.on_hover:
            self.on_hover(self.address)


class Footswitch(Gtk.DrawingArea):
    """Wide box stomp. No legend; engaged state is a subtle accent fill."""

    def __init__(self, width: int = 168, height: int = 40):
        super().__init__()
        self._on = True
        self.on_toggle = None
        self.on_hover = None
        self.address = ""
        self.set_content_width(width)
        self.set_content_height(height)
        self.set_size_request(width, height)
        self.set_halign(Gtk.Align.CENTER)
        add_class(self, "pedal-foot")
        self.set_draw_func(self._draw)
        click = Gtk.GestureClick()
        click.connect("pressed", self._pressed)
        self.add_controller(click)
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self._enter)
        self.add_controller(motion)

    @property
    def active(self) -> bool:
        return self._on

    @active.setter
    def active(self, on: bool) -> None:
        on = bool(on)
        if on != self._on:
            self._on = on
            self.queue_draw()

    def _draw(self, _area, cr: cairo.Context, w: int, h: int) -> None:
        acc = theme_rgb(self, ("theme_selected_bg_color", "accent_color"), (0.91, 0.54, 0.62))
        face = theme_rgb(self, ("theme_bg_color",), (0.16, 0.16, 0.18))
        r = 8.0
        x, y = 1.5, 1.5
        bw, bh = w - 3, h - 3
        if self._on:
            cr.set_source_rgb(
                face[0] * 0.65 + acc[0] * 0.35,
                face[1] * 0.65 + acc[1] * 0.35,
                face[2] * 0.65 + acc[2] * 0.35,
            )
        else:
            cr.set_source_rgb(min(1, face[0] + 0.08), min(1, face[1] + 0.08), min(1, face[2] + 0.08))
        self._round_rect(cr, x, y, bw, bh, r)
        cr.fill()
        cr.set_line_width(2.0)
        if self._on:
            cr.set_source_rgba(*acc, 0.7)
        else:
            cr.set_source_rgba(1, 1, 1, 0.12)
        self._round_rect(cr, x, y, bw, bh, r)
        cr.stroke()

    @staticmethod
    def _round_rect(cr: cairo.Context, x: float, y: float, w: float, h: float, r: float) -> None:
        cr.new_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()

    def _pressed(self, _g, n_press: int, _x: float, _y: float) -> None:
        if n_press != 1:
            return
        self._on = not self._on
        self.queue_draw()
        if self.on_toggle:
            self.on_toggle(self._on)

    def _enter(self, _c, _x: float, _y: float) -> None:
        if self.on_hover:
            self.on_hover(self.address)


class Pedal(Gtk.Box):
    """Colored enclosure: wet bar, two knob rows, mini switches, title, footswitch."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        add_class(self, "pedal")
        self.set_hexpand(False)
        self.set_vexpand(False)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.on_param = None
        self.on_hover = None
        self._building = False
        self._role = ""
        self._slot = 0
        self._layout: tuple | None = None
        self._color = None
        self._css = None
        self._knobs: dict[int, Knob] = {}
        self._switches: dict[int, Gtk.Widget] = {}

        self._wet = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 1.0, 0.001)
        self._wet.set_draw_value(False)
        self._wet.set_hexpand(True)
        add_class(self._wet, "pedal-wet")
        self._wet.connect("value-changed", self._wet_changed)

        self._knob_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._knob_box.set_halign(Gtk.Align.CENTER)

        self._sw_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._sw_box.set_halign(Gtk.Align.CENTER)

        self._title = Gtk.Label(label="PEDAL")
        add_class(self._title, "pedal-title")
        self._title.set_halign(Gtk.Align.CENTER)
        self._title.set_ellipsize(Pango.EllipsizeMode.END)
        self._title.set_max_width_chars(14)

        self._foot = Footswitch(168, 40)
        self._foot.on_toggle = self._on_toggled
        self._foot.on_hover = self._hover

        self.append(self._wet)
        self.append(self._knob_box)
        self.append(self._sw_box)
        self.append(self._title)
        self.append(self._foot)

    def bind(self, fx: dict, role: str) -> None:
        self._role = role
        self._slot = fx.get("slot", 0)
        key = layout_key(fx)
        if key != self._layout:
            self._rebuild(fx)
            self._layout = key
        self._building = True
        self._apply_color(fx)
        self._title.set_text(title_of(fx))
        self._wet.set_tooltip_text(wet_label(fx))
        wet = param_at(fx, IDX_WET)
        if wet:
            self._wet.set_value(float(wet.get("norm") or 0))
        on = param_at(fx, IDX_ON)
        engaged = float((on or {}).get("norm") or 0) >= 0.5
        self._foot.active = engaged
        self._foot.address = f"{role} → FX {self._slot} → On"
        self._set_engaged(engaged)
        specs = knob_specs(fx)
        for spec in specs:
            idx = spec["param"]
            knob = self._knobs.get(idx)
            if not knob:
                continue
            p = param_at(fx, idx)
            if p:
                knob.value = float(p.get("norm") or 0)
            knob.label = spec["label"]
            knob.address = f"{role} → FX {self._slot} → {spec['label']}"
            knob.queue_draw()
        sw_specs = switch_specs(fx)
        for spec in sw_specs:
            idx = spec["param"]
            sw = self._switches.get(idx)
            if not sw:
                continue
            p = param_at(fx, idx)
            if p:
                sw.value = float(p.get("norm") or 0)
            name = spec["label"]
            sw.set_label(name)
            sw.address = f"{role} → FX {self._slot} → {name}"
        self._building = False

    def _rebuild(self, fx: dict) -> None:
        clear(self._knob_box)
        clear(self._sw_box)
        self._knobs.clear()
        self._switches.clear()
        specs = knob_specs(fx)
        top_n, bot_n = knob_row_sizes(len(specs))
        self._knob_box.append(self._knob_row(fx, specs, 0, top_n))
        if bot_n:
            self._knob_box.append(self._knob_row(fx, specs, top_n, bot_n))
        sw_specs = switch_specs(fx)
        self._sw_box.set_visible(len(sw_specs) > 0)
        for spec in sw_specs:
            idx = spec["param"]
            p = param_at(fx, idx) or {}
            if spec["type"] == "multi":
                sw: Gtk.Widget = CycleSwitch(spec["label"], spec["steps"])
            else:
                sw = Switch(spec["label"])
                sw.set_size_request(56, 48)
            sw.value = float(p.get("norm") or 0)
            sw.on_change = lambda v, i=idx: self._emit(i, v)
            sw.on_hover = self._hover
            self._sw_box.append(sw)
            self._switches[idx] = sw

    def _knob_row(self, fx: dict, specs: list[dict], start: int, count: int) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_halign(Gtk.Align.CENTER)
        for i in range(start, start + count):
            spec = specs[i]
            idx = spec["param"]
            p = param_at(fx, idx) or {}
            norm = float(p.get("norm") or 0)
            if spec["type"] == "discrete":
                knob: Knob = DiscreteKnob(spec["label"], spec["steps"], norm, size=48)
            else:
                knob = Knob(spec["label"], "", 0, 1, norm, size=48)
            knob.on_change = lambda v, i=idx: self._emit(i, v)
            knob.on_hover = self._hover
            row.append(knob)
            self._knobs[idx] = knob
        return row

    def _set_engaged(self, on: bool) -> None:
        if on:
            self.remove_css_class("pedal-off")
        else:
            add_class(self, "pedal-off")

    def _apply_color(self, fx: dict) -> None:
        hexc = color_hex(fx)
        ctx = self.get_style_context()
        if hexc:
            if hexc == self._color:
                return
            if isinstance(self._color, int) and self._color >= 0:
                self.remove_css_class(f"pedal-c{self._color}")
            self._color = hexc
            css = f".pedal {{ background-color: {hexc}; }}"
            provider = Gtk.CssProvider()
            load_css_data(provider, css)
            if self._css is not None:
                ctx.remove_provider(self._css)
            ctx.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self._css = provider
            return
        index = color_index(fx)
        if index == self._color:
            return
        if self._css is not None:
            ctx.remove_provider(self._css)
            self._css = None
        if isinstance(self._color, int) and self._color >= 0:
            self.remove_css_class(f"pedal-c{self._color}")
        add_class(self, f"pedal-c{index}")
        self._color = index

    def _wet_changed(self, *_args) -> None:
        if self._building:
            return
        self._emit(IDX_WET, self._wet.get_value())

    def _on_toggled(self, on: bool) -> None:
        if self._building:
            return
        self._emit(IDX_ON, 1.0 if on else 0.0)
        self._set_engaged(on)

    def _emit(self, index: int, value: float) -> None:
        if self._building or self.on_param is None:
            return
        self.on_param(self._role, self._slot, index, value)

    def _hover(self, text: str) -> None:
        if self.on_hover:
            self.on_hover(text)
