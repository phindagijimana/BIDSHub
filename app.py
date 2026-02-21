"""
Data Explorer - Main Streamlit Application

A professional BIDS dataset management tool with Pennsieve integration.
"""

import streamlit as st
import os
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import local modules
from src.theme import apply_custom_theme, Theme, render_status_badge, format_file_size
from src.database import Database
from src.bids_loader import BIDSLoader
from src.pennsieve_client import PennsieveClient
from src.pennsieve_agent import PennsieveAgent, check_available_space
from src.openneuro_agent import OpenNeuroAgent, check_openneuro_connection
from src.automated_qc import AutomatedQC
from src.metadata_filter import MetadataFilter


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


def execute_downloads(download_manager, database):
    """Execute queued downloads routing to correct agent per dataset (v1.5+ multi-dataset)."""
    
    queue_items = download_manager.get_queue_items(status='queued')
    
    if not queue_items:
        st.info("No items queued for download")
        return
    
    # Group items by dataset and platform
    datasets_cache = {}
    pennsieve_groups = {}  # dataset_id -> items
    openneuro_groups = {}  # dataset_id -> items
    
    for item in queue_items:
        dataset_id = item.get('dataset_id')
        
        # Get dataset info (cache to avoid repeated queries)
        if dataset_id not in datasets_cache:
            dataset = database.get_dataset(dataset_id)
            if not dataset:
                st.error(f"Dataset ID {dataset_id} not found. Skipping item.")
                continue
            datasets_cache[dataset_id] = dataset
        
        dataset = datasets_cache[dataset_id]
        
        # Group by platform
        if dataset['platform'] == 'pennsieve':
            if dataset_id not in pennsieve_groups:
                pennsieve_groups[dataset_id] = []
            pennsieve_groups[dataset_id].append(item)
        else:
            if dataset_id not in openneuro_groups:
                openneuro_groups[dataset_id] = []
            openneuro_groups[dataset_id].append(item)
    
    # Execute downloads per platform
    if pennsieve_groups:
        for dataset_id, items in pennsieve_groups.items():
            dataset = datasets_cache[dataset_id]
            st.info(f"Downloading from Pennsieve: {dataset['name']}")
            execute_pennsieve_downloads_multi(items, dataset, database)
    
    if openneuro_groups:
        for dataset_id, items in openneuro_groups.items():
            dataset = datasets_cache[dataset_id]
            st.info(f"Downloading from OpenNeuro: {dataset['name']}")
            execute_openneuro_downloads_multi(items, dataset, database)


def execute_pennsieve_downloads_multi(queue_items, dataset_config, database):
    """Execute downloads using Pennsieve Agent for specific dataset (v1.5+ multi-dataset)."""
    import time
    from src.utils import format_file_size
    
    # Get credentials from dataset config
    api_key = dataset_config.get('api_key_encrypted') or os.getenv('PENNSIEVE_API_KEY')
    api_secret = dataset_config.get('api_secret_encrypted') or os.getenv('PENNSIEVE_API_SECRET')
    
    if not api_key or not api_secret:
        st.error(f"❌ Pennsieve credentials not configured for dataset '{dataset_config['name']}'")
        return
    
    agent = st.session_state.pennsieve_agent
    if not agent:
        st.error("❌ Pennsieve Agent not available. Install with: pip install pennsieve")
        return
    
    if not queue_items:
        st.info("No items queued for download")
        return
    
    # Create enhanced progress container
    progress_container = st.container()
    
    with progress_container:
        progress_bar = st.progress(0)
        status_col1, status_col2, status_col3 = st.columns(3)
        status_text = st.empty()
        details_expander = st.expander("📊 Download Details", expanded=False)
    
    total = len(queue_items)
    successful = 0
    failed = 0
    start_time = time.time()
    total_bytes = sum(item.get('file_size_bytes', 0) for item in queue_items)
    downloaded_bytes = 0
    
    # Track download log
    download_log = []
    
    for i, item in enumerate(queue_items):
        file_path = item['file_path']
        file_name = Path(file_path).name
        file_size = item.get('file_size_bytes', 0)
        
        # Update status
        database.execute_query(
            "UPDATE download_queue SET status = 'downloading', started_date = ? WHERE id = ?",
            (datetime.now(), item['id'])
        )
        
        item_start_time = time.time()
        
        # Update status display with ETA
        elapsed = time.time() - start_time
        if i > 0 and elapsed > 0:
            avg_time_per_file = elapsed / i
            remaining_files = total - i
            eta_seconds = avg_time_per_file * remaining_files
            eta_str = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
        else:
            eta_str = "Calculating..."
        
        status_text.markdown(f"""
        **Downloading {i+1}/{total}**: `{file_name}`  
        **Progress**: {(i/total)*100:.1f}% | **ETA**: {eta_str}
        """)
        
        with status_col1:
            st.metric("Files", f"{i}/{total}")
        with status_col2:
            st.metric("Success", successful, delta="+1" if i > 0 and successful > 0 else None)
        with status_col3:
            st.metric("Failed", failed, delta="+1" if i > 0 and failed > 0 else None, delta_color="inverse")
        
        # Progress callback for individual file
        def progress_callback(pct, msg):
            if pct is not None:
                overall_pct = ((i + pct/100) / total)
                progress_bar.progress(min(overall_pct, 0.99))  # Cap at 99% until complete
        
        # Download file using Pennsieve Agent with retry
        max_retries = 3
        success = False
        error_msg = None
        
        for attempt in range(max_retries):
            try:
                success = agent.pull_file(file_path, api_key, api_secret, progress_callback)
                if success:
                    break
                else:
                    error_msg = f"Download failed (attempt {attempt+1}/{max_retries})"
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        
        item_elapsed = time.time() - item_start_time
        
        if success:
            successful += 1
            downloaded_bytes += file_size
            
            # Calculate speed
            speed_mbps = (file_size / (1024 * 1024)) / item_elapsed if item_elapsed > 0 else 0
            
            database.execute_query(
                "UPDATE download_queue SET status = 'completed', completed_date = ? WHERE id = ?",
                (datetime.now(), item['id'])
            )
            # Update scan as downloaded
            database.execute_query(
                "UPDATE scans SET is_downloaded = 1, download_date = ? WHERE file_path = ?",
                (datetime.now(), file_path)
            )
            
            download_log.append({
                'file': file_name,
                'status': '✓ Success',
                'size': format_file_size(file_size),
                'time': f"{item_elapsed:.1f}s",
                'speed': f"{speed_mbps:.2f} MB/s" if speed_mbps > 0 else "N/A"
            })
        else:
            failed += 1
            database.execute_query(
                "UPDATE download_queue SET status = 'failed', error_message = ? WHERE id = ?",
                (error_msg or "Download failed", item['id'])
            )
            
            download_log.append({
                'file': file_name,
                'status': '✗ Failed',
                'size': format_file_size(file_size),
                'time': f"{item_elapsed:.1f}s",
                'speed': error_msg or "Failed"
            })
        
        # Update overall progress
        progress_bar.progress(min((i + 1) / total, 0.99))
        
        # Update details
        with details_expander:
            if download_log:
                log_df = pd.DataFrame(download_log)
                st.dataframe(log_df, use_container_width=True, hide_index=True)
    
    # Complete at 100%
    progress_bar.progress(1.0)
    
    # Final statistics
    total_elapsed = time.time() - start_time
    avg_speed = (downloaded_bytes / (1024 * 1024)) / total_elapsed if total_elapsed > 0 else 0
    
    status_text.empty()
    
    if successful > 0:
        st.success(f"""
        ✓ **Download Complete!**  
        **Success**: {successful}/{total} files ({(successful/total)*100:.1f}%)  
        **Total Size**: {format_file_size(downloaded_bytes)}  
        **Time**: {int(total_elapsed // 60)}m {int(total_elapsed % 60)}s  
        **Avg Speed**: {avg_speed:.2f} MB/s
        """)
    if failed > 0:
        st.error(f"✗ {failed} files failed to download. Check the download log for details.")
    
    # Save download session to history
    database.execute_query("""
        INSERT INTO metadata (key, value) 
        VALUES (?, ?)
    """, (
        f"download_session_{int(time.time())}",
        json.dumps({
            'timestamp': datetime.now().isoformat(),
            'platform': 'pennsieve',
            'total': total,
            'successful': successful,
            'failed': failed,
            'duration': total_elapsed,
            'avg_speed_mbps': avg_speed
        })
    ))
    
    time.sleep(2)  # Brief pause to show results
    st.rerun()


