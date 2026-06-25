"""Regression test: manual QC update must not fail the qc_history FK.

qc_history.subject_id is an INTEGER FK to subjects.id, NOT the BIDS label.
update_subject_qc used to insert the label, which failed the foreign-key
constraint and made every Subject Detail QC update report "Failed to update".
"""

import os
import sqlite3
import tempfile

import pytest

from src.database import Database
from scripts.init_db import init_database


@pytest.fixture
def db_with_subject():
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "bidshub.db")
    assert init_database(path)
    db = Database(path)
    ds = db.add_dataset(name="DS", platform="local")
    db.add_subject(dataset_id=ds, subject_id="sub-01", local_subject_id="01")
    yield db, path
    try:
        os.remove(path)
    except OSError:
        pass


def test_update_subject_qc_succeeds_and_writes_integer_fk(db_with_subject):
    db, path = db_with_subject
    ok = db.update_subject_qc(
        subject_id="sub-01", qc_status="pass", notes="ok",
        reviewed_by="tester", flagged=True,
    )
    assert ok is True

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        # subject row updated
        row = conn.execute(
            "SELECT qc_status, flagged FROM subjects WHERE subject_id='sub-01'"
        ).fetchone()
        assert row[0] == "pass" and row[1] == 1

        # history row references the integer subjects.id, not the label
        sub_pk = conn.execute(
            "SELECT id FROM subjects WHERE subject_id='sub-01'"
        ).fetchone()[0]
        hist = conn.execute(
            "SELECT subject_id, new_status FROM qc_history"
        ).fetchall()
        assert hist == [(sub_pk, "pass")]
    finally:
        conn.close()


def test_update_subject_qc_missing_subject_returns_false(db_with_subject):
    db, _ = db_with_subject
    assert db.update_subject_qc(subject_id="sub-99", qc_status="pass") is False
