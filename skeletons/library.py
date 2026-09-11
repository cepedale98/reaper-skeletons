"""REAPER-native FXChains / TrackTemplates layout used by every launcher.

Chains live under the resource folder, one subfolder per app and tab:

    FXChains/SkeletonsGuitar/{IN,PEDALS,AMP,CAB,FX}/*.RfxChain
    TrackTemplates/SkeletonsGuitar/SkeletonsGuitar.RTrackTemplate
"""

from __future__ import annotations

from pathlib import Path

APP_FOLDER = {
    "guitar": "SkeletonsGuitar",
    "keys": "SkeletonsKeyboard",
    "mic": "SkeletonsMicrophone",
    "sidefx": "SkeletonsSideFX",
}

CHAIN_DIR = {
    "guitar.input": "IN",
    "guitar.pedals": "PEDALS",
    "guitar.amp": "AMP",
    "guitar.cabinet": "CAB",
    "guitar.fx": "FX",
    "keys.input": "IN",
    "keys.inst": "INST",
    "keys.fx": "FX",
    "mic.input": "IN",
    "mic.fx": "FX",
    "sidefx.reverb": "REVERB",
    "sidefx.delay": "DELAY",
}

CHAIN_ROLES = {
    "guitar": ("guitar.input", "guitar.pedals", "guitar.amp", "guitar.cabinet", "guitar.fx"),
    "keys": ("keys.input", "keys.inst", "keys.fx"),
    "mic": ("mic.input", "mic.fx"),
    "sidefx": ("sidefx.reverb", "sidefx.delay"),
}

LEGACY_FILE = {
    "guitar.input": "input.RfxChain",
    "guitar.pedals": "pedals.RfxChain",
    "guitar.amp": "amp.RfxChain",
    "guitar.cabinet": "cabinet.RfxChain",
    "guitar.fx": "fx.RfxChain",
}

EXAMPLE_TAB = {
    "input.RfxChain": "IN",
    "pedals.RfxChain": "PEDALS",
    "amp.RfxChain": "AMP",
    "cabinet.RfxChain": "CAB",
    "fx.RfxChain": "FX",
}


def chain_folder(role: str, cfg: dict) -> Path:
    inst = role.split(".", 1)[0]
    return Path(cfg["fx_chains"]).expanduser() / APP_FOLDER[inst] / CHAIN_DIR[role]


def chain_path(role: str, chain_id: str, cfg: dict) -> Path:
    return chain_folder(role, cfg) / f"{chain_id}.RfxChain"


def ensure_library_tree(cfg: dict) -> None:
    root = Path(cfg["fx_chains"]).expanduser()
    templates = Path(cfg["track_templates"]).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    templates.mkdir(parents=True, exist_ok=True)
    for inst, app in APP_FOLDER.items():
        (templates / app).mkdir(parents=True, exist_ok=True)
        for role in CHAIN_ROLES.get(inst, ()):
            (root / app / CHAIN_DIR[role]).mkdir(parents=True, exist_ok=True)


def list_role_chains(role: str, cfg: dict) -> list[str]:
    folder = chain_folder(role, cfg)
    if not folder.is_dir():
        return []
    return sorted(p.stem for p in folder.glob("*.RfxChain") if p.is_file())


def list_rigs(instrument: str, cfg: dict) -> list[str]:
    seen: set[str] = set()
    app = APP_FOLDER.get(instrument)
    root = Path(cfg["fx_chains"]).expanduser()
    if app:
        for role in CHAIN_ROLES.get(instrument, ()):
            folder = root / app / CHAIN_DIR[role]
            if folder.is_dir():
                for path in folder.glob("*.RfxChain"):
                    if path.is_file():
                        seen.add(path.stem)
    legacy = root / instrument
    if legacy.is_dir():
        for path in legacy.iterdir():
            if path.is_dir():
                seen.add(path.name)
    return sorted(seen)


def seed_example_chains(cfg: dict, src_root: Path, *, dry_run: bool = False) -> list[tuple[Path, str]]:
    """Copy checkout fxchains/guitar/cleantonic into SkeletonsGuitar/<TAB>/cleantonic.RfxChain.

    Existing files are left alone so a later install does not wipe a saved chain.
    """
    ensure_library_tree(cfg)
    src_dir = src_root / "fxchains" / "guitar" / "cleantonic"
    dest_root = Path(cfg["fx_chains"]).expanduser() / APP_FOLDER["guitar"]
    results: list[tuple[Path, str]] = []
    if not src_dir.is_dir():
        return results
    for src in sorted(src_dir.glob("*.RfxChain")):
        tab = EXAMPLE_TAB.get(src.name)
        if not tab:
            continue
        dest = dest_root / tab / "cleantonic.RfxChain"
        if dest.is_file():
            results.append((dest, "unchanged"))
            continue
        if dry_run:
            results.append((dest, "would-copy"))
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        results.append((dest, "copied"))
    return results
