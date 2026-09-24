"""Guitar control surface."""

from __future__ import annotations

import math
import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from skeletons.gi_init import Gdk, Gtk, Pango

from skeletons.bridge.indices import Indices
from skeletons.gtkutil import add_class, clear
from skeletons.model import RigModel
from skeletons.presets import load_set
from skeletons.shell.application import run_app
from skeletons.shell.window import AppWindow
from skeletons.widgets.fileslot import FileSlot
from skeletons.widgets.knob import Knob
from skeletons.widgets.param import grouped_params
from skeletons.widgets.slider import Slider
from skeletons.widgets.spin import Spin
from skeletons.widgets.switch import Switch

TABS = [
    ("guitar.input", "IN"),
    ("guitar.pedals", "PEDALS"),
    ("guitar.amp", "AMP"),
    ("guitar.cabinet", "CAB"),
    ("guitar.fx", "FX"),
]


def is_utility_fx(fx: dict) -> bool:
    if fx.get("utility") or fx.get("tuner") or fx.get("scope") or fx.get("live") or fx.get("control"):
        return True
    if fx.get("panel"):
        return True
    blob = f"{fx.get('name') or ''} {fx.get('ident') or ''}".lower()
    return any(
        n in blob
        for n in (
            "skel_tuner",
            "skel_scope",
            "skel_live",
            "skel_control",
            "skeletons control",
            "skel_panel_pedal",
            "skeletons pedal",
            "rapp_tuner",
            "rapp_scope",
            "rapp_live",
            "rapp_control",
            "reaperapp control",
            "rapp_panel_pedal",
            "reaperapp pedal",
            "reatune",
        )
    )

IDX = Indices()
RATA_AMP_KEYS = ["input_a", "input_b", "blend", "output"]
RATA_CAB_KEYS = ["ir_mix"]


def gain_to_db(gain: float) -> float:
    if gain <= 1e-8:
        return -60.0
    return 20.0 * math.log10(gain)


def db_to_gain(db: float) -> float:
    return 10 ** (db / 20.0)


def find_rata(fxlist: list[dict]) -> dict | None:
    for fx in fxlist:
        if fx.get("ratatouille"):
            return fx
    return None


def find_pedals(fxlist: list[dict]) -> list[dict]:
    out: list[dict] = []
    for fx in fxlist:
        if fx.get("panel") == "pedal":
            out.append(fx)
            continue
        blob = f"{fx.get('name') or ''} {fx.get('ident') or ''}".lower()
        if "skel_panel_pedal" in blob or "skeletons pedal" in blob or "rapp_panel_pedal" in blob or "reaperapp pedal" in blob:
            out.append(fx)
    return out


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


