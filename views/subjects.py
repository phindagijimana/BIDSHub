"""Subjects browser + subject detail pages (extracted from app.py)."""
from datetime import datetime
from typing import List
import streamlit as st
from views.common import display_session_scans, render_breadcrumb, render_page_header


def page_subjects():
    """Subject browser page (v1.5+ supports multi-dataset)."""
    render_page_header('subjects', show_back_to_dashboard=True)
    render_breadcrumb('subjects')
    st.markdown('<h1 class="main-header">Subjects Browser</h1>', 
                unsafe_allow_html=True)
    
    if not st.session_state.db:
        st.warning("Please complete setup first")
        return
    
    # Dataset filter (v1.5+)
    datasets = st.session_state.db.get_all_datasets(status='active')
    
    if len(datasets) > 1:
        st.markdown('<h2 class="section-header">Dataset Filter</h2>', 
                    unsafe_allow_html=True)
        
        platform_emojis = {
            'pennsieve': '',
            'openneuro': '',
            'dandi': '',
            'xnat': '',
            'hpc': '',
            'remote_server': ''
        }
        
        selected_dataset_ids = st.multiselect(
            "Show subjects from:",
            options=[d['id'] for d in datasets],
            format_func=lambda x: next((f"{platform_emojis.get(d['platform'], '')} {d['name']}" 
                                       for d in datasets if d['id'] == x), str(x)),
            default=[d['id'] for d in datasets],
            key="subject_dataset_filter"
        )
        
        if not selected_dataset_ids:
            st.warning("Select at least one dataset to view subjects")
            return
        
        st.markdown("---")
    else:
        selected_dataset_ids = [d['id'] for d in datasets] if datasets else []
    
    # Search and filters
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        search = st.text_input(
            "Search subjects",
            value=st.session_state.search_query,
            placeholder="TBI011007",
            key="subject_search"
        )
        st.session_state.search_query = search
    
    with col2:
        qc_filter = st.selectbox(
            "QC Status",
            options=['all', 'pending', 'pass', 'fail', 'needs_review'],
            index=0,
            key="qc_filter_select"
        )
    
    with col3:
        session_filter = st.selectbox(
            "Session",
            options=['all', '2WK', '6MO', 'both'],
            index=0,
            key="session_filter_select"
        )
    
    # Get subjects from database (filter by selected datasets if multi-dataset)
    filters = {}
    if qc_filter != 'all':
        filters['qc_status'] = qc_filter
    
    # Get subjects from selected datasets (v1.5+)
    # Use caching for better performance (v3.1.1+)
    cache = st.session_state.get('cache_manager')
    
    subjects = []
    if len(datasets) > 1 and selected_dataset_ids:
        for dataset_id in selected_dataset_ids:
            cache_key = f"subjects_{dataset_id}"
            
            if cache:
                dataset_subjects = cache.cached_query(
                    cache_key,
                    st.session_state.db.get_subjects_by_dataset,
                    dataset_id
                )
            else:
                dataset_subjects = st.session_state.db.get_subjects_by_dataset(dataset_id)
            
            # Add dataset info to each subject
            for subj in dataset_subjects:
                dataset = st.session_state.db.get_dataset(dataset_id)
                if dataset:
                    subj['_dataset_name'] = dataset['name']
                    subj['_dataset_platform'] = dataset['platform']
            subjects.extend(dataset_subjects)
    else:
        # Single dataset or backwards compatibility
        subjects = st.session_state.db.get_all_subjects(filters)
    
    # Apply additional filters
    from src.utils import filter_subjects, create_subject_dataframe
    
    filter_criteria = {
        'search': search,
        'session': session_filter if session_filter != 'all' else None,
    }
    
    filtered_subjects = filter_subjects(subjects, filter_criteria)
    
    # Pagination (v3.1.1+)
    total_subjects = len(filtered_subjects)
    per_page = st.session_state.subjects_per_page
    total_pages = (total_subjects + per_page - 1) // per_page if total_subjects > 0 else 1
    current_page = st.session_state.current_page_num
    
    # Ensure current page is valid
    if current_page > total_pages:
        st.session_state.current_page_num = 1
        current_page = 1
    
    start_idx = (current_page - 1) * per_page
    end_idx = min(start_idx + per_page, total_subjects)
    paginated_subjects = filtered_subjects[start_idx:end_idx]
    
    # Display count with pagination
    st.caption(f"Showing {start_idx + 1}-{end_idx} of {total_subjects} subjects (Page {current_page}/{total_pages})")
    
    if not filtered_subjects:
        st.info("No subjects match the filters")
        return
    
    # Pagination controls
    if total_pages > 1:
        col1, col2, col3, col4 = st.columns([1, 1, 2, 1])
        with col1:
            if st.button("◀ Previous", disabled=(current_page == 1)):
                st.session_state.current_page_num = current_page - 1
                st.rerun()
        with col2:
            if st.button("Next >", disabled=(current_page == total_pages)):
                st.session_state.current_page_num = current_page + 1
                st.rerun()
        with col3:
            page_num = st.number_input(
                "Go to page:",
                min_value=1,
                max_value=total_pages,
                value=current_page,
                key="page_number_input"
            )
            if page_num != current_page:
                st.session_state.current_page_num = page_num
                st.rerun()
        with col4:
            per_page_select = st.selectbox(
                "Per page:",
                options=[25, 50, 100, 200],
                index=1,
                key="per_page_select"
            )
            if per_page_select != st.session_state.subjects_per_page:
                st.session_state.subjects_per_page = per_page_select
                st.session_state.current_page_num = 1
                st.rerun()
    
    # Enrich with demographics (participants.tsv) + session/scan/modality counts
    # (the subjects table itself no longer stores these as columns).
    from src.utils import enrich_subjects_for_display
    enrich_subjects_for_display(paginated_subjects, st.session_state.db)

    # Create DataFrame for display (paginated)
    df = create_subject_dataframe(paginated_subjects)

    # Display table with selection
    st.dataframe(
        df,
        width='stretch',
        hide_index=True,
        height=400
    )
    
    # Subject selection for detail view
    st.markdown("---")
    st.markdown("### View Subject Details")
    
    # Index-based options so the same BIDS label in different datasets stays
    # distinct (and we can carry the dataset id into the detail page).
    from src.utils import platform_label
    multi_dataset = any('_dataset_name' in s for s in paginated_subjects)

    def _subject_option_label(i):
        s = paginated_subjects[i]
        if multi_dataset:
            return f"{s['subject_id']} — [{platform_label(s.get('_dataset_platform'))}] {s.get('_dataset_name', '')}"
        return s['subject_id']

    selected_idx = st.selectbox(
        "Select subject to view",
        options=list(range(len(paginated_subjects))),
        format_func=_subject_option_label,
        index=0 if paginated_subjects else None,
        key="selected_subject_view"
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("View Details", width='stretch'):
            chosen = paginated_subjects[selected_idx]
            st.session_state.selected_subject = chosen['subject_id']
            st.session_state.selected_subject_dataset = chosen.get('dataset_id')
            st.session_state.current_page = 'subject_detail'
            st.rerun()
    
    with col2:
        if st.button("Export Filtered List", width='stretch'):
            from src.utils import export_to_csv
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"subjects_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )


def page_subject_detail():
    """Subject detail page."""
    subject_id = st.session_state.selected_subject
    
    if not subject_id:
        st.warning("No subject selected")
        if st.button("<- Back to Subjects"):
            st.session_state.current_page = 'subjects'
            st.rerun()
        return
    
    # Breadcrumb navigation
    render_breadcrumb('subject_detail', parent_page='subjects')
    
    # Header with back button
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f'<h1 class="main-header">Subject: {subject_id}</h1>', 
                    unsafe_allow_html=True)
    with col2:
        if st.button("<- Back to Subjects", width='stretch'):
            st.session_state.current_page = 'subjects'
            st.rerun()
    
    # Get subject data (dataset-scoped when we know which dataset was opened,
    # so a label shared across datasets resolves to the right subject).
    detail_dataset_id = st.session_state.get('selected_subject_dataset')
    subject = st.session_state.db.get_subject(subject_id, dataset_id=detail_dataset_id)
    if not subject:
        subject = st.session_state.db.get_subject(subject_id)
    if not subject:
        st.error("Subject not found")
        return
    
    # QC Status Section
    st.markdown('<h2 class="section-header">Quality Control</h2>', 
                unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        new_qc_status = st.selectbox(
            "QC Status",
            options=['pending', 'pass', 'fail', 'needs_review'],
            index=['pending', 'pass', 'fail', 'needs_review'].index(
                subject.get('qc_status', 'pending')
            ),
            key="subject_qc_status"
        )
    
    with col2:
        flagged = st.checkbox(
            "Flag for review",
            value=subject.get('flagged', False),
            key="subject_flagged"
        )
    
    with col3:
        st.write("")
        st.write("")
        if st.button("Update QC Status", width='stretch'):
            success = st.session_state.db.update_subject_qc(
                subject_id=subject_id,
                qc_status=new_qc_status,
                notes=st.session_state.get('qc_notes_text', ''),
                reviewed_by="user",
                flagged=flagged
            )
            if success:
                st.success("QC status updated")
                st.rerun()
            else:
                st.error("Failed to update QC status")
    
    # QC Notes
    qc_notes = st.text_area(
        "QC Notes",
        value=subject.get('qc_notes', ''),
        height=100,
        key="qc_notes_text"
    )
    
    # Session scans - Dynamic session support
    # Get dataset info
    dataset_id = subject.get('dataset_id')

    platform = None
    dataset_remote_id = None

    if dataset_id:
        dataset_info = st.session_state.db.execute_query(
            "SELECT platform, dataset_id_external FROM datasets WHERE id = ?",
            (dataset_id,),
            fetch=True
        )
        if dataset_info and len(dataset_info) > 0:
            platform = dataset_info[0][0]
            dataset_remote_id = dataset_info[0][1]

    # Use the BIDS loader only for the local dataset it was actually opened on;
    # for every other dataset (and whenever no loader is active, e.g. the
    # multi-dataset browse flow) read scans from the database instead. All
    # scans are indexed in the DB, so the loader is an optional local-file path,
    # not a requirement.
    loader = st.session_state.get('bids_loader')
    use_db_scans = (platform != 'local') or (loader is None)

    # Get all sessions for subject (dynamic), scoped to this dataset
    all_sessions = []

    if use_db_scans:
        sessions_info = st.session_state.db.get_subject_sessions(subject_id, dataset_id)
        all_sessions = [s['session_id'] for s in sessions_info if s.get('scan_count', 0) > 0]

        # Fallback: derive sessions from the dataset-scoped scans table
        if not all_sessions:
            all_scans = st.session_state.db.get_scans_by_subject(subject_id, dataset_id=dataset_id)
            all_sessions = sorted({scan.get('session') for scan in all_scans if scan.get('session')})
    else:
        all_sessions = loader.get_sessions(subject_id)

    # Display each session dynamically
    if all_sessions:
        for session_id in sorted(all_sessions):
            # Get scans for this session
            if use_db_scans:
                scans = [
                    s for s in st.session_state.db.get_scans_by_subject(subject_id, dataset_id=dataset_id)
                    if s.get('session') == session_id
                ]
            else:
                scans = loader.get_subject_scans(subject_id, session_id)

            # Display session using helper function
            display_session_scans(session_id, scans, subject_id, platform, dataset_remote_id, use_db_scans)
    else:
        st.info("No session data available for this subject")


