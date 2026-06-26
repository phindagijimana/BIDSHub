"""Windowed smoke-test: confirm the frozen app opens its native window.

Complements smoke_test.py, which runs the server headless (``--no-window``).
A missing GTK/WebKit2 typelib or shared library only fails when pywebview
actually *opens the window* — never in headless mode — so the plain smoke test
can't catch it. This launches the real frozen binary WITH the window under a
virtual display and asserts it (a) starts the server, then (b) survives the
window opening (if ``webview.start()`` crashes on a missing backend lib, the
process exits and we catch it).

Run under a display (CI uses xvfb)::

    xvfb-run -a python packaging/smoke_test_window.py
    xvfb-run -a python packaging/smoke_test_window.py path/to/BIDSHub

Exit 0 = window opened and stayed up; 1 = failed. Note: this proves the window
opens without crashing, not pixel-level WebKit rendering.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

DIST = Path(__file__).resolve().parent.parent / "dist"
GRACE_SECS = 12  # how long the window must stay up after the server is ready


def find_binary(argv_path: str | None) -> Path:
    if argv_path:
        return Path(argv_path)
    for c in [
        DIST / "BIDSHub" / "BIDSHub",
        DIST / "BIDSHub" / "BIDSHub.exe",
        DIST / "BIDSHub.app" / "Contents" / "MacOS" / "BIDSHub",
    ]:
        if c.exists():
            return c
    raise SystemExit(f"No built binary found in {DIST} (run pyinstaller first)")


def health_ok(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/_stcore/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> int:
    binary = find_binary(sys.argv[1] if len(sys.argv) > 1 else None)
    if not os.environ.get("DISPLAY"):
        print("[win-smoke] FAIL: no DISPLAY set — run under `xvfb-run -a`")
        return 1

    data_dir = Path(tempfile.mkdtemp()) / "BIDSHub"
    env = {**os.environ, "BIDSHUB_DATA_DIR": str(data_dir)}
    log = tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False)

    print(f"[win-smoke] launching WINDOWED {binary} (DISPLAY={env['DISPLAY']})")
    proc = subprocess.Popen([str(binary)], env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        # 1. The server must come up (launcher logs "ready at ..." just before
        #    it opens the window).
        port = None
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            m = re.search(r"ready at http://localhost:(\d+)",
                          Path(log.name).read_text(errors="ignore"))
            if m:
                port = int(m.group(1))
                break
            time.sleep(1)

        if port is None:
            print("[win-smoke] FAIL: server never reported ready (crashed before window?)")
            print(Path(log.name).read_text(errors="ignore")[-3000:])
            return 1
        if not health_ok(port):
            print(f"[win-smoke] FAIL: health check failed on port {port}")
            return 1
        print(f"[win-smoke] server ready on {port}; window opening...")

        # 2. If the GTK/WebKit window can't open (missing typelib/.so), the
        #    blocking webview.start() raises and the process exits. Surviving
        #    the grace period means the window opened.
        for _ in range(GRACE_SECS):
            time.sleep(1)
            if proc.poll() is not None:
                print(f"[win-smoke] FAIL: process exited (code {proc.returncode}) — "
                      "window did not open")
                print(Path(log.name).read_text(errors="ignore")[-3000:])
                return 1

        print(f"[win-smoke] PASS: window opened and stayed up {GRACE_SECS}s")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
