"""Export page (extracted from app.py)."""
from datetime import datetime
from pathlib import Path
from typing import List
import pandas as pd
import streamlit as st
from src.ui_calm import expected_empty
from views.common import get_subject_session_columns, render_breadcrumb, render_page_header


def page_export():
    """Export page with cohort export functionality."""
    render_page_header('export', show_back_to_dashboard=True)
    render_breadcrumb('export')
    st.markdown('<h1 class="main-header">Export Data</h1>', 
                unsafe_allow_html=True)
    
    if not st.session_state.db:
        st.warning("Please complete setup first")
        return
    
    # Create tabs for different export options
    tab1, tab2, tab3 = st.tabs(["Export Custom Cohort", "QC Results", "Subject Lists"])
    
    with tab1:
        # Custom Cohort Export
        st.markdown('<h2 class="section-header">Export Custom Cohort as BIDS Dataset</h2>',
                    unsafe_allow_html=True)

        st.info(
            "Create a new BIDS-compliant dataset from selected subjects across one or more "
            "source datasets. Works with data that is on disk locally (local or already-downloaded "
            "datasets); subjects whose files aren't on disk are skipped and reported."
        )

        from src.utils import platform_label
        from src.cohort_exporter import CohortExporter

        cohort_datasets = st.session_state.db.get_all_datasets(status='active') or []
        if not cohort_datasets:
            st.warning("No datasets available. Add a dataset in **Manage Datasets** first.")
        else:
            ds_by_id = {d['id']: d for d in cohort_datasets}

            sel_ds_ids = st.multiselect(
                "Source datasets",
                options=[d['id'] for d in cohort_datasets],
                format_func=lambda i: f"[{platform_label(ds_by_id[i]['platform'])}] {ds_by_id[i]['name']}",
                key="cohort_src_datasets",
            )

            # Gather subjects across the selected datasets.
            subject_choices = {}  # display label -> (subject_id, dataset_id)
            for did in sel_ds_ids:
                for s in (st.session_state.db.get_subjects_by_dataset(did) or []):
                    label = (f"[{platform_label(ds_by_id[did]['platform'])}] "
                             f"{ds_by_id[did]['name']} / {s['subject_id']}")
                    subject_choices[label] = (s['subject_id'], did)

            if sel_ds_ids and not subject_choices:
                st.info("No subjects found in the selected dataset(s). Sync subjects in **Manage Datasets** first.")

            sel_subject_labels = st.multiselect(
                "Subjects to include",
                options=sorted(subject_choices.keys()),
                default=sorted(subject_choices.keys()),
                key="cohort_subjects",
                help="Defaults to all subjects in the selected datasets.",
            )

            col_a, col_b = st.columns(2)
            with col_a:
                cohort_name = st.text_input("Cohort name", value="my_cohort", key="cohort_name")
                copy_mode = st.radio(
                    "File handling",
                    options=["symlink", "copy", "hardlink"],
                    format_func=lambda m: {
                        "symlink": "Symlink (fast; references source files)",
                        "copy": "Copy (independent duplicate)",
                        "hardlink": "Hardlink (fast; same filesystem only)",
                    }[m],
                    key="cohort_copy_mode",
                )
            with col_b:
                from src.app_paths import cohorts_dir
                default_out = str(cohorts_dir() / (cohort_name or "my_cohort"))
                output_path = st.text_input("Output folder", value=default_out, key="cohort_output_path")
                description = st.text_area(
                    "Description (optional)",
                    key="cohort_desc",
                    placeholder="Purpose / inclusion criteria for this cohort",
                )

            st.caption(f"{len(sel_subject_labels)} subject(s) selected from {len(sel_ds_ids)} dataset(s).")

            export_disabled = not (sel_subject_labels and cohort_name.strip() and output_path.strip())
            if st.button("Export Cohort", type="primary", disabled=export_disabled, key="cohort_export_btn"):
                pairs = [subject_choices[label] for label in sel_subject_labels]
                subject_ids = [p[0] for p in pairs]
                dataset_ids = [p[1] for p in pairs]

                exporter = CohortExporter(st.session_state.db)
                with st.spinner(f"Exporting {len(subject_ids)} subject(s) to {output_path}..."):
                    result = exporter.export_cohort(
                        subject_ids=subject_ids,
                        dataset_ids=dataset_ids,
                        output_path=output_path,
                        cohort_name=cohort_name.strip(),
                        description=description.strip(),
                        copy_mode=copy_mode,
                    )

                if result.get('success'):
                    st.success(
                        f"Exported {result['subjects_exported']} subject(s) to "
                        f"{result['output_path']} ({result['total_size_mb']:.1f} MB)."
                    )
                else:
                    st.error("Export did not complete — no subject data was copied. See details below.")

                if result.get('warnings'):
                    with st.expander(f"Warnings ({len(result['warnings'])})"):
                        for w in result['warnings']:
                            st.write(f"- {w}")
                if result.get('errors'):
                    with st.expander(f"Errors ({len(result['errors'])})", expanded=True):
                        for e in result['errors']:
                            st.write(f"- {e}")
    
    with tab2:
        # QC Results Export
        st.markdown('<h2 class="section-header">Quality Control Results</h2>', 
                    unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.write("Export QC status, notes, and review history for all subjects")
    
        with col2:
            if st.button("Export QC Results", width='stretch'):
                # Get all subjects with QC data
                subjects = st.session_state.db.get_all_subjects()
                
                if not subjects:
                    expected_empty("No subjects to export. Sync datasets in Manage Datasets first.")
                else:
                    export_data = []
                    for subject in subjects:
                        # Get dynamic session columns
                        session_cols = get_subject_session_columns(subject)
                        
                        row = {
                            'Subject ID': subject['subject_id'],
                            'QC Status': subject.get('qc_status', 'pending'),
                            'Flagged': 'Yes' if subject.get('flagged') else 'No',
                        }
                        # Add dynamic session columns
                        row.update(session_cols)
                        # Add remaining columns
                        row.update({
                            'QC Notes': subject.get('qc_notes', ''),
                            'Reviewed By': subject.get('reviewed_by', ''),
                            'Review Date': subject.get('review_date', '')
                        })
                        export_data.append(row)
                    
                    df = pd.DataFrame(export_data)
                    csv = df.to_csv(index=False)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"qc_results_{timestamp}.csv",
                        mime="text/csv",
                        width='stretch'
                    )
                    
                    st.success(f"Ready to download {len(export_data)} QC records")
    
    with tab3:
        # Subject List Export
        st.markdown('<h2 class="section-header">Subject Lists</h2>', 
                    unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**All Subjects**")
            if st.button("Export All", width='stretch', key="export_all"):
                subjects = st.session_state.db.get_all_subjects()
                
                if subjects:
                    export_data = []
                    for subject in subjects:
                        # Get dynamic session columns
                        session_cols = get_subject_session_columns(subject)
                        
                        row = {
                            'Subject ID': subject['subject_id'],
                        }
                        # Add dynamic session columns
                        row.update(session_cols)
                        # Add remaining columns
                        row['QC Status'] = subject.get('qc_status', 'pending')
                        export_data.append(row)
                    
                    df = pd.DataFrame(export_data)
                    csv = df.to_csv(index=False)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"all_subjects_{timestamp}.csv",
                        mime="text/csv",
                        width='stretch',
                        key="download_all"
                    )
        
        with col2:
            st.write("**Complete Subjects**")
            st.caption("2+ sessions")
            if st.button("Export Complete", width='stretch', key="export_complete"):
                subjects = st.session_state.db.get_all_subjects()
                
                # Filter complete subjects (2+ sessions)
                complete_subjects = []
                for s in subjects:
                    dataset_id = s.get('dataset_id')
                    subject_id = s['subject_id']
                    sessions_info = st.session_state.db.get_subject_sessions(subject_id, dataset_id)
                    if len(sessions_info) >= 2:
                        complete_subjects.append(s)
                
                if complete_subjects:
                    export_data = []
                    for subject in complete_subjects:
                        # Get dynamic session columns
                        session_cols = get_subject_session_columns(subject)
                        
                        row = {
                            'Subject ID': subject['subject_id'],
                        }
                        # Add dynamic session columns
                        row.update(session_cols)
                        # Add remaining columns
                        row['QC Status'] = subject.get('qc_status', 'pending')
                        export_data.append(row)
                    
                    df = pd.DataFrame(export_data)
                    csv = df.to_csv(index=False)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"complete_subjects_{timestamp}.csv",
                        mime="text/csv",
                        width='stretch',
                        key="download_complete"
                    )
                    
                    st.caption(f"{len(complete_subjects)} subjects")
                else:
                    st.info("No complete subjects")
        
        with col3:
            st.write("**Flagged Subjects**")
            st.caption("Needs review")
            if st.button("Export Flagged", width='stretch', key="export_flagged"):
                subjects = st.session_state.db.get_all_subjects()
                
                # Filter flagged subjects
                flagged_subjects = [s for s in subjects if s.get('flagged')]
                
                if flagged_subjects:
                    export_data = []
                    for subject in flagged_subjects:
                        # Get dynamic session columns
                        session_cols = get_subject_session_columns(subject)
                        
                        row = {
                            'Subject ID': subject['subject_id'],
                            'QC Status': subject.get('qc_status', 'pending'),
                        }
                        # Add dynamic session columns
                        row.update(session_cols)
                        # Add remaining columns
                        row.update({
                            'QC Notes': subject.get('qc_notes', ''),
                            'Reviewed By': subject.get('reviewed_by', '')
                        })
                        export_data.append(row)
                    
                    df = pd.DataFrame(export_data)
                    csv = df.to_csv(index=False)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"flagged_subjects_{timestamp}.csv",
                        mime="text/csv",
                        width='stretch',
                        key="download_flagged"
                    )
                    
                    st.caption(f"{len(flagged_subjects)} subjects")
                else:
                    st.info("No flagged subjects")
        
        st.markdown("---")
        
        # Download History Export
        st.markdown('<h2 class="section-header">Download History</h2>', 
                    unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.write("Export download queue status and history")
        
        with col2:
            if st.button("Export Downloads", width='stretch'):
                # Get download queue items
                query = """
                    SELECT 
                        subject_id,
                        file_path,
                        status,
                        file_size_bytes,
                        added_date,
                        started_date,
                        completed_date,
                        error_message
                    FROM download_queue
                    ORDER BY added_date DESC
                """
                
                queue_items = st.session_state.db.execute_query(query)
                
                if queue_items:
                    export_data = []
                    for item in queue_items:
                        export_data.append({
                            'Subject ID': item['subject_id'],
                            'File Path': item['file_path'],
                            'File Name': Path(item['file_path']).name,
                            'Status': item['status'],
                            'Size (MB)': round(item.get('file_size_bytes', 0) / (1024 * 1024), 2),
                            'Added Date': item.get('added_date', ''),
                            'Started Date': item.get('started_date', ''),
                            'Completed Date': item.get('completed_date', ''),
                            'Error Message': item.get('error_message', '')
                        })
                    
                    df = pd.DataFrame(export_data)
                    csv = df.to_csv(index=False)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"download_history_{timestamp}.csv",
                        mime="text/csv",
                        width='stretch',
                        key="download_history"
                    )
                    
                    st.success(f"Ready to download {len(export_data)} download records")
                else:
                    st.info("No download history available")


