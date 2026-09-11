#!/usr/bin/env python3
"""Classify preset transitions without talking to REAPER."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skeletons.presets import badge_label, classify_transition, load_banks, load_presets, residency_matches

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"ok   {label}")
    else:
        print(f"FAIL {label}" + (f"\n     {detail}" if detail else ""))
        failures.append(label)


def main() -> int:
    presets = load_presets("guitar")
    banks = load_banks()
    check("cleantonic preset loads", any(p.get("id") == "cleantonic" for p in presets), str([p.get("id") for p in presets]))
    check("cleantonic bank loads", "cleantonic" in banks)

    preset = next(p for p in presets if p.get("id") == "cleantonic")
    check("no live state is treated as instant (optimistic)",
          classify_transition(preset, banks, None) == "instant")

    live_ok = {
        "guitar.amp": {
            "model_a": banks["cleantonic"]["slots"]["guitar.amp"]["A"]["model"],
            "ir_a": banks["cleantonic"]["slots"]["guitar.amp"]["A"]["ir"],
            "model_b": None,
            "ir_b": banks["cleantonic"]["slots"]["guitar.amp"]["B"]["ir"],
        },
        "guitar.input": {
            "model_a": banks["cleantonic"]["slots"]["guitar.input"]["A"]["model"],
            "ir_a": None,
            "model_b": None,
            "ir_b": None,
        },
    }
    check("matching residency is instant", classify_transition(preset, banks, live_ok) == "instant")
    check("residency_matches agrees", residency_matches(banks["cleantonic"], live_ok))

    live_other = dict(live_ok)
    live_other["guitar.amp"] = dict(live_ok["guitar.amp"], model_a="/tmp/other.nam")
    check("mismatched NAM needs arming", classify_transition(preset, banks, live_other) == "arming")

    label = badge_label(preset, banks, live_other)
    check("badge includes arming", "arming" in label, label)

    no_bank = {"id": "x", "label": "X"}
    check("preset without bank is instant", classify_transition(no_bank, banks, {}) == "instant")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
