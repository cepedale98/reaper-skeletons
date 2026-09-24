"""Load bank and preset JSON from disk."""

from __future__ import annotations

import json
from pathlib import Path

from skeletons.paths import repo_root


def load_presets(instrument: str) -> list[dict]:
    folder = repo_root() / "presets" / instrument
    items: list[dict] = []
    if not folder.is_dir():
        return items
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            items.append({"id": path.stem, "label": path.stem, "error": str(exc)})
            continue
        data.setdefault("id", path.stem)
        data["__file"] = str(path)
        items.append(data)
    return items


def load_set(instrument: str) -> dict:
    """Pages of four preset ids for the MODE strip.

    This index is a floor-unit page (A–D). It is not a residency bank.
    """
    path = repo_root() / "sets" / f"{instrument}.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        pages = []
        for page in data.get("pages") or []:
            slots = [(slot or None) for slot in list(page.get("slots") or [])[:4]]
            while len(slots) < 4:
                slots.append(None)
            pages.append({"slots": slots})
        if pages:
            return {"pages": pages}
    ids = [p.get("id") for p in load_presets(instrument) if p.get("id") and not p.get("error")]
    if not ids:
        return {"pages": [{"slots": [None, None, None, None]}]}
    pages = []
    for start in range(0, len(ids), 4):
        slots = list(ids[start : start + 4])
        while len(slots) < 4:
            slots.append(None)
        pages.append({"slots": slots})
    return {"pages": pages}


def load_banks() -> dict[str, dict]:
    folder = repo_root() / "banks"
    out: dict[str, dict] = {}
    if not folder.is_dir():
        return out
    for path in folder.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out[data.get("id", path.stem)] = data
    return out


def key_params_for(preset: dict, role: str, fx_slot: int) -> list:
    slots = preset.get("slots") or {}
    spec = slots.get(role) or {}
    for entry in spec.get("fx") or []:
        if entry.get("slot") == fx_slot:
            return list(entry.get("key_params") or [])
    return []


def _norm_path(value) -> str | None:
    if value is None or value is False or value == "None" or value == "":
        return None
    return str(value)


def residency_matches(bank: dict, live: dict[str, dict]) -> bool:
    """True when every bank slot is already loaded in `live`.

    `live` is role -> {model_a, model_b, ir_a, ir_b} as published by the agent.
    """
    slots = bank.get("slots") or {}
    for role, spec in slots.items():
        have = live.get(role) or {}
        for slot_id, prefix in (("A", "a"), ("B", "b")):
            want = spec.get(slot_id) or {}
            if "model" in want and _norm_path(want.get("model")) != _norm_path(have.get(f"model_{prefix}")):
                return False
            if "ir" in want and _norm_path(want.get("ir")) != _norm_path(have.get(f"ir_{prefix}")):
                return False
    return True


def classify_transition(preset: dict, banks: dict[str, dict], live: dict[str, dict] | None = None) -> str:
    """Return 'instant' or 'arming' for the browser badge."""
    bank_id = preset.get("bank")
    if not bank_id:
        return "instant"
    if preset.get("error"):
        return "arming"
    bank = banks.get(bank_id)
    if not bank:
        return "arming"
    if live is None:
        return "instant"
    return "instant" if residency_matches(bank, live) else "arming"


def badge_label(preset: dict, banks: dict[str, dict], live: dict[str, dict] | None = None) -> str:
    name = preset.get("label") or preset.get("id") or "?"
    if preset.get("error"):
        return f"{name} (error)"
    kind = classify_transition(preset, banks, live)
    return f"{name}  · {kind}"
