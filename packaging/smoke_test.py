"""Smoke-test a *built* BIDSHub bundle (phase 5).

Launches the frozen launcher headless against an isolated data dir and asserts
that the server comes up healthy and the database is created. Used locally and
in CI right after the build — catches missing hidden imports / data files that
only surface in the frozen app, which unit tests can't see.

    python packaging/smoke_test.py                 # auto-detect dist/BIDSHub[.exe]
    python packaging/smoke_test.py path/to/BIDSHub

Exit code 0 = pass, 1 = fail.
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


def find_binary(argv_path: str | None) -> Path:
    if argv_path:
        return Path(argv_path)
    candidates = [
        DIST / "BIDSHub" / "BIDSHub",
        DIST / "BIDSHub" / "BIDSHub.exe",
        DIST / "BIDSHub.app" / "Contents" / "MacOS" / "BIDSHub",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise SystemExit(f"No built binary found in {DIST} (run packaging/build.sh first)")


def health_ok(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/_stcore/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def frontend_ok(port: int) -> bool:
    """The root URL must serve the actual app HTML, not a 404.

    /_stcore/health returns 200 even when Streamlit (mis)detects development
    mode in a frozen bundle and serves "/" from a non-existent Node dev server.
    This catches that: the app's index.html must come back.
    """
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/", timeout=4) as r:
            if r.status != 200:
                return False
            body = r.read(4000).decode("utf-8", errors="ignore").lower()
            return "streamlit" in body or "<!doctype html" in body
    except Exception:
        return False


def main() -> int:
    binary = find_binary(sys.argv[1] if len(sys.argv) > 1 else None)
    data_dir = Path(tempfile.mkdtemp()) / "BIDSHub"
    env = {**os.environ, "BIDSHUB_DATA_DIR": str(data_dir)}

    print(f"[smoke] launching {binary}")
    log = tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False)
    proc = subprocess.Popen([str(binary), "--no-window"], env=env,
                            stdout=log, stderr=subprocess.STDOUT)
    try:
        port = None
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            text = Path(log.name).read_text(errors="ignore")
            m = re.search(r"ready at http://localhost:(\d+)", text)
            if m:
                port = int(m.group(1))
                break
            time.sleep(1)

        if port is None:
            print("[smoke] FAIL: server never reported ready")
            print(Path(log.name).read_text(errors="ignore")[-2000:])
            return 1

        if not health_ok(port):
            print(f"[smoke] FAIL: health check failed on port {port}")
            return 1
        print(f"[smoke] health OK on port {port}")

        if not frontend_ok(port):
            print(f"[smoke] FAIL: root URL did not serve the app (frozen dev-mode / missing static?)")
            return 1
        print("[smoke] frontend served OK")

        db = data_dir / "bidshub.db"
        if not db.exists():
            print(f"[smoke] FAIL: database not created at {db}")
            return 1
        print(f"[smoke] database created ({db.stat().st_size} bytes)")

        print("[smoke] PASS")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
