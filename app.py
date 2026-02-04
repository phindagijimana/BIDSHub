"""
Data Explorer - Main Streamlit Application

A professional BIDS dataset management tool with Pennsieve integration.
"""

import streamlit as st
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import local modules
from src.theme import apply_custom_theme, Theme, render_status_badge, format_file_size
from src.database import Database
from src.bids_loader import BIDSLoader
from src.pennsieve_client import PennsieveClient


# Page configuration
st.set_page_config(
    page_title="Data Explorer",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom theme
apply_custom_theme()


def init_session_state():
    """Initialize Streamlit session state variables."""
    if 'setup_complete' not in st.session_state:
        st.session_state.setup_complete = False
    
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'setup' if not st.session_state.setup_complete else 'dashboard'
    
    if 'bids_root' not in st.session_state:
        st.session_state.bids_root = None
    
    if 'dataset_name' not in st.session_state:
        st.session_state.dataset_name = None
    
    if 'db' not in st.session_state:
        st.session_state.db = None
    
    if 'bids_loader' not in st.session_state:
        st.session_state.bids_loader = None
    
    if 'ps_client' not in st.session_state:
        st.session_state.ps_client = None
    
    if 'selected_subject' not in st.session_state:
        st.session_state.selected_subject = None
    
    if 'filter_status' not in st.session_state:
        st.session_state.filter_status = 'all'
    
    if 'filter_session' not in st.session_state:
        st.session_state.filter_session = 'all'
    
    if 'search_query' not in st.session_state:
        st.session_state.search_query = ''


def render_breadcrumb(current_page: str, parent_page: str = None):
    """Render breadcrumb navigation at top of page."""
    # Only show breadcrumb if not on dashboard
    if current_page == 'dashboard':
        return
    
    # Page names mapping
    page_names = {
        'dashboard': 'Dashboard',
        'subjects': 'Subjects',
        'subject_detail': 'Subject Detail',
        'downloads': 'Download Manager',
        'qc': 'QC Dashboard',
        'export': 'Export',
        'setup': 'Settings'
    }
    
    # Build breadcrumb trail as text only (clean, minimal)
    breadcrumb_parts = ['Home']
    
    # Add parent page if exists
    if parent_page and parent_page != 'dashboard':
        breadcrumb_parts.append(page_names.get(parent_page, parent_page))
    
    # Add current page
    breadcrumb_parts.append(page_names.get(current_page, current_page))
    
    # Display breadcrumb
    breadcrumb_text = ' / '.join(breadcrumb_parts)
    st.caption(breadcrumb_text)


def render_sidebar():
    """Render navigation sidebar."""
    with st.sidebar:
        st.markdown('<h1 style="color: #002d72;">Data Explorer</h1>', 
                   unsafe_allow_html=True)
        
        if st.session_state.dataset_name:
            st.caption(f"**Dataset:** {st.session_state.dataset_name}")
        
        st.markdown("---")
        
        if st.session_state.setup_complete:
            st.markdown("### Navigation")
            
            # Get current page for highlighting
            current = st.session_state.current_page
            
            # Dashboard
            dashboard_label = "▶ Dashboard" if current == 'dashboard' else "Dashboard"
            if st.button(dashboard_label, 
                        use_container_width=True,
                        key="nav_dashboard"):
                st.session_state.current_page = 'dashboard'
                st.rerun()
            
            # Subjects
            subjects_label = "▶ Subjects" if current in ['subjects', 'subject_detail'] else "Subjects"
            if st.button(subjects_label, 
                        use_container_width=True,
                        key="nav_subjects"):
                st.session_state.current_page = 'subjects'
                st.rerun()
            
            # Download Manager
            downloads_label = "▶ Download Manager" if current == 'downloads' else "Download Manager"
            if st.button(downloads_label, 
                        use_container_width=True,
                        key="nav_downloads"):
                st.session_state.current_page = 'downloads'
                st.rerun()
            
            # QC Dashboard
            qc_label = "▶ QC Dashboard" if current == 'qc' else "QC Dashboard"
            if st.button(qc_label, 
                        use_container_width=True,
                        key="nav_qc"):
                st.session_state.current_page = 'qc'
                st.rerun()
            
            # Export
            export_label = "▶ Export" if current == 'export' else "Export"
            if st.button(export_label, 
                        use_container_width=True,
                        key="nav_export"):
                st.session_state.current_page = 'export'
                st.rerun()
            
            st.markdown("---")
            
            # Settings
            settings_label = "▶ Settings" if current == 'setup' else "Settings"
            if st.button(settings_label, 
                        use_container_width=True,
                        key="nav_settings"):
                st.session_state.current_page = 'setup'
                st.rerun()
        
        else:
            st.info("Complete setup to access features")
        
        st.markdown("---")
        st.caption("Data Explorer v1.0.0")


def page_setup():
    """Setup page for first-time configuration."""
    render_breadcrumb('setup')
    st.markdown('<h1 class="main-header">Data Explorer - Setup</h1>', 
                unsafe_allow_html=True)
    
    st.markdown("""
    Welcome to Data Explorer! Configure your BIDS dataset and Pennsieve connection.
    """)
    
    st.markdown('<h2 class="section-header">BIDS Dataset Configuration</h2>', 
                unsafe_allow_html=True)
    
    # BIDS directory input
    bids_root = st.text_input(
        "BIDS Directory Path",
        value=st.session_state.bids_root or "",
        placeholder="/path/to/your/bids/dataset",
        help="Path to the root directory of your BIDS dataset"
    )
    
    # Check if directory exists
    if bids_root and not Path(bids_root).exists():
        st.error(f"Directory not found: {bids_root}")
    elif bids_root and Path(bids_root).exists():
        st.success(f"Directory found")
    
    st.markdown('<h2 class="section-header">Pennsieve Configuration</h2>', 
                unsafe_allow_html=True)
    
    # Pennsieve dataset name
    dataset_name = st.text_input(
        "Pennsieve Dataset Name",
        value=st.session_state.dataset_name or "",
        placeholder="TrackTBI",
        help="Name of your dataset on Pennsieve"
    )
    
    col1, col2 = st.columns(2)
    
    # Pennsieve credentials
    with col1:
        api_key = st.text_input(
            "Pennsieve API Key",
            type="password",
            help="Your Pennsieve API key"
        )
    
    with col2:
        api_secret = st.text_input(
            "Pennsieve API Secret",
            type="password",
            help="Your Pennsieve API secret"
        )
    
    st.markdown("---")
    
    # Initialize button
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        initialize_button = st.button(
            "Initialize Dataset",
            type="primary",
            use_container_width=True,
            disabled=not (bids_root and dataset_name and api_key and api_secret)
        )
    
    with col2:
        if st.session_state.setup_complete:
            if st.button("Skip Setup", use_container_width=True):
                st.session_state.current_page = 'dashboard'
                st.rerun()
    
    # Handle initialization
    if initialize_button:
        with st.spinner("Initializing dataset..."):
            try:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Step 1: Verify BIDS directory
                status_text.text("1/5 Verifying BIDS directory...")
                progress_bar.progress(20)
                
                if not Path(bids_root).exists():
                    st.error("BIDS directory not found!")
                    return
                
                # Step 2: Connect to Pennsieve
                status_text.text("2/5 Connecting to Pennsieve...")
                progress_bar.progress(40)
                
                ps_client = PennsieveClient(
                    api_key=api_key,
                    api_secret=api_secret,
                    dataset_name=dataset_name
                )
                
                if not ps_client.verify_connection():
                    st.error("Failed to connect to Pennsieve!")
                    return
                
                # Step 3: Load BIDS dataset
                status_text.text("3/5 Loading BIDS dataset...")
                progress_bar.progress(60)
                
                bids_loader = BIDSLoader(bids_root, validate=False)
                
                # Step 4: Initialize database
                status_text.text("4/5 Initializing database...")
                progress_bar.progress(80)
                
                db = Database()
                
                # Step 5: Index subjects
                status_text.text("5/5 Indexing subjects...")
                progress_bar.progress(90)
                
                subjects = bids_loader.get_subjects()
                for subject in subjects:
                    sessions = bids_loader.get_sessions(subject=subject)
                    has_2wk = '2WK' in sessions
                    has_6mo = '6MO' in sessions
                    
                    scan_count_2wk = len(bids_loader.get_subject_scans(subject, '2WK')) if has_2wk else 0
                    scan_count_6mo = len(bids_loader.get_subject_scans(subject, '6MO')) if has_6mo else 0
                    
                    db.add_subject(
                        subject_id=subject,
                        has_2wk=has_2wk,
                        has_6mo=has_6mo,
                        scan_count_2wk=scan_count_2wk,
                        scan_count_6mo=scan_count_6mo
                    )
                
                progress_bar.progress(100)
                status_text.text("Initialization complete!")
                
                # Save to session state
                st.session_state.bids_root = bids_root
                st.session_state.dataset_name = dataset_name
                st.session_state.db = db
                st.session_state.bids_loader = bids_loader
                st.session_state.ps_client = ps_client
                st.session_state.setup_complete = True
                st.session_state.current_page = 'dashboard'
                
                st.success(f"Successfully initialized dataset with {len(subjects)} subjects!")
                st.balloons()
                
                # Auto-navigate to dashboard
                st.rerun()
                
            except Exception as e:
                st.error(f"Initialization failed: {e}")
                import traceback
                with st.expander("Error Details"):
                    st.code(traceback.format_exc())


def page_dashboard():
    """Main dashboard page."""
    render_breadcrumb('dashboard')
    st.markdown('<h1 class="main-header">Data Explorer</h1>', 
                unsafe_allow_html=True)
    
    if not st.session_state.db:
        st.warning("Please complete setup first")
        return
    
    # Get statistics
    stats = st.session_state.db.get_stats()
    
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
                 delta=f"{pct:.1f}% have both sessions")
    
    with col3:
        st.metric("Total Scans", stats.get('total_scans', 0))
    
    with col4:
        downloaded = stats.get('downloaded_scans', 0)
        total_scans = stats.get('total_scans', 1)
        pct = (downloaded / total_scans * 100) if total_scans > 0 else 0
        st.metric("Downloaded", downloaded, 
                 delta=f"{pct:.1f}%")
    
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
    
    st.markdown("---")
    
    # Quick actions
    st.markdown('<h2 class="section-header">Quick Actions</h2>', 
                unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Browse Subjects", use_container_width=True):
            st.session_state.current_page = 'subjects'
            st.rerun()
    
    with col2:
        if st.button("Download Manager", use_container_width=True):
            st.session_state.current_page = 'downloads'
            st.rerun()
    
    with col3:
        if st.button("QC Dashboard", use_container_width=True):
            st.session_state.current_page = 'qc'
            st.rerun()


def page_subjects():
    """Subject browser page."""
    render_breadcrumb('subjects')
    st.markdown('<h1 class="main-header">Subjects</h1>', 
                unsafe_allow_html=True)
    
    if not st.session_state.db:
        st.warning("Please complete setup first")
        return
    
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
    
    # Get subjects from database
    filters = {}
    if qc_filter != 'all':
        filters['qc_status'] = qc_filter
    
    subjects = st.session_state.db.get_all_subjects(filters)
    
    # Apply additional filters
    from src.utils import filter_subjects, create_subject_dataframe
    
    filter_criteria = {
        'search': search,
        'session': session_filter if session_filter != 'all' else None,
    }
    
    filtered_subjects = filter_subjects(subjects, filter_criteria)
    
    # Display count
    st.caption(f"Showing {len(filtered_subjects)} of {len(subjects)} subjects")
    
    if not filtered_subjects:
        st.info("No subjects match the filters")
        return
    
    # Create DataFrame for display
    df = create_subject_dataframe(filtered_subjects)
    
    # Display table with selection
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=400
    )
    
    # Subject selection for detail view
    st.markdown("---")
    st.markdown("### View Subject Details")
    
    subject_ids = [s['subject_id'] for s in filtered_subjects]
    selected = st.selectbox(
        "Select subject to view",
        options=subject_ids,
        index=0 if subject_ids else None,
        key="selected_subject_view"
    )
    
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("View Details", use_container_width=True):
            st.session_state.selected_subject = selected
            st.session_state.current_page = 'subject_detail'
            st.rerun()
    
    with col2:
        if st.button("Export Filtered List", use_container_width=True):
            from src.utils import export_to_csv
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"subjects_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )


