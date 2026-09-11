"""Environment and REAPER-integration checks used by the CLI."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from skeletons.export import (
    export_status,
    relative_dest,
    resource_dir,
    startup_ok,
    startup_path,
)
from skeletons.paths import repo_root


class Report:
    def __init__(self) -> None:
        self.ok = 0
        self.fail = 0
        self.warn = 0

    def _print(self, tag: str, label: str, detail: str) -> None:
        extra = f"  ({detail})" if detail and tag == "OK" else (f"  — {detail}" if detail else "")
        print(f"  {tag:<5} {label}{extra}")

    def good(self, label: str, detail: str = "") -> None:
        self.ok += 1
        self._print("OK", label, detail)

    def bad(self, label: str, detail: str = "") -> None:
        self.fail += 1
        self._print("FAIL", label, detail)

    def note(self, label: str, detail: str = "") -> None:
        self.warn += 1
        self._print("WARN", label, detail)


def check_python(rep: Report) -> None:
    v = sys.version_info
    if v >= (3, 10):
        rep.good("Python", f"{v.major}.{v.minor}.{v.micro}")
    else:
        rep.bad("Python >= 3.10", f"got {v.major}.{v.minor}")


def check_gi(rep: Report) -> None:
    try:
        import gi
    except ImportError:
        rep.bad("PyGObject (gi)", "dnf install python3-gobject")
        return
    rep.good("PyGObject (gi)", getattr(gi, "__version__", "present"))
    try:
        gi.require_version("Gtk", "4.0")
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk, Gtk

        gtk_ver = f"{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}"
        gdk_ver = getattr(Gdk, "_version", "?")
        if Gtk.get_major_version() != 4:
            rep.bad("GTK major version is 4", f"got {Gtk.get_major_version()}")
        else:
            rep.good("GTK 4 typelib", gtk_ver)
        if not str(gdk_ver).startswith("4"):
            rep.bad("Gdk 4 typelib", f"got {gdk_ver}")
        else:
            rep.good("Gdk 4 typelib", str(gdk_ver))
    except ValueError as exc:
        rep.bad("GTK 4 / Gdk 4 typelibs", f"{exc}  (dnf install gtk4 python3-gobject)")
    except Exception as exc:  # noqa: BLE001
        rep.bad("GTK 4 import", str(exc))


def check_skeletons_pin(rep: Report) -> None:
    try:
        from skeletons.gi_init import Gdk, Gtk

        gdk_ver = getattr(Gdk, "_version", "?")
        gtk_ver = getattr(Gtk, "_version", "?")
        if not str(gtk_ver).startswith("4") or not str(gdk_ver).startswith("4"):
            rep.bad("skeletons GTK4 pin", f"Gtk {gtk_ver}, Gdk {gdk_ver} (need 4.0)")
            return
        rep.good("skeletons GTK4 pin", f"Gtk {gtk_ver}, Gdk {gdk_ver}")
    except Exception as exc:  # noqa: BLE001
        rep.bad("import skeletons.gi_init", str(exc))


def check_cairo(rep: Report) -> None:
    try:
        import cairo

        ver = cairo.cairo_version_string() if hasattr(cairo, "cairo_version_string") else "present"
        rep.good("pycairo", ver)
    except ImportError:
        rep.bad("pycairo", "dnf install python3-cairo")


def check_display(rep: Report) -> None:
    display = os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")
    if display:
        rep.good("Wayland/X11 session", display)
    else:
        rep.note("graphical session", "WAYLAND_DISPLAY and DISPLAY are unset")
    try:
        from skeletons.gi_init import Gtk

        if bool(Gtk.init_check()):
            rep.good("Gtk.init_check")
        else:
            rep.bad("Gtk.init_check", "no display for GTK")
    except Exception as exc:  # noqa: BLE001
        rep.bad("Gtk.init_check", str(exc))


def check_export(rep: Report, cfg: dict) -> None:
    res = resource_dir(cfg)
    if (res / "reaper.ini").is_file():
        rep.good("REAPER resource folder", str(res))
    else:
        rep.note("REAPER resource folder", f"no reaper.ini in {res}")

    missing = stale = 0
    rows = export_status(cfg)
    for item, status in rows:
        rel = relative_dest(item, cfg)
        if status == "ok":
            continue
        if status == "missing-src":
            rep.bad(f"checkout {item.src.name}", f"not in the repo at {item.src}")
        elif status == "missing":
            missing += 1
            rep.bad(rel, "not exported — run: python3 -m skeletons install")
        elif status == "stale":
            stale += 1
            rep.note(rel, "differs from checkout — run: python3 -m skeletons install")
    if missing == 0 and stale == 0:
        n = len(rows)
        rep.good("exported Lua/JSFX/OSC/templates", f"{n} files match the checkout")

    pedal = resource_dir(cfg) / "Effects" / "Skeletons" / "skel_panel_pedal"
    if pedal.is_file():
        rep.good("Skeletons Pedal JSFX", str(pedal))
    else:
        rep.note("Skeletons Pedal JSFX", f"missing {pedal} — run: python3 -m skeletons install")

    editor = resource_dir(cfg) / "Scripts" / "Skeletons" / "skel_panel_editor.lua"
    if editor.is_file():
        rep.good("Pedal Panel Editor script", str(editor))
    else:
        rep.note(
            "Pedal Panel Editor script",
            f"missing {editor} — run: python3 -m skeletons install",
        )

    start = startup_path(cfg)
    if startup_ok(cfg):
        rep.good("Scripts/__startup.lua", "loads Scripts/Skeletons/skel_agent.lua")
    elif start.is_file():
        rep.bad("Scripts/__startup.lua", "does not load the agent — run: python3 -m skeletons install")
    else:
        rep.bad("Scripts/__startup.lua", "missing — run: python3 -m skeletons install")


def check_reaper_live(rep: Report, cfg: dict) -> None:
    from skeletons import SECTION
    from skeletons.bridge.http import HttpBridge

    binary = Path(cfg["reaper_install"]).expanduser() / "reaper"
    if binary.is_file() and os.access(binary, os.X_OK):
        rep.good("REAPER binary", str(binary))
    else:
        rep.note("REAPER binary", f"not found at {binary}")

    host, port = str(cfg["http_host"]), int(cfg["http_port"])
    http = HttpBridge(host, port)
    probe = http.probe()
    if probe["alive"]:
        rep.good(f"REAPER HTTP :{port}", f"TRANSPORT + {probe['ntrack']} track(s) at {host}")
        if probe["agent_alive"]:
            rep.good(f"ExtState {SECTION}/agent.alive", probe["agent_value"] or "set")
        else:
            rep.note(
                f"ExtState {SECTION}/agent.alive",
                "agent is not running. Restart REAPER so __startup.lua loads it, "
                "or Actions → Load ReaScript on Scripts/Skeletons/skel_agent.lua",
            )
    else:
        rep.note(
            f"REAPER HTTP :{port}",
            probe["error"] or "start REAPER with the web control surface enabled",
        )


def check_library(rep: Report, cfg: dict) -> None:
    from skeletons.library import APP_FOLDER, CHAIN_ROLES, CHAIN_DIR

    root = Path(cfg["fx_chains"]).expanduser()
    if root.is_dir():
        rep.good("FXChains folder", str(root))
    else:
        rep.note("FXChains folder", f"missing {root} — run: python3 -m skeletons install")
        return
    guitar = root / APP_FOLDER["guitar"]
    for role in CHAIN_ROLES["guitar"]:
        folder = guitar / CHAIN_DIR[role]
        n = len(list(folder.glob("*.RfxChain"))) if folder.is_dir() else 0
        if folder.is_dir():
            rep.good(f"SkeletonsGuitar/{CHAIN_DIR[role]}", f"{n} .RfxChain")
        else:
            rep.note(f"SkeletonsGuitar/{CHAIN_DIR[role]}", "missing — run: python3 -m skeletons install")
    tpl = Path(cfg["track_templates"]).expanduser() / "SkeletonsGuitar" / "SkeletonsGuitar.RTrackTemplate"
    if tpl.is_file():
        rep.good("TrackTemplates/SkeletonsGuitar", str(tpl.name))
    else:
        rep.note("TrackTemplates/SkeletonsGuitar", "missing SkeletonsGuitar.RTrackTemplate — run install")


def check_project(rep: Report) -> None:
    root = repo_root()
    skel = root / "project" / "Skeletons.RPP"
    if skel.is_file():
        rep.good("skeleton project", str(skel.relative_to(root)))
    else:
        rep.note("skeleton project", "run: python3 -m skeletons build")
    presets = root / "presets" / "guitar"
    if presets.is_dir() and any(presets.glob("*.json")):
        rep.good("guitar presets", str(presets.relative_to(root)))
    else:
        rep.note("guitar presets", "none under presets/guitar/")


def run_check() -> int:
    from skeletons.config import load

    cfg = load()
    print("Skeletons environment checklist")
    print("==============================")
    print("\nRequired")
    rep = Report()
    check_python(rep)
    check_gi(rep)
    check_cairo(rep)
    check_skeletons_pin(rep)
    check_display(rep)
    print("\nExported into REAPER")
    check_export(rep, cfg)
    print("\nFXChains / TrackTemplates")
    check_library(rep, cfg)
    print("\nREAPER (apps run without it, but controls stay disconnected)")
    check_reaper_live(rep, cfg)
    print("\nProject files")
    check_project(rep)
    print()
    print(f"{rep.ok} ok, {rep.fail} failed, {rep.warn} warnings")
    if rep.fail:
        print("\nFix FAIL items with:  python3 -m skeletons install")
        print("Fedora packages:      sudo dnf install gtk4 python3-gobject python3-cairo")
        return 1
    return 0
