"""Phase 2 — desktop entry point: run BIDSHub in a native window.

BIDSHub is a Streamlit server app, so "desktop" means: start the server
locally, wait for it to come up, and show it in a native OS window instead of a
browser tab. Two roles share this one module so the same code works frozen:

- **launcher** (default): prepares the per-user data dir + DB (Phase 1), picks
  a free port, spawns a *server* child process, waits for health, then opens a
  pywebview window pointed at it. Closing the window stops the child.
- **server** (``--role=server``): runs the Streamlit server in-process and
  blocks. Run on the child's main thread so Streamlit's signal handlers work.

Why a child process rather than a background thread: Streamlit installs signal
handlers (main thread only) and pywebview must own the main thread on macOS —
they can't both be the main thread in one process. Re-exec-self keeps this
working identically in a PyInstaller bundle, where ``sys.executable`` is the
app binary.

Run in development::

    python -m desktop.app                 # launcher + window
    python -m desktop.app --no-window     # launcher, server only (for testing)
    python -m desktop.app --role=server --port=8533
"""
from __future__ import annotations

import argparse
import logging
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bidshub.desktop")

APP_TITLE = "BIDSHub"
DEFAULT_PORT = 8501
PORT_SPAN = 50


# --------------------------------------------------------------------------- #
# Pure helpers (unit-testable, no side effects on import)
# --------------------------------------------------------------------------- #

def is_port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_free_port(start: int = DEFAULT_PORT, span: int = PORT_SPAN) -> int:
    """First free port in [start, start+span]; raise if none."""
    for port in range(start, start + span + 1):
        if is_port_free(port):
            return port
    raise RuntimeError(f"No free port in {start}..{start + span}")


def app_script_path() -> str:
    """Absolute path to app.py, in dev tree or a PyInstaller bundle."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return str(base / "app.py")


def streamlit_flag_options(port: int) -> dict:
    """Streamlit config for an embedded desktop server.

    Headless (we open our own window), no file watcher (none in a frozen app),
    no telemetry, minimal toolbar so it doesn't look like a dev server.
    """
    return {
        "server.port": port,
        "server.address": "localhost",
        "server.headless": True,
        "server.fileWatcherType": "none",
        "server.runOnSave": False,
        "browser.gatherUsageStats": False,
        "client.toolbarMode": "minimal",
    }


def streamlit_env(port: int) -> dict:
    """Environment overrides that pin the server's behaviour deterministically.

    Streamlit env vars are honoured during config init, *before* any stray
    ``.streamlit/config.toml`` in the working directory is applied — and a repo
    checkout's config.toml pins ``server.port = 8501``, which would otherwise
    override our chosen port. Setting browser.serverPort too keeps the URL it
    prints (and any client-side calls) on our port.
    """
    return {
        "STREAMLIT_SERVER_PORT": str(port),
        "STREAMLIT_BROWSER_SERVER_PORT": str(port),
        "STREAMLIT_SERVER_ADDRESS": "localhost",
        "STREAMLIT_BROWSER_SERVER_ADDRESS": "localhost",
        "STREAMLIT_SERVER_HEADLESS": "true",
        "STREAMLIT_SERVER_FILE_WATCHER_TYPE": "none",
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        "STREAMLIT_GLOBAL_DEVELOPMENT_MODE": "false",
    }


def server_cwd() -> str:
    """Working dir for the server child.

    The per-user data dir, deliberately *not* a repo checkout: it has no
    ``.streamlit/config.toml`` to override our settings, and keeps the embedded
    server isolated from the source tree.
    """
    from src.app_paths import data_dir
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def server_command(port: int) -> list:
    """Argv that re-execs this entry point in server role.

    Frozen: the app binary itself (``sys.executable``). Dev: the interpreter
    running ``-m desktop.app``.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, f"--role=server", f"--port={port}"]
    return [sys.executable, "-m", "desktop.app", "--role=server", f"--port={port}"]


def health_url(port: int) -> str:
    return f"http://localhost:{port}/_stcore/health"


def setup_logging() -> None:
    """Log to stderr and, once a data dir is known, to a rotating file.

    A windowed build (console=False) has no terminal, so the file under
    ``<data_dir>/logs/desktop.log`` is the only diagnostic trail. Best-effort:
    if the data dir can't be resolved/created yet, fall back to stderr only.
    """
    from logging.handlers import RotatingFileHandler

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        root.addHandler(stream)

    try:
        from src.app_paths import data_dir
        log_dir = data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(log_dir / "desktop.log", maxBytes=1_000_000, backupCount=3)
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except Exception:
        pass  # stderr-only is acceptable


