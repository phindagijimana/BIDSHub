"""
Data Explorer - Main Streamlit Application

A professional BIDS dataset management tool with Pennsieve integration.
"""

import streamlit as st
import os
from pathlib import Path
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
            
            if st.button("🏠 Dashboard", use_container_width=True):
                st.session_state.current_page = 'dashboard'
                st.rerun()
            
            if st.button("📋 Subjects", use_container_width=True):
                st.session_state.current_page = 'subjects'
                st.rerun()
            
            if st.button("⬇️ Download Manager", use_container_width=True):
                st.session_state.current_page = 'downloads'
                st.rerun()
            
            if st.button("✅ QC Dashboard", use_container_width=True):
                st.session_state.current_page = 'qc'
                st.rerun()
            
            if st.button("📤 Export", use_container_width=True):
                st.session_state.current_page = 'export'
                st.rerun()
            
            st.markdown("---")
            
            if st.button("⚙️ Settings", use_container_width=True):
                st.session_state.current_page = 'setup'
                st.rerun()
        
        else:
            st.info("Complete setup to access features")
        
        st.markdown("---")
        st.caption("Data Explorer v1.0.0")


def page_setup():
    """Setup page for first-time configuration."""
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
        st.success(f"✓ Directory found")
    
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
                status_text.text("✓ Initialization complete!")
                
                # Save to session state
                st.session_state.bids_root = bids_root
                st.session_state.dataset_name = dataset_name
                st.session_state.db = db
                st.session_state.bids_loader = bids_loader
                st.session_state.ps_client = ps_client
                st.session_state.setup_complete = True
                st.session_state.current_page = 'dashboard'
                
                st.success(f"✓ Successfully initialized dataset with {len(subjects)} subjects!")
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
    st.markdown('<h1 class="main-header">Subjects</h1>', 
                unsafe_allow_html=True)
    
    st.info("Subject browser coming in next commit...")


def page_downloads():
    """Download manager page."""
    st.markdown('<h1 class="main-header">Download Manager</h1>', 
                unsafe_allow_html=True)
    
    st.info("Download manager coming in Phase 3...")


def page_qc():
    """QC dashboard page."""
    st.markdown('<h1 class="main-header">Quality Control Dashboard</h1>', 
                unsafe_allow_html=True)
    
    st.info("QC dashboard coming in Phase 4...")


def page_export():
    """Export page."""
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
