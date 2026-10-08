"""Downloads for the build scripts, through curl.

curl uses the system's certificates on macOS, Linux and Windows alike, where
Python's own may not be set up (python.org's macOS installer leaves that to a
separate step).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

USER_AGENT = "Orbit Browser build"


def fetch(url: str) -> bytes:
    return subprocess.run(
        ["curl", "-fsSL", "--retry", "3", "-A", USER_AGENT, url],
        check=True, capture_output=True,
    ).stdout


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    subprocess.run(
        ["curl", "-fSL", "--retry", "3", "--progress-bar", "-A", USER_AGENT, "-o", str(partial), url],
        check=True,
    )
    partial.replace(target)