# --------------------------------------------------------------------------- #
# Server role
# --------------------------------------------------------------------------- #

def run_server(port: int) -> None:
    """Run the Streamlit server in-process (blocks). Child-process main thread."""
    # Pin behaviour via env *before* importing streamlit (config reads env at
    # init, and env beats a stray working-dir config.toml).
    os.environ.update(streamlit_env(port))

    from streamlit import config as st_config
    from streamlit.web import bootstrap as st_bootstrap

    flag_options = streamlit_flag_options(port)
    for key, value in flag_options.items():
        try:
            st_config.set_option(key, value)
        except Exception:  # some options are read-only depending on context
            pass

    script = app_script_path()
    logger.info("Starting Streamlit server on port %s (%s)", port, script)
    st_bootstrap.run(script, is_hello=False, args=[], flag_options=flag_options)


# --------------------------------------------------------------------------- #
# Launcher role
# --------------------------------------------------------------------------- #

def wait_for_health(port: int, timeout: float = 60.0, interval: float = 0.4) -> bool:
    """Poll the Streamlit health endpoint until ready or timeout."""
    deadline = time.monotonic() + timeout
    url = health_url(port)
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def spawn_server(port: int) -> subprocess.Popen:
    """Launch the server child with a pinned port and an isolated working dir.

    Env carries BIDSHUB_DATA_DIR (so the child resolves the same paths) plus the
    Streamlit overrides; cwd is the data dir so no repo config.toml interferes.
    """
    cmd = server_command(port)
    env = os.environ.copy()
    env.update(streamlit_env(port))
    # In dev the child runs `-m desktop.app` from the data dir (not the repo),
    # so the repo must be importable via PYTHONPATH. Frozen builds re-exec the
    # binary directly and need none of this.
    if not getattr(sys, "frozen", False):
        repo_root = str(Path(__file__).resolve().parent.parent)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = repo_root + (os.pathsep + existing if existing else "")
    cwd = server_cwd()
    logger.info("Spawning server on port %s (cwd=%s): %s", port, cwd, " ".join(cmd))
    return subprocess.Popen(cmd, env=env, cwd=cwd)


def open_window(port: int, title: str = APP_TITLE) -> None:
    """Open the native window (blocks until closed). Lazy import of pywebview."""
    import webview  # imported lazily so the module loads without the GUI dep

    webview.create_window(title, health_url(port).replace("/_stcore/health", ""),
                          width=1400, height=900, min_size=(900, 600))
    webview.start()


def launch(open_gui: bool = True, port: Optional[int] = None) -> int:
    """Full desktop launch: bootstrap, start server, (optionally) open window.

    With ``open_gui=False`` it starts the server and blocks until interrupted —
    used for headless verification. Returns a process exit code.
    """
    from desktop.bootstrap import bootstrap

    info = bootstrap()
    setup_logging()  # now BIDSHUB_DATA_DIR is set -> log under the data dir
    logger.info("Data dir: %s", info["data_dir"])

    port = port or find_free_port()
    proc = spawn_server(port)
    try:
        if not wait_for_health(port):
            logger.error("Server did not become healthy on port %s", port)
            proc.terminate()
            return 1
        logger.info("BIDSHub ready at http://localhost:%s", port)

        if open_gui:
            open_window(port)
        else:
            print(f"BIDSHub running at http://localhost:{port} (Ctrl-C to stop)")
            try:
                proc.wait()
            except KeyboardInterrupt:
                pass
    finally:
        _terminate(proc)
    return 0


def _terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="bidshub-desktop")
    parser.add_argument("--role", choices=["launcher", "server"], default="launcher")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--no-window", action="store_true",
                        help="launcher: run the server without opening a window")
    args = parser.parse_args(argv)

    if args.role == "server":
        if args.port is None:
            parser.error("--role=server requires --port")
        setup_logging()  # env (incl. BIDSHUB_DATA_DIR) is inherited from launcher
        run_server(args.port)
        return 0

    return launch(open_gui=not args.no_window, port=args.port)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()  # safe no-op unless frozen + multiprocessing
    sys.exit(main())
