"""Copy Skeletons Lua, JSFX, OSC and templates into the REAPER resource folder."""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from skeletons.config import DEFAULTS, _migrate_paths, ensure_layout, load, save
from skeletons.paths import repo_root

STARTUP_SNIPPET = "dofile(reaper.GetResourcePath() .. '/Scripts/Skeletons/skel_agent.lua')"

JSFX_FILES = (
    "skel_control.jsfx",
    "skel_tuner.jsfx",
    "skel_scope.jsfx",
    "skel_live.jsfx",
    "skel_panel_pedal.jsfx",
)


def jsfx_effect_name(filename: str) -> str:
    """REAPER indexes factory JS without an extension (`guitar/distortion`).

    The skeleton and TrackFX_AddByName use `Skeletons/skel_control`, so the
    installed file must be `Effects/Skeletons/skel_control`, not `.jsfx`.
    """
    return filename[:-5] if filename.endswith(".jsfx") else filename

DESKTOP_APPS = (
    ("skeletons-guitar", "Skeletons Guitar", "apps.guitar"),
    ("skeletons-settings", "Skeletons Settings", "apps.settings"),
    ("skeletons-keyboard", "Skeletons Keyboard", "apps.keyboard"),
    ("skeletons-microphone", "Skeletons Microphone", "apps.microphone"),
    ("skeletons-sidefx", "Skeletons SideFX", "apps.sidefx"),
    ("skeletons-looper", "Skeletons Looper", "apps.looper"),
)


@dataclass(frozen=True)
class ExportItem:
    src: Path
    dest: Path
    kind: str


@dataclass
class CopyResult:
    item: ExportItem
    status: str  # copied, unchanged, missing-src, would-copy, would-update


def resource_dir(cfg: dict | None = None) -> Path:
    cfg = cfg or load()
    return Path(cfg["reaper_resource"]).expanduser()


def install_dir(cfg: dict | None = None) -> Path:
    cfg = cfg or load()
    return Path(cfg["reaper_install"]).expanduser()


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def manifest(cfg: dict | None = None) -> list[ExportItem]:
    """Checkout files that must land inside the REAPER resource folder."""
    cfg = cfg or load()
    root = repo_root()
    res = resource_dir(cfg)
    items: list[ExportItem] = [
        ExportItem(root / "reaper" / "skel_agent.lua", res / "Scripts" / "Skeletons" / "skel_agent.lua", "lua"),
        ExportItem(root / "reaper" / "skel_panel_editor.lua", res / "Scripts" / "Skeletons" / "skel_panel_editor.lua", "lua"),
        ExportItem(root / "reaper" / "tagger.lua", res / "Scripts" / "Skeletons" / "tagger.lua", "lua"),
        ExportItem(root / "reaper" / "Skeletons.ReaperOSC", res / "OSC" / "Skeletons.ReaperOSC", "osc"),
        ExportItem(
            root / "project" / "SkeletonsGuitar.RTrackTemplate",
            res / "TrackTemplates" / "SkeletonsGuitar" / "SkeletonsGuitar.RTrackTemplate",
            "template",
        ),
    ]
    lib = root / "reaper" / "skel_lib"
    if lib.is_dir():
        for src in sorted(lib.glob("*.lua")):
            items.append(ExportItem(src, res / "Scripts" / "Skeletons" / "skel_lib" / src.name, "lua"))
    for name in JSFX_FILES:
        items.append(
            ExportItem(
                root / "reaper" / name,
                res / "Effects" / "Skeletons" / jsfx_effect_name(name),
                "jsfx",
            )
        )
    return items


def export_status(cfg: dict | None = None) -> list[tuple[ExportItem, str]]:
    """Return (item, ok|missing|stale|missing-src) for every manifest entry."""
    out: list[tuple[ExportItem, str]] = []
    for item in manifest(cfg):
        if not item.src.is_file():
            out.append((item, "missing-src"))
        elif not item.dest.is_file():
            out.append((item, "missing"))
        elif file_digest(item.src) != file_digest(item.dest):
            out.append((item, "stale"))
        else:
            out.append((item, "ok"))
    return out


