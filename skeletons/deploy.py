"""Install, uninstall, and legacy cleanup for Skeletons.

The file lists follow `export.manifest` and `export.DESKTOP_APPS`, so these
commands stay in sync as features are added or removed. Shell wrappers:

    ./uninstall.sh
    ./cleanup.sh
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from skeletons.config import CONFIG_DIR, LEGACY_CONFIG_DIR, load
from skeletons.export import DESKTOP_APPS, manifest, resource_dir, startup_path


STARTUP_NEEDLES_CURRENT = (
    "Scripts/Skeletons/skel_agent.lua",
    "reaper/skel_agent.lua",
    "-- Skeletons",
)

STARTUP_NEEDLES_LEGACY = (
    "Scripts/ReaperAPP/rapp_agent.lua",
    "reaper/rapp_agent.lua",
    "-- ReaperAPP",
)

LEGACY_DESKTOP_IDS = (
    "reaperapp-guitar",
    "reaperapp-settings",
    "reaperapp-keyboard",
    "reaperapp-microphone",
    "reaperapp-sidefx",
    "reaperapp-looper",
)


def _xdg_apps() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "applications"


def _remove_path(path: Path, *, dry_run: bool) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    if dry_run:
        return True
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def _rmdir_empty(path: Path, *, dry_run: bool) -> bool:
    if not path.is_dir():
        return False
    try:
        next(path.iterdir())
        return False
    except StopIteration:
        pass
    if not dry_run:
        path.rmdir()
    return True


def _unpatch_startup(path: Path, needles: tuple[str, ...], *, dry_run: bool) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines(keepends=True)
    keep = [line for line in lines if not any(n in line for n in needles)]
    if keep == lines:
        return False
    if not dry_run:
        path.write_text("".join(keep), encoding="utf-8")
    return True


def desktop_paths_current() -> list[Path]:
    apps = _xdg_apps()
    return [apps / f"{desktop_id}.desktop" for desktop_id, _name, _mod in DESKTOP_APPS]


def desktop_paths_legacy() -> list[Path]:
    apps = _xdg_apps()
    return [apps / f"{desktop_id}.desktop" for desktop_id in LEGACY_DESKTOP_IDS]


def owned_dirs(cfg: dict | None = None) -> list[Path]:
    """Folders this project creates inside the REAPER resource tree."""
    res = resource_dir(cfg)
    return [
        res / "Scripts" / "Skeletons",
        res / "Effects" / "Skeletons",
        res / "TrackTemplates" / "SkeletonsGuitar",
    ]


def legacy_paths(cfg: dict | None = None) -> list[Path]:
    """Deprecated copies left by ReaperAPP / rapp_* installs.

    Does not delete FXChains/GuitarApp — those are user rigs.
    """
    res = resource_dir(cfg)
    out = [
        res / "Scripts" / "ReaperAPP",
        res / "Effects" / "ReaperAPP",
        res / "TrackTemplates" / "GuitarApp" / "GuitarApp.RTrackTemplate",
        res / "TrackTemplates" / "GuitarSkeleton.RTrackTemplate",
        res / "OSC" / "ReaperApp.ReaperOSC",
        res / "rapp-probe.txt",
        res / "rapp-probe-timing.txt",
        Path.home() / ".clap" / "ReaperAPP",
        Path.home() / ".clap" / "Skeletons" / "Skeletons Pedal.clap",
        Path.home() / ".clap" / "Skeletons",
    ]
    out.extend(desktop_paths_legacy())
    # Stale ident copies that shadow factory JS names.
    for folder in (res / "Effects" / "ReaperAPP", res / "Effects" / "Skeletons"):
        if folder.is_dir():
            out.extend(sorted(p for p in folder.glob("*.jsfx") if p.is_file()))
    return out


def uninstall_paths(cfg: dict | None = None) -> list[Path]:
    """Everything the current installer writes (except user FXChains)."""
    cfg = cfg or load()
    out = [item.dest for item in manifest(cfg)]
    out.extend(owned_dirs(cfg))
    out.append(resource_dir(cfg) / "OSC" / "Skeletons.ReaperOSC")
    out.extend(desktop_paths_current())
    return out


def _report(removed: list[Path], *, dry_run: bool) -> int:
    verb = "would remove" if dry_run else "removed"
    for path in removed:
        print(f"  -  {verb}  {path}")
    print(f"{len(removed)} path(s) {verb}")
    return 0


def run_uninstall(cfg: dict | None = None, *, dry_run: bool = False, purge_config: bool = False) -> int:
    """Remove the current Skeletons install from REAPER and desktop launchers."""
    cfg = cfg or load()
    print("Skeletons uninstall")
    print("==================")
    removed: list[Path] = []
    seen: set[Path] = set()
    for path in uninstall_paths(cfg):
        if path in seen:
            continue
        seen.add(path)
        if _remove_path(path, dry_run=dry_run):
            removed.append(path)
    for folder in owned_dirs(cfg):
        if _rmdir_empty(folder, dry_run=dry_run) and folder not in seen:
            removed.append(folder)
    if _unpatch_startup(startup_path(cfg), STARTUP_NEEDLES_CURRENT, dry_run=dry_run):
        print("  ~  unpatched Scripts/__startup.lua (Skeletons agent)")
    if purge_config and _remove_path(CONFIG_DIR, dry_run=dry_run):
        removed.append(CONFIG_DIR)
    notes = [
        "FXChains/SkeletonsGuitar is left in place (user rigs).",
        "HTTP/OSC rows in reaper.ini are left in place.",
        "Restart REAPER after uninstall so it drops the agent.",
    ]
    code = _report(removed, dry_run=dry_run)
    for note in notes:
        print(f"note: {note}")
    return code


def run_cleanup(cfg: dict | None = None, *, dry_run: bool = False, purge_config: bool = False) -> int:
    """Delete deprecated ReaperAPP / rapp_* copies that confuse REAPER."""
    cfg = cfg or load()
    print("Skeletons cleanup (legacy ReaperAPP files)")
    print("=========================================")
    removed: list[Path] = []
    seen: set[Path] = set()
    for path in legacy_paths(cfg):
        if path in seen:
            continue
        seen.add(path)
        if _remove_path(path, dry_run=dry_run):
            removed.append(path)
    res = resource_dir(cfg)
    for folder in (
        res / "Scripts" / "ReaperAPP",
        res / "Effects" / "ReaperAPP",
        res / "TrackTemplates" / "GuitarApp",
        Path.home() / ".clap" / "ReaperAPP",
        Path.home() / ".clap" / "Skeletons",
    ):
        if _rmdir_empty(folder, dry_run=dry_run) and folder not in seen:
            removed.append(folder)
    if _unpatch_startup(startup_path(cfg), STARTUP_NEEDLES_LEGACY, dry_run=dry_run):
        print("  ~  unpatched Scripts/__startup.lua (legacy ReaperAPP agent)")
    if purge_config and _remove_path(LEGACY_CONFIG_DIR, dry_run=dry_run):
        removed.append(LEGACY_CONFIG_DIR)
    leftover_chains = Path(cfg["fx_chains"]).expanduser() / "GuitarApp"
    code = _report(removed, dry_run=dry_run)
    if leftover_chains.is_dir():
        print(f"note: user chains left at {leftover_chains} (copy into FXChains/SkeletonsGuitar if you still need them)")
    print("note: restart REAPER so it forgets removed JSFX idents")
    return code
