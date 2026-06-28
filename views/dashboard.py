"""Dashboard page (extracted from app.py)."""
import streamlit as st
from views.common import render_breadcrumb


def page_dashboard():
    """Main dashboard page."""
    render_breadcrumb('dashboard')
    st.markdown('<h1 class="main-header">BIDSHub</h1>',
                unsafe_allow_html=True)

    # Show integrity warning if issues detected (v3.1.1+)
    if st.session_state.get('show_integrity_warning', False):
        issues = st.session_state.get('integrity_issues', {})
        total_issues = sum(issues.values())

        if total_issues > 0:
            with st.expander(f"Database Integrity Alert: {total_issues} issue(s) detected", expanded=True):
                for issue_type, count in issues.items():
                    if count > 0:
                        st.markdown(f"- **{issue_type.replace('_', ' ').title()}**: {count}")

                st.markdown("Go to **Manage Datasets** to run database maintenance.")

    # Get statistics
    stats = st.session_state.db.get_stats()

    # Show helpful message for first-time users (v3.1.1+)
    if stats.get('total_subjects', 0) == 0:
        st.info("Welcome to BIDSHub! Get started by adding your first dataset in **Manage Datasets**.")

    st.markdown('<h2 class="section-header">Overview</h2>',
                unsafe_allow_html=True)

    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Subjects", stats.get('total_subjects', 0))

    with col2:
        complete = stats.get('complete_subjects', 0)
        total = stats.get('total_subjects', 1)
        pct = (complete / total * 100) if total > 0 else 0
        st.metric("Complete Subjects", complete,
                 delta=f"{pct:.1f}% have both sessions",
                 delta_color="off")

    with col3:
        st.metric("Total Scans", stats.get('total_scans', 0))

    with col4:
        downloaded = stats.get('downloaded_scans', 0)
        total_scans = stats.get('total_scans', 1)
        pct = (downloaded / total_scans * 100) if total_scans > 0 else 0
        st.metric("Downloaded", downloaded,
                 delta=f"{pct:.1f}% of scans",
                 delta_color="off")

    st.markdown("---")

    # QC Overview
    st.markdown('<h2 class="section-header">Quality Control Status</h2>',
                unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Pending", stats.get('qc_pending', 0))

    with col2:
        st.metric("Pass", stats.get('qc_pass', 0))

    with col3:
        st.metric("Needs Review", stats.get('qc_review', 0))

    with col4:
        st.metric("Fail", stats.get('qc_fail', 0))
