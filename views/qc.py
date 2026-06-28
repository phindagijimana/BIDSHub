"""Quality control page + QC tabs (extracted from app.py)."""
from datetime import datetime
from pathlib import Path
import json
import pandas as pd
import streamlit as st
from src.automated_qc import AutomatedQC
from src.pennsieve_agent import PennsieveAgent
from src.ui_calm import expected_empty
from views.common import render_breadcrumb, render_page_header


def page_qc():
    """QC dashboard page."""
    render_page_header('qc', show_back_to_dashboard=True)
    render_breadcrumb('qc')
    st.markdown('<h1 class="main-header">Quality Control Dashboard</h1>', 
                unsafe_allow_html=True)
    
    if not st.session_state.db:
        st.warning("Please complete setup first")
        return
    
    # Initialize QC manager
    if 'qc_manager' not in st.session_state:
        from src.qc_manager import QCManager
        st.session_state.qc_manager = QCManager(st.session_state.db)
    
    qc_mgr = st.session_state.qc_manager
    
    # Initialize Automated QC
    if 'automated_qc' not in st.session_state:
        st.session_state.automated_qc = AutomatedQC(
            st.session_state.bids_loader,
            st.session_state.db
        )
    
    auto_qc = st.session_state.automated_qc
    
    # QC Type Tabs (v3.1+: Added Pennsieve Sync tab)
    tab1, tab2, tab3 = st.tabs(["Manual QC", "Automated QC", "Pennsieve Sync"])
    
    with tab1:
        render_manual_qc_tab(qc_mgr)
    
    with tab2:
        render_automated_qc_tab(auto_qc)
    
    with tab3:
        render_pennsieve_sync_tab(qc_mgr)


