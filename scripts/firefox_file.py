"""Print a pristine Mozilla file from the pinned Firefox's omni.ja.

For rewriting a patch a new Firefox has moved (see the README, "Moving to a new
Firefox"). The first argument is the jar -- "browser" (browser/omni.ja) or "gre"
(the omni.ja beside it), as a patch's folder under patches/ says -- and the
second is the file's path inside it, as the patch's "--- a/…" line says.

    python3 scripts/firefox_file.py browser modules/GenAI.sys.mjs > /tmp/orig
    # edit a copy, then diff it back into the patch:
    cp /tmp/orig /tmp/new && $EDITOR /tmp/new
    diff -u /tmp/orig /tmp/new    # the body of patches/browser/modules/GenAI.sys.mjs.patch

Reads the Windows build by default (it unpacks on any OS); --mac reads the Mac
build (a Mac only), for a patch that is only in the Mac's omni.ja.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build  # noqa: E402


def main(argv: list[str]) -> int:
    mac = "--mac" in argv
    argv = [a for a in argv if a != "--mac"]
    if len(argv) != 2 or argv[0] not in ("browser", "gre"):
        raise SystemExit("usage: firefox_file.py [--mac] <browser|gre> <path/inside/omni.ja>")
    jar, path = argv
    jars = build.read_jars("mac" if mac else "win64")
    if path not in jars[jar]:
        where = "mac" if mac else "win64"
        raise SystemExit(f"{jar}:{path} isn't in the {where} Firefox's omni.ja (try --mac, or check the path).")
    sys.stdout.buffer.write(jars[jar][path])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
