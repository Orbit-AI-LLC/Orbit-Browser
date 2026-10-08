"""A small Marionette client: drives Orbit Browser the way Firefox's own
tests do, over the protocol the browser serves when started with
--marionette (a TCP port, JSON messages prefixed with their length).

Used by tests/smoke.py. Only what the smoke test needs.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path


class MarionetteError(Exception):
    pass


class Browser:
    """Starts a build in a fresh profile of its own and talks to it."""

    def __init__(self, executable: Path, *, headless: bool = True, port: int = 2828):
        self.profile = Path(tempfile.mkdtemp(prefix="orbit-browser-profile-"))
        (self.profile / "user.js").write_text(f'user_pref("marionette.port", {port});\n')
        env = {**os.environ, "MOZ_CRASHREPORTER_DISABLE": "1"}
        if headless:
            env["MOZ_HEADLESS"] = "1"
            env["MOZ_HEADLESS_WIDTH"] = "1440"
            env["MOZ_HEADLESS_HEIGHT"] = "900"
        self.process = subprocess.Popen(
            [str(executable), "--marionette", "-remote-allow-system-access", "--profile", str(self.profile)],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.next_id = 0
        deadline = time.time() + 60
        while True:
            try:
                self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
                break
            except OSError:
                if time.time() > deadline or self.process.poll() is not None:
                    self.quit()
                    raise MarionetteError("The browser didn't start (or didn't serve Marionette).")
                time.sleep(0.5)
        self.sock.settimeout(120)
        self._read()  # the server's hello
        self.command("WebDriver:NewSession", {"capabilities": {}})

    def _read(self):
        size = b""
        while not size.endswith(b":"):
            chunk = self.sock.recv(1)
            if not chunk:
                raise MarionetteError("Marionette closed the connection.")
            size += chunk
        length = int(size[:-1])
        data = b""
        while len(data) < length:
            data += self.sock.recv(length - len(data))
        return json.loads(data)

    def command(self, name: str, params: dict | None = None):
        self.next_id += 1
        body = json.dumps([0, self.next_id, name, params or {}]).encode()
        self.sock.sendall(str(len(body)).encode() + b":" + body)
        while True:
            message = self._read()
            if message[0] == 1 and message[1] == self.next_id:
                _, _, error, result = message
                if error:
                    raise MarionetteError(f"{name}: {error.get('error')}: {error.get('message')}")
                return result.get("value", result) if isinstance(result, dict) else result

    def chrome(self):
        self.command("Marionette:SetContext", {"value": "chrome"})

    def content(self):
        self.command("Marionette:SetContext", {"value": "content"})

    def js(self, script: str, *args, asynchronous: bool = False):
        """Runs script (a function body; `arguments` holds args) in the
        current context. With asynchronous, the last argument is the callback
        that ends it."""
        name = "WebDriver:ExecuteAsyncScript" if asynchronous else "WebDriver:ExecuteScript"
        return self.command(name, {"script": script, "args": list(args), "scriptTimeout": 60000})

    def screenshot(self, target: Path, *, full: bool = False) -> Path:
        data = self.command("WebDriver:TakeScreenshot", {"full": full, "hash": False})
        target.write_bytes(base64.b64decode(data))
        return target

    def quit(self):
        try:
            if getattr(self, "sock", None):
                self.command("Marionette:Quit", {"flags": ["eForceQuit"]})
        except Exception:
            pass
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.kill()
        shutil.rmtree(self.profile, ignore_errors=True)