class FxCard(Gtk.Box):
    def __init__(self, model: RigModel, role: str, show_addr: callable):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        add_class(self, "card")
        add_class(self, "fx-card")
        self.set_hexpand(True)
        self.set_halign(Gtk.Align.FILL)
        self.model = model
        self.role = role
        self.show_addr = show_addr

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        add_class(head, "fx-header")
        head.set_hexpand(True)
        self.title = Gtk.Label()
        add_class(self.title, "card-title")
        self.title.set_xalign(0)
        self.title.set_hexpand(True)
        self.title.set_ellipsize(Pango.EllipsizeMode.END)
        self.enable = Gtk.Switch()
        self.enable.set_valign(Gtk.Align.CENTER)
        self.enable.connect("notify::active", self._enabled)
        head.append(self.title)
        head.append(self.enable)
        self.append(head)

        self.sub = Gtk.Label()
        add_class(self.sub, "card-sub")
        self.sub.set_xalign(0)
        self.sub.set_ellipsize(Pango.EllipsizeMode.END)
        self.append(self.sub)

        self.ctrl_row = Gtk.FlowBox()
        add_class(self.ctrl_row, "fx-controls")
        self.ctrl_row.set_selection_mode(Gtk.SelectionMode.NONE)
        self.ctrl_row.set_max_children_per_line(16)
        self.ctrl_row.set_min_children_per_line(1)
        self.ctrl_row.set_homogeneous(False)
        self.ctrl_row.set_hexpand(True)
        self.ctrl_row.set_halign(Gtk.Align.CENTER)
        self.ctrl_row.set_column_spacing(8)
        self.ctrl_row.set_row_spacing(8)
        self.append(self.ctrl_row)

        self.slots = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.append(self.slots)
        self.trunc = Gtk.Label()
        add_class(self.trunc, "hint")
        self.trunc.set_xalign(0)
        self.append(self.trunc)

        self._file_a = FileSlot("Model A", "nam")
        self._file_b = FileSlot("Model B", "nam")
        self._ir_a = FileSlot("IR A", "ir")
        self._ir_b = FileSlot("IR B", "ir")
        self._fx_index = 0
        self._ident = ""
        self._building = False
        self._built_for: tuple | None = None
        self._widgets: dict[int, Gtk.Widget] = {}
        self._rata: dict[str, Gtk.Widget] = {}

    def bind(self, fx: dict, show_addresses: bool, mode: str = "auto") -> None:
        self._building = True
        self._fx_index = fx.get("slot", 0)
        self._ident = fx.get("ident") or fx.get("name") or ""
        raw_name = (fx.get("name") or "FX").split(":")[-1].strip()
        self.title.set_text(raw_name)
        addr = f"{self.role} → FX {self._fx_index} · {self._ident}"
        self.sub.set_text(addr if show_addresses else "")
        self.sub.set_visible(show_addresses)
        enabled = fx.get("enabled", True)
        self.enable.handler_block_by_func(self._enabled)
        self.enable.set_active(bool(enabled))
        self.enable.handler_unblock_by_func(self._enabled)

        nparams = int(fx.get("nparams") or 0)
        shown = len(fx.get("params") or [])
        if fx.get("truncated") or (nparams and nparams > shown):
            self.trunc.set_text(f"showing {shown} of {nparams} parameters")
            self.trunc.set_visible(True)
        else:
            self.trunc.set_text("")
            self.trunc.set_visible(False)

        key = self._layout_key(fx, mode)
        if fx.get("ratatouille") and mode in ("auto", "amp", "cab", "rata"):
            if key != self._built_for:
                self._rebuild_rata(fx, mode)
                self._built_for = key
            self._update_rata(fx, mode)
            self._building = False
            return

        if key != self._built_for:
            self._rebuild_params(fx)
            self._built_for = key
        self._update_params(fx)
        self.slots.set_visible(False)
        self._building = False

    def _layout_key(self, fx: dict, mode: str) -> tuple:
        if fx.get("ratatouille") and mode in ("auto", "amp", "cab", "rata"):
            keys = tuple(sorted((fx.get("controls") or {}).keys()))
            return ("rata", mode, self._fx_index, self._ident, keys)
        grouped = grouped_params(fx.get("params") or [])
        names = tuple((kind, p.get("index"), p.get("name")) for kind, p in grouped)
        return ("params", mode, self._fx_index, self._ident, names)

    def _add_widget(self, widget: Gtk.Widget) -> None:
        widget.set_halign(Gtk.Align.CENTER)
        widget.set_valign(Gtk.Align.CENTER)
        self.ctrl_row.append(widget)

    def _rebuild_params(self, fx: dict) -> None:
        clear(self.ctrl_row)
        self._widgets.clear()
        self._rata.clear()
        for kind, p in grouped_params(fx.get("params") or []):
            w = self._make_control(kind, p)
            self._widgets[p.get("index", 0)] = w
            self._add_widget(w)

    def _update_params(self, fx: dict) -> None:
        for p in fx.get("params") or []:
            w = self._widgets.get(p.get("index"))
            if w is None:
                continue
            if hasattr(w, "set_text"):
                w.set_text(p.get("text") or "")
            w.value = p.get("norm") or 0
            name = (p.get("name") or "").strip()
            text = p.get("text") or ""
            w.address = f"{self.role} → FX {self._fx_index} ({self._ident}) → {name} = {text}"

    def _make_control(self, kind: str, p: dict) -> Gtk.Widget:
        idx = p.get("index", 0)
        name = (p.get("name") or f"p{idx}").strip()
        text = p.get("text") or ""
        addr = f"{self.role} → FX {self._fx_index} ({self._ident}) → {name} = {text}"
        if kind == "switch":
            w = Switch(name)
            w.value = p.get("norm") or 0
            w.address = addr
            w.on_change = lambda v, i=idx: self._param(i, v)
            w.on_hover = self.show_addr
            return w
        if kind == "knob":
            w = Knob(name, "", 0, 1, p.get("norm") or 0, size=48)
            w.value = p.get("norm") or 0
            w.address = addr
            w.on_change = lambda v, i=idx: self._param(i, v)
            w.on_hover = self.show_addr
            return w
        if kind == "spin":
            pmin = float(p.get("min") if p.get("min") is not None else 0)
            pmax = float(p.get("max") if p.get("max") is not None else 1)
            step = float(p.get("step") or 1)
            w = Spin(name, pmin, pmax, step)
            w.value = p.get("norm") or 0
            w.address = addr
            w.on_change = lambda v, i=idx: self._param(i, v)
            w.on_hover = self.show_addr
            return w
        w = Slider(name)
        w.value = p.get("norm") or 0
        w.set_text(text)
        w.address = addr
        w.on_change = lambda v, i=idx: self._param(i, v)
        w.on_hover = self.show_addr
        return w

    def _rata_keys(self, mode: str) -> list[str]:
        if mode == "cab":
            return list(RATA_CAB_KEYS)
        if mode == "amp":
            return list(RATA_AMP_KEYS)
        return ["input_a", "blend", "output"]

    def _rebuild_rata(self, fx: dict, mode: str) -> None:
        clear(self.ctrl_row)
        self._widgets.clear()
        self._rata.clear()
        controls = fx.get("controls") or {}
        for key in self._rata_keys(mode):
            if key not in controls:
                continue
            fake = {"name": key.replace("_", " ")}
            kind = grouped_params([fake])[0][0]
            lo, hi, unit = (-20, 20, " dB") if "input" in key or key == "output" else (0, 1, "")
            if kind == "knob":
                w = Knob(key.replace("_", " "), unit, lo, hi, controls[key], size=48)
                w.on_change = lambda v, k=key: self._rata(k, v)
            else:
                w = Slider(key.replace("_", " "))
                span = hi - lo
                w.value = 0 if span <= 0 else (controls[key] - lo) / span
                w.on_change = lambda v, k=key, a=lo, b=hi: self._rata(k, a + v * (b - a))
            w.address = f"{self.role} → FX {self._fx_index} ({self._ident}) → {key}"
            w.on_hover = self.show_addr
            self._rata[key] = w
            self._add_widget(w)
        if mode == "cab":
            pairs = ((self._ir_a, "ir_a", "ir_norm_a"), (self._ir_b, "ir_b", "ir_norm_b"))
        elif mode == "amp":
            pairs = ((self._file_a, "model_a", "model_norm_a"), (self._file_b, "model_b", "model_norm_b"))
        else:
            pairs = (
                (self._file_a, "model_a", "model_norm_a"),
                (self._file_b, "model_b", "model_norm_b"),
                (self._ir_a, "ir_a", "ir_norm_a"),
                (self._ir_b, "ir_b", "ir_norm_b"),
            )
        clear(self.slots)
        for slotw, key, norm_key in pairs:
            slotw.on_normalize = lambda on, k=norm_key: self._rata(k, 1.0 if on else 0.0)
            self.slots.append(slotw)
        self.slots.set_visible(True)

    def _update_rata(self, fx: dict, mode: str) -> None:
        controls = fx.get("controls") or {}
        for key in self._rata_keys(mode):
            w = self._rata.get(key)
            if w is None or key not in controls:
                continue
            lo, hi = (-20, 20) if "input" in key or key == "output" else (0, 1)
            raw = controls[key]
            if isinstance(w, Knob):
                w.value = raw
            else:
                span = hi - lo
                w.value = 0 if span <= 0 else (raw - lo) / span
            w.address = f"{self.role} → FX {self._fx_index} ({self._ident}) → {key}"
        res = fx.get("residency") or {}
        if mode == "cab":
            pairs = ((self._ir_a, "ir_a", "ir_norm_a"), (self._ir_b, "ir_b", "ir_norm_b"))
        elif mode == "amp":
            pairs = ((self._file_a, "model_a", "model_norm_a"), (self._file_b, "model_b", "model_norm_b"))
        else:
            pairs = (
                (self._file_a, "model_a", "model_norm_a"),
                (self._file_b, "model_b", "model_norm_b"),
                (self._ir_a, "ir_a", "ir_norm_a"),
                (self._ir_b, "ir_b", "ir_norm_b"),
            )
        for slotw, key, norm_key in pairs:
            slotw.set_path(res.get(key))
            slotw.set_normalized(bool(controls.get(norm_key)))
        self.slots.set_visible(True)

    def _enabled(self, *_args) -> None:
        if self._building:
            return
        engaged = self.enable.get_active()
        self.model.send_cmd("set_fx_enabled", role=self.role, fx=self._fx_index, value=engaged)
        info = self.model.track_for(self.role)
        if info:
            self.model.osc.set_fx_bypass(
                IDX.reaper_to_osc(info["index"]),
                IDX.reaper_fx_to_osc(self._fx_index),
                not engaged,
            )

    def _rata(self, control: str, value: float) -> None:
        if self._building:
            return
        self.model.send_cmd("set_rata", role=self.role, fx=self._fx_index, control=control, value=value)

    def _param(self, index: int, value: float) -> None:
        if self._building:
            return
        self.model.send_cmd("set_param", role=self.role, fx=self._fx_index, index=index, value=value)
        info = self.model.track_for(self.role)
        if info:
            self.model.osc.set_fx_param(
                IDX.reaper_to_osc(info["index"]),
                IDX.reaper_fx_to_osc(self._fx_index),
                IDX.reaper_param_to_osc(index),
                value,
            )


