from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
STYLE_DIR = PACKAGE_ROOT / "style"


def repo_root() -> Path:
    return REPO_ROOT


def css_path() -> Path:
    return STYLE_DIR / "app.css"