def execute_openneuro_downloads_multi(queue_items, dataset_config, database):
    """Execute downloads using OpenNeuro Agent for specific dataset (v1.5+ multi-dataset)."""
    import time
    from src.utils import format_file_size
    
    agent = st.session_state.openneuro_agent
    if not agent:
        st.error("❌ OpenNeuro Agent not available. Install with: pip install openneuro-py")
        return
    
    dataset_id = dataset_config['dataset_id_external']
    target_dir = dataset_config.get('root_path') or st.session_state.bids_root
    
    if not queue_items:
        st.info("No items queued for download")
        return
    
    # Group by subject for efficient downloading
    subjects_to_download = {}
    for item in queue_items:
        subject_id = item['subject_id']
        if subject_id not in subjects_to_download:
            subjects_to_download[subject_id] = []
        subjects_to_download[subject_id].append(item)
    
    # Create enhanced progress container
    progress_container = st.container()
    
    with progress_container:
        progress_bar = st.progress(0)
        status_col1, status_col2, status_col3 = st.columns(3)
        status_text = st.empty()
        details_expander = st.expander("📊 Download Details", expanded=False)
    
    total_subjects = len(subjects_to_download)
    total_files = len(queue_items)
    successful = 0
    failed = 0
    start_time = time.time()
    
    download_log = []
    
    # Download each subject
    for i, (subject_id, items) in enumerate(subjects_to_download.items()):
        # Calculate ETA
        elapsed = time.time() - start_time
        if i > 0 and elapsed > 0:
            avg_time_per_subject = elapsed / i
            remaining_subjects = total_subjects - i
            eta_seconds = avg_time_per_subject * remaining_subjects
            eta_str = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
        else:
            eta_str = "Calculating..."
        
        status_text.markdown(f"""
        **Downloading subject {i+1}/{total_subjects}**: `{subject_id}`  
        **Files**: {len(items)} | **Progress**: {(i/total_subjects)*100:.1f}% | **ETA**: {eta_str}
        """)
        
        with status_col1:
            st.metric("Subjects", f"{i}/{total_subjects}")
        with status_col2:
            st.metric("Success", successful, delta="+1" if i > 0 and successful > 0 else None)
        with status_col3:
            st.metric("Failed", failed, delta="+1" if i > 0 and failed > 0 else None, delta_color="inverse")
        
        # Mark items as downloading
        for item in items:
            database.execute_query(
                "UPDATE download_queue SET status = 'downloading', started_date = ? WHERE id = ?",
                (datetime.now(), item['id'])
            )
        
        subject_start_time = time.time()
        
        # Progress callback
        current_msg = ""
        def progress_callback(msg):
            nonlocal current_msg
            current_msg = msg
            status_text.markdown(f"""
            **Subject {i+1}/{total_subjects}**: `{subject_id}`  
            **Status**: {msg} | **ETA**: {eta_str}
            """)
        
        # Download subject using OpenNeuro agent with retry
        max_retries = 3
        success = False
        error_msg = None
        
        for attempt in range(max_retries):
            try:
                success = agent.download_subject(
                    dataset_id=dataset_id,
                    subject_id=subject_id,
                    target_dir=target_dir,
                    progress_callback=progress_callback
                )
                if success:
                    break
                else:
                    error_msg = f"Download failed (attempt {attempt+1}/{max_retries})"
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        
        subject_elapsed = time.time() - subject_start_time
        
        if success:
            successful += 1
            # Mark all items for this subject as completed
            for item in items:
                database.execute_query(
                    "UPDATE download_queue SET status = 'completed', completed_date = ? WHERE id = ?",
                    (datetime.now(), item['id'])
                )
                # Update scan as downloaded
                database.execute_query(
                    "UPDATE scans SET is_downloaded = 1, download_date = ? WHERE file_path = ?",
                    (datetime.now(), item['file_path'])
                )
            
            download_log.append({
                'subject': subject_id,
                'status': '✓ Success',
                'files': len(items),
                'time': f"{subject_elapsed:.1f}s"
            })
        else:
            failed += 1
            # Mark items as failed
            for item in items:
                database.execute_query(
                    "UPDATE download_queue SET status = 'failed', error_message = ? WHERE id = ?",
                    (error_msg or "Download failed", item['id'])
                )
            
            download_log.append({
                'subject': subject_id,
                'status': '✗ Failed',
                'files': len(items),
                'time': error_msg or "Failed"
            })
        
        # Update progress
        progress_bar.progress(min((i + 1) / total_subjects, 0.99))
        
        # Update details
        with details_expander:
            if download_log:
                log_df = pd.DataFrame(download_log)
                st.dataframe(log_df, use_container_width=True, hide_index=True)
    
    # Complete at 100%
    progress_bar.progress(1.0)
    
    # Final statistics
    total_elapsed = time.time() - start_time
    
    status_text.empty()
    
    if successful > 0:
        st.success(f"""
        ✓ **Download Complete!**  
        **Subjects**: {successful}/{total_subjects} ({(successful/total_subjects)*100:.1f}%)  
        **Total Files**: {total_files}  
        **Time**: {int(total_elapsed // 60)}m {int(total_elapsed % 60)}s  
        **Avg Time/Subject**: {total_elapsed/successful:.1f}s
        """)
    if failed > 0:
        st.error(f"✗ {failed} subjects failed to download. Check the download log for details.")
    
    # Save download session to history
    database.execute_query("""
        INSERT INTO metadata (key, value) 
        VALUES (?, ?)
    """, (
        f"download_session_{int(time.time())}",
        json.dumps({
            'timestamp': datetime.now().isoformat(),
            'platform': 'openneuro',
            'total_subjects': total_subjects,
            'total_files': total_files,
            'successful': successful,
            'failed': failed,
            'duration': total_elapsed
        })
    ))
    
    time.sleep(2)
    st.rerun()