class RolePage(Gtk.Box):
    def __init__(self, model: RigModel, role: str, label: str, show_addr: callable, addr_on: callable):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(8)
        self.model = model
        self.role = role
        self.show_addr = show_addr
        self.addr_on = addr_on

        self.heading = Gtk.Button(label=label)
        add_class(self.heading, "section-title")
        add_class(self.heading, "panel-title")
        self.heading.set_has_frame(False)
        self.heading.set_halign(Gtk.Align.START)
        self.heading.set_tooltip_text("Select this track in REAPER")
        self.heading.connect("clicked", lambda *_: model.select_role(role))
        self.append(self.heading)

        self.cards_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.cards_box.set_halign(Gtk.Align.FILL)
        self.cards_box.set_hexpand(True)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.set_overlay_scrolling(False)
        scroll.set_child(self.cards_box)
        self.append(scroll)
        self.empty = Gtk.Label(label="Add plugins on this track in REAPER.")
        add_class(self.empty, "empty-hint")
        self.empty.set_wrap(True)
        self.empty.set_justify(Gtk.Justification.CENTER)
        self.empty.set_halign(Gtk.Align.CENTER)
        self.append(self.empty)
        self._cards: list[FxCard] = []

    def refresh(self) -> None:
        info = self.model.track_for(self.role)
        if not info:
            self.heading.set_opacity(0.45)
            self.empty.set_text(f'Track "{self.role}" is missing from the skeleton')
            self.empty.set_visible(True)
            return
        self.heading.set_opacity(1.0)
        name = info.get("name") or self.role
        self.heading.set_tooltip_text(f"Select {name} in REAPER")

        fxlist = info.get("fx") or []
        show_addr = self.addr_on()
        display, modes = self._layout(fxlist)
        while len(self._cards) < len(display):
            card = FxCard(self.model, self.role, self.show_addr)
            self._cards.append(card)
            self.cards_box.append(card)
        for i, fx in enumerate(display):
            bind_role = fx.get("_bind_role") or self.role
            card = self._cards[i]
            card.role = bind_role
            card.bind(fx, show_addresses=show_addr, mode=modes[i])
            card.set_visible(True)
        for j in range(len(display), len(self._cards)):
            self._cards[j].set_visible(False)
        self.empty.set_visible(not display)

    def _layout(self, fxlist: list[dict]) -> tuple[list[dict], list[str]]:
        hosted = [f for f in fxlist if not is_utility_fx(f)]
        rata = find_rata(fxlist)
        if self.role == "guitar.amp":
            items, modes = [], []
            if rata:
                items.append(rata)
                modes.append("amp")
            extras = [f for f in hosted if f is not rata]
            items.extend(extras)
            modes.extend(["auto"] * len(extras))
            return items, modes
        if self.role == "guitar.cabinet":
            items, modes = [], []
            local = find_rata(fxlist)
            if local:
                items.append(local)
                modes.append("cab")
            else:
                amp = self.model.track_for("guitar.amp")
                amp_rata = find_rata((amp or {}).get("fx") or [])
                if amp_rata:
                    amp_rata = dict(amp_rata)
                    amp_rata["_bind_role"] = "guitar.amp"
                    items.append(amp_rata)
                    modes.append("cab")
            extras = [f for f in hosted if f is not local]
            items.extend(extras)
            modes.extend(["auto"] * len(extras))
            return items, modes
        return hosted, ["auto"] * len(hosted)


