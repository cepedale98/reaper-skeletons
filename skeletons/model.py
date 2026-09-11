"""Single source of truth for one launcher's view of REAPER."""

from __future__ import annotations

import json
from typing import Any

from skeletons.gi_init import GLib

from skeletons import LEGACY_SECTION, SECTION
from skeletons.bridge.http import HttpBridge
from skeletons.bridge.indices import Indices
from skeletons.bridge.osc import OscBridge
from skeletons.config import load as load_cfg, push_to_agent
from skeletons.presets import load_banks, load_presets


class RigModel:
    POLL_MS = 100

    def __init__(self, instrument: str, http: HttpBridge | None = None, osc: OscBridge | None = None):
        self.instrument = instrument
        self.cfg = load_cfg()
        self.http = http or HttpBridge(str(self.cfg["http_host"]), int(self.cfg["http_port"]))
        self.osc = osc or OscBridge(
            send_port=int(self.cfg["osc_send_port"]),
            listen_port=int(self.cfg["osc_listen_port"]),
        )
        self.indices = Indices()
        self.seq = 0
        self.state: dict[str, Any] = {}
        self.presets = load_presets(instrument)
        self.banks = load_banks()
        self._tick_id: int | None = None
        self.listeners: list = []
        self._pushed_paths = False

    def start(self) -> None:
        self.osc.start()
        push_to_agent(self.cfg, self.http)
        self._pushed_paths = True
        self._tick()
        self._tick_id = GLib.timeout_add(self.POLL_MS, self._tick)

    def stop(self) -> None:
        if self._tick_id is not None:
            GLib.source_remove(self._tick_id)
            self._tick_id = None
        self.osc.stop()

    def on_change(self, cb) -> None:
        self.listeners.append(cb)

    def _emit(self) -> None:
        for cb in self.listeners:
            cb()

    def _tick(self) -> bool:
        extra = [
            f"GET/EXTSTATE/{SECTION}/state.{self.instrument}",
            f"GET/EXTSTATE/{LEGACY_SECTION}/state.{self.instrument}",
            f"GET/EXTSTATE/{SECTION}/agent.alive",
            f"GET/EXTSTATE/{LEGACY_SECTION}/agent.alive",
        ]
        self.http.poll(extra)
        raw = self.http.extstate.get((SECTION, f"state.{self.instrument}"), "") or self.http.extstate.get(
            (LEGACY_SECTION, f"state.{self.instrument}"), ""
        )
        if raw:
            try:
                self.state = json.loads(raw)
            except json.JSONDecodeError:
                pass
        self._emit()
        return True

    @property
    def alive(self) -> bool:
        return self.http.status.alive

    @property
    def agent_alive(self) -> bool:
        return bool(
            self.http.extstate.get((SECTION, "agent.alive"))
            or self.http.extstate.get((LEGACY_SECTION, "agent.alive"))
        )

    @property
    def degraded(self) -> str | None:
        if not self.alive:
            return self.http.status.error or "REAPER is not running, or the HTTP control surface is off (port 8080)."
        if not self.agent_alive:
            return (
                "HTTP is up but skel_agent.lua is not running. Restart REAPER so "
                "Scripts/__startup.lua loads it, or Actions → Load ReaScript on "
                "Scripts/Skeletons/skel_agent.lua."
            )
        missing = self.state.get("missing") or []
        if missing:
            return (
                "Role-tagged tracks missing: "
                + ", ".join(missing)
                + ". Open project/Skeletons.RPP or insert TrackTemplates/SkeletonsGuitar/SkeletonsGuitar.RTrackTemplate."
            )
        tracks = self.state.get("tracks") or {}
        if not tracks:
            return "Agent is running but published no tracks for this instrument. Load the skeleton project or insert the track template."
        return None

    def send_cmd(self, op: str, **payload: Any) -> None:
        self.seq += 1
        body = {"seq": self.seq, "op": op, **payload}
        self.http.set_extstate(f"cmd.{self.instrument}", json.dumps(body, separators=(",", ":")))

    def apply_preset(self, preset_id: str) -> None:
        self.send_cmd("apply_preset", id=preset_id)

    def select_role(self, role: str) -> None:
        self.send_cmd("select", role=role)

    def track_for(self, role: str) -> dict | None:
        return (self.state.get("tracks") or {}).get(role)

    def http_track(self, role: str):
        info = self.track_for(role)
        if not info:
            return None
        return self.http.tracks.get(info.get("web_index"))

    def live_residency(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for role, info in (self.state.get("tracks") or {}).items():
            for fx in info.get("fx") or []:
                if fx.get("ratatouille") and fx.get("residency"):
                    out[role] = dict(fx["residency"])
                    break
        return out

    def current_preset(self) -> dict | None:
        pid = self.state.get("current_preset")
        if pid:
            for p in self.presets:
                if p.get("id") == pid:
                    return p
        return self.presets[0] if self.presets else None
