"""
Startup smoke tests.

These guard against the kinds of regressions unit tests miss:
  * a new dep imported in src/ that isn't pinned in requirements.txt
  * a module-level NameError or SyntaxError introduced in app.py
  * a schema change that breaks `Database(...)` on a fresh DB

If these pass, `./hub start` / `streamlit run app.py` will at minimum
reach the first Streamlit render on a clean machine.

Cheap to run (< 1s) — intentionally kept at the top of the suite.
"""

import importlib
import os
import pkgutil
import py_compile
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"

sys.path.insert(0, str(REPO_ROOT))


def test_app_py_compiles():
    """app.py must parse cleanly. Catches SyntaxError and bad indentation.

    We compile rather than import because app.py calls st.set_page_config()
    at module scope, which raises outside a `streamlit run` context.
    """
    py_compile.compile(str(REPO_ROOT / "app.py"), doraise=True)


def _src_modules():
    """Yield every importable module under src/ (skip dunders and private)."""
    for info in pkgutil.iter_modules([str(SRC_DIR)]):
        if info.name.startswith("_"):
            continue
        yield f"src.{info.name}"


@pytest.mark.parametrize("mod_name", list(_src_modules()))
def test_src_module_imports(mod_name):
    """Each src/ module must import without error.

    Catches: missing PyPI deps, broken cross-module imports, top-level
    exceptions. Parametrized so a single broken module is reported by name.
    """
    importlib.import_module(mod_name)


def test_version_is_exposed():
    """src.bidshub_version.__version__ must be a non-empty string."""
    from src.bidshub_version import __version__

    assert isinstance(__version__, str) and __version__, "version missing/empty"


def test_fresh_database_initializes():
    """A fresh Database() creates the expected tables.

    Regression guard for the v1.5+ multi-dataset schema. If init_db.py
    drops a table or renames one, this fails immediately.
    """
    from src.database import Database

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "smoke.db")
        Database(db_path)  # constructor initializes schema

        conn = sqlite3.connect(db_path)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        finally:
            conn.close()

    required = {"datasets", "subjects", "scans", "download_queue", "subject_sessions"}
    missing = required - tables
    assert not missing, f"fresh DB missing tables: {missing}"
