"""Launch the Settings app as its own GTK 4 process."""

from __future__ import annotations

import os
import subprocess
import sys

from skeletons.paths import repo_root


def open_settings() -> None:
    root = repo_root()
    env = os.environ.copy()
    extra = str(root)
    env["PYTHONPATH"] = extra + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    subprocess.Popen(
        [sys.executable, "-m", "apps.settings"],
        cwd=str(root),
        env=env,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
