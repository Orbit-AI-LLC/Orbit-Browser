"""Fetch depot_tools and the pinned Chromium source.

Orbit Browser is a source fork: scripts/build.py compiles Chromium with Orbit's
changes, rather than repacking a downloaded binary. This module gets the tree
ready:

- depot_tools (Chromium's build tools: gclient, gn, autoninja) in .cache/,
  added to PATH for the build;
- the Chromium source at the tag chromium.json pins, in src/ (a big, long
  checkout the first time: tens of GB and, with `gclient sync`, the full set of
  third-party dependencies that tag's DEPS names).

The source is pinned by git tag and verified by git, not by a checksum of a
download (there is no single signed Chromium release the way there is for
Firefox). `gclient sync` is what pulls every dependency at the versions the tag
requires.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
DEPOT_TOOLS = CACHE / "depot_tools"
#: The Chromium checkout. Big and slow to make; kept between builds and synced
#: to the pin, never thrown away by the build.
SRC = ROOT / "src"


def log(message: str) -> None:
    print(f"==> {message}", flush=True)


def run(*args, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def pin() -> dict:
    return json.loads((ROOT / "chromium.json").read_text())


def depot_tools_env() -> dict:
    """The environment a Chromium build runs in: depot_tools first on PATH, and
    its managed toolchain fetch left on (DEPOT_TOOLS_WIN_TOOLCHAIN is only read
    on Windows)."""
    env = dict(os.environ)
    env["PATH"] = f"{DEPOT_TOOLS}{os.pathsep}{env.get('PATH', '')}"
    env.setdefault("DEPOT_TOOLS_UPDATE", "1")
    return env


def ensure_depot_tools() -> None:
    url = pin()["depot_tools"]
    if DEPOT_TOOLS.exists():
        run("git", "-C", DEPOT_TOOLS, "pull", "--ff-only", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    CACHE.mkdir(parents=True, exist_ok=True)
    log("Cloning depot_tools")
    run("git", "clone", "--depth", "1", url, DEPOT_TOOLS)


def ensure_source(shallow: bool = False) -> Path:
    """The Chromium source at the pinned tag, ready to patch and build. Returns
    the src/ path. The first run is a full `fetch chromium` + `gclient sync`;
    later runs fetch the tag and sync to it."""
    info = pin()
    tag = info["version"]
    env = depot_tools_env()
    if not (SRC / ".git").exists():
        log(f"Fetching Chromium {tag} (this takes a long time the first time)")
        SRC.parent.mkdir(parents=True, exist_ok=True)
        # A .gclient naming src, then fetch + checkout the tag, so the checkout
        # is the pinned release rather than tip of tree.
        (ROOT / ".gclient").write_text(_gclient_file(info["src"]))
        run("git", "clone", info["src"], SRC, env=env)
    log(f"Checking out Chromium {tag}")
    run("git", "-C", SRC, "fetch", "--tags", "origin", env=env)
    run("git", "-C", SRC, "checkout", "-f", tag, env=env)
    _reset_tree()
    log("gclient sync (dependencies for this tag)")
    sync = ["gclient", "sync", "-D", "--reset", "--with_branch_heads", "--with_tags"]
    if shallow:
        sync.append("--no-history")
    run(*sync, cwd=ROOT, env=env)
    run("gclient", "runhooks", cwd=ROOT, env=env)
    return SRC


def _reset_tree() -> None:
    """Undo the previous build's patches and overrides, so a build always starts
    from pristine Chromium. git tracks Orbit's patches (they edit tracked
    files); the override copies are removed by patches.py before it re-applies."""
    run("git", "-C", SRC, "reset", "--hard", "HEAD", stdout=subprocess.DEVNULL)
    run("git", "-C", SRC, "clean", "-fdq",
        "-e", "out", "-e", "third_party", stdout=subprocess.DEVNULL)


def _gclient_file(src_url: str) -> str:
    return (
        "solutions = [\n"
        "  {\n"
        '    "name": "src",\n'
        f'    "url": "{src_url}",\n'
        '    "managed": False,\n'
        '    "custom_deps": {},\n'
        '    "custom_vars": {"checkout_pgo_profiles": False},\n'
        "  },\n"
        "]\n"
    )


if __name__ == "__main__":
    ensure_depot_tools()
    ensure_source(shallow="--shallow" in sys.argv)
    print(f"Chromium source ready at {SRC}")
