"""Batched REAPER web-control client.

REAPER's HTTP surface answers `GET /_/;CMD1;CMD2` with tab-separated plaintext.
Unrecognized commands are silently dropped; we detect liveness by whether a
TRANSPORT line comes back.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

from skeletons import LEGACY_SECTION, SECTION


def simple_unescape(value: str) -> str:
    return (
        value.replace("\\\\", "\x00")
        .replace("\\t", "\t")
        .replace("\\n", "\n")
        .replace("\x00", "\\")
    )


@dataclass
class Transport:
    playstate: int = 0
    position: float = 0.0
    repeat: bool = False
    position_str: str = ""
    beats_str: str = ""

    @property
    def playing(self) -> bool:
        return bool(self.playstate & 1)


@dataclass
class TrackSnapshot:
    number: int
    name: str
    flags: int
    volume: float
    pan: float
    peak: int
    hold: int
    width: float
    panmode: int
    sendcnt: int
    recvcnt: int
    hwoutcnt: int
    color: int

    @property
    def muted(self) -> bool:
        return bool(self.flags & 8)

    @property
    def soloed(self) -> bool:
        return bool(self.flags & 16)

    @property
    def recarmed(self) -> bool:
        return bool(self.flags & 64)

    @property
    def folder(self) -> bool:
        return bool(self.flags & 1)

    @property
    def peak_db(self) -> float:
        return self.peak / 10.0


@dataclass
class HttpStatus:
    alive: bool = False
    error: str | None = None
    last_rtt_ms: float = 0.0


class HttpBridge:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080, timeout: float = 0.4):
        self.base = f"http://{host}:{port}"
        self.timeout = timeout
        self.status = HttpStatus()
        self.transport = Transport()
        self.tracks: dict[int, TrackSnapshot] = {}
        self.extstate: dict[tuple[str, str], str] = {}
        self.ntrack = 0
        self._on_update: list[Callable[[], None]] = []

    def on_update(self, cb: Callable[[], None]) -> None:
        self._on_update.append(cb)

    def _notify(self) -> None:
        for cb in self._on_update:
            cb()

    def request(self, commands: list[str]) -> list[str]:
        cleaned = [c for c in commands if c]
        if not cleaned:
            return []
        path = "/_/" + ";".join(cleaned)
        url = self.base + path
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            self.status.alive = True
            self.status.error = None
            return [ln for ln in body.split("\n") if ln]
        except urllib.error.URLError as exc:
            self.status.alive = False
            self.status.error = f"HTTP surface not responding on {self.base} ({exc.reason})"
            return []
        except Exception as exc:  # noqa: BLE001
            self.status.alive = False
            self.status.error = str(exc)
            return []

    def probe(self) -> dict:
        """One-shot check: TRANSPORT must come back; agent.alive is ExtState."""
        self.poll()
        return {
            "alive": self.status.alive,
            "error": self.status.error,
            "ntrack": self.ntrack,
            "agent_alive": bool(
                self.extstate.get((SECTION, "agent.alive"))
                or self.extstate.get((LEGACY_SECTION, "agent.alive"))
            ),
            "agent_value": self.extstate.get((SECTION, "agent.alive"), "")
            or self.extstate.get((LEGACY_SECTION, "agent.alive"), ""),
        }

    def poll(self, extra: list[str] | None = None) -> None:
        cmds = ["TRANSPORT", "NTRACK"]
        n = min(self.ntrack, 32) if self.ntrack else 16
        cmds.extend(f"TRACK/{i}" for i in range(1, n + 1))
        cmds.append(f"GET/EXTSTATE/{SECTION}/agent.alive")
        cmds.append(f"GET/EXTSTATE/{LEGACY_SECTION}/agent.alive")
        if extra:
            cmds.extend(extra)
        lines = self.request(cmds)
        saw_transport = False
        for line in lines:
            self._parse(line)
            if line.startswith("TRANSPORT"):
                saw_transport = True
        if lines and not saw_transport:
            self.status.alive = False
            self.status.error = "REAPER answered but sent no TRANSPORT line"
        self._notify()

    def _parse(self, line: str) -> None:
        parts = line.split("\t")
        kind = parts[0]
        if kind == "TRANSPORT" and len(parts) >= 6:
            self.transport = Transport(
                playstate=int(parts[1] or 0),
                position=float(parts[2] or 0),
                repeat=parts[3] == "1",
                position_str=simple_unescape(parts[4]),
                beats_str=simple_unescape(parts[5]),
            )
        elif kind == "NTRACK" and len(parts) >= 2:
            self.ntrack = int(parts[1] or 0)
        elif kind == "TRACK" and len(parts) >= 14:
            num = int(parts[1])
            self.tracks[num] = TrackSnapshot(
                number=num,
                name=simple_unescape(parts[2]),
                flags=int(parts[3] or 0),
                volume=float(parts[4] or 0),
                pan=float(parts[5] or 0),
                peak=int(float(parts[6] or 0)),
                hold=int(float(parts[7] or 0)),
                width=float(parts[8] or 0),
                panmode=int(float(parts[9] or 0)),
                sendcnt=int(parts[10] or 0),
                recvcnt=int(parts[11] or 0),
                hwoutcnt=int(parts[12] or 0),
                color=int(parts[13] or 0),
            )
        elif kind == "EXTSTATE" and len(parts) >= 4:
            self.extstate[(parts[1], parts[2])] = simple_unescape(parts[3])

    def get_extstate(self, key: str, section: str = SECTION) -> str:
        lines = self.request([f"GET/EXTSTATE/{section}/{key}"])
        for line in lines:
            self._parse(line)
        value = self.extstate.get((section, key), "")
        if value or section == LEGACY_SECTION:
            return value
        return self.get_extstate(key, LEGACY_SECTION)

    def set_extstate(self, key: str, value: str, section: str = SECTION) -> None:
        encoded = urllib.parse.quote(value, safe="")
        self.request([f"SET/EXTSTATE/{section}/{key}/{encoded}"])

    def set_track_vol(self, web_index: int, value: float) -> None:
        self.request([f"SET/TRACK/{web_index}/VOL/{value}"])

    def set_track_mute(self, web_index: int, value: int) -> None:
        self.request([f"SET/TRACK/{web_index}/MUTE/{value}"])

    def action(self, cmd: str | int) -> None:
        self.request([str(cmd)])

    def osc(self, address: str, value: float | str | None = None) -> None:
        if value is None:
            self.request([f"OSC{address}"])
        elif isinstance(value, str):
            self.request([f"OSC{address}:s{urllib.parse.quote(value)}"])
        else:
            self.request([f"OSC{address}:{value}"])