def execute_uploads(file_paths: List[str], dataset_name: str, remote_path: str, 
                    overwrite: bool = False, verify_checksums: bool = True):
    """Execute file uploads to Pennsieve using Agent with enhanced tracking."""
    import time
    from src.utils import format_file_size
    
    # Get API credentials from env
    api_key = os.getenv('PENNSIEVE_API_KEY')
    api_secret = os.getenv('PENNSIEVE_API_SECRET')
    
    if not api_key or not api_secret:
        st.error("❌ Pennsieve credentials not configured")
        return
    
    agent = st.session_state.pennsieve_agent
    if not agent:
        st.error("❌ Pennsieve Agent not available")
        return
    
    # Filter out non-existent files
    valid_paths = [p for p in file_paths if Path(p).exists()]
    if len(valid_paths) < len(file_paths):
        st.warning(f"⚠️ Skipping {len(file_paths) - len(valid_paths)} non-existent files")
    
    if not valid_paths:
        st.error("No valid files to upload")
        return
    
    # Calculate total size
    total_size = sum(Path(p).stat().st_size for p in valid_paths)
    
    # Create enhanced progress container
    progress_container = st.container()
    
    with progress_container:
        progress_bar = st.progress(0)
        status_col1, status_col2, status_col3 = st.columns(3)
        status_text = st.empty()
        details_expander = st.expander("📊 Upload Details", expanded=False)
    
    total = len(valid_paths)
    uploaded_bytes = 0
    upload_log = []
    start_time = time.time()
    
    def batch_progress_callback(completed, total_files, current_file):
        # Calculate progress
        progress_pct = completed / total_files
        progress_bar.progress(min(progress_pct, 0.99))
        
        # Calculate ETA
        elapsed = time.time() - start_time
        if completed > 0 and elapsed > 0:
            avg_time_per_file = elapsed / completed
            remaining_files = total_files - completed
            eta_seconds = avg_time_per_file * remaining_files
            eta_str = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
        else:
            eta_str = "Calculating..."
        
        # Calculate speed
        if elapsed > 0:
            speed_mbps = (uploaded_bytes / (1024 * 1024)) / elapsed
        else:
            speed_mbps = 0
        
        status_text.markdown(f"""
        **Uploading {completed}/{total_files}**: `{Path(current_file).name}`  
        **Progress**: {progress_pct*100:.1f}% | **Speed**: {speed_mbps:.2f} MB/s | **ETA**: {eta_str}
        """)
        
        with status_col1:
            st.metric("Files", f"{completed}/{total_files}")
        with status_col2:
            st.metric("Uploaded", format_file_size(uploaded_bytes))
        with status_col3:
            st.metric("Speed", f"{speed_mbps:.2f} MB/s")
    
    # Execute batch upload
    results = agent.batch_upload(
        valid_paths,
        dataset_name,
        remote_path,
        api_key,
        api_secret,
        batch_progress_callback
    )
    
    # Complete at 100%
    progress_bar.progress(1.0)
    
    # Calculate final statistics
    total_elapsed = time.time() - start_time
    successful_size = sum(Path(p).stat().st_size for p in valid_paths if p not in results.get('errors', []))
    avg_speed = (successful_size / (1024 * 1024)) / total_elapsed if total_elapsed > 0 else 0
    
    # Build upload log
    for i, file_path in enumerate(valid_paths):
        file_name = Path(file_path).name
        file_size = Path(file_path).stat().st_size
        
        if file_path in results.get('errors', []):
            upload_log.append({
                'file': file_name,
                'status': '✗ Failed',
                'size': format_file_size(file_size),
                'error': results.get('error_messages', {}).get(file_path, 'Unknown error')
            })
        else:
            upload_log.append({
                'file': file_name,
                'status': '✓ Success',
                'size': format_file_size(file_size),
                'error': '—'
            })
            uploaded_bytes += file_size
    
    # Display upload log
    with details_expander:
        if upload_log:
            log_df = pd.DataFrame(upload_log)
            st.dataframe(log_df, use_container_width=True, hide_index=True)
    
    # Final status
    status_text.empty()
    
    if results['successful'] > 0:
        st.success(f"""
        ✓ **Upload Complete!**  
        **Success**: {results['successful']}/{total} files ({(results['successful']/total)*100:.1f}%)  
        **Total Size**: {format_file_size(successful_size)}  
        **Time**: {int(total_elapsed // 60)}m {int(total_elapsed % 60)}s  
        **Avg Speed**: {avg_speed:.2f} MB/s  
        **Destination**: `{remote_path}`
        """)
    if results['failed'] > 0:
        st.error(f"✗ {results['failed']} files failed to upload")
        with st.expander("❌ View Failed Files"):
            for error_file in results['errors']:
                error_msg = results.get('error_messages', {}).get(error_file, 'Unknown error')
                st.text(f"• {Path(error_file).name}: {error_msg}")
    
    # Save upload session to database
    if 'db' in st.session_state and st.session_state.db:
        st.session_state.db.execute_query("""
            INSERT INTO metadata (key, value) 
            VALUES (?, ?)
        """, (
            f"upload_session_{int(time.time())}",
            json.dumps({
                'timestamp': datetime.now().isoformat(),
                'platform': 'pennsieve',
                'total': total,
                'successful': results['successful'],
                'failed': results['failed'],
                'duration': total_elapsed,
                'size_bytes': successful_size,
                'avg_speed_mbps': avg_speed,
                'remote_path': remote_path
            })
        ))
    
    time.sleep(2)