def page_downloads():
    """Download manager page."""
    render_breadcrumb('downloads')
    st.markdown('<h1 class="main-header">Download Manager</h1>', 
                unsafe_allow_html=True)
    
    if not st.session_state.db or not st.session_state.ps_client:
        st.warning("Please complete setup first")
        return
    
    # Initialize download manager in session state
    if 'download_manager' not in st.session_state:
        from src.download_manager import DownloadManager
        st.session_state.download_manager = DownloadManager(
            ps_client=st.session_state.ps_client,
            database=st.session_state.db,
            max_concurrent=3
        )
    
    dm = st.session_state.download_manager
    
    # Storage Estimation
    st.markdown('<h2 class="section-header">Storage Estimation</h2>', 
                unsafe_allow_html=True)
    
    from src.download_manager import check_available_space
    from src.utils import format_file_size
    
    queued_size = dm.get_total_queue_size()
    queued_count = dm.get_queued_count()
    
    try:
        available_space = check_available_space('.')
    except:
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
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Select All Subjects", use_container_width=True):
            st.info("Quick select coming soon - use subject browser to add downloads")
    
    with col2:
        if st.button("Select Complete Only", use_container_width=True):
            st.info("Quick select coming soon - use subject browser to add downloads")
    
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
        st.info("No items in download queue. Add files from the subject browser.")
    else:
        # Create queue table
        queue_data = []
        for item in queue_items:
            queue_data.append({
                'ID': item['id'],
                'File': Path(item['file_path']).name,
                'Subject': item['subject_id'],
                'Size': format_file_size(item.get('file_size_bytes', 0)),
                'Status': item['status'].title(),
                'Added': item.get('added_date', 'Unknown')
            })
        
        df_queue = pd.DataFrame(queue_data)
        
        # Display table
        st.dataframe(
            df_queue,
            use_container_width=True,
            hide_index=True,
            height=300
        )
        
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
                        use_container_width=True,
                        disabled=stats['queued'] == 0):
                success = dm.start_downloads()
                if success:
                    st.success("Downloads started!")
                    st.rerun()
                else:
                    st.error("No items to download")
        
        with col2:
            if st.button("Pause All",
                        use_container_width=True,
                        disabled=stats['downloading'] == 0):
                dm.pause_downloads()
                st.info("Downloads paused")
                st.rerun()
        
        with col3:
            if st.button("Resume",
                        use_container_width=True,
                        disabled=stats['paused'] == 0):
                dm.resume_downloads()
                st.success("Downloads resumed")
                st.rerun()
        
        with col4:
            if st.button("Clear Queue",
                        use_container_width=True):
                cleared = dm.clear_queue('queued')
                st.success(f"Cleared {cleared} items")
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


