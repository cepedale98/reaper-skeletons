"""Minimal OSC UDP client/server for REAPER, integrated with GLib.

python-osc is not required. Packets follow the OSC 1.0 spec closely enough
for REAPER's Default.ReaperOSC patterns.
"""

from __future__ import annotations

import socket
import struct
from collections.abc import Callable
from typing import Any

from skeletons.gi_init import GLib


def _pad(data: bytes) -> bytes:
    return data + b"\x00" * ((4 - (len(data) % 4)) % 4)


def pack_message(address: str, *args: Any) -> bytes:
    addr = _pad(address.encode("utf-8") + b"\x00")
    tags = [","]
    payload = b""
    for arg in args:
        if isinstance(arg, bool):
            tags.append("T" if arg else "F")
        elif isinstance(arg, int):
            tags.append("i")
            payload += struct.pack(">i", arg)
        elif isinstance(arg, float):
            tags.append("f")
            payload += struct.pack(">f", arg)
        elif isinstance(arg, str):
            tags.append("s")
            payload += _pad(arg.encode("utf-8") + b"\x00")
        else:
            raise TypeError(f"unsupported OSC type {type(arg)}")
    return addr + _pad("".join(tags).encode("ascii") + b"\x00") + payload


def unpack_string(data: bytes, offset: int) -> tuple[str, int]:
    end = data.find(b"\x00", offset)
    if end < 0:
        raise ValueError("unterminated OSC string")
    text = data[offset:end].decode("utf-8", errors="replace")
    end += 1
    end += (4 - (end % 4)) % 4
    return text, end


def unpack_message(data: bytes) -> tuple[str, list[Any]]:
    address, offset = unpack_string(data, 0)
    if offset >= len(data) or data[offset:offset + 1] != b",":
        return address, []
    tags, offset = unpack_string(data, offset)
    args: list[Any] = []
    for tag in tags[1:]:
        if tag == "i":
            args.append(struct.unpack(">i", data[offset:offset + 4])[0])
            offset += 4
        elif tag == "f":
            args.append(struct.unpack(">f", data[offset:offset + 4])[0])
            offset += 4
        elif tag == "s":
            s, offset = unpack_string(data, offset)
            args.append(s)
        elif tag == "T":
            args.append(True)
        elif tag == "F":
            args.append(False)
        elif tag == "N":
            args.append(None)
    return address, args


class OscBridge:
    def __init__(
        self,
        send_host: str = "127.0.0.1",
        send_port: int = 8000,
        listen_port: int = 9000,
    ):
        self.send_addr = (send_host, send_port)
        self.listen_port = listen_port
        self._sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock_in: socket.socket | None = None
        self._handlers: dict[str, list[Callable[[str, list[Any]], None]]] = {}
        self._watch: int | None = None
        self.available = False
        self.error: str | None = None

    def start(self) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", self.listen_port))
            sock.setblocking(False)
            self._sock_in = sock
            self._watch = GLib.io_add_watch(sock.fileno(), GLib.IO_IN, self._on_readable)
            self.available = True
            self.error = None
        except OSError as exc:
            self.available = False
            self.error = f"OSC listen {self.listen_port}: {exc}"

    def stop(self) -> None:
        if self._watch is not None:
            GLib.source_remove(self._watch)
            self._watch = None
        if self._sock_in is not None:
            self._sock_in.close()
            self._sock_in = None

    def send(self, address: str, *args: Any) -> None:
        packet = pack_message(address, *args)
        try:
            self._sock_out.sendto(packet, self.send_addr)
        except OSError:
            pass

    def on(self, prefix: str, handler: Callable[[str, list[Any]], None]) -> None:
        self._handlers.setdefault(prefix, []).append(handler)

    def set_fx_param(self, track_osc: int, fx_osc: int, param_osc: int, value: float) -> None:
        self.send(f"/track/{track_osc}/fx/{fx_osc}/fxparam/{param_osc}/value", float(value))

    def set_fx_bypass(self, track_osc: int, fx_osc: int, bypassed: bool) -> None:
        self.send(f"/track/{track_osc}/fx/{fx_osc}/bypass", bypassed)

    def fx_preset_next(self, track_osc: int, fx_osc: int) -> None:
        self.send(f"/track/{track_osc}/fx/{fx_osc}/preset+")

    def fx_preset_prev(self, track_osc: int, fx_osc: int) -> None:
        self.send(f"/track/{track_osc}/fx/{fx_osc}/preset-")

    def _on_readable(self, _fd, _cond) -> bool:
        if self._sock_in is None:
            return False
        try:
            data, _ = self._sock_in.recvfrom(4096)
        except BlockingIOError:
            return True
        except OSError:
            return True
        try:
            address, args = unpack_message(data)
        except (ValueError, struct.error):
            return True
        for prefix, handlers in self._handlers.items():
            if address.startswith(prefix):
                for handler in handlers:
                    handler(address, args)
        return True