def copy_item(item: ExportItem, *, dry_run: bool) -> CopyResult:
    if not item.src.is_file():
        return CopyResult(item, "missing-src")
    if item.dest.is_file() and file_digest(item.src) == file_digest(item.dest):
        return CopyResult(item, "unchanged")
    if dry_run:
        return CopyResult(item, "would-update" if item.dest.is_file() else "would-copy")
    item.dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(item.src, item.dest)
    return CopyResult(item, "copied")


def remove_stale_jsfx(cfg: dict | None = None, *, dry_run: bool = False) -> list[Path]:
    """Drop leftover Effects/Skeletons/*.jsfx copies that shadow the real idents."""
    folder = resource_dir(cfg) / "Effects" / "Skeletons"
    removed: list[Path] = []
    if not folder.is_dir():
        return removed
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.name.endswith(".jsfx"):
            removed.append(path)
            if not dry_run:
                path.unlink()
    return removed


def clap_install_dir() -> Path:
    return Path.home() / ".clap" / "Skeletons"


def clap_dest() -> Path:
    return clap_install_dir() / "Skeletons Pedal.clap"


def remove_stale_clap(cfg: dict | None = None, *, dry_run: bool = False) -> list[Path]:
    """Remove the retired Skeletons Pedal CLAP if a previous install left it behind."""
    del cfg
    removed: list[Path] = []
    dest = clap_dest()
    if dest.is_file():
        removed.append(dest)
        if not dry_run:
            dest.unlink()
    folder = clap_install_dir()
    if folder.is_dir() and not any(folder.iterdir()) and not dry_run:
        folder.rmdir()
    return removed


def export_resources(cfg: dict | None = None, *, dry_run: bool = False) -> list[CopyResult]:
    return [copy_item(item, dry_run=dry_run) for item in manifest(cfg)]


def startup_path(cfg: dict | None = None) -> Path:
    return resource_dir(cfg) / "Scripts" / "__startup.lua"


def startup_ok(cfg: dict | None = None) -> bool:
    path = startup_path(cfg)
    if not path.is_file():
        return False
    return "Skeletons/skel_agent.lua" in path.read_text(encoding="utf-8", errors="replace")


def ensure_startup(cfg: dict | None = None, *, dry_run: bool = False) -> str:
    """Make sure Scripts/__startup.lua dofiles the installed agent."""
    dest = startup_path(cfg)
    src = repo_root() / "reaper" / "__startup.lua"
    if dest.is_file() and startup_ok(cfg):
        return "unchanged"
    if dry_run:
        return "would-create" if not dest.is_file() else "would-update"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.is_file():
        shutil.copy2(src, dest)
        return "created"
    text = dest.read_text(encoding="utf-8", errors="replace")
    migrated = (
        text.replace("Scripts/ReaperAPP/rapp_agent.lua", "Scripts/Skeletons/skel_agent.lua")
        .replace("reaper/rapp_agent.lua", "reaper/skel_agent.lua")
        .replace("GetExtState('ReaperAPP'", "GetExtState('Skeletons'")
        .replace('GetExtState("ReaperAPP"', 'GetExtState("Skeletons"')
    )
    if "Skeletons/skel_agent.lua" not in migrated:
        migrated = migrated.rstrip() + "\n\n-- Skeletons\n" + STARTUP_SNIPPET + "\n"
    if migrated != text:
        dest.write_text(migrated, encoding="utf-8")
        return "migrated" if "ReaperAPP" in text or "rapp_agent" in text else "appended"
    return "unchanged"


def _csurf_lines(text: str) -> tuple[dict[int, str], int | None]:
    found: dict[int, str] = {}
    count = None
    for line in text.splitlines():
        if line.startswith("csurf_cnt="):
            try:
                count = int(line.split("=", 1)[1].strip())
            except ValueError:
                count = None
        elif line.startswith("csurf_"):
            key, _, val = line.partition("=")
            try:
                idx = int(key.split("_", 1)[1])
            except ValueError:
                continue
            found[idx] = val
    return found, count