class SkeletonsGuitar:
    def __init__(self, gtk_app: Gtk.Application):
        self.model = RigModel("guitar")
        self._set = load_set("guitar")
        self.pages: dict[str, RolePage] = {}
        self.win = AppWindow("Skeletons Guitar", TABS, self._make_page, application=gtk_app)
        self.win.connect("close-request", self._on_close)
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._keys)
        self.win.add_controller(keys)
        self._freq_hist: deque[float] = deque(maxlen=5)
        self._cents_hist: deque[float] = deque(maxlen=5)
        self.win.in_rail.level.on_change = lambda v: self._vol("guitar.input", v)
        self.win.out_rail.level.on_change = lambda v: self._vol("guitar.bus", v)
        self.win.footer.info_btn.connect("toggled", lambda *_: self.refresh())
        self.win.live.on_param = self._live_param
        self.win.live.on_preset = self.model.apply_preset
        self.win.live.on_hover = self._show_addr
        chained_tab = self.win.tabs.on_select

        def _on_tab(role: str) -> None:
            if chained_tab:
                chained_tab(role)
            info = self.model.track_for(role)
            self.win.live.bind(find_pedals((info or {}).get("fx") or []), role)

        self.win.tabs.on_select = _on_tab
        self.model.on_change(self.refresh)
        self.model.start()
        self.refresh()

    def _on_close(self, *_args) -> bool:
        self.model.stop()
        return False

    def _show_addr(self, text: str) -> None:
        self.win.status.set_address(text)

    def _addr_on(self) -> bool:
        return self.win.footer.info_btn.get_active()

    def _make_page(self, role: str) -> Gtk.Widget:
        label = dict(TABS).get(role, role)
        page = RolePage(self.model, role, label, self._show_addr, self._addr_on)
        self.pages[role] = page
        return page

    def _vol(self, role: str, db: float) -> None:
        info = self.model.track_for(role)
        if not info:
            return
        gain = db_to_gain(db)
        self.model.send_cmd("set_vol", role=role, gain=gain)
        self.model.http.set_track_vol(info["web_index"], gain)

    def _live_param(self, role: str, fx: int, index: int, value: float) -> None:
        self.model.send_cmd("set_param", role=role, fx=fx, index=index, value=value)
        info = self.model.track_for(role)
        if info:
            self.model.osc.set_fx_param(
                IDX.reaper_to_osc(info["index"]),
                IDX.reaper_fx_to_osc(fx),
                IDX.reaper_param_to_osc(index),
                value,
            )

    def _keys(self, _controller, keyval: int, _keycode: int, state: Gdk.ModifierType) -> bool:
        if state & Gdk.ModifierType.CONTROL_MASK:
            if keyval in (Gdk.KEY_z, Gdk.KEY_Z):
                self.model.send_cmd("undo")
                return True
            if keyval in (Gdk.KEY_y, Gdk.KEY_Y):
                self.model.send_cmd("redo")
                return True
        return False

    def refresh(self) -> None:
        deg = self.model.degraded
        self.win.show_banner(deg)
        ok = self.model.alive and self.model.agent_alive
        self.win.status.set_agent(self.model.agent_alive)
        pid = self.model.state.get("current_preset") or None
        preset_name = None
        if pid:
            for preset in self.model.presets:
                if preset.get("id") == pid:
                    preset_name = preset.get("label") or pid
                    break
            preset_name = preset_name or pid
        self.win.status.set_preset(preset_name)
        self.win.live.show_set(self._set.get("pages") or [], pid, self.model.presets)
        if ok:
            self.win.status.set_status("REAPER: connected ●", True)
        elif self.model.alive:
            self.win.status.set_status("REAPER: HTTP only — agent down", False)
        else:
            self.win.status.set_status("REAPER: disconnected", False)

        tuner = self.model.state.get("tuner") or {}
        freq = float(tuner.get("freq") or 0)
        cents = float(tuner.get("cents") or 0)
        if freq > 0:
            self._freq_hist.append(freq)
            self._cents_hist.append(cents)
        freq_s = median(list(self._freq_hist)) if self._freq_hist else 0.0
        cents_s = median(list(self._cents_hist)) if self._cents_hist else 0.0
        note = float(tuner.get("note") or -1)
        level = float(tuner.get("level") or 0)
        self.win.tuner.update(freq_s, cents_s, note, level)
        self.win.footer.tuner_strip.update(freq_s, cents_s, note, level)

        scope = self.model.state.get("scope") or {}
        self.win.scope.update(list(scope.get("samples") or []), float(scope.get("peak") or 0))

        in_tr = self.model.http_track("guitar.input")
        bus_tr = self.model.http_track("guitar.bus")
        if in_tr:
            self.win.in_rail.meter.set_db(in_tr.peak_db)
            self.win.in_rail.level.value = gain_to_db(in_tr.volume)
        if bus_tr:
            self.win.out_rail.meter.set_db(bus_tr.peak_db)
            self.win.out_rail.level.value = gain_to_db(bus_tr.volume)

        self.win.tabs.set_send("guitar.fx", None)

        role = self.win.tabs.active or "guitar.input"
        tab_info = self.model.track_for(role)
        self.win.live.bind(find_pedals((tab_info or {}).get("fx") or []), role)

        missing = set(self.model.state.get("missing") or [])

        for role, page in self.pages.items():
            page.refresh()
            self.win.tabs.set_dimmed(role, role in missing)
            info = self.model.track_for(role)
            if info:
                fx = info.get("fx") or []
                all_off = fx and not any(f.get("enabled", True) for f in fx)
                if all_off:
                    self.win.tabs.set_dimmed(role, True)

        arming = self.model.state.get("arming")
        if arming:
            self.win.status.set_address(f"arming bank {arming.get('bank')}…")
        warnings = self.model.state.get("warnings") or []
        if warnings and not arming:
            self.win.status.set_address(str(warnings[0]))


def main() -> None:
    holder: dict[str, SkeletonsGuitar] = {}

    def build(gtk_app: Gtk.Application) -> Gtk.Window:
        holder["app"] = SkeletonsGuitar(gtk_app)
        return holder["app"].win

    raise SystemExit(run_app("org.skeletons.guitar", build))


if __name__ == "__main__":
    main()