def render_manual_qc_tab(qc_mgr):
    """Render manual QC tab for human review."""
    # QC Overview
    st.markdown('<h2 class="section-header">Manual QC Overview</h2>', 
                unsafe_allow_html=True)
    
    summary = qc_mgr.get_qc_summary()
    
    col1, col2, col3, col4 = st.columns(4)
    
    # delta values here are proportions of total (not trends), so render them
    # neutral/gray with delta_color="off" instead of a misleading green up-arrow.
    with col1:
        st.metric(
            "Pending",
            summary['pending'],
            delta=f"{summary['pending_pct']:.1f}% of total",
            delta_color="off"
        )

    with col2:
        st.metric(
            "Pass",
            summary['pass'],
            delta=f"{summary['pass_pct']:.1f}% of total",
            delta_color="off"
        )

    with col3:
        st.metric(
            "Needs Review",
            summary['needs_review'],
            delta=f"{summary['needs_review_pct']:.1f}% of total",
            delta_color="off"
        )

    with col4:
        st.metric(
            "Fail",
            summary['fail'],
            delta=f"{summary['fail_pct']:.1f}% of total",
            delta_color="off"
        )
    
    # Progress bar
    reviewed = summary['total'] - summary['pending']
    if summary['total'] > 0:
        progress = reviewed / summary['total']
        st.progress(progress)
        st.caption(f"Progress: {reviewed}/{summary['total']} subjects reviewed ({summary['reviewed_pct']:.1f}%)")
    
    st.markdown("---")
    
    # Filters
    st.markdown('<h2 class="section-header">Filter</h2>', 
                unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_filter = st.selectbox(
            "QC Status",
            options=['all', 'pending', 'pass', 'fail', 'needs_review'],
            key="qc_dashboard_status_filter"
        )
    
    with col2:
        session_filter = st.selectbox(
            "Session",
            options=['all', '2WK', '6MO', 'both'],
            key="qc_dashboard_session_filter"
        )
    
    with col3:
        flagged_only = st.checkbox(
            "Flagged only",
            key="qc_dashboard_flagged_only"
        )
    
    # Get filtered subjects
    if flagged_only:
        subjects = qc_mgr.get_flagged_subjects()
    else:
        subjects = qc_mgr.get_subjects_by_qc_status(status_filter)
    
    # Apply session filter
    if session_filter != 'all':
        from src.utils import filter_subjects
        subjects = filter_subjects(subjects, {'session': session_filter})
    
    st.markdown("---")
    
    # Subjects table
    st.markdown(f'<h2 class="section-header">Subjects ({len(subjects)})</h2>', 
                unsafe_allow_html=True)
    
    if subjects:
        from src.utils import create_subject_dataframe, enrich_subjects_for_display
        enrich_subjects_for_display(subjects, st.session_state.db)
        df = create_subject_dataframe(subjects)

        # Display table
        st.dataframe(
            df,
            width='stretch',
            hide_index=True,
            height=300
        )
        
        # Bulk actions
        st.markdown("### Bulk Actions")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            bulk_status = st.selectbox(
                "Set status to",
                options=['pass', 'fail', 'needs_review'],
                key="bulk_qc_status"
            )
        
        with col2:
            st.write("")
            st.write("")
            if st.button("Apply to Filtered", width='stretch'):
                subject_ids = [s['subject_id'] for s in subjects]
                count = qc_mgr.bulk_update_qc(
                    subject_ids=subject_ids,
                    qc_status=bulk_status,
                    reviewed_by="bulk_update"
                )
                st.success(f"Updated {count} subjects to {bulk_status}")
                st.rerun()
        
        with col3:
            st.write("")
            st.write("")
            if st.button("Export QC Report", width='stretch'):
                report = qc_mgr.export_qc_report()
                
                # Convert to CSV
                import json
                from src.utils import create_subject_dataframe
                
                df_export = create_subject_dataframe(subjects)
                csv = df_export.to_csv(index=False)
                
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"qc_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
    else:
        st.info("No subjects match the filters")
    
    st.markdown("---")
    
    # Recent QC Activity
    st.markdown('<h2 class="section-header">Recent QC Activity</h2>', 
                unsafe_allow_html=True)
    
    activity = qc_mgr.get_recent_qc_activity(limit=10)
    
    if activity:
        from src.qc_manager import format_qc_history_entry
        
        for entry in activity:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                text = format_qc_history_entry(entry)
                st.text(text)
            
            with col2:
                if entry.get('notes'):
                    with st.expander("View Notes"):
                        st.text(entry['notes'])
    else:
        st.info("No recent QC activity")
    
    st.markdown("---")
    
    # QC Progress Summary
    st.markdown('<h2 class="section-header">Progress Summary</h2>', 
                unsafe_allow_html=True)
    
    progress_data = qc_mgr.get_qc_progress()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(
            "Reviewed",
            f"{progress_data['reviewed']}/{progress_data['total_subjects']}",
            delta=f"{progress_data['progress_pct']:.1f}% complete"
        )
    
    with col2:
        if progress_data['reviewed'] > 0:
            st.metric(
                "Pass Rate",
                f"{progress_data['pass_rate']:.1f}%",
                delta="of reviewed subjects"
            )
        else:
            st.metric("Pass Rate", "—", delta="No subjects reviewed yet")


def render_automated_qc_tab(auto_qc):
    """Render automated QC tab for computer checks."""
    # Automated QC Overview
    st.markdown('<h2 class="section-header">Automated QC Overview</h2>', 
                unsafe_allow_html=True)
    
    st.info("Automated checks detect technical issues: missing files, stub files, small files, missing metadata")
    
    # Get automated QC summary
    auto_summary = auto_qc.get_qc_summary()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Pass",
            auto_summary['pass'],
            delta=f"{auto_summary.get('pass_pct', 0):.1f}%"
        )
    
    with col2:
        st.metric(
            "Warnings",
            auto_summary['warning'],
            delta=f"{auto_summary.get('warning_pct', 0):.1f}%"
        )
    
    with col3:
        st.metric(
            "Fail",
            auto_summary['fail'],
            delta=f"{auto_summary.get('fail_pct', 0):.1f}%"
        )
    
    with col4:
        st.metric(
            "Pending",
            auto_summary['pending'],
            delta=f"{auto_summary.get('pending_pct', 0):.1f}%"
        )
    
    st.markdown("---")
    
    # Run Automated QC
    st.markdown('<h2 class="section-header">Run Automated Checks</h2>', 
                unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("Run automated quality checks on all subjects to detect technical issues")
    
    with col2:
        if st.button("Run Automated QC", type="primary", width='stretch'):
            subjects = st.session_state.db.get_all_subjects()
            subject_ids = [s['subject_id'] for s in subjects]
            
            if not subject_ids:
                expected_empty("No subjects indexed yet. Sync datasets in Manage Datasets first.")
            else:
                # Create progress container
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def progress_callback(current, total, subject_id):
                    progress_bar.progress(current / total)
                    status_text.text(f"Checking {current}/{total}: {subject_id}")
                
                # Run batch QC
                results = auto_qc.run_batch_qc(subject_ids, progress_callback)
                
                # Clear progress
                progress_bar.empty()
                status_text.empty()
                
                # Show summary
                pass_count = sum(1 for r in results.values() if r['status'] == 'pass')
                warn_count = sum(1 for r in results.values() if r['status'] == 'warning')
                fail_count = sum(1 for r in results.values() if r['status'] == 'fail')
                
                st.success(f"Automated QC complete: {pass_count} pass, {warn_count} warnings, {fail_count} fail")
                st.rerun()
    
    st.markdown("---")
    
    # Flagged Subjects (issues/warnings)
    st.markdown('<h2 class="section-header">Flagged Subjects</h2>', 
                unsafe_allow_html=True)
    
    flagged = auto_qc.get_flagged_subjects()
    
    if flagged:
        st.warning(f"{len(flagged)} subjects have automated QC issues or warnings")
        
        flagged_data = []
        for subject in flagged:
            auto_qc_status = subject.get('automated_qc_status', 'pending')
            
            # Parse results to count issues/warnings
            import json
            results_json = subject.get('automated_qc_results', '{}')
            try:
                results = json.loads(results_json) if results_json else {}
                issue_count = len(results.get('issues', []))
                warning_count = len(results.get('warnings', []))
            except Exception:
                issue_count = 0
                warning_count = 0
            
            flagged_data.append({
                'Subject': subject['subject_id'],
                'Status': auto_qc_status.upper(),
                'Issues': issue_count,
                'Warnings': warning_count,
                'Last Check': subject.get('automated_qc_date', 'Never')[:10] if subject.get('automated_qc_date') else 'Never'
            })
        
        df_flagged = pd.DataFrame(flagged_data)
        st.dataframe(df_flagged, width='stretch', hide_index=True)
        
        # Allow user to view details
        selected_subject = st.selectbox(
            "Select subject to view details",
            options=[s['subject_id'] for s in flagged],
            key="auto_qc_selected_subject"
        )
        
        if st.button("View Details", width='stretch'):
            st.session_state.selected_subject = selected_subject
            st.session_state.current_page = 'subject_detail'
            st.rerun()
    else:
        st.success("No automated QC issues detected")
    
    st.markdown("---")
    
    # Filter by Automated QC Status
    st.markdown('<h2 class="section-header">Browse by Status</h2>', 
                unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        auto_status_filter = st.selectbox(
            "Filter by Automated QC",
            options=['all', 'pass', 'warning', 'fail', 'pending'],
            key="auto_qc_status_filter"
        )
    
    with col2:
        if auto_status_filter != 'all':
            filtered = auto_qc.get_subjects_by_status(auto_status_filter)
            st.info(f"{len(filtered)} subjects with status: {auto_status_filter}")
        else:
            filtered = st.session_state.db.get_all_subjects()
            st.info(f"Showing all {len(filtered)} subjects")


def render_pennsieve_sync_tab(qc_mgr):
    """Render Pennsieve QC sync tab for uploading QC results (v3.1+)."""
    # Sync Overview
    st.markdown('<h2 class="section-header">QC Sync Status</h2>', 
                unsafe_allow_html=True)
    
    st.info("Export and upload QC results to Pennsieve datasets as CSV files in derivatives/qc/")
    
    # Get Pennsieve datasets
    datasets = st.session_state.db.get_all_datasets(status='active')
    pennsieve_datasets = [ds for ds in datasets if ds['platform'] == 'pennsieve']
    
    if not pennsieve_datasets:
        st.warning("No Pennsieve datasets configured")
        st.markdown("**Note**: QC sync is only available for Pennsieve datasets")
        return
    
    # Dataset selector
    dataset_options = {ds['name']: ds for ds in pennsieve_datasets}
    
    if len(dataset_options) == 1:
        selected_dataset_name = list(dataset_options.keys())[0]
        selected_dataset = dataset_options[selected_dataset_name]
        st.caption(f"Dataset: {selected_dataset_name}")
    else:
        selected_dataset_name = st.selectbox(
            "Select Pennsieve Dataset",
            options=list(dataset_options.keys()),
            key="pennsieve_sync_dataset"
        )
        selected_dataset = dataset_options[selected_dataset_name]
    
    dataset_id = selected_dataset['id']
    
    # Get unsynced QC count
    unsynced_count = qc_mgr.get_unsynced_qc_count(dataset_id)
    unsynced_scans = st.session_state.db.get_unsynced_scans(dataset_id)
    
    # Sync metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Unsynced QC Records",
            unsynced_count,
            delta="pending upload"
        )
    
    with col2:
        # Get last sync date
        conn = st.session_state.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MAX(sync_date) 
            FROM scans 
            WHERE dataset_id = ? AND synced_to_platform = 1
        """, (dataset_id,))
        last_sync = cursor.fetchone()[0]
        conn.close()
        
        if last_sync:
            from src.utils import format_timestamp
            st.metric(
                "Last Sync",
                format_timestamp(last_sync)
            )
        else:
            st.metric("Last Sync", "Never")
    
    with col3:
        # Count total reviewed scans
        conn = st.session_state.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM scans 
            WHERE dataset_id = ? AND qc_status != 'pending'
        """, (dataset_id,))
        reviewed_count = cursor.fetchone()[0]
        conn.close()
        
        st.metric(
            "Total Reviewed Scans",
            reviewed_count
        )
    
    st.markdown("---")
    
    # Unsynced QC preview
    if unsynced_count > 0:
        st.markdown('<h2 class="section-header">Unsynced QC Results</h2>', 
                    unsafe_allow_html=True)
        
        preview_data = []
        for scan in unsynced_scans[:10]:
            preview_data.append({
                'Subject': scan['subject_id'],
                'Session': scan['session'],
                'Scan': f"{scan['modality']}/{scan['suffix']}",
                'QC Status': scan['qc_status'],
                'Flagged': 'Yes' if scan['flagged'] else 'No',
                'Reviewed By': scan.get('reviewed_by', '—')
            })
        
        if preview_data:
            st.dataframe(pd.DataFrame(preview_data), width='stretch', hide_index=True)
            if len(unsynced_scans) > 10:
                st.caption(f"Showing 10 of {len(unsynced_scans)} unsynced records")
    
    st.markdown("---")
    
    # Export and Upload Actions
    st.markdown('<h2 class="section-header">Export & Upload QC Results</h2>', 
                unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button(" Export QC CSV", width='stretch', disabled=(unsynced_count == 0)):
            if unsynced_count == 0:
                st.warning("No QC results to export")
            else:
                # Generate CSV filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                dataset_name_clean = selected_dataset_name.replace(' ', '_').replace('/', '_')
                csv_filename = f"qc_results_{dataset_name_clean}_{timestamp}.csv"
                csv_path = f"data/{csv_filename}"
                
                # Export CSV
                with st.spinner("Generating QC CSV..."):
                    success = qc_mgr.export_qc_csv(
                        dataset_id=dataset_id,
                        output_path=csv_path,
                        include_pending=False
                    )
                
                if success:
                    st.success(f"QC CSV exported: {csv_filename}")
                    st.session_state.last_qc_csv_path = csv_path
                    
                    # Offer download
                    with open(csv_path, 'rb') as f:
                        st.download_button(
                            label="Download CSV",
                            data=f,
                            file_name=csv_filename,
                            mime='text/csv',
                            width='stretch'
                        )
                else:
                    st.error("Failed to export QC CSV")
    
    with col2:
        # Check if we have credentials and a recent CSV
        has_csv = st.session_state.get('last_qc_csv_path') and Path(st.session_state.last_qc_csv_path).exists()
        has_credentials = selected_dataset.get('api_key_encrypted') and selected_dataset.get('api_secret_encrypted')
        
        upload_disabled = not (has_csv and has_credentials and unsynced_count > 0)
        
        if st.button("Push to Pennsieve", 
                    type="primary", 
                    width='stretch',
                    disabled=upload_disabled):
            
            if not has_csv:
                st.error("Please export QC CSV first")
            elif not has_credentials:
                st.error("No Pennsieve credentials found for this dataset")
            else:
                csv_path = st.session_state.last_qc_csv_path
                
                # Initialize Pennsieve Agent
                try:
                    from src.pennsieve_agent import PennsieveAgent
                    
                    agent = PennsieveAgent()
                    
                    # Upload with progress
                    with st.spinner("Uploading QC results to Pennsieve..."):
                        progress_container = st.empty()
                        
                        def upload_progress(pct, msg):
                            if pct:
                                progress_container.progress(pct / 100, text=msg)
                            else:
                                progress_container.text(msg)
                        
                        success = agent.upload_qc_csv(
                            csv_path=csv_path,
                            dataset_name=selected_dataset.get('dataset_id_external') or selected_dataset['name'],
                            api_key=selected_dataset['api_key_encrypted'],
                            api_secret=selected_dataset['api_secret_encrypted'],
                            remote_folder='derivatives/qc',
                            progress_callback=upload_progress
                        )
                    
                    progress_container.empty()
                    
                    if success:
                        # Mark scans as synced
                        scan_ids = [scan['id'] for scan in unsynced_scans]
                        st.session_state.db.mark_scans_synced(scan_ids)
                        
                        st.success(f"QC results uploaded to Pennsieve!")
                        st.info(f"Location: derivatives/qc/{Path(csv_path).name}")
                        st.balloons()
                        
                        # Clear cached CSV path
                        st.session_state.last_qc_csv_path = None
                        
                        st.rerun()
                    else:
                        st.error("Upload failed - check credentials and network connection")
                
                except RuntimeError as e:
                    st.error(f"Pennsieve Agent not available: {e}")
                    st.info("Install with: pip install pennsieve")
                except Exception as e:
                    st.error(f"Upload error: {e}")
    
    # Help text
    if upload_disabled:
        reasons = []
        if not has_csv:
            reasons.append("Export QC CSV first")
        if not has_credentials:
            reasons.append("Configure Pennsieve credentials")
        if unsynced_count == 0:
            reasons.append("No unsynced QC results")
        
        st.caption(f"Push disabled: {', '.join(reasons)}")
    
    st.markdown("---")
    
    # Sync workflow guide
    with st.expander("How QC Sync Works"):
        st.markdown("""
        **Workflow**:
        1. Review scans on Subject Detail pages or QC page
        2. Mark QC status for each scan (pass/fail/needs review)
        3. Add notes and flag issues as needed
        4. Export QC results as CSV (includes all unsynced scans)
        5. Push CSV to Pennsieve (uploads to derivatives/qc/ folder)
        6. QC results marked as synced in local database
        
        **CSV Format**:
        - Filename: `qc_results_<dataset>_<timestamp>.csv`
        - Location in Pennsieve: `derivatives/qc/`
        - Columns: scan_id, subject_id, session_id, modality, suffix, qc_status, qc_notes, reviewed_by, reviewed_date, flagged, file_path
        
        **Collaboration**:
        - Other reviewers can download the CSV from Pennsieve
        - Import CSV to merge QC results (latest timestamp wins)
        - Track QC history and changes over time
        
        **BIDS Compliance**:
        - QC results stored in derivatives/ (not raw data)
        - Follows BIDS convention for derived/processed data
        - Does not modify original dataset files
        """)


