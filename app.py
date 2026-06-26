"""
BIDSHub - Main Streamlit Application

A professional BIDS dataset management tool for neuroimaging data.
Multi-platform support: Local, Pennsieve, OpenNeuro, XNAT, DANDI, HPC, Remote Server.
"""

import streamlit as st
import os
import sys
import pandas as pd
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

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
from src.agent_factory import AgentFactory, create_agent_factory
from src.bids_utils import extract_bids_path, normalize_subject_id, normalize_session_id, detect_sessions_in_path
from src.error_messages import ErrorMessages, handle_agent_error
from src.bidshub_version import __version__
from src.cache_manager import CacheManager
from src.ui_calm import (
    DOWNLOAD_QUEUE_PLATFORMS,
    expected_empty,
    quiet_queue_empty,
    render_xnat_beta_notice,
    toast_note,
    toast_ok,
)

# Page modules extracted from this file (incremental de-monolithing — see views/).
from views.dashboard import page_dashboard
from views.home import page_home
from views.viewer import page_viewer
from views.export import page_export
from views.subjects import page_subjects, page_subject_detail
from views.transfer import page_transfer
from views.qc import page_qc


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


def execute_downloads(download_manager, database):
    """Execute queued downloads routing to correct agent per dataset (v3.1.1+: all platforms)."""
    
    queue_items = download_manager.get_queue_items(status='queued')
    
    if not queue_items:
        quiet_queue_empty()
        return
    
    # Group items by dataset
    datasets_cache = {}
    dataset_groups = {}  # dataset_id -> items
    
    for item in queue_items:
        dataset_id = item.get('dataset_id')
        
        # Get dataset info (cache to avoid repeated queries)
        if dataset_id not in datasets_cache:
            dataset = database.get_dataset(dataset_id)
            if not dataset:
                st.error(f"Dataset ID {dataset_id} not found. Skipping item.")
                continue
            datasets_cache[dataset_id] = dataset
        
        # Group by dataset
        if dataset_id not in dataset_groups:
            dataset_groups[dataset_id] = []
        dataset_groups[dataset_id].append(item)
    
    # Skip platforms without download execution (e.g. local) — one toast, no per-batch warnings
    skipped_desc = []
    supported_groups = {}
    for dataset_id, items in dataset_groups.items():
        dataset = datasets_cache[dataset_id]
        plat = dataset['platform']
        if plat not in DOWNLOAD_QUEUE_PLATFORMS:
            skipped_desc.append(f"{plat} ({len(items)} items)")
            continue
        supported_groups[dataset_id] = items
    
    if skipped_desc:
        toast_note("Skipped — downloads not available for: " + "; ".join(skipped_desc))
    
    if not supported_groups:
        return
    
    # Execute downloads per dataset using AgentFactory
    from src.agent_factory import AgentFactory
    factory = AgentFactory(database)
    
    for dataset_id, items in supported_groups.items():
        dataset = datasets_cache[dataset_id]
        platform_name = dataset['platform'].title()
        
        st.caption(f"Downloading from {platform_name}: {dataset['name']}")
        
        # Use platform-specific execution based on platform type
        if dataset['platform'] == 'pennsieve':
            execute_pennsieve_downloads_multi(items, dataset, database)
        elif dataset['platform'] in ['openneuro', 'dandi', 'xnat']:
            execute_openneuro_downloads_multi(items, dataset, database)
        elif dataset['platform'] in ['hpc', 'remote_server']:
            execute_ssh_downloads_multi(items, dataset, database, factory)


