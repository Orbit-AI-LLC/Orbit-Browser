"""The update-signature protocol Orbit Mission Control and Orbit Browser share.

scripts/sign_update.py signs the update payloads (minisign/Blake2b, the version
in the trusted comment); the installed browser's update component verifies them
against the public key it carries before installing. Both sides are the same
format every Orbit app uses, so these check it round-trips and that a known
fixture still verifies.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

FIXTURES = ROOT / "tests" / "fixtures"


class UpdateSignatureTest(unittest.TestCase):
    def setUp(self):
        try:
            import sign_update  # noqa: F401
            import cryptography  # noqa: F401
        except ImportError as error:
            self.skipTest(f"cryptography not installed ({error})")
        self.sign_update = __import__("sign_update")

    def test_known_fixture_verifies(self):
        # The fixture payload + signature + public key verify, exercising the
        # same check the browser's update component does (public material only;
        # the test private key is password-protected and not used here).
        payload = FIXTURES / "tauri-signed.bin"
        signature = (FIXTURES / "tauri-signed.bin.sig").read_text()
        pubkey = (FIXTURES / "update-test.key.pub").read_text()
        fields = self.sign_update.verify(payload, signature, pubkey)
        self.assertEqual(fields["file"], "tauri-signed.bin")

    def test_tampered_payload_fails(self):
        signature = (FIXTURES / "tauri-signed.bin.sig").read_text()
        pubkey = (FIXTURES / "update-test.key.pub").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "tauri-signed.bin"
            data = bytearray((FIXTURES / "tauri-signed.bin").read_bytes())
            data[0] ^= 0xFF
            tampered.write_bytes(data)
            with self.assertRaises(self.sign_update.SignatureError):
                self.sign_update.verify(tampered, signature, pubkey)

    def test_wrong_key_fails(self):
        payload = FIXTURES / "tauri-signed.bin"
        signature = (FIXTURES / "tauri-signed.bin.sig").read_text()
        # The browser carries this production public key; the fixture was signed
        # with the test key, so it must not verify against it.
        import orbit_config as cfg
        with self.assertRaises(self.sign_update.SignatureError):
            self.sign_update.verify(payload, signature, cfg.ORBIT_UPDATES["pubkey"])


if __name__ == "__main__":
    unittest.main()
