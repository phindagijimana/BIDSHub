"""Tests for the desktop entry point's pure helpers (Phase 2).

The window/server lifecycle needs a real Streamlit process and a GUI, so it is
exercised by a manual smoke run; here we lock in the deterministic pieces:
port selection, the server re-exec command, config, and health-wait timeout.
"""

import socket
import sys
import time
from pathlib import Path

from desktop import app as dapp


def test_find_free_port_returns_bindable_port():
    port = dapp.find_free_port(start=8600, span=50)
    assert 8600 <= port <= 8650
    # The returned port must actually be bindable.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", port))


def test_find_free_port_skips_taken_port():
    # Occupy one port, then ask starting at it — must skip to the next.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
        taken.bind(("127.0.0.1", 0))
        taken_port = taken.getsockname()[1]
        chosen = dapp.find_free_port(start=taken_port, span=50)
        assert chosen != taken_port


def test_is_port_free_detects_taken():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
        taken.bind(("127.0.0.1", 0))
        taken_port = taken.getsockname()[1]
        assert dapp.is_port_free(taken_port) is False


def test_server_command_dev_mode(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    cmd = dapp.server_command(8533)
    assert cmd[0] == sys.executable
    assert "desktop.app" in cmd
    assert "--role=server" in cmd
    assert "--port=8533" in cmd


def test_server_command_frozen_mode(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    cmd = dapp.server_command(8533)
    assert cmd[0] == sys.executable
    assert "-m" not in cmd  # frozen binary can't run `-m`
    assert "--role=server" in cmd
    assert "--port=8533" in cmd


def test_streamlit_flag_options_are_desktop_safe():
    opts = dapp.streamlit_flag_options(8533)
    assert opts["server.port"] == 8533
    assert opts["server.headless"] is True
    assert opts["server.fileWatcherType"] == "none"   # no watchdog in a bundle
    assert opts["browser.gatherUsageStats"] is False


def test_streamlit_env_pins_port_via_env():
    # Env overrides are what actually win over a stray working-dir config.toml.
    env = dapp.streamlit_env(8533)
    assert env["STREAMLIT_SERVER_PORT"] == "8533"
    assert env["STREAMLIT_BROWSER_SERVER_PORT"] == "8533"
    assert env["STREAMLIT_SERVER_HEADLESS"] == "true"
    assert env["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] == "none"


def test_server_cwd_is_the_data_dir(monkeypatch, tmp_path):
    # cwd must be the per-user data dir (no repo .streamlit/config.toml there).
    target = tmp_path / "BIDSHub"
    monkeypatch.setenv("BIDSHUB_DATA_DIR", str(target))
    cwd = dapp.server_cwd()
    assert cwd == str(target)
    assert (target).is_dir()


def test_app_script_path_points_at_app_py():
    p = Path(dapp.app_script_path())
    assert p.name == "app.py"


def test_health_and_window_urls():
    assert dapp.health_url(8533) == "http://localhost:8533/_stcore/health"


def test_wait_for_health_times_out_quickly():
    # Nothing is listening on this port -> returns False within the timeout.
    start = time.monotonic()
    ok = dapp.wait_for_health(59999, timeout=1.0, interval=0.2)
    assert ok is False
    assert time.monotonic() - start < 5.0