def execute_pennsieve_downloads_multi(queue_items, dataset_config, database):
    """Execute downloads using Pennsieve Agent for specific dataset (v1.5+ multi-dataset)."""
    import time
    from src.utils import format_file_size
    
    # Get credentials from dataset config
    api_key = dataset_config.get('api_key_encrypted') or os.getenv('PENNSIEVE_API_KEY')
    api_secret = dataset_config.get('api_secret_encrypted') or os.getenv('PENNSIEVE_API_SECRET')
    
    if not api_key or not api_secret:
        st.error(f"[ERROR] Pennsieve credentials not configured for dataset '{dataset_config['name']}'")
        return
    
    agent = st.session_state.pennsieve_agent
    if not agent:
        st.error(ErrorMessages.format_error('CONNECTION_FAILED', 'pennsieve', 
                                            'Pennsieve Agent not installed'))
        st.code("pip install pennsieve")
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
        details_expander = st.expander("Download Details", expanded=False)
    
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
                'status': 'Success',
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
                'status': '[X] Failed',
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
        **Download Complete!**  
        **Success**: {successful}/{total} files ({(successful/total)*100:.1f}%)  
        **Total Size**: {format_file_size(downloaded_bytes)}  
        **Time**: {int(total_elapsed // 60)}m {int(total_elapsed % 60)}s  
        **Avg Speed**: {avg_speed:.2f} MB/s
        """)
    if failed > 0:
        st.error(f"[X] {failed} files failed to download. Check the download log for details.")
    
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
        st.error(ErrorMessages.format_error('CONNECTION_FAILED', 'openneuro',
                                            'openneuro-py not installed'))
        st.code("pip install openneuro-py")
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
        details_expander = st.expander("Download Details", expanded=False)
    
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
                'status': 'Success',
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
                'status': '[X] Failed',
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
        **Download Complete!**  
        **Subjects**: {successful}/{total_subjects} ({(successful/total_subjects)*100:.1f}%)  
        **Total Files**: {total_files}  
        **Time**: {int(total_elapsed // 60)}m {int(total_elapsed % 60)}s  
        **Avg Time/Subject**: {total_elapsed/successful:.1f}s
        """)
    if failed > 0:
        st.error(f"[X] {failed} subjects failed to download. Check the download log for details.")
    
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


def execute_ssh_downloads_multi(queue_items, dataset_config, database, factory):
    """Execute downloads from HPC/Remote Server via SSH/SFTP (v3.1.1+)."""
    import time
    from src.utils import format_file_size
    
    try:
        agent = factory.get_agent(dataset_config['id'])
    except Exception as e:
        platform = dataset_config['platform']
        st.error(handle_agent_error(e, platform, 'connection'))
        st.info(ErrorMessages.get_platform_help(platform))
        return
    
    if not agent:
        platform = dataset_config['platform']
        st.error(ErrorMessages.format_error('CONNECTION_FAILED', platform))
        return
    
    dataset_path = dataset_config['dataset_id_external']
    from src.app_paths import downloads_dir
    target_dir = dataset_config.get('root_path') or str(downloads_dir() / dataset_config['name'])
    
    if not queue_items:
        st.info("No items queued for download")
        return
    
    # Group by subject
    subjects_to_download = {}
    for item in queue_items:
        subject_id = item['subject_id']
        if subject_id not in subjects_to_download:
            subjects_to_download[subject_id] = []
        subjects_to_download[subject_id].append(item)
    
    # Create progress container
    progress_container = st.container()
    
    with progress_container:
        progress_bar = st.progress(0)
        status_col1, status_col2, status_col3 = st.columns(3)
        status_text = st.empty()
        details_expander = st.expander("Download Details", expanded=False)
    
    total_subjects = len(subjects_to_download)
    total_files = len(queue_items)
    successful = 0
    failed = 0
    start_time = time.time()
    
    download_log = []
    
    # Download each subject
    for i, (subject_id, items) in enumerate(subjects_to_download.items()):
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
        def progress_callback(msg):
            status_text.markdown(f"""
            **Subject {i+1}/{total_subjects}**: `{subject_id}`  
            **Status**: {msg} | **ETA**: {eta_str}
            """)
        
        # Download subject via SSH/SFTP
        max_retries = 2
        success = False
        error_msg = None
        
        for attempt in range(max_retries):
            try:
                # Determine sessions to download
                sessions = None  # Download all sessions
                
                success = agent.download_subject(
                    dataset_path=dataset_path,
                    subject_id=subject_id,
                    target_dir=target_dir,
                    sessions=sessions,
                    progress_callback=progress_callback
                )
                
                if success:
                    break
                else:
                    error_msg = f"Download failed (attempt {attempt+1}/{max_retries})"
                    if attempt < max_retries - 1:
                        time.sleep(2)
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                if attempt < max_retries - 1:
                    time.sleep(2)
        
        subject_elapsed = time.time() - subject_start_time
        
        if success:
            successful += 1
            # Mark all items as completed
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
                'status': 'Success',
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
                'status': '[X] Failed',
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
        **Download Complete!**  
        **Subjects**: {successful}/{total_subjects} ({(successful/total_subjects)*100:.1f}%)  
        **Total Files**: {total_files}  
        **Time**: {int(total_elapsed // 60)}m {int(total_elapsed % 60)}s  
        **Avg Time/Subject**: {total_elapsed/successful:.1f}s
        """)
    if failed > 0:
        st.error(f"[X] {failed} subjects failed. Check the download log.")
    
    # Save to history
    database.execute_query("""
        INSERT INTO metadata (key, value) 
        VALUES (?, ?)
    """, (
        f"download_session_{int(time.time())}",
        json.dumps({
            'timestamp': datetime.now().isoformat(),
            'platform': dataset_config['platform'],
            'dataset': dataset_config['name'],
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
        st.error(ErrorMessages.format_error('AUTH_FAILED', 'pennsieve'))
        st.info(ErrorMessages.suggest_fix('CONNECTION_FAILED', 'pennsieve'))
        return
    
    agent = st.session_state.pennsieve_agent
    if not agent:
        st.error("[ERROR] Pennsieve Agent not available")
        return
    
    # Filter out non-existent files
    valid_paths = [p for p in file_paths if Path(p).exists()]
    if len(valid_paths) < len(file_paths):
        st.warning(f"Skipping {len(file_paths) - len(valid_paths)} non-existent files")
    
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
        details_expander = st.expander("Upload Details", expanded=False)
    
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
                'status': '[X] Failed',
                'size': format_file_size(file_size),
                'error': results.get('error_messages', {}).get(file_path, 'Unknown error')
            })
        else:
            upload_log.append({
                'file': file_name,
                'status': 'Success',
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
        **Upload Complete!**  
        **Success**: {results['successful']}/{total} files ({(results['successful']/total)*100:.1f}%)  
        **Total Size**: {format_file_size(successful_size)}  
        **Time**: {int(total_elapsed // 60)}m {int(total_elapsed % 60)}s  
        **Avg Speed**: {avg_speed:.2f} MB/s  
        **Destination**: `{remote_path}`
        """)
    if results['failed'] > 0:
        st.error(f"[X] {results['failed']} files failed to upload")
        with st.expander("[ERROR] View Failed Files"):
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
            if st.button("← Dashboard", use_container_width=True, key=f"back_dash_{current_page}"):
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
                    use_container_width=True,
                    key="nav_home"):
            st.session_state.current_page = 'home'
            st.rerun()
        
        # Manage Datasets (v1.5+) - Moved to top for easy access
        datasets_label = "> Manage Datasets" if current == 'manage_datasets' else "Manage Datasets"
        if st.button(datasets_label,
                    use_container_width=True,
                    key="nav_manage_datasets"):
            st.session_state.current_page = 'manage_datasets'
            st.rerun()
        
        st.markdown("---")
        
        # Browse Subjects
        subjects_label = "> Browse Subjects" if current in ['subjects', 'subject_detail'] else "Browse Subjects"
        if st.button(subjects_label, 
                    use_container_width=True,
                    key="nav_subjects"):
            st.session_state.current_page = 'subjects'
            st.rerun()
        
        # Viewer
        viewer_label = "> Viewer" if current == 'viewer' else "Viewer"
        if st.button(viewer_label, 
                    use_container_width=True,
                    key="nav_viewer"):
            st.session_state.current_page = 'viewer'
            st.rerun()
        
        # QC Dashboard
        qc_label = "> QC Dashboard" if current == 'qc' else "QC Dashboard"
        if st.button(qc_label, 
                    use_container_width=True,
                    key="nav_qc"):
            st.session_state.current_page = 'qc'
            st.rerun()
        
        st.markdown("---")
        
        # Download Manager
        downloads_label = "> Download Manager" if current == 'downloads' else "Download Manager"
        if st.button(downloads_label, 
                    use_container_width=True,
                    key="nav_downloads"):
            st.session_state.current_page = 'downloads'
            st.rerun()
        
        # Data Transfer (v3.1.1+)
        transfer_label = "> Data Transfer" if current == 'transfer' else "Data Transfer"
        if st.button(transfer_label, 
                    use_container_width=True,
                    key="nav_transfer"):
            st.session_state.current_page = 'transfer'
            st.rerun()
        
        # Export
        export_label = "> Export" if current == 'export' else "Export"
        if st.button(export_label, 
                    use_container_width=True,
                    key="nav_export"):
            st.session_state.current_page = 'export'
            st.rerun()
        
        st.markdown("---")
        st.caption(f"BIDSHub v{__version__}")


def page_setup():
    """Setup page for first-time configuration."""
    render_breadcrumb('setup')
    st.markdown('<h1 class="main-header">BIDSHub - Setup</h1>', 
                unsafe_allow_html=True)
    
    st.markdown("""
    Welcome to BIDSHub! Configure your BIDS dataset and cloud platform connection.
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
                'pennsieve': 'Pennsieve (Private datasets, upload support)',
                'openneuro': 'OpenNeuro (Public datasets, read-only)'
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
                'cloud_only': 'Cloud only (browse & download remotely)',
                'local': 'Local (BIDS data already on disk)'
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
        from src.app_paths import downloads_dir
        default_dl = str(downloads_dir())
        bids_root = st.text_input(
            "Local Working Directory (optional)",
            value=st.session_state.bids_root or default_dl,
            placeholder=default_dl,
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
                        st.error(ErrorMessages.format_error('CONNECTION_FAILED', 'pennsieve'))
                        st.info(ErrorMessages.suggest_fix('CONNECTION_FAILED', 'pennsieve'))
                        return
                
                else:  # OpenNeuro
                    status_text.text("2/5 Verifying OpenNeuro connection...")
                    progress_bar.progress(40)
                    
                    if not check_openneuro_connection():
                        st.warning(ErrorMessages.format_error('CONNECTION_FAILED', 'openneuro'))
                    
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
                    # Get or create dataset entry
                    dataset_id = db.add_dataset(
                        name=dataset_name,
                        platform='local',
                        root_path=bids_root
                    )
                    
                    for subject in subjects_list:
                        sessions = bids_loader.get_sessions(subject=subject)
                        has_2wk = '2WK' in sessions
                        has_6mo = '6MO' in sessions
                        
                        scan_count_2wk = len(bids_loader.get_subject_scans(subject, '2WK')) if has_2wk else 0
                        scan_count_6mo = len(bids_loader.get_subject_scans(subject, '6MO')) if has_6mo else 0
                        
                        db.add_subject(
                            subject_id=subject,
                            dataset_id=dataset_id,
                            has_2wk=has_2wk,
                            has_6mo=has_6mo,
                            scan_count_2wk=scan_count_2wk,
                            scan_count_6mo=scan_count_6mo
                        )
                        
                        # Populate subject_sessions table for dynamic session tracking
                        for session in sessions:
                            scans = bids_loader.get_subject_scans(subject, session)
                            scan_count = len(scans)
                            
                            # Add to scans table
                            for scan in scans:
                                db.add_scan(
                                    subject_id=subject,
                                    dataset_id=dataset_id,
                                    session=session if session else 'ses-01',
                                    modality=scan.get('modality', ''),
                                    file_path=scan.get('file_path', ''),
                                    suffix=scan.get('suffix', '')
                                )
                            
                            # Add session to subject_sessions table for dynamic session tracking
                            if scan_count > 0:
                                db.add_subject_session(
                                    subject_id=subject,
                                    dataset_id=dataset_id,
                                    session_id=session if session else 'ses-01',
                                    scan_count=scan_count
                                )
                else:
                    # Index from remote structure
                    # Get or create dataset entry
                    dataset_id = db.add_dataset(
                        name=dataset_name,
                        platform=st.session_state.platform,
                        dataset_id_external=dataset_name,
                        root_path=bids_root
                    )
                    
                    sessions_map = remote_structure.get('sessions', {}) if remote_structure else {}
                    scans_map = remote_structure.get('scans', {}) if remote_structure else {}
                    
                    for subject in subjects_list:
                        subject_sessions = sessions_map.get(subject, [])
                        has_2wk = '2WK' in subject_sessions
                        has_6mo = '6MO' in subject_sessions
                        
                        db.add_subject(
                            subject_id=subject,
                            dataset_id=dataset_id,
                            has_2wk=has_2wk,
                            has_6mo=has_6mo,
                            scan_count_2wk=0,  # Unknown until downloaded
                            scan_count_6mo=0   # Unknown until downloaded
                        )
                        
                        # Populate subject_sessions table for dynamic session tracking
                        # Group scans by session
                        from collections import defaultdict
                        session_scan_counts = defaultdict(int)
                        
                        # Get scans for this subject from remote structure
                        subject_scans = scans_map.get(subject, [])
                        for scan in subject_scans:
                            session = scan.get('session', '')
                            if session:
                                session_scan_counts[session] += 1
                                
                                # Add scan to database
                                db.add_scan(
                                    subject_id=subject,
                                    dataset_id=dataset_id,
                                    session=session,
                                    modality=scan.get('modality', ''),
                                    file_path=scan.get('file_path', ''),
                                    suffix=scan.get('suffix', ''),
                                    pennsieve_package_id=scan.get('package_id', '')
                                )
                        
                        # Populate subject_sessions table for dynamic session tracking
                        for session, scan_count in session_scan_counts.items():
                            db.add_subject_session(
                                subject_id=subject,
                                dataset_id=dataset_id,
                                session_id=session,
                                scan_count=scan_count
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

    # One-shot confirmation after an add (we rerun on add so the new row appears).
    just_added = st.session_state.pop('_dataset_added', None)
    if just_added:
        st.success(
            f"Dataset '{just_added}' added. Expand it below and click **Sync** "
            "to fetch its subjects from the platform."
        )

    if not datasets:
        st.info("No datasets configured yet. Add your first dataset below.")
    else:
        for dataset in datasets:
            platform_emoji_map = {
                'pennsieve': '',
                'openneuro': '',
                'dandi': '',
                'xnat': '',
                'hpc': '',
                'remote_server': '',
                'local': ''
            }
            
            with st.expander(f"{platform_emoji_map.get(dataset['platform'], '')} {dataset['name']}", 
                           expanded=False):
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    # Count subjects for this dataset
                    subjects = st.session_state.db.get_subjects_by_dataset(dataset['id'])
                    st.metric("Subjects", len(subjects))
                
                with col2:
                    st.metric("Platform", dataset['platform'].title())
                
                with col3:
                    status_color = {"active": "[PASS]", "inactive": "[REVIEW]", "error": "[FAIL]"}
                    st.metric("Status", f"{status_color.get(dataset['status'], '[INACTIVE]')} {dataset['status'].title()}")
                
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
                    if st.button("[Sync] Sync", key=f"sync_{dataset['id']}", 
                               use_container_width=True):
                        # Sync subjects from platform (v3.1.1+: supports all platforms)
                        if dataset['platform'] == 'local':
                            st.info("Local datasets are indexed automatically")
                        else:
                            with st.spinner(f"Syncing subjects from {dataset['platform'].title()}..."):
                                try:
                                    from src.agent_factory import AgentFactory
                                    
                                    factory = AgentFactory(st.session_state.db)
                                    agent = factory.get_agent(dataset['id'])
                                    
                                    if agent:
                                        # Fetch subjects with metadata
                                        if dataset['platform'] in ['hpc', 'remote_server']:
                                            # SSH-based platforms need dataset path
                                            subjects_data = agent.get_subjects_with_metadata(
                                                dataset_path=dataset['dataset_id_external']
                                            )
                                        else:
                                            # Cloud platforms (pennsieve, openneuro, dandi, xnat)
                                            subjects_data = agent.get_subjects_with_metadata(
                                                dataset.get('dataset_id_external', dataset['name'])
                                            )
                                        
                                        # Index subjects to database
                                        indexed_count = 0
                                        scan_count = 0
                                        for subject_data in subjects_data:
                                            subject_id = subject_data.get('subject_id')
                                            
                                            # Add subject
                                            db_subject_id = st.session_state.db.add_subject(
                                                dataset_id=dataset['id'],
                                                subject_id=subject_id,
                                                age=subject_data.get('age'),
                                                sex=subject_data.get('sex'),
                                                diagnosis=subject_data.get('diagnosis'),
                                                participant_group=subject_data.get('participant_group')
                                            )
                                            
                                            # Add sessions (or create default if none)
                                            sessions = subject_data.get('sessions', [])
                                            if not sessions:
                                                # Dataset doesn't use sessions, create default entry
                                                sessions = ['ses-default']
                                            
                                            for session in sessions:
                                                st.session_state.db.add_subject_session(
                                                    subject_id=subject_id,
                                                    dataset_id=dataset['id'],
                                                    session_id=session
                                                )
                                            
                                            # Add scans
                                            for scan in subject_data.get('scans', []):
                                                st.session_state.db.add_scan(
                                                    dataset_id=dataset['id'],
                                                    subject_id=subject_id,
                                                    session=scan.get('session', 'ses-01'),
                                                    modality=scan.get('modality', 'unknown'),
                                                    suffix=scan.get('suffix', ''),
                                                    file_path=scan.get('file_path', ''),
                                                    file_size_bytes=scan.get('size', 0)
                                                )
                                                scan_count += 1
                                            
                                            indexed_count += 1

                                        # Cache platform-fetched demographics as a
                                        # participants.tsv so the Browse/QC tables show
                                        # age/sex/diagnosis for this (cloud) dataset.
                                        try:
                                            from src.app_paths import dataset_metadata_dir
                                            cols = ['participant_id', 'age', 'sex', 'diagnosis',
                                                    'group', 'handedness']
                                            lines = ['\t'.join(cols)]
                                            for sd in subjects_data:
                                                pid = sd.get('subject_id', '')
                                                if pid and not pid.startswith('sub-'):
                                                    pid = f'sub-{pid}'
                                                row = [pid,
                                                       sd.get('age'), sd.get('sex'),
                                                       sd.get('diagnosis'),
                                                       sd.get('participant_group'),
                                                       sd.get('handedness')]
                                                lines.append('\t'.join(
                                                    '' if v is None else str(v) for v in row))
                                            mdir = dataset_metadata_dir(dataset['id'])
                                            mdir.mkdir(parents=True, exist_ok=True)
                                            (mdir / 'participants.tsv').write_text(
                                                '\n'.join(lines) + '\n')
                                        except Exception:
                                            pass  # demographics cache is best-effort

                                        # Update last sync
                                        st.session_state.db.update_dataset(
                                            dataset['id'],
                                            last_sync_date=datetime.now()
                                        )
                                        
                                        st.success(f"Synced {indexed_count} subjects, {scan_count} scans from {dataset['name']}")
                                        st.rerun()
                                    else:
                                        st.error("Could not create agent for this platform")
                                except Exception as e:
                                    st.error(f"Sync failed: {str(e)}")
                                    logger.error(f"Sync error for dataset {dataset['id']}: {e}")
                
                with col2:
                    new_status = "inactive" if dataset['status'] == "active" else "active"
                    if st.button(f"{'[Pause] Deactivate' if dataset['status'] == 'active' else '[Start] Activate'}", 
                               key=f"toggle_{dataset['id']}", 
                               use_container_width=True):
                        st.session_state.db.update_dataset(dataset['id'], status=new_status)
                        st.success(f"Dataset {new_status}")
                        st.rerun()
                
                with col3:
                    if st.button("[Delete] Remove", key=f"remove_{dataset['id']}", 
                               use_container_width=True,
                               type="secondary"):
                        # Confirm deletion
                        if len(subjects) > 0:
                            st.warning(f"This will delete {len(subjects)} subjects and all associated data!")
                            if st.button(f"Confirm Delete", key=f"confirm_delete_{dataset['id']}",
                                       type="primary"):
                                st.session_state.db.delete_dataset(dataset['id'])
                                st.success("Dataset removed")
                                st.rerun()
                        else:
                            st.session_state.db.delete_dataset(dataset['id'])
                            st.success("Dataset removed")
                            st.rerun()
    
    # Database maintenance section (v3.1.1+)
    st.markdown("---")
    st.markdown('<h2 class="section-header"> Database Maintenance</h2>', 
                unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Check Integrity", use_container_width=True):
            with st.spinner("Checking database integrity..."):
                issues = st.session_state.db.check_integrity()
                total_issues = sum(issues.values())
                
                if total_issues == 0:
                    st.success("Database is clean - no integrity issues found")
                else:
                    st.warning(f"Found {total_issues} integrity issue(s):")
                    for issue_type, count in issues.items():
                        if count > 0:
                            st.markdown(f"- **{issue_type.replace('_', ' ').title()}**: {count}")
                    
                    st.session_state.integrity_issues = issues
                    st.session_state.show_integrity_warning = True
    
    with col2:
        if st.button(" Run Maintenance", use_container_width=True,
                    disabled=not st.session_state.get('integrity_issues')):
            with st.spinner("Running database maintenance..."):
                report = st.session_state.db.run_integrity_maintenance(auto_fix=True)
                
                if report['status'] == 'fixed':
                    st.success("Database maintenance complete!")
                    
                    fixes = report.get('fixes_applied', {})
                    if fixes:
                        st.markdown("**Fixes Applied:**")
                        for fix_type, count in fixes.items():
                            if isinstance(count, dict):
                                for sub_type, sub_count in count.items():
                                    if sub_count > 0:
                                        st.markdown(f"- {sub_type.replace('_', ' ').title()}: {sub_count}")
                            elif count > 0:
                                st.markdown(f"- {fix_type.replace('_', ' ').title()}: {count}")
                    
                    st.session_state.integrity_issues = None
                    st.session_state.show_integrity_warning = False
                    st.rerun()
    
    # Add new dataset section
    st.markdown("---")
    st.markdown('<h2 class="section-header">Add New Dataset</h2>', 
                unsafe_allow_html=True)
    
    if len(datasets) >= 5:
        st.warning("Maximum of 5 datasets supported in v1.5.")
        return
    
    # Platform selection (v3.1.1+: Added HPC and Remote Server)
    col1, col2 = st.columns(2)
    
    with col1:
        new_platform = st.selectbox(
            "Platform",
            options=['pennsieve', 'openneuro', 'dandi', 'xnat', 'hpc', 'remote_server'],
            format_func=lambda x: {
                'pennsieve': 'Pennsieve',
                'openneuro': 'OpenNeuro',
                'dandi': 'DANDI',
                'xnat': 'XNAT',
                'hpc': 'HPC Cluster',
                'remote_server': 'Remote Server (SSH)'
            }.get(x, x.title()),
            key="new_dataset_platform"
        )
    
    with col2:
        platform_descriptions = {
            'pennsieve': "Private datasets with upload support",
            'openneuro': "Public neuroimaging datasets",
            'dandi': "Public cellular neurophysiology datasets",
            'xnat': "Institutional imaging archives",
            'hpc': "HPC cluster via SSH/SFTP",
            'remote_server': "Generic remote server via SSH/SFTP"
        }
        st.info(platform_descriptions.get(new_platform, "Data platform"))
    
    if new_platform == 'xnat':
        render_xnat_beta_notice()
    
    # Dataset configuration form
    with st.form(f"add_dataset_form_{new_platform}"):
        dataset_name = st.text_input(
            "Dataset Name",
            placeholder="My Dataset",
            help="Unique name for this dataset",
            key=f"new_dataset_name_{new_platform}",
        )
        
        col1, col2 = st.columns(2)
        
        # Platform-specific configuration
        server_url = None
        
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
        
        elif new_platform == 'openneuro':
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
        
        elif new_platform == 'dandi':
            external_id = st.text_input(
                "DANDI Dandiset ID",
                placeholder="000001",
                help="Dandiset ID from DANDI (e.g., 000001)"
            )
            
            api_key = st.text_input(
                "API Token (optional)",
                type="password",
                help="Only needed for embargoed dandisets"
            )
            
            api_secret = None
        
        elif new_platform == 'xnat':
            server_url = st.text_input(
                "XNAT Server URL",
                placeholder="https://xnat.example.edu",
                help="URL of your XNAT server"
            )
            
            external_id = st.text_input(
                "XNAT Project ID",
                placeholder="PROJECT_001",
                help="Project ID in XNAT"
            )
            
            with col1:
                api_key = st.text_input(
                    "XNAT Username",
                    help="Your XNAT username"
                )
            
            with col2:
                api_secret = st.text_input(
                    "XNAT Password",
                    type="password",
                    help="Your XNAT password"
                )
        
        elif new_platform == 'hpc':
            server_url = st.text_input(
                "HPC Hostname",
                placeholder="hpc.institution.edu",
                help="Hostname of your HPC cluster"
            )
            
            external_id = st.text_input(
                "Dataset Path on HPC",
                placeholder="/data/bids/my_dataset",
                help="Full path to BIDS dataset on HPC"
            )
            
            with col1:
                api_key = st.text_input(
                    "SSH Username",
                    help="Your SSH username for HPC"
                )
            
            with col2:
                auth_method = st.radio(
                    "Authentication",
                    options=['password', 'ssh_key'],
                    format_func=lambda x: 'Password' if x == 'password' else 'SSH Key File'
                )
            
            if auth_method == 'password':
                api_secret = st.text_input(
                    "SSH Password",
                    type="password",
                    help="Your SSH password"
                )
            else:
                api_secret = None
                ssh_key_path = st.text_input(
                    "SSH Private Key Path",
                    placeholder=str(Path.home() / ".ssh" / "id_rsa"),
                    help="Path to your SSH private key file"
                )
        
        elif new_platform == 'remote_server':
            server_url = st.text_input(
                "Server Hostname or IP",
                placeholder="data.lab.edu or 192.168.1.100",
                help="Hostname or IP address of remote server"
            )
            
            external_id = st.text_input(
                "Dataset Path on Server",
                placeholder="/mnt/data/bids_datasets/my_dataset",
                help="Full path to BIDS dataset on remote server"
            )
            
            with col1:
                api_key = st.text_input(
                    "SSH Username",
                    help="Your SSH username"
                )
            
            with col2:
                auth_method = st.radio(
                    "Authentication",
                    options=['password', 'ssh_key'],
                    format_func=lambda x: 'Password' if x == 'password' else 'SSH Key File'
                )
            
            if auth_method == 'password':
                api_secret = st.text_input(
                    "SSH Password",
                    type="password",
                    help="Your SSH password"
                )
            else:
                api_secret = None
                ssh_key_path = st.text_input(
                    "SSH Private Key Path",
                    placeholder=str(Path.home() / ".ssh" / "id_rsa"),
                    help="Path to your SSH private key file"
                )
        
        from src.app_paths import downloads_dir
        root_path = st.text_input(
            "Local Working Directory",
            placeholder=str(downloads_dir() / dataset_name),
            help="Directory for downloaded files"
        )
        
        validate_bids = st.checkbox(
            "Validate BIDS compliance",
            value=True,
            help="Check if dataset follows BIDS specification"
        )
        
        submit = st.form_submit_button("[+] Add Dataset", type="primary", use_container_width=True)
        
        if submit:
            # Validate inputs based on platform
            validation_error = None
            
            if not dataset_name:
                validation_error = "Dataset name is required"
            elif not external_id:
                error_messages = {
                    'pennsieve': 'Pennsieve dataset name is required',
                    'openneuro': 'OpenNeuro dataset ID is required',
                    'dandi': 'DANDI dandiset ID is required',
                    'xnat': 'XNAT project ID is required',
                    'hpc': 'Dataset path on HPC is required',
                    'remote_server': 'Dataset path on server is required'
                }
                validation_error = error_messages.get(new_platform, 'Dataset ID/Path is required')
            elif new_platform == 'pennsieve' and (not api_key or not api_secret):
                validation_error = "Pennsieve credentials (API key and secret) are required"
            elif new_platform in ['xnat', 'hpc', 'remote_server']:
                if not server_url:
                    validation_error = f"{new_platform.upper()} server URL/hostname is required"
                elif not api_key:
                    validation_error = "SSH/XNAT username is required"
                elif new_platform in ['hpc', 'remote_server'] and auth_method == 'password' and not api_secret:
                    validation_error = "SSH password is required (or provide SSH key)"
                elif new_platform in ['hpc', 'remote_server'] and auth_method == 'ssh_key' and not ssh_key_path:
                    validation_error = "SSH key file path is required"
                elif new_platform == 'xnat' and not api_secret:
                    validation_error = "XNAT password is required"
            
            if validation_error:
                st.error(validation_error)
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
                                st.warning("BIDS Validation Issues:")
                                st.text(validation_msg)
                                st.info(ErrorMessages.suggest_fix('NOT_BIDS_COMPLIANT', None))

                                if st.checkbox("Add dataset anyway (not recommended)"):
                                    validation_passed = True
                                else:
                                    validation_passed = False
                                    st.error(ErrorMessages.NOT_BIDS_COMPLIANT)
                            else:
                                st.success("BIDS validation passed!")
                    elif validate_bids and new_platform in ('openneuro', 'dandi'):
                        # Validate cloud (public) datasets too, so BIDS compliance is
                        # checked consistently — not only for local datasets. The
                        # reliable remote signal is dataset_description.json + sub-*
                        # folders (OpenNeuro passes; DANDI/NWB does not).
                        with st.spinner(f"Validating BIDS structure on {new_platform.title()}..."):
                            try:
                                from src.bids_validator import BIDSValidator
                                if new_platform == 'openneuro':
                                    from src.openneuro_agent import OpenNeuroAgent
                                    agent = OpenNeuroAgent()
                                else:
                                    from src.dandi_agent import DANDIAgent
                                    agent = DANDIAgent()
                                is_valid, validation_msg, _ = BIDSValidator().validate_remote_dataset(
                                    agent, external_id, new_platform
                                )
                            except Exception as e:
                                # Never block a legitimate add on a validator error.
                                is_valid, validation_msg = True, f"(BIDS check skipped: {e})"

                            if not is_valid:
                                st.warning("BIDS Validation Issues:")
                                st.text(validation_msg)
                                if st.checkbox("Add dataset anyway (not recommended)", key="cloud_add_anyway"):
                                    validation_passed = True
                                else:
                                    validation_passed = False
                                    st.error(
                                        "This dataset doesn't look BIDS-compliant. BIDSHub's "
                                        "browsing, QC, and viewer features assume BIDS — non-BIDS "
                                        "data (e.g. DANDI/NWB) will show limited information."
                                    )
                            else:
                                st.success("BIDS validation passed!")
                    
                    if validation_passed:
                        # Prepare root_path: For SSH key auth, store key path; otherwise store working dir
                        final_root_path = root_path if root_path else None
                        
                        if new_platform in ['hpc', 'remote_server'] and auth_method == 'ssh_key':
                            final_root_path = ssh_key_path  # Store SSH key path for agent
                        
                        # Add dataset to database
                        dataset_id = st.session_state.db.add_dataset(
                            name=dataset_name,
                            platform=new_platform,
                            api_key=api_key if api_key else None,
                            api_secret=api_secret if api_secret else None,
                            dataset_id_external=external_id,
                            root_path=final_root_path,
                            server_url=server_url if server_url else None
                        )
                        
                        if dataset_id:
                            st.success(f"Dataset '{dataset_name}' added successfully!")
                            
                            # For local datasets, index subjects immediately
                            # (this Add form only offers remote/cloud platforms, so
                            # this branch is normally skipped; cloud datasets sync below)
                            if new_platform == 'local' and root_path:
                                with st.spinner("Indexing local BIDS dataset..."):
                                    try:
                                        from src.bids_loader import BIDSLoader
                                        
                                        # Load BIDS layout
                                        bids_loader = BIDSLoader(root_path)
                                        subjects_list = bids_loader.get_subjects()
                                        
                                        indexed_count = 0
                                        for subject in subjects_list:
                                            sessions = bids_loader.get_sessions(subject)
                                            
                                            # Add subject to database
                                            st.session_state.db.add_subject(
                                                dataset_id=dataset_id,
                                                subject_id=subject,
                                                local_subject_id=subject
                                            )
                                            
                                            # Add scans for each session AND populate subject_sessions table
                                            for session in sessions:
                                                scans = bids_loader.get_subject_scans(subject, session)
                                                
                                                # Count scans for this session
                                                scan_count = len(scans)
                                                
                                                for scan in scans:
                                                    st.session_state.db.add_scan(
                                                        dataset_id=dataset_id,
                                                        subject_id=subject,
                                                        session=session if session else 'ses-01',
                                                        modality=scan['modality'],
                                                        suffix=scan.get('suffix', ''),
                                                        file_path=scan['file_path'],
                                                        file_size_bytes=scan.get('size', 0),
                                                        is_downloaded=True
                                                    )
                                                
                                                # Add session to subject_sessions table for dynamic session tracking
                                                if scan_count > 0:
                                                    st.session_state.db.add_subject_session(
                                                        subject_id=subject,
                                                        dataset_id=dataset_id,
                                                        session_id=session if session else 'ses-01',
                                                        scan_count=scan_count
                                                    )
                                            
                                            indexed_count += 1
                                        
                                        st.success(f"Indexed {indexed_count} subjects from local dataset")
                                        # Nav buttons can't live inside st.form(); guide via the sidebar.
                                        st.markdown("**Next:** open **Browse Subjects** from the sidebar to review the indexed subjects.")
                                    except Exception as e:
                                        st.error(f"Error indexing local dataset: {str(e)}")
                                        st.warning("Dataset added but subjects not indexed. Check BIDS structure.")
                            else:
                                # Cloud dataset - needs sync. Rerun so the new row
                                # shows under Connected Datasets (the list above was
                                # built before this add) and can be synced right away.
                                st.session_state['_dataset_added'] = dataset_name
                                st.rerun()
                        else:
                            st.error("Failed to add dataset. Check database connection.")


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
            if st.button("Preview Filtered Results", use_container_width=True):
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
            if st.button("[Delete] Clear Filters", use_container_width=True):
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
        st.caption(f"Filters active: {len(filtered_ids)} subjects selected")
    
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
            use_container_width=True,
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
                if st.button("Remove Selected", use_container_width=True, key="remove_single_item"):
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
                if st.button("Remove All Failed", use_container_width=True):
                    removed = st.session_state.db.execute_query(
                        "DELETE FROM download_queue WHERE status = 'failed'"
                    )
                    toast_ok("Removed all failed items")
                    st.rerun()
            
            with col2:
                if st.button("Remove All Completed", use_container_width=True):
                    removed = st.session_state.db.execute_query(
                        "DELETE FROM download_queue WHERE status = 'completed'"
                    )
                    toast_ok("Removed all completed items")
                    st.rerun()
            
            with col3:
                if st.button("Retry All Failed", use_container_width=True):
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
                        use_container_width=True,
                        disabled=stats['queued'] == 0):
                # Execute actual downloads using Pennsieve Agent
                execute_downloads(dm, st.session_state.db)
        
        with col2:
            if st.button("Pause All",
                        use_container_width=True,
                        disabled=stats['downloading'] == 0):
                dm.pause_downloads()
                toast_note("Downloads paused")
                st.rerun()
        
        with col3:
            if st.button("Resume",
                        use_container_width=True,
                        disabled=stats['paused'] == 0):
                dm.resume_downloads()
                toast_ok("Downloads resumed")
                st.rerun()
        
        with col4:
            if st.button("Clear Queue",
                        use_container_width=True):
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
                        'Type': f"{'' if session_type == 'Download' else ''} {session_type}",
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
                with st.expander("View Recent Sessions", expanded=False):
                    history_df = pd.DataFrame(history_data)
                    st.dataframe(history_df, use_container_width=True, hide_index=True)
                    
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
        st.info(" **OpenNeuro is read-only**. Upload not supported. Use Pennsieve for private datasets with upload capabilities.")


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
    except Exception as e:
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
                    if st.button("[View]", key=f"view_{scan_id}_{idx}", help="Open in Viewer", use_container_width=True):
                        st.session_state.viewer_selected_file = scan.get('file_path', '')
                        st.session_state.viewer_file_loaded = True
                        st.session_state.current_page = 'viewer'
                        st.rerun()
                
                with col6:
                    # Download action
                    if is_stub and platform and dataset_remote_id:
                        if st.button("[DL]", key=f"dl_{scan_id}_{idx}", help="Download", use_container_width=True):
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