def ensure_csurfaces(cfg: dict | None = None, *, dry_run: bool = False) -> str:
    """Add HTTP and OSC control surfaces to reaper.ini when they are missing.

    Does not change existing surfaces. REAPER must be restarted to load new ones.
    """
    cfg = cfg or load()
    ini = resource_dir(cfg) / "reaper.ini"
    if not ini.is_file():
        return "no-ini"
    text = ini.read_text(encoding="utf-8", errors="replace")
    rows, _cnt = _csurf_lines(text)
    values = list(rows.values())
    need_http = not any(v.startswith("HTTP ") for v in values)
    need_osc = not any(
        ("Skeletons.ReaperOSC" in v or "ReaperApp.ReaperOSC" in v) for v in values
    )
    if not need_http and not need_osc:
        return "unchanged"
    http_port = int(cfg.get("http_port") or DEFAULTS["http_port"])
    osc_send = int(cfg.get("osc_send_port") or DEFAULTS["osc_send_port"])
    osc_listen = int(cfg.get("osc_listen_port") or DEFAULTS["osc_listen_port"])
    labels = []
    new_values: list[str] = []
    if need_http:
        new_values.append(f"HTTP 0 {http_port} '' 'fancier.html' 0 ''")
        labels.append(f"HTTP :{http_port}")
    if need_osc:
        new_values.append(
            f'OSC "Skeletons.ReaperOSC" 4 {osc_send} "0.0.0.0" {osc_listen} 1024 10 ""'
        )
        labels.append("OSC Skeletons.ReaperOSC")
    if dry_run:
        return "would-add:" + ",".join(labels)
    backup = ini.with_suffix(".ini.skeletons.bak")
    if not backup.is_file():
        shutil.copy2(ini, backup)
    next_idx = (max(rows) + 1) if rows else 0
    inserts = [f"csurf_{next_idx + i}={val}\n" for i, val in enumerate(new_values)]
    new_cnt = next_idx + len(new_values)
    lines = text.splitlines(keepends=True)
    cnt_i = last_i = None
    for i, line in enumerate(lines):
        if line.startswith("csurf_cnt="):
            cnt_i = i
        if line.startswith("csurf_"):
            last_i = i
    if cnt_i is not None:
        lines[cnt_i] = f"csurf_cnt={new_cnt}\n"
    if last_i is not None:
        lines[last_i + 1 : last_i + 1] = inserts
    elif cnt_i is not None:
        lines[cnt_i + 1 : cnt_i + 1] = inserts
    else:
        lines.append(f"csurf_cnt={new_cnt}\n")
        lines.extend(inserts)
    ini.write_text("".join(lines), encoding="utf-8")
    return "added:" + ", ".join(labels)


def write_desktops(cfg: dict | None = None, *, dry_run: bool = False) -> list[Path]:
    root = repo_root()
    apps = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "applications"
    written: list[Path] = []
    icon = root / "assets" / "icons" / "amp.svg"
    launcher = root / "tools" / "launch.sh"
    for desktop_id, name, module in DESKTOP_APPS:
        dest = apps / f"{desktop_id}.desktop"
        body = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={name}\n"
            "Comment=GTK 4 interface onto the running REAPER instance\n"
            f"Exec={launcher} {module}\n"
            f"Path={root}\n"
            f"Icon={icon}\n"
            "Terminal=false\n"
            "Categories=AudioVideo;Audio;\n"
            "StartupNotify=true\n"
        )
        if dry_run:
            written.append(dest)
            continue
        apps.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")
        written.append(dest)
    return written


def prepare_config() -> dict:
    from skeletons.library import seed_example_chains

    cfg = _migrate_paths(load())
    save(cfg)
    ensure_layout(cfg)
    seed_example_chains(cfg, repo_root())
    return cfg


def relative_dest(item: ExportItem, cfg: dict | None = None) -> str:
    try:
        return str(item.dest.relative_to(resource_dir(cfg)))
    except ValueError:
        return str(item.dest)
