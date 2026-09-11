"""Environment paths. Stored in ~/.config/Skeletons/config.json."""

from __future__ import annotations

import json
from pathlib import Path

from skeletons.paths import repo_root

CONFIG_DIR = Path.home() / ".config" / "Skeletons"
CONFIG_FILE = CONFIG_DIR / "config.json"
LEGACY_CONFIG_DIR = Path.home() / ".config" / "ReaperAPP"
LEGACY_CONFIG_FILE = LEGACY_CONFIG_DIR / "config.json"

DEFAULTS = {
    "reaper_resource": str(Path.home() / ".config" / "REAPER"),
    "reaper_install": str(Path.home() / "opt" / "REAPER"),
    "track_templates": str(Path.home() / ".config" / "REAPER" / "TrackTemplates"),
    "fx_chains": str(Path.home() / ".config" / "REAPER" / "FXChains"),
    "icons_reaper": str(Path.home() / ".config" / "REAPER" / "Data" / "track_icons"),
    "assets": str(repo_root() / "assets"),
    "http_host": "127.0.0.1",
    "http_port": 8080,
    "osc_send_port": 8000,
    "osc_listen_port": 9000,
}

FIELDS = [
    ("reaper_resource", "REAPER resource folder", "reaper.ini, Scripts, TrackTemplates, Data/track_icons"),
    ("reaper_install", "REAPER install folder", "The folder that contains the reaper binary"),
    ("track_templates", "Track group templates", ".RTrackTemplate files (TrackTemplates/SkeletonsGuitar/…)"),
    ("fx_chains", "FX chain templates", "REAPER FXChains folder (SkeletonsGuitar/IN, PEDALS, AMP, CAB, FX)"),
    ("icons_reaper", "REAPER track icons", "PNG icons the GTK apps can draw next to tabs"),
    ("assets", "Environment assets", "Icons, skins and other files owned by Skeletons"),
]

NETWORK_FIELDS = [
    ("http_host", "HTTP host", "REAPER web control surface bind address"),
    ("http_port", "HTTP port", "Usually 8080"),
    ("osc_send_port", "OSC send port", "REAPER OSC input (app → REAPER)"),
    ("osc_listen_port", "OSC listen port", "REAPER OSC output (REAPER → app)"),
]

AGENT_KEYS = ("fx_chains", "track_templates")


def _migrate_paths(data: dict) -> dict:
    """Point leftover checkouts at REAPER's FXChains / TrackTemplates folders."""
    res = Path(data.get("reaper_resource") or DEFAULTS["reaper_resource"]).expanduser()
    if data.get("fx_chains") == str(repo_root() / "fxchains"):
        data["fx_chains"] = str(res / "FXChains")
    return data


def load() -> dict:
    data = dict(DEFAULTS)
    src = CONFIG_FILE if CONFIG_FILE.is_file() else LEGACY_CONFIG_FILE
    if src.is_file():
        try:
            saved = json.loads(src.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                data.update({k: saved[k] for k in DEFAULTS if k in saved})
        except (OSError, json.JSONDecodeError):
            pass
    return _migrate_paths(data)


def save(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    merged = dict(DEFAULTS)
    merged.update(data)
    CONFIG_FILE.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")


def ensure_layout(cfg: dict | None = None) -> None:
    from skeletons.library import ensure_library_tree

    cfg = cfg or load()
    assets = Path(cfg["assets"])
    for sub in ("icons", "skins", "fonts"):
        (assets / sub).mkdir(parents=True, exist_ok=True)
    ensure_library_tree(cfg)


def list_rigs(instrument: str, cfg: dict | None = None) -> list[str]:
    from skeletons.library import list_rigs as list_library_rigs

    return list_library_rigs(instrument, cfg or load())


def rig_path(instrument: str, name: str, cfg: dict | None = None) -> Path:
    from skeletons.library import APP_FOLDER, CHAIN_ROLES, chain_folder

    cfg = cfg or load()
    roles = CHAIN_ROLES.get(instrument) or ()
    if roles:
        return chain_folder(roles[0], cfg).parent / name
    return Path(cfg["fx_chains"]).expanduser() / APP_FOLDER.get(instrument, instrument) / name


def icon_search_dirs(cfg: dict | None = None) -> list[Path]:
    cfg = cfg or load()
    return [
        Path(cfg["assets"]) / "icons",
        Path(cfg["icons_reaper"]),
        Path(cfg["reaper_resource"]) / "Data" / "track_icons",
        Path(cfg["reaper_install"]) / "Data" / "track_icons",
    ]


def push_to_agent(cfg: dict | None = None, http=None) -> str | None:
    """Publish folder paths so skel_agent.lua reads the same trees as the GTK apps."""
    from skeletons.bridge.http import HttpBridge

    cfg = cfg or load()
    client = http or HttpBridge(str(cfg["http_host"]), int(cfg["http_port"]))
    client.set_extstate("root", str(repo_root()))
    for key in AGENT_KEYS:
        client.set_extstate(key, str(cfg[key]))
    if not client.status.alive:
        return client.status.error
    return None


def list_track_templates(cfg: dict | None = None) -> list[Path]:
    cfg = cfg or load()
    folder = Path(cfg["track_templates"]).expanduser()
    if not folder.is_dir():
        return []
    return sorted(folder.rglob("*.RTrackTemplate"))


def find_icon(name: str, cfg: dict | None = None) -> Path | None:
    stem = name.rsplit(".", 1)[0]
    for folder in icon_search_dirs(cfg):
        if not folder.is_dir():
            continue
        for cand in (f"{stem}.png", f"{stem}.svg", name):
            path = folder / cand
            if path.is_file():
                return path
        try:
            for path in folder.rglob(f"{stem}.png"):
                return path
        except OSError:
            continue
    return None
