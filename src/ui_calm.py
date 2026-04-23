"""
Calm UI helpers for Streamlit: less banner noise, toasts for transient feedback.
"""

from __future__ import annotations

import streamlit as st

# Platforms handled by execute_downloads() in app.py
DOWNLOAD_QUEUE_PLATFORMS = frozenset(
    {"pennsieve", "openneuro", "dandi", "xnat", "hpc", "remote_server"}
)


def toast_ok(message: str) -> None:
    """Short-lived confirmation; falls back to success if toast unavailable."""
    try:
        st.toast(message)
    except Exception:
        st.success(message)


def toast_note(message: str) -> None:
    """Brief non-error note; falls back to info."""
    try:
        st.toast(message)
    except Exception:
        st.info(message)


def expected_empty(message: str) -> None:
    """Expected empty state (e.g. not synced yet) — neutral, not a warning banner."""
    st.caption(message)


def quiet_queue_empty() -> None:
    st.caption("No items in the download queue.")


def render_xnat_beta_notice() -> None:
    """Dismissible one-line beta note for XNAT (session state)."""
    if st.session_state.get("ux_dismiss_xnat_beta"):
        return
    c1, c2 = st.columns([5, 1])
    with c1:
        st.caption(
            "XNAT support is in beta — export or organize data as BIDS when possible."
        )
    with c2:
        if st.button("Dismiss", key="ux_dismiss_xnat_beta_btn", type="secondary"):
            st.session_state.ux_dismiss_xnat_beta = True
            st.rerun()
