"""Render tests for the in-app 'update available' banner (app.render_update_banner).

Uses Streamlit's AppTest so the banner is rendered exactly as the app would
render it — no browser required. The network check and the frozen-build gate
are stubbed so the tests are deterministic and offline-safe.
"""
import sys

from streamlit.testing.v1 import AppTest

def _render_banner_script():
    # Inlined (not module-global) so it survives AppTest's isolated exec context.
    import app
    app._check_latest_release = lambda: {
        "version": "v9.9.9",
        "url": "https://github.com/phindagijimana/BIDSHub/releases/tag/v9.9.9",
        "name": "BIDSHub 9.9.9",
    }
    app.render_update_banner()


def test_banner_shows_on_desktop_when_newer(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    at = AppTest.from_function(_render_banner_script).run()
    assert any("v9.9.9" in a.value for a in at.info), "expected an update banner"


def test_banner_hidden_when_not_frozen(monkeypatch):
    # Source / Docker runs (not frozen) must not show the 'reinstall' banner.
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    at = AppTest.from_function(_render_banner_script).run()
    assert len(at.info) == 0


def test_banner_hidden_when_dismissed(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    def script():
        import streamlit as st
        import app
        st.session_state.update_banner_dismissed = True
        app._check_latest_release = lambda: NEWER
        app.render_update_banner()

    at = AppTest.from_function(script).run()
    assert len(at.info) == 0


def test_banner_hidden_when_no_update(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    def script():
        import app
        app._check_latest_release = lambda: None
        app.render_update_banner()

    at = AppTest.from_function(script).run()
    assert len(at.info) == 0
