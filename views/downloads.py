"""Download Manager page (UI). The execution engine lives in download_engine.py."""
from pathlib import Path
import json
import pandas as pd
import streamlit as st
from src.metadata_filter import MetadataFilter
from src.ui_calm import toast_note, toast_ok
from views.common import get_available_sessions, render_breadcrumb, render_page_header
from views.download_engine import execute_downloads, execute_uploads


def page_downloads():
    """Download manager page."""
    render_page_header('downloads', show_back_to_dashboard=True)
    render_breadcrumb('downloads')
    st.markdown('<h1 class="main-header">Download Manager</h1>', 
                unsafe_allow_html=True)
    
    if not st.session_state.db:
        st.warning("Database not initialized. Please restart the app.")
        return
    
    # Initialize agent factory and download manager (v3.1.1+: with multi-platform destination)
    if 'agent_factory' not in st.session_state:
        from src.agent_factory import AgentFactory
        st.session_state.agent_factory = AgentFactory(st.session_state.db)
    
    if 'download_manager' not in st.session_state:
        from src.download_manager import DownloadManager
        st.session_state.download_manager = DownloadManager(
            ps_client=st.session_state.get('ps_client'),
            database=st.session_state.db,
            max_concurrent=3,
            agent_factory=st.session_state.agent_factory,
            upload_destination=None
        )
    
    dm = st.session_state.download_manager
    
    # Update download destination based on user selection (v3.1.1+: Multi-platform)
    dest_type = st.session_state.get('download_destination_type', 'local')
    dest_dataset_id = st.session_state.get('download_dest_dataset_id')
    dest_platform = st.session_state.get('download_dest_platform')
    
    if dest_type == 'local_and_platform' and dest_dataset_id and dest_platform:
        dm.set_upload_destination({
            'platform': dest_platform,
            'dataset_id': dest_dataset_id
        })
    else:
        dm.set_upload_destination(None)
    
    # Initialize Metadata Filter (v1.5+ supports multi-dataset, v3.0+ adds database)
    if 'metadata_filter' not in st.session_state:
        datasets = st.session_state.db.get_all_datasets(status='active')
        if datasets and len(datasets) > 1:
            # Multi-dataset mode
            st.session_state.metadata_filter = MetadataFilter(
                datasets=datasets, 
                database=st.session_state.db
            )
        else:
            # Single dataset mode (backwards compatibility)
            st.session_state.metadata_filter = MetadataFilter(
                st.session_state.bids_root,
                database=st.session_state.db
            )
    
    metadata_filter = st.session_state.metadata_filter
    
    # Download Destination Selector (v3.1.1+: Multi-platform support)
    st.markdown('<h2 class="section-header">Download Destination</h2>', 
                unsafe_allow_html=True)
    
    st.info("Choose where to save downloaded data - local storage only, or push directly to another platform")
    
    # Destination options
    col1, col2 = st.columns([1, 2])
    
    with col1:
        dest_type = st.radio(
            "Destination Type",
            options=['local', 'local_and_platform'],
            format_func=lambda x: 'Local Only' if x == 'local' else 'Local + Upload to Platform',
            key='download_destination_type',
            help="Choose whether to keep data local or also push to another platform"
        )
    
    with col2:
        if dest_type == 'local_and_platform':
            # Get all datasets that support uploads (v3.1.1+: all platforms except openneuro, dandi)
            all_datasets = st.session_state.db.get_all_datasets(status='active')
            upload_platforms = ['pennsieve', 'xnat', 'hpc', 'remote_server']
            upload_capable_datasets = [ds for ds in all_datasets if ds['platform'] in upload_platforms]
            
            if not upload_capable_datasets:
                st.warning("No upload-capable datasets configured. Add Pennsieve, XNAT, HPC, or Remote Server dataset in Manage Datasets.")
                st.session_state.download_dest_dataset_id = None
                st.session_state.download_dest_platform = None
            else:
                # Platform emojis for display
                platform_emojis = {
                    'pennsieve': '[P]',
                    'xnat': '[X]',
                    'hpc': '[H]',
                    'remote_server': '[R]'
                }
                
                dest_dataset_options = {
                    f"{platform_emojis.get(ds['platform'], '')} {ds['name']} ({ds['platform'].upper()})": ds['id'] 
                    for ds in upload_capable_datasets
                }
                
                selected_dest_display = st.selectbox(
                    "Target Upload Destination",
                    options=list(dest_dataset_options.keys()),
                    key='download_dest_dataset_display',
                    help="Data will be uploaded to this platform after downloading locally"
                )
                
                selected_dest_id = dest_dataset_options[selected_dest_display]
                selected_dataset = st.session_state.db.get_dataset(selected_dest_id)
                
                st.session_state.download_dest_dataset_id = selected_dest_id
                st.session_state.download_dest_platform = selected_dataset['platform']
                st.session_state.download_dest_name = selected_dataset['name']
                
                st.caption(f"Downloads will be pushed to: {selected_dataset['name']} ({selected_dataset['platform'].upper()})")
        else:
            st.session_state.download_dest_dataset_id = None
            st.session_state.download_dest_platform = None
    
    st.markdown("---")
    
    # Metadata Filtering Section
    st.markdown('<h2 class="section-header">Filter by Metadata</h2>', 
                unsafe_allow_html=True)
    
    if metadata_filter.is_available():
        st.info("Filter subjects by demographics before downloading to save bandwidth and storage")
        
        # Get available fields
        available_fields = metadata_filter.get_available_fields()
        
        # Build filter criteria
        filter_criteria = {}
        
        # Age filter (if available)
        if 'age' in available_fields:
            col1, col2 = st.columns(2)
            with col1:
                min_age = st.number_input("Min Age", min_value=0, max_value=120, value=0, key="filter_min_age")
            with col2:
                max_age = st.number_input("Max Age", min_value=0, max_value=120, value=120, key="filter_max_age")
            
            if min_age > 0 or max_age < 120:
                filter_criteria['age'] = {'min': min_age, 'max': max_age}
        
        # Sex filter (if available)
        if 'sex' in available_fields:
            sex_values = metadata_filter.get_field_values('sex')
            selected_sex = st.multiselect(
                "Sex",
                options=sex_values,
                default=sex_values,
                key="filter_sex"
            )
            if selected_sex and len(selected_sex) < len(sex_values):
                filter_criteria['sex'] = selected_sex
        
        # Diagnosis filter (if available)
        if 'diagnosis' in available_fields:
            dx_values = metadata_filter.get_field_values('diagnosis')
            selected_dx = st.multiselect(
                "Diagnosis",
                options=dx_values,
                default=dx_values,
                key="filter_diagnosis"
            )
            if selected_dx and len(selected_dx) < len(dx_values):
                filter_criteria['diagnosis'] = selected_dx
        
        # Keyword search (v3.0+ - useful for datasets with sparse metadata)
        st.markdown("---")
        st.markdown("**Additional Filters** (for datasets with limited metadata)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            keyword_input = st.text_input(
                "Keywords (comma-separated)",
                placeholder="e.g., epilepsy, TBI, hippocampal sclerosis",
                key="filter_keywords",
                help="Searches dataset descriptions, subject IDs, and scan filenames"
            )
            
            if keyword_input:
                keywords = [kw.strip() for kw in keyword_input.split(',') if kw.strip()]
                filter_criteria['keywords'] = keywords
        
        with col2:
            modality_options = ['T1w', 'T2w', 'FLAIR', 'DWI', 'ASL', 'SWI', 'bold', 'dwi', 'PDw']
            selected_modalities = st.multiselect(
                "MRI Modalities",
                options=modality_options,
                key="filter_modalities",
                help="Filter by specific MRI sequence types"
            )
            
            if selected_modalities:
                filter_criteria['modalities'] = selected_modalities
        
        # Preview filtered results
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Preview Filtered Results", width='stretch'):
                # Apply demographic filters first
                filtered_ids = metadata_filter.filter_subjects(filter_criteria)
                
                # Extract demographic criteria (without keywords/modalities)
                demographic_criteria = {k: v for k, v in filter_criteria.items() 
                                      if k not in ['keywords', 'modalities']}
                summary = metadata_filter.get_filter_summary(demographic_criteria)
                
                # Apply keyword filter (intersect with demographic results)
                if 'keywords' in filter_criteria:
                    keyword_matches = metadata_filter.filter_by_keywords(filter_criteria['keywords'])
                    keyword_ids = [(m['subject_id'], m['dataset_id']) for m in keyword_matches]
                    
                    # Intersect with demographic results
                    if filtered_ids:
                        filtered_ids = [sid for sid in filtered_ids if sid in keyword_ids]
                    else:
                        filtered_ids = keyword_ids
                    
                    st.info(f"Keyword search: found {len(keyword_matches)} matches for {', '.join(filter_criteria['keywords'])}")
                
                # Apply modality filter (intersect with previous results)
                if 'modalities' in filter_criteria:
                    modality_matches = metadata_filter.filter_by_modalities(filter_criteria['modalities'])
                    modality_ids = [(m['subject_id'], m['dataset_id']) for m in modality_matches]
                    
                    # Intersect with previous results
                    if filtered_ids:
                        filtered_ids = [sid for sid in filtered_ids if sid in modality_ids]
                    else:
                        filtered_ids = modality_ids
                    
                    st.info(f"[D] Modality filter: found {len(modality_matches)} subjects with {', '.join(filter_criteria['modalities'])}")
                
                st.session_state.filtered_subject_ids = filtered_ids
                st.session_state.filter_active = True
                
                st.success(f"{len(filtered_ids)} subjects match your criteria")
                
                if summary['demographics']:
                    with st.expander("View Demographics"):
                        if 'age' in summary['demographics']:
                            age_stats = summary['demographics']['age']
                            st.write(f"**Age**: {age_stats['min']:.0f}-{age_stats['max']:.0f} (mean: {age_stats['mean']:.1f})")
                        if 'sex' in summary['demographics']:
                            st.write(f"**Sex**: {summary['demographics']['sex']}")
                        if 'diagnosis' in summary['demographics']:
                            st.write(f"**Diagnosis**: {summary['demographics']['diagnosis']}")
        
        with col2:
            if st.button("[Delete] Clear Filters", width='stretch'):
                st.session_state.filtered_subject_ids = None
                st.session_state.filter_active = False
                st.rerun()
        
        with col3:
            if st.session_state.get('filter_active'):
                filtered_count = len(st.session_state.get('filtered_subject_ids', []))
                st.metric("Filtered", filtered_count, delta="subjects")
        
        # Show active filter summary
        if st.session_state.get('filter_active'):
            filter_text = []
            if 'age' in filter_criteria:
                age_range = filter_criteria['age']
                if 'min' in age_range and age_range['min'] > 0:
                    filter_text.append(f"Age ≥ {age_range['min']}")
                if 'max' in age_range and age_range['max'] < 120:
                    filter_text.append(f"Age ≤ {age_range['max']}")
            if 'sex' in filter_criteria:
                filter_text.append(f"Sex: {', '.join(filter_criteria['sex'])}")
            if 'diagnosis' in filter_criteria:
                filter_text.append(f"Diagnosis: {', '.join(filter_criteria['diagnosis'])}")
            if 'keywords' in filter_criteria:
                filter_text.append(f"Keywords: {', '.join(filter_criteria['keywords'])}")
            if 'modalities' in filter_criteria:
                filter_text.append(f"Modalities: {', '.join(filter_criteria['modalities'])}")
            
            if filter_text:
                st.caption(f"**Active filters**: {' | '.join(filter_text)}")
    else:
        st.warning("No participants.tsv found - metadata filtering unavailable")
    
    st.markdown("---")
    
    # Download Destination Status (v3.1.1+: Multi-platform)
    if dest_type == 'local_and_platform' and dest_dataset_id:
        dest_dataset = st.session_state.db.get_dataset(dest_dataset_id)
        if dest_dataset:
            platform_emojis = {
                'pennsieve': '[P]',
                'xnat': '[X]',
                'hpc': '[H]',
                'remote_server': '[R]'
            }
            platform_emoji = platform_emojis.get(dest_dataset['platform'], '')
            platform_display = dest_dataset['platform'].upper()
            
            st.success(f"{platform_emoji} Active Destination: Downloads will be pushed to **{dest_dataset['name']}** ({platform_display})")
        else:
            st.error("Invalid destination dataset selected")
    else:
        st.info("Active Destination: Downloads saved to local storage only")
    
    st.markdown("---")
    
    # Storage Estimation
    st.markdown('<h2 class="section-header">Storage Estimation</h2>', 
                unsafe_allow_html=True)
    
    from src.download_manager import check_available_space
    from src.utils import format_file_size
    
    queued_size = dm.get_total_queue_size()
    queued_count = dm.get_queued_count()
    
    try:
        available_space = check_available_space('.')
    except Exception:
        available_space = 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Queued Items", queued_count)
    
    with col2:
        st.metric("Total Size", format_file_size(queued_size))
    
    with col3:
        st.metric("Available Space", format_file_size(available_space))
    
    with col4:
        if available_space > 0 and queued_size > 0:
            if available_space >= queued_size:
                st.metric("Status", "Sufficient", delta="Ready")
            else:
                st.metric("Status", "Insufficient", delta="Warning", delta_color="inverse")
        else:
            st.metric("Status", "—")
    
    st.markdown("---")
    
    # Quick Select
    st.markdown('<h2 class="section-header">Quick Select</h2>', 
                unsafe_allow_html=True)
    
    # Check if filters are active
    filter_active = st.session_state.get('filter_active', False)
    filtered_ids = st.session_state.get('filtered_subject_ids', None)
    
    if filter_active and filtered_ids:
        st.caption(f"Filters active: {len(filtered_ids)} subjects selected")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        button_label = "Select Filtered Subjects" if filter_active else "Select All Subjects"
        if st.button(button_label, width='stretch'):
            # Add subjects' scans to download queue (respecting filters)
            added_count = 0
            skipped_count = 0
            
            # Get subjects (filtered or all)
            if filter_active and filtered_ids:
                subjects = [st.session_state.db.get_subject(sid) for sid in filtered_ids]
                subjects = [s for s in subjects if s]  # Remove None values
            else:
                subjects = st.session_state.db.get_all_subjects()
            
            bids_loader = st.session_state.bids_loader
            
            if not bids_loader:
                st.error("BIDS loader not initialized")
            else:
                for subject in subjects:
                    subject_id = subject['subject_id']
                    dataset_id = subject.get('dataset_id')
                    
                    # Get all available sessions for this subject's dataset (dynamic)
                    available_sessions = get_available_sessions(dataset_id)
                    
                    # If no sessions from metadata, try getting from BIDS loader
                    if not available_sessions:
                        available_sessions = bids_loader.get_sessions(subject_id)
                    
                    # Get scans for all sessions (dynamic)
                    for session in available_sessions:
                        scans = bids_loader.get_subject_scans(subject_id, session)
                        
                        for scan in scans:
                            # Check if already in queue
                            existing = st.session_state.db.execute_query(
                                "SELECT id FROM download_queue WHERE subject_id = ? AND file_path = ?",
                                (subject_id, scan['path'])
                            )
                            
                            if not existing:
                                success = dm.add_to_queue(
                                    scan_id=scan.get('scan_id', 0),
                                    subject_id=subject_id,
                                    file_path=scan['path'],
                                    package_id=scan.get('package_id', ''),
                                    file_size=scan.get('size', 0)
                                )
                                if success:
                                    added_count += 1
                            else:
                                skipped_count += 1
                
                if added_count > 0:
                    filter_msg = f" from {len(subjects)} filtered subjects" if filter_active else ""
                    toast_ok(f"Added {added_count} file(s){filter_msg} to queue ({skipped_count} already queued)")
                    st.rerun()
                else:
                    st.caption(f"No new files added ({skipped_count} already in queue).")
    
    with col2:
        button_label = "Select Complete (Filtered)" if filter_active else "Select Complete Only"
        if st.button(button_label, width='stretch'):
            # Add only subjects with both 2WK and 6MO sessions (respecting filters)
            added_count = 0
            skipped_count = 0
            incomplete_count = 0
            
            # Get subjects (filtered or all)
            if filter_active and filtered_ids:
                subjects = [st.session_state.db.get_subject(sid) for sid in filtered_ids]
                subjects = [s for s in subjects if s]
            else:
                subjects = st.session_state.db.get_all_subjects()
            
            bids_loader = st.session_state.bids_loader
            
            if not bids_loader:
                st.error("BIDS loader not initialized")
            else:
                for subject in subjects:
                    subject_id = subject['subject_id']
                    dataset_id = subject.get('dataset_id')
                    
                    # Check if subject has 2+ sessions (dynamic completeness definition)
                    sessions_info = st.session_state.db.get_subject_sessions(subject_id, dataset_id)
                    
                    # Fallback: get sessions from BIDS loader if not in database
                    if not sessions_info:
                        subject_sessions = bids_loader.get_sessions(subject_id)
                        is_complete = len(subject_sessions) >= 2
                    else:
                        is_complete = len(sessions_info) >= 2
                    
                    if not is_complete:
                        incomplete_count += 1
                        continue
                    
                    # Get all available sessions for this subject (dynamic)
                    available_sessions = get_available_sessions(dataset_id)
                    if not available_sessions:
                        available_sessions = bids_loader.get_sessions(subject_id)
                    
                    # Add scans from all sessions (dynamic)
                    for session in available_sessions:
                        scans = bids_loader.get_subject_scans(subject_id, session)
                        
                        for scan in scans:
                            # Check if already in queue
                            existing = st.session_state.db.execute_query(
                                "SELECT id FROM download_queue WHERE subject_id = ? AND file_path = ?",
                                (subject_id, scan['path'])
                            )
                            
                            if not existing:
                                success = dm.add_to_queue(
                                    scan_id=scan.get('scan_id', 0),
                                    subject_id=subject_id,
                                    file_path=scan['path'],
                                    package_id=scan.get('package_id', ''),
                                    file_size=scan.get('size', 0)
                                )
                                if success:
                                    added_count += 1
                            else:
                                skipped_count += 1
                
                if added_count > 0:
                    filter_msg = f" from {len(subjects)} filtered" if filter_active else ""
                    toast_ok(
                        f"Added {added_count} file(s) from {len(subjects) - incomplete_count} complete{filter_msg} subjects "
                        f"({skipped_count} skipped, {incomplete_count} incomplete)"
                    )
                    st.rerun()
                else:
                    st.caption(
                        f"No new files added ({skipped_count} already in queue, {incomplete_count} incomplete subjects)."
                    )
    
    with col3:
        session_select = st.selectbox(
            "Filter by Session",
            options=['All', '2WK', '6MO'],
            key="download_session_filter"
        )
    
    st.markdown("---")
    
    # Download Queue
    st.markdown('<h2 class="section-header">Download Queue</h2>', 
                unsafe_allow_html=True)
    
    # Get queue items
    queue_items = dm.get_queue_items()
    
    if not queue_items:
        st.caption("Queue is empty — add files from the Subjects page or use Quick Select above.")
    else:
        # Create queue table with action column
        queue_data = []
        for item in queue_items:
            queue_data.append({
                'ID': item['id'],
                'File': Path(item['file_path']).name,
                'Subject': item['subject_id'],
                'Size': format_file_size(item.get('file_size_bytes', 0)),
                'Status': item['status'].title(),
                'Added': item.get('added_date', 'Unknown')[:19] if item.get('added_date') else 'Unknown'
            })
        
        df_queue = pd.DataFrame(queue_data)
        
        # Display table
        st.dataframe(
            df_queue,
            width='stretch',
            hide_index=True,
            height=300
        )
        
        # Individual item management
        with st.expander("[Delete] Manage Individual Items"):
            col1, col2 = st.columns(2)
            
            with col1:
                item_to_remove = st.selectbox(
                    "Select item to remove",
                    options=[f"{item['id']}: {Path(item['file_path']).name}" for item in queue_items],
                    key="item_to_remove"
                )
            
            with col2:
                if st.button("Remove Selected", width='stretch', key="remove_single_item"):
                    if item_to_remove:
                        item_id = int(item_to_remove.split(':')[0])
                        success = st.session_state.db.execute_query(
                            "DELETE FROM download_queue WHERE id = ?",
                            (item_id,)
                        )
                        if success:
                            toast_ok(f"Removed item {item_id}")
                            st.rerun()
            
            # Bulk actions by status
            st.markdown("**Bulk Actions**")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("Remove All Failed", width='stretch'):
                    removed = st.session_state.db.execute_query(
                        "DELETE FROM download_queue WHERE status = 'failed'"
                    )
                    toast_ok("Removed all failed items")
                    st.rerun()
            
            with col2:
                if st.button("Remove All Completed", width='stretch'):
                    removed = st.session_state.db.execute_query(
                        "DELETE FROM download_queue WHERE status = 'completed'"
                    )
                    toast_ok("Removed all completed items")
                    st.rerun()
            
            with col3:
                if st.button("Retry All Failed", width='stretch'):
                    st.session_state.db.execute_query(
                        "UPDATE download_queue SET status = 'queued', error_message = NULL WHERE status = 'failed'"
                    )
                    toast_ok("Failed items reset to queued")
                    st.rerun()
        
        # Get download stats
        stats = dm.get_download_stats()
        
        # Progress bar
        if stats['total'] > 0:
            progress = stats['completed'] / stats['total']
            st.progress(progress)
            st.caption(f"Progress: {stats['completed']}/{stats['total']} files ({stats['progress_pct']:.1f}%)")
        
        st.markdown("---")
        
        # Control buttons
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("Start Downloads", 
                        type="primary",
                        width='stretch',
                        disabled=stats['queued'] == 0):
                # Execute actual downloads using Pennsieve Agent
                execute_downloads(dm, st.session_state.db)
        
        with col2:
            if st.button("Pause All",
                        width='stretch',
                        disabled=stats['downloading'] == 0):
                dm.pause_downloads()
                toast_note("Downloads paused")
                st.rerun()
        
        with col3:
            if st.button("Resume",
                        width='stretch',
                        disabled=stats['paused'] == 0):
                dm.resume_downloads()
                toast_ok("Downloads resumed")
                st.rerun()
        
        with col4:
            if st.button("Clear Queue",
                        width='stretch'):
                cleared = dm.clear_queue('queued')
                toast_ok(f"Cleared {cleared} queued item(s)")
                st.rerun()
        
        # Download Statistics
        st.markdown("---")
        st.markdown('<h2 class="section-header">Statistics</h2>', 
                    unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Completed", stats['completed'])
        
        with col2:
            st.metric("Failed", stats['failed'])
        
        with col3:
            st.metric("Downloading", stats['downloading'])
        
        with col4:
            st.metric("Remaining", stats['queued'])
    
    # Download History
    st.markdown("---")
    st.markdown('<h2 class="section-header"> Download & Upload History</h2>', 
                unsafe_allow_html=True)
    
    # Get recent sessions from metadata table
    if st.session_state.db:
        sessions = st.session_state.db.execute_query("""
            SELECT key, value, updated_at
            FROM metadata
            WHERE key LIKE 'download_session_%' OR key LIKE 'upload_session_%'
            ORDER BY updated_at DESC
            LIMIT 20
        """)
        
        if sessions:
            history_data = []
            for session in sessions:
                try:
                    session_data = json.loads(session['value'])
                    session_type = 'Download' if 'download_session_' in session['key'] else 'Upload'
                    
                    history_data.append({
                        'Type': f"{'' if session_type == 'Download' else ''} {session_type}",
                        'Platform': session_data.get('platform', 'Unknown').title(),
                        'Timestamp': session_data.get('timestamp', session['updated_at'])[:19],
                        'Success': session_data.get('successful', 0),
                        'Failed': session_data.get('failed', 0),
                        'Duration': f"{int(session_data.get('duration', 0) // 60)}m {int(session_data.get('duration', 0) % 60)}s",
                        'Avg Speed': f"{session_data.get('avg_speed_mbps', 0):.2f} MB/s" if session_data.get('avg_speed_mbps') else 'N/A'
                    })
                except Exception:
                    pass
            
            if history_data:
                with st.expander("View Recent Sessions", expanded=False):
                    history_df = pd.DataFrame(history_data)
                    st.dataframe(history_df, width='stretch', hide_index=True)
                    
                    if st.button("[Delete] Clear History", key="clear_history"):
                        st.session_state.db.execute_query("""
                            DELETE FROM metadata 
                            WHERE key LIKE 'download_session_%' OR key LIKE 'upload_session_%'
                        """)
                        st.success("History cleared")
                        st.rerun()
            else:
                st.caption("No download/upload history yet")
        else:
            st.caption("No download/upload history yet")
    
    # Settings
    st.markdown("---")
    st.markdown('<h2 class="section-header">Settings</h2>', 
                unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        max_concurrent = st.selectbox(
            "Max Concurrent Downloads",
            options=[1, 2, 3, 4, 5],
            index=2,
            key="max_concurrent_downloads"
        )
        st.caption("Number of simultaneous downloads")
    
    with col2:
        download_dir = st.text_input(
            "Download Directory",
            value=st.session_state.bids_root or "",
            key="download_directory"
        )
        st.caption("Local destination for downloads")
    
    # Upload Section (Pennsieve only)
    if st.session_state.get('platform') == 'pennsieve':
        st.markdown("---")
        st.markdown('<h2 class="section-header"> Upload to Pennsieve</h2>', 
                    unsafe_allow_html=True)
        
        st.info("Upload processed/derived data back to Pennsieve dataset")
        
        # Upload mode selection
        upload_mode = st.radio(
            "Upload Mode",
            options=['files', 'directory'],
            format_func=lambda x: {
                'files': ' Individual Files (drag & drop)',
                'directory': 'Directory (select folder from local system)'
            }[x],
            key="upload_mode",
            horizontal=True
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if upload_mode == 'files':
                upload_files = st.file_uploader(
                    "Select files to upload",
                    accept_multiple_files=True,
                    key="upload_files",
                    help="Drag and drop multiple files or click to browse"
                )
            else:
                local_directory = st.text_input(
                    "Local Directory Path",
                    placeholder="/path/to/local/derivatives",
                    key="upload_local_directory",
                    help="Path to directory on your computer"
                )
                
                # Option to include subdirectories
                include_subdirs = st.checkbox(
                    "Include subdirectories",
                    value=True,
                    key="upload_include_subdirs"
                )
                
                # Preview files in directory
                if local_directory and Path(local_directory).exists():
                    if include_subdirs:
                        files_in_dir = list(Path(local_directory).rglob('*'))
                    else:
                        files_in_dir = list(Path(local_directory).glob('*'))
                    
                    files_in_dir = [f for f in files_in_dir if f.is_file()]
                    
                    total_size = sum(f.stat().st_size for f in files_in_dir)
                    
                    with st.expander(f"Preview: {len(files_in_dir)} files ({format_file_size(total_size)})"):
                        preview_df = pd.DataFrame([
                            {
                                'File': f.name,
                                'Size': format_file_size(f.stat().st_size),
                                'Path': str(f.relative_to(local_directory))
                            }
                            for f in files_in_dir[:50]  # Show first 50
                        ])
                        st.dataframe(preview_df, width='stretch', hide_index=True)
                        
                        if len(files_in_dir) > 50:
                            st.caption(f"Showing first 50 files. Total: {len(files_in_dir)}")
                elif local_directory:
                    st.error(f"Directory not found: {local_directory}")
        
        with col2:
            remote_path = st.text_input(
                "Remote Path in Pennsieve",
                value="derivatives/",
                key="upload_remote_path",
                help="Destination path in your Pennsieve dataset"
            )
            st.caption("[Fast] Files will be uploaded to this path")
            
            # Upload options
            st.markdown("**Upload Options**")
            overwrite_existing = st.checkbox(
                "Overwrite existing files",
                value=False,
                key="upload_overwrite"
            )
            create_checksums = st.checkbox(
                "Generate checksums",
                value=True,
                key="upload_checksums",
                help="Verify file integrity after upload"
            )
        
        # Upload button
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            can_upload = False
            file_paths_to_upload = []
            
            if upload_mode == 'files' and upload_files:
                can_upload = True
                # Save uploaded files temporarily
                temp_dir = Path("data/temp_uploads")
                temp_dir.mkdir(parents=True, exist_ok=True)
                
                for uploaded_file in upload_files:
                    temp_path = temp_dir / uploaded_file.name
                    file_paths_to_upload.append(str(temp_path))
            elif upload_mode == 'directory' and local_directory and Path(local_directory).exists():
                can_upload = True
                # Get all files from directory
                if include_subdirs:
                    file_paths_to_upload = [str(f) for f in Path(local_directory).rglob('*') if f.is_file()]
                else:
                    file_paths_to_upload = [str(f) for f in Path(local_directory).glob('*') if f.is_file()]
            
            upload_button = st.button(
                f" Upload {len(file_paths_to_upload) if file_paths_to_upload else 0} Files",
                type="primary",
                width='stretch',
                disabled=not can_upload
            )
        
        with col2:
            if can_upload:
                total_size = 0
                if upload_mode == 'files' and upload_files:
                    total_size = sum(f.size for f in upload_files)
                elif file_paths_to_upload:
                    total_size = sum(Path(f).stat().st_size for f in file_paths_to_upload if Path(f).exists())
                
                st.metric("Total Size", format_file_size(total_size))
        
        with col3:
            if can_upload:
                st.metric("Files", len(file_paths_to_upload))
        
        # Execute upload
        if upload_button and file_paths_to_upload:
            if upload_mode == 'files':
                # Save uploaded files first
                temp_dir = Path("data/temp_uploads")
                temp_dir.mkdir(parents=True, exist_ok=True)
                
                saved_paths = []
                for uploaded_file in upload_files:
                    temp_path = temp_dir / uploaded_file.name
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    saved_paths.append(str(temp_path))
                
                # Execute upload
                execute_uploads(
                    saved_paths,
                    st.session_state.dataset_name,
                    remote_path,
                    overwrite_existing,
                    create_checksums
                )
                
                # Clean up temp files
                for temp_path in saved_paths:
                    Path(temp_path).unlink(missing_ok=True)
            else:
                # Upload from local directory
                execute_uploads(
                    file_paths_to_upload,
                    st.session_state.dataset_name,
                    remote_path,
                    overwrite_existing,
                    create_checksums
                )
    else:
        st.markdown("---")
        st.info(" **OpenNeuro is read-only**. Upload not supported. Use Pennsieve for private datasets with upload capabilities.")
