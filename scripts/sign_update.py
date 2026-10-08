"""Sign Orbit Browser's update payloads as the Tauri apps' are signed.

    python3 scripts/sign_update.py --version 0.1.0-build.12 dist/*.app.tar.gz dist/*-Setup.exe

Writes <payload>.sig beside each payload: a minisign signature in the form the
Tauri bundler writes for the other Orbit apps (Ed25519 over the payload's
BLAKE2b-512, minisign's "ED"; the whole signature base64'd), whose trusted
comment names the version. Orbit Mission Control offers a payload only when
its signature names the version in the release's orbit-update.json
(.github/scripts/orbit_update_manifest.py collects the .sig files), and an
installed Orbit Browser checks it against the public key it carries
(orbitbrowser.updates.pubkey, branding/firefox-branding.js) before installing.

The key is a Tauri signing key (`cargo tauri signer generate`), read from
TAURI_SIGNING_PRIVATE_KEY and TAURI_SIGNING_PRIVATE_KEY_PASSWORD as in the other
Orbit repositories. The Tauri CLI's own `signer sign` doesn't write the version,
which Mission Control requires, hence this script. Needs `cryptography`.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import sys
import time
from pathlib import Path

UNTRUSTED_COMMENT = "signature from tauri secret key"


class SignatureError(Exception):
    pass


def _box_line(encoded: str) -> bytes:
    """The key or signature in a base64'd minisign file: its second line, decoded."""
    lines = base64.b64decode(encoded).decode().splitlines()
    if len(lines) < 2 or not lines[0].startswith("untrusted comment:"):
        raise SignatureError("not a minisign key or signature")
    return base64.b64decode(lines[1])


def _scrypt_params(opslimit: int, memlimit: int) -> tuple[int, int, int]:
    """libsodium's scryptsalsa208sha256 pickparams, which minisign keys use: (N, r, p)."""
    opslimit = max(opslimit, 32768)
    r = 8
    if opslimit < memlimit // 32:
        p = 1
        max_n = opslimit // (r * 4)
    else:
        max_n = memlimit // (r * 128)
    n_log2 = 1
    while n_log2 < 63 and (1 << n_log2) <= max_n // 2:
        n_log2 += 1
    if not opslimit < memlimit // 32:
        p = min((opslimit // 4) // (1 << n_log2), 0x3FFFFFFF) // r
    return 1 << n_log2, r, p


def load_secret_key(encoded: str, password: str = "") -> tuple[bytes, bytes]:
    """A Tauri signing key (the base64 of a minisign secret key file) as (key id, Ed25519 seed)."""
    raw = _box_line(encoded)
    if len(raw) != 158 or raw[:2] != b"Ed" or raw[4:6] != b"B2":
        raise SignatureError("not a minisign Ed25519 secret key")
    kdf, salt = raw[2:4], raw[6:38]
    opslimit = int.from_bytes(raw[38:46], "little")
    memlimit = int.from_bytes(raw[46:54], "little")
    keynum = raw[54:158]
    if kdf == b"Sc":
        n, r, p = _scrypt_params(opslimit, memlimit)
        stream = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, maxmem=2 * 128 * r * n + (1 << 20), dklen=len(keynum))
        keynum = bytes(a ^ b for a, b in zip(keynum, stream))
    elif kdf != b"\0\0":
        raise SignatureError("unknown key derivation in the secret key")
    key_id, secret, checksum = keynum[:8], keynum[8:72], keynum[72:]
    if hashlib.blake2b(raw[:2] + key_id + secret, digest_size=32).digest() != checksum:
        raise SignatureError("the secret key's password is wrong")
    return key_id, secret[:32]


def _blake2b(path: Path) -> bytes:
    h = hashlib.blake2b(digest_size=64)
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.digest()


def sign(path: Path, version: str, key_id: bytes, seed: bytes, *, timestamp: int | None = None) -> str:
    """The base64'd signature of the payload at ``path``, made for ``version``."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.from_private_bytes(seed)
    signature = key.sign(_blake2b(path))
    trusted = f"timestamp:{int(time.time()) if timestamp is None else timestamp}\tfile:{path.name}\tversion:{version}"
    global_signature = key.sign(signature + trusted.encode())
    text = (
        f"untrusted comment: {UNTRUSTED_COMMENT}\n"
        f"{base64.b64encode(b'ED' + key_id + signature).decode()}\n"
        f"trusted comment: {trusted}\n"
        f"{base64.b64encode(global_signature).decode()}\n"
    )
    return base64.b64encode(text.encode()).decode()


def verify(path: Path, signature: str, public_key: str) -> dict[str, str]:
    """Checks ``signature`` over the payload at ``path`` with a Tauri public key
    (as tauri.conf.json holds it); returns the trusted comment's fields. What
    OrbitBrowser.sys.mjs does in the browser, here for the tests."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    pk = _box_line(public_key)
    if len(pk) != 42 or pk[:2] != b"Ed":
        raise SignatureError("not a minisign Ed25519 public key")
    lines = base64.b64decode(signature).decode().splitlines()
    if len(lines) < 4 or not lines[2].startswith("trusted comment: "):
        raise SignatureError("not a minisign signature")
    sig = base64.b64decode(lines[1])
    if len(sig) != 74 or sig[:2] != b"ED":
        raise SignatureError("not a prehashed (ED) Ed25519 signature")
    if sig[2:10] != pk[2:10]:
        raise SignatureError("signed with another key")
    trusted = lines[2][len("trusted comment: "):]
    key = Ed25519PublicKey.from_public_bytes(pk[10:])
    try:
        key.verify(sig[10:], _blake2b(path))
        key.verify(base64.b64decode(lines[3]), sig[10:] + trusted.encode())
    except InvalidSignature:
        raise SignatureError("the signature doesn't match") from None
    return dict(field.split(":", 1) for field in trusted.split("\t") if ":" in field)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("payloads", nargs="+", type=Path)
    parser.add_argument("--version", required=True, help="the version stamped into the build")
    args = parser.parse_args(argv)

    encoded = os.environ.get("TAURI_SIGNING_PRIVATE_KEY", "").strip()
    if not encoded:
        print("::warning::TAURI_SIGNING_PRIVATE_KEY is not set: the build is not signed for updates, so installed browsers won't be offered it.")
        return 0
    try:
        key_id, seed = load_secret_key(encoded, os.environ.get("TAURI_SIGNING_PRIVATE_KEY_PASSWORD", ""))
    except (SignatureError, ValueError) as error:
        raise SystemExit(f"TAURI_SIGNING_PRIVATE_KEY: {error}")
    for path in args.payloads:
        path.with_name(path.name + ".sig").write_text(sign(path, args.version, key_id, seed))
        print(f"{path.name}.sig: {args.version}, key {key_id[::-1].hex().upper()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
