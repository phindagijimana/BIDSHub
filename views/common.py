"""Shared helpers used across the page modules in ``views/``.

These were previously defined in ``app.py`` and imported back into the view
modules via lazy ``from app import ...`` calls to dodge a circular import.
Hosting them here (the entry point depends on ``views``, never the reverse)
removes that bidirectional dependency, so views can import them at module top.
"""

import os

import streamlit as st


def render_page_header(current_page: str, show_back_to_dashboard: bool = False):
    """Render page header with optional back button."""
    if show_back_to_dashboard and current_page != 'dashboard':
        col1, col2 = st.columns([5, 1])
        with col2:
            if st.button("← Dashboard", width='stretch', key=f"back_dash_{current_page}"):
                st.session_state.current_page = 'dashboard'
                st.rerun()


def render_breadcrumb(current_page: str, parent_page: str = None):
    """Render breadcrumb navigation at top of page - only for nested pages."""
    # Only show breadcrumb for nested pages (like subject detail)
    # Top-level pages use sidebar for navigation
    if current_page not in ['subject_detail']:
        return

    # Page names mapping (v3.1.1+: Added transfer)
    page_names = {
        'dashboard': 'Dashboard',
        'subjects': 'Subjects',
        'subject_detail': 'Subject Detail',
        'transfer': 'Data Transfer',
        'downloads': 'Download Manager',
        'qc': 'QC Dashboard',
        'export': 'Export',
        'setup': 'Settings'
    }

    # Simple text breadcrumb for context
    st.caption(f"Home / {page_names.get(parent_page, 'Subjects')} / {page_names.get(current_page, current_page)}")


def get_available_sessions(dataset_id):
    """Get list of available sessions for a dataset from subject_sessions table."""
    if not st.session_state.db or not dataset_id:
        return []

    try:
        # Query unique session IDs for this dataset
        sessions_info = st.session_state.db.execute_query(
            "SELECT DISTINCT session_id FROM subject_sessions WHERE dataset_id = ? ORDER BY session_id",
            (dataset_id,),
            fetch=True
        )
        return [row[0] for row in sessions_info] if sessions_info else []
    except Exception:
        return []