def page_qc():
    """QC dashboard page."""
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
    
    # QC Overview
    st.markdown('<h2 class="section-header">QC Overview</h2>', 
                unsafe_allow_html=True)
    
    summary = qc_mgr.get_qc_summary()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Pending",
            summary['pending'],
            delta=f"{summary['pending_pct']:.1f}%"
        )
    
    with col2:
        st.metric(
            "Pass",
            summary['pass'],
            delta=f"{summary['pass_pct']:.1f}%"
        )
    
    with col3:
        st.metric(
            "Needs Review",
            summary['needs_review'],
            delta=f"{summary['needs_review_pct']:.1f}%"
        )
    
    with col4:
        st.metric(
            "Fail",
            summary['fail'],
            delta=f"{summary['fail_pct']:.1f}%"
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
        from src.utils import create_subject_dataframe
        df = create_subject_dataframe(subjects)
        
        # Display table
        st.dataframe(
            df,
            use_container_width=True,
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
            if st.button("Apply to Filtered", use_container_width=True):
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
            if st.button("Export QC Report", use_container_width=True):
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


def page_subject_detail():
    """Subject detail page."""
    subject_id = st.session_state.selected_subject
    
    if not subject_id:
        st.warning("No subject selected")
        if st.button("← Back to Subjects"):
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
        if st.button("← Back to Subjects", use_container_width=True):
            st.session_state.current_page = 'subjects'
            st.rerun()
    
    # Get subject data
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
        if st.button("Update QC Status", use_container_width=True):
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
    
    # Session scans
    if not st.session_state.bids_loader:
        st.warning("BIDS loader not initialized")
        return
    
    # Session 2WK
    if subject.get('has_2wk'):
        st.markdown("---")
        st.markdown('<h2 class="section-header">Session 2WK</h2>', 
                    unsafe_allow_html=True)
        
        scans_2wk = st.session_state.bids_loader.get_subject_scans(
            subject_id, '2WK'
        )
        
        if scans_2wk:
            scan_data = []
            for scan in scans_2wk:
                from src.utils import format_file_size
                file_size = st.session_state.bids_loader.get_file_size(
                    scan['file_path']
                )
                is_stub = st.session_state.bids_loader.is_stub_file(
                    scan['file_path']
                )
                
                scan_data.append({
                    'Scan': scan.get('suffix', 'unknown'),
                    'Modality': scan.get('modality', ''),
                    'Size': format_file_size(file_size),
                    'Status': 'Stub' if is_stub else 'Downloaded',
                    'File': Path(scan['file_path']).name
                })
            
            df_2wk = pd.DataFrame(scan_data)
            st.dataframe(df_2wk, use_container_width=True, hide_index=True)
            
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("Add All to Queue", key="dl_2wk"):
                    # Initialize download manager if needed
                    if 'download_manager' not in st.session_state:
                        from src.download_manager import DownloadManager
                        st.session_state.download_manager = DownloadManager(
                            ps_client=st.session_state.ps_client,
                            database=st.session_state.db,
                            max_concurrent=3
                        )
                    
                    # Add each scan to queue
                    added = 0
                    for scan in scans_2wk:
                        # Get package ID (from stub file or metadata)
                        package_id = None
                        if st.session_state.bids_loader.is_stub_file(scan['file_path']):
                            from src.utils import parse_pennsieve_stub
                            package_id = parse_pennsieve_stub(scan['file_path'])
                        
                        if package_id:
                            # Get scan from database to get scan_id
                            db_scans = st.session_state.db.get_subject_scans(subject_id, '2WK')
                            scan_id = None
                            for db_scan in db_scans:
                                if db_scan['file_path'] == scan['file_path']:
                                    scan_id = db_scan['id']
                                    break
                            
                            # If scan not in DB, add it
                            if not scan_id:
                                scan_id = st.session_state.db.add_scan(
                                    subject_id=subject_id,
                                    session='2WK',
                                    modality=scan.get('modality', ''),
                                    file_path=scan['file_path'],
                                    suffix=scan.get('suffix', ''),
                                    pennsieve_package_id=package_id
                                )
                            
                            if scan_id:
                                success = st.session_state.download_manager.add_to_queue(
                                    scan_id=scan_id,
                                    subject_id=subject_id,
                                    file_path=scan['file_path'],
                                    package_id=package_id,
                                    file_size=st.session_state.bids_loader.get_file_size(scan['file_path'])
                                )
                                if success:
                                    added += 1
                    
                    if added > 0:
                        st.success(f"Added {added} scans to download queue")
                    else:
                        st.warning("No scans added to queue")
        else:
            st.info("No scans found for session 2WK")
    
    # Session 6MO
    if subject.get('has_6mo'):
        st.markdown("---")
        st.markdown('<h2 class="section-header">Session 6MO</h2>', 
                    unsafe_allow_html=True)
        
        scans_6mo = st.session_state.bids_loader.get_subject_scans(
            subject_id, '6MO'
        )
        
        if scans_6mo:
            scan_data = []
            for scan in scans_6mo:
                from src.utils import format_file_size
                file_size = st.session_state.bids_loader.get_file_size(
                    scan['file_path']
                )
                is_stub = st.session_state.bids_loader.is_stub_file(
                    scan['file_path']
                )
                
                scan_data.append({
                    'Scan': scan.get('suffix', 'unknown'),
                    'Modality': scan.get('modality', ''),
                    'Size': format_file_size(file_size),
                    'Status': 'Stub' if is_stub else 'Downloaded',
                    'File': Path(scan['file_path']).name
                })
            
            df_6mo = pd.DataFrame(scan_data)
            st.dataframe(df_6mo, use_container_width=True, hide_index=True)
            
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("Add All to Queue", key="dl_6mo"):
                    # Initialize download manager if needed
                    if 'download_manager' not in st.session_state:
                        from src.download_manager import DownloadManager
                        st.session_state.download_manager = DownloadManager(
                            ps_client=st.session_state.ps_client,
                            database=st.session_state.db,
                            max_concurrent=3
                        )
                    
                    # Add each scan to queue
                    added = 0
                    for scan in scans_6mo:
                        # Get package ID (from stub file or metadata)
                        package_id = None
                        if st.session_state.bids_loader.is_stub_file(scan['file_path']):
                            from src.utils import parse_pennsieve_stub
                            package_id = parse_pennsieve_stub(scan['file_path'])
                        
                        if package_id:
                            # Get scan from database to get scan_id
                            db_scans = st.session_state.db.get_subject_scans(subject_id, '6MO')
                            scan_id = None
                            for db_scan in db_scans:
                                if db_scan['file_path'] == scan['file_path']:
                                    scan_id = db_scan['id']
                                    break
                            
                            # If scan not in DB, add it
                            if not scan_id:
                                scan_id = st.session_state.db.add_scan(
                                    subject_id=subject_id,
                                    session='6MO',
                                    modality=scan.get('modality', ''),
                                    file_path=scan['file_path'],
                                    suffix=scan.get('suffix', ''),
                                    pennsieve_package_id=package_id
                                )
                            
                            if scan_id:
                                success = st.session_state.download_manager.add_to_queue(
                                    scan_id=scan_id,
                                    subject_id=subject_id,
                                    file_path=scan['file_path'],
                                    package_id=package_id,
                                    file_size=st.session_state.bids_loader.get_file_size(scan['file_path'])
                                )
                                if success:
                                    added += 1
                    
                    if added > 0:
                        st.success(f"Added {added} scans to download queue")
                    else:
                        st.warning("No scans added to queue")
        else:
            st.info("No scans found for session 6MO")


def page_export():
    """Export page."""
    render_breadcrumb('export')
    st.markdown('<h1 class="main-header">Export Data</h1>', 
                unsafe_allow_html=True)
    
    st.info("Export functionality coming soon...")


def main():
    """Main application entry point."""
    # Initialize session state
    init_session_state()
    
    # Render sidebar
    render_sidebar()
    
    # Route to appropriate page
    page = st.session_state.current_page
    
    if page == 'setup' or not st.session_state.setup_complete:
        page_setup()
    elif page == 'dashboard':
        page_dashboard()
    elif page == 'subjects':
        page_subjects()
    elif page == 'subject_detail':
        page_subject_detail()
    elif page == 'downloads':
        page_downloads()
    elif page == 'qc':
        page_qc()
    elif page == 'export':
        page_export()
    else:
        page_dashboard()


if __name__ == "__main__":
    main()
