"""Render tests for page modules extracted from app.py into views/.

These give the de-monolithing refactor a runtime safety net: unit tests don't
render Streamlit pages, so a broken extraction (missing import, bad lazy import)
would otherwise only surface in the live app. Each test renders a page in
isolation with a mocked database via Streamlit's AppTest.
"""
from unittest.mock import MagicMock

from streamlit.testing.v1 import AppTest


def _dashboard_script():
    import streamlit as st
    from unittest.mock import MagicMock
    db = MagicMock()
    db.get_stats.return_value = {
        'total_subjects': 2, 'complete_subjects': 1, 'total_scans': 4,
        'downloaded_scans': 4, 'qc_pending': 2, 'qc_pass': 0,
        'qc_review': 0, 'qc_fail': 0,
    }
    st.session_state.db = db
    st.session_state.current_page = 'dashboard'
    from views.dashboard import page_dashboard
    page_dashboard()


def test_dashboard_page_renders():
    at = AppTest.from_function(_dashboard_script).run()
    assert not at.exception, f"dashboard render raised: {at.exception}"
    labels = [m.label for m in at.metric]
    # Overview + QC metric cards
    assert "Subjects" in labels
    assert "Pending" in labels


def _home_script():
    import streamlit as st
    from unittest.mock import MagicMock
    db = MagicMock()
    db.get_all_datasets.return_value = []  # no datasets -> "Getting Started" path
    st.session_state.db = db
    st.session_state.current_page = 'home'
    st.session_state.dataset_name = None
    from views.home import page_home
    page_home()


def test_home_page_renders():
    at = AppTest.from_function(_home_script).run()
    assert not at.exception, f"home render raised: {at.exception}"


def _viewer_script():
    import streamlit as st
    from unittest.mock import MagicMock
    db = MagicMock()
    db.get_all_datasets.return_value = []
    st.session_state.db = db
    st.session_state.current_page = 'viewer'
    from views.viewer import page_viewer
    page_viewer()


def test_viewer_page_renders():
    at = AppTest.from_function(_viewer_script).run()
    assert not at.exception, f"viewer render raised: {at.exception}"


def _mk_empty_db():
    # Inlined per-script (AppTest runs scripts in an isolated namespace).
    from unittest.mock import MagicMock
    db = MagicMock()
    db.get_all_datasets.return_value = []
    db.get_all_subjects.return_value = []
    db.get_subjects.return_value = []
    return db


def _subjects_script():
    import streamlit as st
    from unittest.mock import MagicMock
    import app
    app.init_session_state()  # initialize the session-state keys the page expects
    db = MagicMock()
    db.get_all_datasets.return_value = []
    db.get_all_subjects.return_value = []
    db.get_subjects.return_value = []
    st.session_state.db = db
    st.session_state.current_page = 'subjects'
    st.session_state.subjects_per_page = 25       # set by main() in the real app
    st.session_state.current_page_num = 1
    from views.subjects import page_subjects
    page_subjects()


def _export_script():
    import streamlit as st
    from unittest.mock import MagicMock
    db = MagicMock()
    db.get_all_datasets.return_value = []
    db.get_all_subjects.return_value = []
    db.get_subjects.return_value = []
    st.session_state.db = db
    st.session_state.current_page = 'export'
    from views.export import page_export
    page_export()


def _transfer_script():
    import streamlit as st
    from unittest.mock import MagicMock
    db = MagicMock()
    db.get_all_datasets.return_value = []
    st.session_state.db = db
    st.session_state.current_page = 'transfer'
    from views.transfer import page_transfer
    page_transfer()


def test_subjects_page_renders():
    at = AppTest.from_function(_subjects_script).run()
    assert not at.exception, f"subjects render raised: {at.exception}"


def test_export_page_renders():
    at = AppTest.from_function(_export_script).run()
    assert not at.exception, f"export render raised: {at.exception}"


def test_transfer_page_renders():
    at = AppTest.from_function(_transfer_script).run()
    assert not at.exception, f"transfer render raised: {at.exception}"


def _qc_script():
    import streamlit as st
    from unittest.mock import MagicMock
    import app
    app.init_session_state()
    st.session_state.db = MagicMock()
    st.session_state.current_page = 'qc'
    from views.qc import page_qc
    page_qc()


def test_qc_page_no_refactor_errors():
    # The QC page builds real QCManager/AutomatedQC objects, so a mocked DB may
    # raise data-shape errors — those are not refactor bugs. We assert only that
    # no import/name error (the refactor failure mode) occurred.
    at = AppTest.from_function(_qc_script).run()
    blob = " ".join(
        f"{getattr(e, 'type', '')} {getattr(e, 'value', '')} {getattr(e, 'message', '')}"
        for e in at.exception
    )
    for bad in ("NameError", "ImportError", "ModuleNotFoundError", "cannot import"):
        assert bad not in blob, f"qc page refactor error: {blob}"


def _manage_datasets_script():
    import streamlit as st
    from unittest.mock import MagicMock
    import app
    app.init_session_state()
    db = MagicMock()
    db.get_all_datasets.return_value = []
    st.session_state.db = db
    st.session_state.current_page = 'manage_datasets'
    from views.datasets import page_manage_datasets
    page_manage_datasets()


def test_manage_datasets_page_no_refactor_errors():
    at = AppTest.from_function(_manage_datasets_script).run()
    blob = " ".join(
        f"{getattr(e, 'type', '')} {getattr(e, 'value', '')} {getattr(e, 'message', '')}"
        for e in at.exception
    )
    for bad in ("NameError", "ImportError", "ModuleNotFoundError", "cannot import"):
        assert bad not in blob, f"manage_datasets refactor error: {blob}"