def display_session_scans(session_id, scans, subject_id, platform=None, dataset_remote_id=None, use_db_scans=False):
    """Display scans for a specific session with actions.

    Args:
        session_id: Session identifier (e.g., '2WK', 'ses-01')
        scans: List of scan dictionaries for this session
        subject_id: Subject identifier
        platform: Platform name (for URL generation)
        dataset_remote_id: Remote dataset ID
        use_db_scans: Whether using database scans vs BIDS loader
    """
    st.markdown("---")
    st.markdown(f'<h2 class="section-header">Session {session_id}</h2>',
                unsafe_allow_html=True)

    if scans:
        # Scan-level QC interface (v3.1+)
        for idx, scan in enumerate(scans):
            from src.utils import format_file_size

            if use_db_scans:
                # Database scans (cloud + multi-dataset browse). Column names
                # come straight from the scans table.
                file_size = scan.get('file_size_bytes', scan.get('file_size', 0))
                is_stub = not scan.get('is_downloaded')
                scan_id = scan.get('id')
            else:
                # BIDS loader scans (local datasets)
                file_size = st.session_state.bids_loader.get_file_size(
                    scan['file_path']
                )
                is_stub = st.session_state.bids_loader.is_stub_file(
                    scan['file_path']
                )
                # Get scan_id from database
                db_scans = st.session_state.db.get_subject_scans(subject_id, session_id)
                scan_id = None
                for db_scan in db_scans:
                    if db_scan['file_path'] == scan['file_path']:
                        scan_id = db_scan['id']
                        break

            # Get current QC status from database
            qc_data = st.session_state.db.get_scan_qc(scan_id) if scan_id else None
            current_qc_status = qc_data.get('qc_status', 'pending') if qc_data else 'pending'
            current_notes = qc_data.get('qc_notes', '') if qc_data else ''
            current_flagged = qc_data.get('flagged', 0) if qc_data else 0

            # Display scan with QC controls
            with st.container():
                col1, col2, col3, col4, col5, col6 = st.columns([2, 1, 1, 2, 1, 1])

                with col1:
                    st.markdown(f"**{scan.get('suffix', 'unknown')}**")
                    st.caption(f"{scan.get('modality', '')} | {format_file_size(file_size)}")

                with col2:
                    status_badge = 'Stub' if is_stub else 'Downloaded'
                    st.caption(status_badge)

                with col3:
                    # QC status indicator
                    qc_colors = {
                        'pass': '[PASS]',
                        'fail': '[FAIL]',
                        'needs_review': '[REVIEW]',
                        'pending': '[INACTIVE]'
                    }
                    qc_icon = qc_colors.get(current_qc_status, '[INACTIVE]')
                    st.caption(f"{qc_icon} {current_qc_status}")

                with col4:
                    # Quick QC buttons
                    qc_col1, qc_col2, qc_col3 = st.columns(3)
                    with qc_col1:
                        if st.button("Pass", key=f"qc_pass_{scan_id}_{idx}", help="Mark as Pass"):
                            if scan_id:
                                st.session_state.db.update_scan_qc(
                                    scan_id=scan_id,
                                    qc_status='pass',
                                    reviewed_by=os.getenv('USER', 'reviewer'),
                                    flagged=False
                                )
                                st.rerun()
                    with qc_col2:
                        if st.button("[X]", key=f"qc_fail_{scan_id}_{idx}", help="Mark as Fail"):
                            if scan_id:
                                st.session_state.db.update_scan_qc(
                                    scan_id=scan_id,
                                    qc_status='fail',
                                    reviewed_by=os.getenv('USER', 'reviewer'),
                                    flagged=True
                                )
                                st.rerun()
                    with qc_col3:
                        if st.button("?", key=f"qc_review_{scan_id}_{idx}", help="Needs Review"):
                            if scan_id:
                                st.session_state.db.update_scan_qc(
                                    scan_id=scan_id,
                                    qc_status='needs_review',
                                    reviewed_by=os.getenv('USER', 'reviewer'),
                                    flagged=True
                                )
                                st.rerun()

                with col5:
                    # View button for quick access to viewer
                    if st.button("[View]", key=f"view_{scan_id}_{idx}", help="Open in Viewer", width='stretch'):
                        st.session_state.viewer_selected_file = scan.get('file_path', '')
                        st.session_state.viewer_file_loaded = True
                        st.session_state.current_page = 'viewer'
                        st.rerun()

                with col6:
                    # Download action
                    if is_stub and platform and dataset_remote_id:
                        if st.button("[DL]", key=f"dl_{scan_id}_{idx}", help="Download", width='stretch'):
                            st.info("Use Download Manager for batch downloads")

                # Show QC notes if any
                if current_notes:
                    st.caption(f"[Note] {current_notes}")

                # Add notes expander
                with st.expander(f"QC Notes", expanded=False):
                    notes_input = st.text_area(
                        "Notes",
                        value=current_notes,
                        key=f"notes_{scan_id}_{idx}",
                        height=80,
                        label_visibility="collapsed"
                    )

                    if st.button("Save Notes", key=f"save_notes_{scan_id}_{idx}"):
                        if scan_id:
                            st.session_state.db.update_scan_qc(
                                scan_id=scan_id,
                                qc_status=current_qc_status,
                                notes=notes_input,
                                reviewed_by=os.getenv('USER', 'reviewer')
                            )
                            st.success("Notes saved")
                            st.rerun()

        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("Add All to Queue", key=f"dl_{session_id}"):
                # Initialize agent factory and download manager if needed (v3.1.1+)
                if 'agent_factory' not in st.session_state:
                    from src.agent_factory import AgentFactory
                    st.session_state.agent_factory = AgentFactory(st.session_state.db)

                if 'download_manager' not in st.session_state:
                    from src.download_manager import DownloadManager
                    st.session_state.download_manager = DownloadManager(
                        ps_client=st.session_state.ps_client,
                        database=st.session_state.db,
                        max_concurrent=3,
                        agent_factory=st.session_state.agent_factory
                    )

                # Add each scan to queue
                added = 0
                for scan in scans:
                    # Get package ID (from stub file or metadata)
                    package_id = None
                    file_path = scan.get('file_path', '')

                    if use_db_scans:
                        package_id = scan.get('pennsieve_package_id')
                    elif st.session_state.bids_loader.is_stub_file(file_path):
                        from src.utils import parse_pennsieve_stub
                        package_id = parse_pennsieve_stub(file_path)

                    if package_id:
                        # Get scan from database to get scan_id
                        db_scans = st.session_state.db.get_subject_scans(subject_id, session_id)
                        scan_id = None
                        for db_scan in db_scans:
                            if db_scan['file_path'] == file_path:
                                scan_id = db_scan['id']
                                break

                        # If scan not in DB, add it
                        if not scan_id:
                            scan_id = st.session_state.db.add_scan(
                                subject_id=subject_id,
                                session=session_id,
                                modality=scan.get('modality', ''),
                                file_path=file_path,
                                suffix=scan.get('suffix', ''),
                                pennsieve_package_id=package_id
                            )

                        if scan_id:
                            file_size = scan.get('file_size', 0) if use_db_scans else st.session_state.bids_loader.get_file_size(file_path)
                            success = st.session_state.download_manager.add_to_queue(
                                scan_id=scan_id,
                                subject_id=subject_id,
                                file_path=file_path,
                                package_id=package_id,
                                file_size=file_size
                            )
                            if success:
                                added += 1

                if added > 0:
                    st.success(f"Added {added} scans to download queue")
                else:
                    st.warning("No scans added to queue")
    else:
        st.info(f"No scans found for session {session_id}")


def get_subject_session_columns(subject):
    """Get session columns dynamically for export.

    Returns dict with session column names and values.
    """
    dataset_id = subject.get('dataset_id')
    subject_id = subject['subject_id']

    # Get sessions for this subject
    if st.session_state.db and dataset_id:
        sessions_info = st.session_state.db.get_subject_sessions(subject_id, dataset_id)

        columns = {}
        for session in sessions_info:
            session_id = session['session_id']
            columns[f'Has {session_id}'] = 'Yes'
            columns[f'Scan Count {session_id}'] = session.get('scan_count', 0)

        return columns

    # Fallback to legacy columns if no session data
    return {
        'Has 2WK': 'Yes' if subject.get('has_2wk') else 'No',
        'Has 6MO': 'Yes' if subject.get('has_6mo') else 'No',
        'Scan Count 2WK': subject.get('scan_count_2wk', 0),
        'Scan Count 6MO': subject.get('scan_count_6mo', 0)
    }
