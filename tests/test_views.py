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