def render_page_header(current_page: str, show_back_to_dashboard: bool = False):
    """Render page header with optional back button."""
    if show_back_to_dashboard and current_page != 'dashboard':
        col1, col2 = st.columns([5, 1])
        with col2:
            if st.button("⌂ Dashboard", use_container_width=True, key=f"back_dash_{current_page}"):
                st.session_state.current_page = 'dashboard'
                st.rerun()


def render_breadcrumb(current_page: str, parent_page: str = None):
    """Render breadcrumb navigation at top of page - only for nested pages."""
    # Only show breadcrumb for nested pages (like subject detail)
    # Top-level pages use sidebar for navigation
    if current_page not in ['subject_detail']:
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
    
    # Simple text breadcrumb for context
    st.caption(f"Home / {page_names.get(parent_page, 'Subjects')} / {page_names.get(current_page, current_page)}")


def render_sidebar():
    """Render navigation sidebar."""
    with st.sidebar:
        st.markdown('<h1 style="color: #002d72;">Data Explorer</h1>', 
                   unsafe_allow_html=True)
        
        if st.session_state.dataset_name:
            platform_emoji = "🔐" if st.session_state.platform == 'pennsieve' else "🌍"
            platform_name = st.session_state.platform.title()
            st.caption(f"**Platform:** {platform_emoji} {platform_name}")
            st.caption(f"**Dataset:** {st.session_state.dataset_name}")
        
        st.markdown("---")
        
        if st.session_state.setup_complete:
            st.markdown("### Navigation")
            st.caption("Use buttons below to navigate between pages")
            
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
            
            # Manage Datasets (v1.5+)
            datasets_label = "▶ Manage Datasets" if current == 'manage_datasets' else "📚 Manage Datasets"
            if st.button(datasets_label,
                        use_container_width=True,
                        key="nav_manage_datasets"):
                st.session_state.current_page = 'manage_datasets'
                st.rerun()
            
            # Settings
            settings_label = "▶ Settings" if current == 'setup' else "⚙️ Settings"
            if st.button(settings_label, 
                        use_container_width=True,
                        key="nav_settings"):
                st.session_state.current_page = 'setup'
                st.rerun()
            
            st.markdown("---")
            st.caption("Current page: " + current)
        
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
    Welcome to Data Explorer! Configure your BIDS dataset and cloud platform connection.
    """)
    
    # Platform Selection
    st.markdown('<h2 class="section-header">Platform Selection</h2>', 
                unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        platform = st.radio(
            "Choose data platform",
            options=['pennsieve', 'openneuro'],
            format_func=lambda x: {
                'pennsieve': '🔐 Pennsieve (Private datasets, upload support)',
                'openneuro': '🌍 OpenNeuro (Public datasets, read-only)'
            }[x],
            key="platform_selection",
            index=0 if st.session_state.platform == 'pennsieve' else 1
        )
        
        st.session_state.platform = platform
    
    with col2:
        if platform == 'pennsieve':
            st.info("**Pennsieve**: Private research datasets with upload/download")
        else:
            st.info("**OpenNeuro**: 1000+ public BIDS datasets, free downloads")
    
    st.markdown("---")
    
    st.markdown('<h2 class="section-header">BIDS Dataset Configuration</h2>', 
                unsafe_allow_html=True)
    
    # Data source mode
    col1, col2 = st.columns(2)
    with col1:
        data_mode = st.radio(
            "Data location",
            options=['cloud_only', 'local'],
            format_func=lambda x: {
                'cloud_only': '☁️ Cloud only (browse & download remotely)',
                'local': '💻 Local (BIDS data already on disk)'
            }[x],
            key="data_mode",
            index=0
        )
    
    with col2:
        if data_mode == 'cloud_only':
            st.info("No local data needed - browse cloud datasets directly")
        else:
            st.info("Use existing local BIDS dataset")
    
    # BIDS directory input (optional for cloud_only)
    if data_mode == 'local':
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
    else:
        # Cloud-only mode: create temp directory for stubs
        bids_root = st.text_input(
            "Local Working Directory (optional)",
            value=st.session_state.bids_root or str(Path.home() / "data-explorer" / "datasets"),
            placeholder=str(Path.home() / "data-explorer" / "datasets"),
            help="Directory for downloaded files (will be created if needed)"
        )
    
    # Platform-specific configuration
    if st.session_state.platform == 'pennsieve':
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
        
        # Validation for Pennsieve
        config_valid = bool(bids_root and dataset_name and api_key and api_secret)
    
    else:  # OpenNeuro
        st.markdown('<h2 class="section-header">OpenNeuro Configuration</h2>', 
                    unsafe_allow_html=True)
        
        # OpenNeuro dataset ID
        dataset_name = st.text_input(
            "OpenNeuro Dataset ID",
            value=st.session_state.dataset_name or "",
            placeholder="ds000246",
            help="Dataset ID from OpenNeuro (e.g., ds000246)"
        )
        
        st.caption("Browse datasets at [openneuro.org](https://openneuro.org)")
        
        # Optional API token for private datasets
        api_key = st.text_input(
            "API Token (optional)",
            type="password",
            help="Only needed for private datasets. Get from openneuro.org/keygen"
        )
        
        api_secret = None  # OpenNeuro doesn't use secret
        
        # Validation for OpenNeuro
        config_valid = bool(bids_root and dataset_name)
    
    st.markdown("---")
    
    # Initialize button
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        initialize_button = st.button(
            "Initialize Dataset",
            type="primary",
            use_container_width=True,
            disabled=not config_valid
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
                
                data_mode = st.session_state.get('data_mode', 'cloud_only')
                
                # Step 1: Prepare working directory
                status_text.text("1/5 Preparing working directory...")
                progress_bar.progress(20)
                
                if data_mode == 'local':
                    # Local mode: verify existing directory
                    if not Path(bids_root).exists():
                        st.error("BIDS directory not found!")
                        return
                else:
                    # Cloud-only mode: create working directory
                    Path(bids_root).mkdir(parents=True, exist_ok=True)
                    status_text.text("1/5 Created working directory")
                
                # Step 2: Connect to platform
                ps_client = None
                
                if st.session_state.platform == 'pennsieve':
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
                
                else:  # OpenNeuro
                    status_text.text("2/5 Verifying OpenNeuro connection...")
                    progress_bar.progress(40)
                    
                    if not check_openneuro_connection():
                        st.warning("Cannot reach OpenNeuro - check internet connection")
                    
                    # OpenNeuro agent will be used for downloads (no pre-connection needed)
                    ps_client = None
                
                # Step 3: Get dataset structure
                status_text.text("3/5 Getting dataset structure...")
                progress_bar.progress(60)
                
                db = Database()
                bids_loader = None
                remote_structure = None
                
                if data_mode == 'local':
                    # Load from local BIDS
                    bids_loader = BIDSLoader(bids_root, validate=False)
                    subjects_list = bids_loader.get_subjects()
                else:
                    # Get structure from cloud
                    if st.session_state.platform == 'pennsieve':
                        agent = st.session_state.pennsieve_agent
                        if agent:
                            remote_structure = agent.get_remote_dataset_structure(
                                dataset_name, api_key, api_secret
                            )
                            subjects_list = remote_structure.get('subjects', [])
                        else:
                            st.error("Pennsieve Agent not available")
                            return
                    else:  # OpenNeuro
                        agent = st.session_state.openneuro_agent
                        if agent:
                            remote_structure = agent.get_remote_dataset_structure(dataset_name)
                            subjects_list = remote_structure.get('subjects', [])
                            
                            # Download participants.tsv for metadata
                            agent.download_participants_tsv(dataset_name, bids_root)
                        else:
                            st.error("OpenNeuro Agent not available")
                            return
                
                # Step 4: Initialize database
                status_text.text("4/5 Initializing database...")
                progress_bar.progress(80)
                
                # Step 5: Index subjects
                status_text.text("5/5 Indexing subjects...")
                progress_bar.progress(90)
                
                if data_mode == 'local' and bids_loader:
                    # Index from local BIDS
                    for subject in subjects_list:
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
                else:
                    # Index from remote structure
                    sessions_map = remote_structure.get('sessions', {}) if remote_structure else {}
                    
                    for subject in subjects_list:
                        subject_sessions = sessions_map.get(subject, [])
                        has_2wk = '2WK' in subject_sessions
                        has_6mo = '6MO' in subject_sessions
                        
                        db.add_subject(
                            subject_id=subject,
                            has_2wk=has_2wk,
                            has_6mo=has_6mo,
                            scan_count_2wk=0,  # Unknown until downloaded
                            scan_count_6mo=0   # Unknown until downloaded
                        )
                
                progress_bar.progress(100)
                status_text.text("Initialization complete!")
                
                # Save to session state
                st.session_state.bids_root = bids_root
                st.session_state.dataset_name = dataset_name
                st.session_state.db = db
                st.session_state.bids_loader = bids_loader
                st.session_state.ps_client = ps_client
                st.session_state.data_mode = data_mode
                st.session_state.setup_complete = True
                st.session_state.current_page = 'dashboard'
                
                mode_text = "cloud (browse remotely)" if data_mode == 'cloud_only' else "local"
                st.success(f"Successfully initialized dataset with {len(subjects_list)} subjects in {mode_text} mode!")
                st.balloons()
                
                # Auto-navigate to dashboard
                st.rerun()
                
            except Exception as e:
                st.error(f"Initialization failed: {e}")
                import traceback
                with st.expander("Error Details"):
                    st.code(traceback.format_exc())


def page_manage_datasets():
    """Dataset management page - add/edit/remove datasets (v1.5+)."""
    render_page_header('manage_datasets', show_back_to_dashboard=True)
    render_breadcrumb('manage_datasets')
    st.markdown('<h1 class="main-header">Manage Datasets</h1>', 
                unsafe_allow_html=True)
    
    if not st.session_state.db:
        st.error("Database not initialized. Please complete setup first.")
        return
    
    st.markdown("""
    Connect to multiple datasets from Pennsieve and/or OpenNeuro. Browse and download 
    subjects from all datasets in a unified interface.
    """)
    
    # Get all datasets
    datasets = st.session_state.db.get_all_datasets()
    
    # Display connected datasets
    st.markdown('<h2 class="section-header">Connected Datasets</h2>', 
                unsafe_allow_html=True)
    
    if not datasets:
        st.info("No datasets configured yet. Add your first dataset below.")
    else:
        for dataset in datasets:
            with st.expander(f"{'🔐' if dataset['platform'] == 'pennsieve' else '🌍'} {dataset['name']}", 
                           expanded=False):
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    # Count subjects for this dataset
                    subjects = st.session_state.db.get_subjects_by_dataset(dataset['id'])
                    st.metric("Subjects", len(subjects))
                
                with col2:
                    st.metric("Platform", dataset['platform'].title())
                
                with col3:
                    status_color = {"active": "🟢", "inactive": "🟡", "error": "🔴"}
                    st.metric("Status", f"{status_color.get(dataset['status'], '⚪')} {dataset['status'].title()}")
                
                with col4:
                    st.metric("Created", dataset['created_date'][:10] if dataset['created_date'] else "Unknown")
                
                # Dataset details
                st.markdown("**Details:**")
                st.text(f"ID: {dataset['id']}")
                if dataset['dataset_id_external']:
                    st.text(f"External ID: {dataset['dataset_id_external']}")
                if dataset['root_path']:
                    st.text(f"Local Path: {dataset['root_path']}")
                
                # Actions
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("🔄 Sync", key=f"sync_{dataset['id']}", 
                               use_container_width=True):
                        st.info("Sync feature coming soon!")
                
                with col2:
                    new_status = "inactive" if dataset['status'] == "active" else "active"
                    if st.button(f"{'⏸️ Deactivate' if dataset['status'] == 'active' else '▶️ Activate'}", 
                               key=f"toggle_{dataset['id']}", 
                               use_container_width=True):
                        st.session_state.db.update_dataset(dataset['id'], status=new_status)
                        st.success(f"Dataset {new_status}")
                        st.rerun()
                
                with col3:
                    if st.button("🗑️ Remove", key=f"remove_{dataset['id']}", 
                               use_container_width=True,
                               type="secondary"):
                        # Confirm deletion
                        if len(subjects) > 0:
                            st.warning(f"⚠️ This will delete {len(subjects)} subjects and all associated data!")
                            if st.button(f"Confirm Delete", key=f"confirm_delete_{dataset['id']}",
                                       type="primary"):
                                st.session_state.db.delete_dataset(dataset['id'])
                                st.success("Dataset removed")
                                st.rerun()
                        else:
                            st.session_state.db.delete_dataset(dataset['id'])
                            st.success("Dataset removed")
                            st.rerun()
    
    # Add new dataset section
    st.markdown("---")
    st.markdown('<h2 class="section-header">Add New Dataset</h2>', 
                unsafe_allow_html=True)
    
    if len(datasets) >= 5:
        st.warning("⚠️ Maximum of 5 datasets supported in v1.5.")
        return
    
    # Platform selection
    col1, col2 = st.columns(2)
    
    with col1:
        new_platform = st.radio(
            "Platform",
            options=['pennsieve', 'openneuro'],
            format_func=lambda x: {
                'pennsieve': '🔐 Pennsieve',
                'openneuro': '🌍 OpenNeuro'
            }[x],
            key="new_dataset_platform"
        )
    
    with col2:
        if new_platform == 'pennsieve':
            st.info("Private datasets with upload support")
        else:
            st.info("Public datasets, read-only")
    
    # Dataset configuration form
    with st.form("add_dataset_form"):
        dataset_name = st.text_input(
            "Dataset Name",
            placeholder="My Dataset",
            help="Unique name for this dataset"
        )
        
        col1, col2 = st.columns(2)
        
        if new_platform == 'pennsieve':
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
            
            external_id = st.text_input(
                "Pennsieve Dataset Name",
                placeholder="TrackTBI",
                help="Name of dataset on Pennsieve"
            )
        else:
            external_id = st.text_input(
                "OpenNeuro Dataset ID",
                placeholder="ds000246",
                help="Dataset ID from OpenNeuro (e.g., ds000246)"
            )
            
            api_key = st.text_input(
                "API Token (optional)",
                type="password",
                help="Only needed for private datasets"
            )
            
            api_secret = None
        
        root_path = st.text_input(
            "Local Working Directory",
            placeholder=str(Path.home() / "data-explorer" / "datasets" / dataset_name),
            help="Directory for downloaded files"
        )
        
        validate_bids = st.checkbox(
            "Validate BIDS compliance",
            value=True,
            help="Check if dataset follows BIDS specification"
        )
        
        submit = st.form_submit_button("➕ Add Dataset", type="primary", use_container_width=True)
        
        if submit:
            # Validate inputs
            if not dataset_name:
                st.error("Dataset name is required")
            elif not external_id:
                st.error(f"{'Pennsieve dataset name' if new_platform == 'pennsieve' else 'OpenNeuro dataset ID'} is required")
            elif new_platform == 'pennsieve' and (not api_key or not api_secret):
                st.error("Pennsieve credentials (API key and secret) are required")
            else:
                # Check if name already exists
                existing = [d for d in datasets if d['name'] == dataset_name]
                if existing:
                    st.error(f"Dataset name '{dataset_name}' already exists. Choose a different name.")
                else:
                    # Validate BIDS if requested and path exists
                    validation_passed = True
                    if validate_bids and root_path and Path(root_path).exists():
                        with st.spinner("Validating BIDS structure..."):
                            is_valid, validation_msg = validate_bids_dataset(root_path)
                            
                            if not is_valid:
                                st.warning("⚠️ BIDS Validation Issues:")
                                st.text(validation_msg)
                                
                                if st.checkbox("Add dataset anyway (not recommended)"):
                                    validation_passed = True
                                else:
                                    validation_passed = False
                                    st.error("❌ Please fix BIDS validation errors before adding dataset.")
                            else:
                                st.success("✅ BIDS validation passed!")
                    
                    if validation_passed:
                        # Add dataset to database
                        dataset_id = st.session_state.db.add_dataset(
                            name=dataset_name,
                            platform=new_platform,
                            api_key=api_key if api_key else None,
                            api_secret=api_secret if api_secret else None,
                            dataset_id_external=external_id,
                            root_path=root_path if root_path else None
                        )
                        
                        if dataset_id:
                            st.success(f"✓ Dataset '{dataset_name}' added successfully!")
                            st.info("Go to Setup page to initialize this dataset with subjects.")
                            st.rerun()
                        else:
                            st.error("Failed to add dataset. Check database connection.")


def page_dashboard():
    """Main dashboard page."""
    render_breadcrumb('dashboard')
    st.markdown('<h1 class="main-header">Data Explorer</h1>', 
                unsafe_allow_html=True)
    
    if not st.session_state.db:
        st.warning("Please complete setup to view the dashboard")
        st.info("Initialize your BIDS dataset and Pennsieve connection to get started.")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("Go to Settings", use_container_width=True):
                st.session_state.current_page = 'setup'
                st.rerun()
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
        
        selected_dataset_ids = st.multiselect(
            "Show subjects from:",
            options=[d['id'] for d in datasets],
            format_func=lambda x: next((f"{'🔐' if d['platform'] == 'pennsieve' else '🌍'} {d['name']}" 
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
    subjects = []
    if len(datasets) > 1 and selected_dataset_ids:
        for dataset_id in selected_dataset_ids:
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
    render_page_header('downloads', show_back_to_dashboard=True)
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
    
    # Initialize Metadata Filter (v1.5+ supports multi-dataset)
    if 'metadata_filter' not in st.session_state:
        datasets = st.session_state.db.get_all_datasets(status='active')
        if datasets and len(datasets) > 1:
            # Multi-dataset mode
            st.session_state.metadata_filter = MetadataFilter(datasets=datasets)
        else:
            # Single dataset mode (backwards compatibility)
            st.session_state.metadata_filter = MetadataFilter(st.session_state.bids_root)
    
    metadata_filter = st.session_state.metadata_filter
    
    # Metadata Filtering Section
    st.markdown('<h2 class="section-header">🎯 Filter by Metadata</h2>', 
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
        
        # Preview filtered results
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📊 Preview Filtered Results", use_container_width=True):
                filtered_ids = metadata_filter.filter_subjects(filter_criteria)
                summary = metadata_filter.get_filter_summary(filter_criteria)
                
                st.session_state.filtered_subject_ids = filtered_ids
                st.session_state.filter_active = True
                
                st.success(f"✓ {len(filtered_ids)} subjects match your criteria")
                
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
            if st.button("🗑️ Clear Filters", use_container_width=True):
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
            
            if filter_text:
                st.caption(f"**Active filters**: {' | '.join(filter_text)}")
    else:
        st.warning("No participants.tsv found - metadata filtering unavailable")
    
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
    
    # Check if filters are active
    filter_active = st.session_state.get('filter_active', False)
    filtered_ids = st.session_state.get('filtered_subject_ids', None)
    
    if filter_active and filtered_ids:
        st.caption(f"🎯 Filters active: {len(filtered_ids)} subjects selected")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        button_label = "Select Filtered Subjects" if filter_active else "Select All Subjects"
        if st.button(button_label, use_container_width=True):
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
                    
                    # Get scans for both sessions
                    for session in ['2WK', '6MO']:
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
                    st.success(f"Added {added_count} files{filter_msg} to queue (skipped {skipped_count} already queued)")
                    st.rerun()
                else:
                    st.info(f"No new files added ({skipped_count} already in queue)")
    
    with col2:
        button_label = "Select Complete (Filtered)" if filter_active else "Select Complete Only"
        if st.button(button_label, use_container_width=True):
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
                    
                    # Check if subject has both sessions
                    has_2wk = subject.get('has_2wk', False)
                    has_6mo = subject.get('has_6mo', False)
                    
                    if not (has_2wk and has_6mo):
                        incomplete_count += 1
                        continue
                    
                    # Add scans from both sessions
                    for session in ['2WK', '6MO']:
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
                    st.success(f"Added {added_count} files from {len(subjects) - incomplete_count} complete{filter_msg} subjects (skipped {skipped_count} already queued, {incomplete_count} incomplete)")
                    st.rerun()
                else:
                    st.info(f"No new files added ({skipped_count} already in queue, {incomplete_count} incomplete subjects)")
    
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
        st.info("No items in download queue. Add files from the subject browser or use Quick Select buttons above.")
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
            use_container_width=True,
            hide_index=True,
            height=300
        )
        
        # Individual item management
        with st.expander("🗑️ Manage Individual Items"):
            col1, col2 = st.columns(2)
            
            with col1:
                item_to_remove = st.selectbox(
                    "Select item to remove",
                    options=[f"{item['id']}: {Path(item['file_path']).name}" for item in queue_items],
                    key="item_to_remove"
                )
            
            with col2:
                if st.button("Remove Selected", use_container_width=True, key="remove_single_item"):
                    if item_to_remove:
                        item_id = int(item_to_remove.split(':')[0])
                        success = st.session_state.db.execute_query(
                            "DELETE FROM download_queue WHERE id = ?",
                            (item_id,)
                        )
                        if success:
                            st.success(f"Removed item {item_id}")
                            st.rerun()
            
            # Bulk actions by status
            st.markdown("**Bulk Actions**")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("Remove All Failed", use_container_width=True):
                    removed = st.session_state.db.execute_query(
                        "DELETE FROM download_queue WHERE status = 'failed'"
                    )
                    st.success(f"Removed all failed items")
                    st.rerun()
            
            with col2:
                if st.button("Remove All Completed", use_container_width=True):
                    removed = st.session_state.db.execute_query(
                        "DELETE FROM download_queue WHERE status = 'completed'"
                    )
                    st.success(f"Removed all completed items")
                    st.rerun()
            
            with col3:
                if st.button("Retry All Failed", use_container_width=True):
                    st.session_state.db.execute_query(
                        "UPDATE download_queue SET status = 'queued', error_message = NULL WHERE status = 'failed'"
                    )
                    st.success("Reset all failed items to queued")
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
                        use_container_width=True,
                        disabled=stats['queued'] == 0):
                # Execute actual downloads using Pennsieve Agent
                execute_downloads(dm, st.session_state.db)
        
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
    
    # Download History
    st.markdown("---")
    st.markdown('<h2 class="section-header">📜 Download & Upload History</h2>', 
                unsafe_allow_html=True)
    
    # Get recent sessions from metadata table
    if st.session_state.db:
        sessions = st.session_state.db.execute_query("""
            SELECT key, value, created_date 
            FROM metadata 
            WHERE key LIKE 'download_session_%' OR key LIKE 'upload_session_%'
            ORDER BY created_date DESC 
            LIMIT 20
        """)
        
        if sessions:
            history_data = []
            for session in sessions:
                try:
                    session_data = json.loads(session['value'])
                    session_type = 'Download' if 'download_session_' in session['key'] else 'Upload'
                    
                    history_data.append({
                        'Type': f"{'⬇️' if session_type == 'Download' else '⬆️'} {session_type}",
                        'Platform': session_data.get('platform', 'Unknown').title(),
                        'Timestamp': session_data.get('timestamp', session['created_date'])[:19],
                        'Success': session_data.get('successful', 0),
                        'Failed': session_data.get('failed', 0),
                        'Duration': f"{int(session_data.get('duration', 0) // 60)}m {int(session_data.get('duration', 0) % 60)}s",
                        'Avg Speed': f"{session_data.get('avg_speed_mbps', 0):.2f} MB/s" if session_data.get('avg_speed_mbps') else 'N/A'
                    })
                except:
                    pass
            
            if history_data:
                with st.expander("📊 View Recent Sessions", expanded=False):
                    history_df = pd.DataFrame(history_data)
                    st.dataframe(history_df, use_container_width=True, hide_index=True)
                    
                    if st.button("🗑️ Clear History", key="clear_history"):
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
    st.markdown('<h2 class="section-header">⚙️ Settings</h2>', 
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
        st.markdown('<h2 class="section-header">📤 Upload to Pennsieve</h2>', 
                    unsafe_allow_html=True)
        
        st.info("Upload processed/derived data back to Pennsieve dataset")
        
        # Upload mode selection
        upload_mode = st.radio(
            "Upload Mode",
            options=['files', 'directory'],
            format_func=lambda x: {
                'files': '📄 Individual Files (drag & drop)',
                'directory': '📁 Directory (select folder from local system)'
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
                    
                    with st.expander(f"📁 Preview: {len(files_in_dir)} files ({format_file_size(total_size)})"):
                        preview_df = pd.DataFrame([
                            {
                                'File': f.name,
                                'Size': format_file_size(f.stat().st_size),
                                'Path': str(f.relative_to(local_directory))
                            }
                            for f in files_in_dir[:50]  # Show first 50
                        ])
                        st.dataframe(preview_df, use_container_width=True, hide_index=True)
                        
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
            st.caption("⚡ Files will be uploaded to this path")
            
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
                f"📤 Upload {len(file_paths_to_upload) if file_paths_to_upload else 0} Files",
                type="primary",
                use_container_width=True,
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
        st.info("📖 **OpenNeuro is read-only**. Upload not supported. Use Pennsieve for private datasets with upload capabilities.")


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
    
    # QC Type Tabs
    tab1, tab2 = st.tabs(["📋 Manual QC", "🤖 Automated QC"])
    
    with tab1:
        render_manual_qc_tab(qc_mgr)
    
    with tab2:
        render_automated_qc_tab(auto_qc)


def render_manual_qc_tab(qc_mgr):
    """Render manual QC tab for human review."""
    
    # QC Overview
    st.markdown('<h2 class="section-header">Manual QC Overview</h2>', 
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
        if st.button("Run Automated QC", type="primary", use_container_width=True):
            subjects = st.session_state.db.get_all_subjects()
            subject_ids = [s['subject_id'] for s in subjects]
            
            if not subject_ids:
                st.warning("No subjects found")
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
                
                st.success(f"✓ Automated QC complete: {pass_count} pass, {warn_count} warnings, {fail_count} fail")
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
            except:
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
        st.dataframe(df_flagged, use_container_width=True, hide_index=True)
        
        # Allow user to view details
        selected_subject = st.selectbox(
            "Select subject to view details",
            options=[s['subject_id'] for s in flagged],
            key="auto_qc_selected_subject"
        )
        
        if st.button("View Details", use_container_width=True):
            st.session_state.selected_subject = selected_subject
            st.session_state.current_page = 'subject_detail'
            st.rerun()
    else:
        st.success("✓ No automated QC issues detected")
    
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
    """Export page with cohort export functionality."""
    render_page_header('export', show_back_to_dashboard=True)
    render_breadcrumb('export')
    st.markdown('<h1 class="main-header">Export Data</h1>', 
                unsafe_allow_html=True)
    
    if not st.session_state.db:
        st.warning("Please complete setup first")
        return
    
    # Create tabs for different export options
    tab1, tab2, tab3 = st.tabs(["📦 Export Custom Cohort", "📊 QC Results", "📋 Subject Lists"])
    
    with tab1:
        # Custom Cohort Export
        st.markdown('<h2 class="section-header">Export Custom Cohort as BIDS Dataset</h2>', 
                    unsafe_allow_html=True)
        
        st.info("Create a new BIDS-compliant dataset from selected subjects across multiple source datasets.")
        
        # Implementation of cohort export UI
        st.warning("Feature implementation in progress. Check ENHANCEMENTS_SUMMARY.md for details.")
    
    with tab2:
        # QC Results Export
        st.markdown('<h2 class="section-header">Quality Control Results</h2>', 
                    unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.write("Export QC status, notes, and review history for all subjects")
    
        with col2:
            if st.button("Export QC Results", use_container_width=True):
                # Get all subjects with QC data
                subjects = st.session_state.db.get_all_subjects()
                
                if not subjects:
                    st.warning("No subjects found")
                else:
                    export_data = []
                    for subject in subjects:
                        export_data.append({
                            'Subject ID': subject['subject_id'],
                            'QC Status': subject.get('qc_status', 'pending'),
                            'Flagged': 'Yes' if subject.get('flagged') else 'No',
                            'Has 2WK': 'Yes' if subject.get('has_2wk') else 'No',
                            'Has 6MO': 'Yes' if subject.get('has_6mo') else 'No',
                            'Scan Count 2WK': subject.get('scan_count_2wk', 0),
                            'Scan Count 6MO': subject.get('scan_count_6mo', 0),
                            'QC Notes': subject.get('qc_notes', ''),
                            'Reviewed By': subject.get('reviewed_by', ''),
                            'Review Date': subject.get('review_date', '')
                        })
                    
                    df = pd.DataFrame(export_data)
                    csv = df.to_csv(index=False)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"qc_results_{timestamp}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                    
                    st.success(f"Ready to download {len(export_data)} QC records")
    
    with tab3:
        # Subject List Export
        st.markdown('<h2 class="section-header">Subject Lists</h2>', 
                    unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**All Subjects**")
            if st.button("Export All", use_container_width=True, key="export_all"):
                subjects = st.session_state.db.get_all_subjects()
                
                if subjects:
                    export_data = []
                    for subject in subjects:
                        export_data.append({
                            'Subject ID': subject['subject_id'],
                            'Has 2WK': 'Yes' if subject.get('has_2wk') else 'No',
                            'Has 6MO': 'Yes' if subject.get('has_6mo') else 'No',
                            'Scan Count 2WK': subject.get('scan_count_2wk', 0),
                            'Scan Count 6MO': subject.get('scan_count_6mo', 0),
                            'QC Status': subject.get('qc_status', 'pending')
                        })
                    
                    df = pd.DataFrame(export_data)
                    csv = df.to_csv(index=False)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"all_subjects_{timestamp}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key="download_all"
                    )
        
        with col2:
            st.write("**Complete Subjects**")
            st.caption("Both 2WK and 6MO")
            if st.button("Export Complete", use_container_width=True, key="export_complete"):
                subjects = st.session_state.db.get_all_subjects()
                
                # Filter complete subjects
                complete_subjects = [s for s in subjects if s.get('has_2wk') and s.get('has_6mo')]
                
                if complete_subjects:
                    export_data = []
                    for subject in complete_subjects:
                        export_data.append({
                            'Subject ID': subject['subject_id'],
                            'Scan Count 2WK': subject.get('scan_count_2wk', 0),
                            'Scan Count 6MO': subject.get('scan_count_6mo', 0),
                            'QC Status': subject.get('qc_status', 'pending')
                        })
                    
                    df = pd.DataFrame(export_data)
                    csv = df.to_csv(index=False)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"complete_subjects_{timestamp}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key="download_complete"
                    )
                    
                    st.caption(f"{len(complete_subjects)} subjects")
                else:
                    st.info("No complete subjects")
        
        with col3:
            st.write("**Flagged Subjects**")
            st.caption("Needs review")
            if st.button("Export Flagged", use_container_width=True, key="export_flagged"):
                subjects = st.session_state.db.get_all_subjects()
                
                # Filter flagged subjects
                flagged_subjects = [s for s in subjects if s.get('flagged')]
                
                if flagged_subjects:
                    export_data = []
                    for subject in flagged_subjects:
                        export_data.append({
                            'Subject ID': subject['subject_id'],
                            'QC Status': subject.get('qc_status', 'pending'),
                            'Has 2WK': 'Yes' if subject.get('has_2wk') else 'No',
                            'Has 6MO': 'Yes' if subject.get('has_6mo') else 'No',
                            'QC Notes': subject.get('qc_notes', ''),
                            'Reviewed By': subject.get('reviewed_by', '')
                        })
                    
                    df = pd.DataFrame(export_data)
                    csv = df.to_csv(index=False)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"flagged_subjects_{timestamp}.csv",
                        mime="text/csv",
                        use_container_width=True,
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
            if st.button("Export Downloads", use_container_width=True):
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
                        use_container_width=True,
                        key="download_history"
                    )
                    
                    st.success(f"Ready to download {len(export_data)} download records")
                else:
                    st.info("No download history available")


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
    elif page == 'manage_datasets':
        page_manage_datasets()
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
