"""
BIDSHub - Main Streamlit Application

A professional BIDS dataset management tool for neuroimaging data.
Multi-platform support: Local, Pennsieve, OpenNeuro, XNAT, DANDI, HPC, Remote Server.
"""

import streamlit as st
import sys
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import local modules
from src.theme import apply_custom_theme
from src.database import Database
from src.pennsieve_agent import PennsieveAgent
from src.openneuro_agent import OpenNeuroAgent
from src.bidshub_version import __version__
from src.cache_manager import CacheManager

# Page modules extracted from this file (incremental de-monolithing — see views/).
from views.dashboard import page_dashboard
from views.home import page_home
from views.viewer import page_viewer
from views.export import page_export
from views.subjects import page_subjects, page_subject_detail
from views.transfer import page_transfer
from views.qc import page_qc
from views.datasets import page_manage_datasets
from views.downloads import page_downloads


# Page configuration
st.set_page_config(
    page_title="BIDSHub",
    page_icon="favicon.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom theme
apply_custom_theme()


def init_session_state():
    """Initialize Streamlit session state variables."""
    # No setup requirement - users can navigate freely
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'
    
    if 'bids_root' not in st.session_state:
        st.session_state.bids_root = None
    
    # Multi-dataset support (v1.5+)
    if 'datasets' not in st.session_state:
        st.session_state.datasets = []  # List of dataset dicts
    
    if 'active_dataset_id' not in st.session_state:
        st.session_state.active_dataset_id = None  # For filtering
    
    # Backwards compatibility
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
    
    if 'platform' not in st.session_state:
        st.session_state.platform = 'pennsieve'
    
    if 'pennsieve_agent' not in st.session_state:
        try:
            st.session_state.pennsieve_agent = PennsieveAgent()
        except RuntimeError:
            st.session_state.pennsieve_agent = None
    
    if 'openneuro_agent' not in st.session_state:
        try:
            st.session_state.openneuro_agent = OpenNeuroAgent()
        except RuntimeError:
            st.session_state.openneuro_agent = None
    
    if 'ux_dismiss_xnat_beta' not in st.session_state:
        st.session_state.ux_dismiss_xnat_beta = False


def render_sidebar():
    """Render navigation sidebar (hidden on home/landing page)."""
    # Hide sidebar on home/landing page for clean entry point
    if st.session_state.current_page == 'home':
        return
    
    with st.sidebar:
        st.markdown('<h1 style="color: #002d72;">BIDSHub</h1>', 
                   unsafe_allow_html=True)
        
        if st.session_state.dataset_name:
            platform_name = st.session_state.platform.title()
            st.caption(f"**Platform:** {platform_name}")
            st.caption(f"**Dataset:** {st.session_state.dataset_name}")
        
        st.markdown("---")
        
        # Navigation - always visible (no setup requirement)
        st.markdown("### Navigation")
        
        # Get current page for highlighting
        current = st.session_state.current_page
        
        # Home (Landing Page)
        home_label = "> Home" if current == 'home' else "Home"
        if st.button(home_label, 
                    width='stretch',
                    key="nav_home"):
            st.session_state.current_page = 'home'
            st.rerun()
        
        # Manage Datasets (v1.5+) - Moved to top for easy access
        datasets_label = "> Manage Datasets" if current == 'manage_datasets' else "Manage Datasets"
        if st.button(datasets_label,
                    width='stretch',
                    key="nav_manage_datasets"):
            st.session_state.current_page = 'manage_datasets'
            st.rerun()
        
        st.markdown("---")
        
        # Browse Subjects
        subjects_label = "> Browse Subjects" if current in ['subjects', 'subject_detail'] else "Browse Subjects"
        if st.button(subjects_label, 
                    width='stretch',
                    key="nav_subjects"):
            st.session_state.current_page = 'subjects'
            st.rerun()
        
        # Viewer
        viewer_label = "> Viewer" if current == 'viewer' else "Viewer"
        if st.button(viewer_label, 
                    width='stretch',
                    key="nav_viewer"):
            st.session_state.current_page = 'viewer'
            st.rerun()
        
        # QC Dashboard
        qc_label = "> QC Dashboard" if current == 'qc' else "QC Dashboard"
        if st.button(qc_label, 
                    width='stretch',
                    key="nav_qc"):
            st.session_state.current_page = 'qc'
            st.rerun()
        
        st.markdown("---")
        
        # Download Manager
        downloads_label = "> Download Manager" if current == 'downloads' else "Download Manager"
        if st.button(downloads_label, 
                    width='stretch',
                    key="nav_downloads"):
            st.session_state.current_page = 'downloads'
            st.rerun()
        
        # Data Transfer (v3.1.1+)
        transfer_label = "> Data Transfer" if current == 'transfer' else "Data Transfer"
        if st.button(transfer_label, 
                    width='stretch',
                    key="nav_transfer"):
            st.session_state.current_page = 'transfer'
            st.rerun()
        
        # Export
        export_label = "> Export" if current == 'export' else "Export"
        if st.button(export_label, 
                    width='stretch',
                    key="nav_export"):
            st.session_state.current_page = 'export'
            st.rerun()
        
        st.markdown("---")
        st.caption(f"BIDSHub v{__version__}")


def format_update_banner(info: dict, current: str) -> str:
    """Markdown for the 'newer release available' banner. Pure / unit-testable."""
    return (
        f"**BIDSHub {info['version']} is available** — you have v{current}. "
        f"[Download the latest release]({info['url']}) and reinstall; "
        f"your data is preserved."
    )


@st.cache_data(ttl=3600, show_spinner=False)
def _check_latest_release():
    """Cached, network-safe check for a newer release. Returns dict or None.

    Cached for an hour so reruns don't re-hit the GitHub API; any
    network/import error yields None (no banner).
    """
    try:
        from desktop.updates import check_for_update
        return check_for_update()
    except Exception:
        return None


def render_update_banner():
    """Dismissible 'update available' banner — desktop (frozen) builds only.

    Source/Docker deployments update via ``git pull``/rebuild, so the
    "download a new installer" advice only applies to the packaged app.
    """
    if not getattr(sys, "frozen", False):
        return
    if st.session_state.get("update_banner_dismissed"):
        return
    info = _check_latest_release()
    if not info:
        return
    col_msg, col_x = st.columns([0.9, 0.1])
    with col_msg:
        st.info(format_update_banner(info, __version__), icon="⬆️")
    with col_x:
        if st.button("Dismiss", key="dismiss_update_banner"):
            st.session_state.update_banner_dismissed = True
            st.rerun()


def main():
    """Main application entry point."""
    # Initialize session state
    init_session_state()
    
    # Auto-initialize database (v3.1.1+)
    if st.session_state.db is None:
        st.session_state.db = Database()
        print("[OK] Database initialized automatically")
    
    # Initialize cache manager (v3.1.1+)
    if 'cache_manager' not in st.session_state:
        st.session_state.cache_manager = CacheManager()
    
    # Initialize pagination settings (v3.1.1+)
    if 'subjects_per_page' not in st.session_state:
        st.session_state.subjects_per_page = 25
    if 'current_page_num' not in st.session_state:
        st.session_state.current_page_num = 1
    
    # Render sidebar
    render_sidebar()

    # Notify (desktop builds) when a newer release is available
    render_update_banner()

    # Route to appropriate page
    page = st.session_state.current_page
    
    if page == 'home':
        page_home()
    elif page == 'dashboard':
        page_dashboard()
    elif page == 'manage_datasets':
        page_manage_datasets()
    elif page == 'subjects':
        page_subjects()
    elif page == 'subject_detail':
        page_subject_detail()
    elif page == 'downloads':
        page_downloads()
    elif page == 'transfer':
        page_transfer()
    elif page == 'qc':
        page_qc()
    elif page == 'export':
        page_export()
    elif page == 'viewer':
        page_viewer()
    else:
        page_home()


if __name__ == "__main__":
    main()
