"""Classify hosted FX parameters into switch / knob / slider / spin."""

from __future__ import annotations

import re

TOGGLE_WORDS = frozenset({
    "bypass", "mute", "on", "off", "enable", "enabled", "solo", "boost", "stomp",
})
ENABLE_WORDS = frozenset({"bypass", "enable", "enabled"})
KNOB_WORDS = frozenset({
    "gain", "drive", "tone", "pan", "mix", "blend", "output", "volume", "vol", "level", "input",
})


def param_words(name: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (name or "").lower()))


def is_unused_param(name: str) -> bool:
    low = (name or "").strip().lower()
    return not low or low.startswith("unused")


def is_fx_enable_param(name: str) -> bool:
    """True when the param duplicates the FX-card header enable switch."""
    low = (name or "").strip().lower()
    if low in ("on", "off"):
        return True
    return bool(param_words(name) & ENABLE_WORDS)


def param_kind(p: dict) -> str:
    """Pick a widget for one published param (normalized 0–1 in the agent)."""
    name = (p.get("name") or "").strip()
    words = param_words(name)
    pmin = float(p.get("min") if p.get("min") is not None else 0)
    pmax = float(p.get("max") if p.get("max") is not None else 1)
    step = float(p.get("step") or 0)
    span = pmax - pmin
    if p.get("toggle") or (words & TOGGLE_WORDS):
        return "switch"
    if step >= 0.999 and span <= 1.001 and not (words & KNOB_WORDS):
        return "switch"
    if words & KNOB_WORDS:
        return "knob"
    if step > 0 and span > 0:
        nsteps = span / step
        integer_step = abs(step - round(step)) < 1e-9 and step >= 1
        if 1 < nsteps <= 32 or (integer_step and span > 1):
            return "spin"
    return "slider"


def grouped_params(params: list[dict]) -> list[tuple[str, dict]]:
    """Toggles, then knobs, then sliders/spins (each group keeps index order)."""
    buckets: dict[str, list[dict]] = {"switch": [], "knob": [], "rest": []}
    for p in sorted(params, key=lambda x: x.get("index", 0)):
        name = p.get("name") or ""
        if is_unused_param(name) or is_fx_enable_param(name):
            continue
        kind = param_kind(p)
        if kind in ("switch", "knob"):
            buckets[kind].append(p)
        else:
            buckets["rest"].append(p)
    out: list[tuple[str, dict]] = []
    for p in buckets["switch"]:
        out.append(("switch", p))
    for p in buckets["knob"]:
        out.append(("knob", p))
    for p in buckets["rest"]:
        out.append((param_kind(p), p))
    return out
