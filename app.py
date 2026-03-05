"""
BIDSHub - Main Streamlit Application

A professional BIDS dataset management tool for neuroimaging data.
Multi-platform support: Local, Pennsieve, OpenNeuro, XNAT, DANDI, HPC, Remote Server.
"""

import streamlit as st
import os
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
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
from src.agent_factory import AgentFactory, create_agent_factory
from src.bids_utils import extract_bids_path, normalize_subject_id, normalize_session_id, detect_sessions_in_path
from src.error_messages import ErrorMessages, handle_agent_error
from src.cache_manager import CacheManager


# Page configuration
st.set_page_config(
    page_title="BIDSHub",
    page_icon="[B]",
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


def execute_downloads(download_manager, database):
    """Execute queued downloads routing to correct agent per dataset (v3.1.1+: all platforms)."""
    
    queue_items = download_manager.get_queue_items(status='queued')
    
    if not queue_items:
        st.info("No items queued for download")
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
    
    # Execute downloads per dataset using AgentFactory
    from src.agent_factory import AgentFactory
    factory = AgentFactory(database)
    
    for dataset_id, items in dataset_groups.items():
        dataset = datasets_cache[dataset_id]
        platform_name = dataset['platform'].title()
        
        st.info(f"Downloading from {platform_name}: {dataset['name']}")
        
        # Use platform-specific execution based on platform type
        if dataset['platform'] == 'pennsieve':
            execute_pennsieve_downloads_multi(items, dataset, database)
        elif dataset['platform'] in ['openneuro', 'dandi', 'xnat']:
            execute_openneuro_downloads_multi(items, dataset, database)
        elif dataset['platform'] in ['hpc', 'remote_server']:
            execute_ssh_downloads_multi(items, dataset, database, factory)
        else:
            st.warning(f"Download not implemented for platform: {dataset['platform']}")


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
        details_expander = st.expander("[Data] Download Details", expanded=False)
    
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
                'status': '[OK] Success',
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
        [OK] **Download Complete!**  
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
        details_expander = st.expander("[Data] Download Details", expanded=False)
    
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
                'status': '[OK] Success',
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
        [OK] **Download Complete!**  
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
    target_dir = dataset_config.get('root_path') or str(Path.home() / "data-explorer" / "datasets" / dataset_config['name'])
    
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
        details_expander = st.expander("[Data] Download Details", expanded=False)
    
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
                'status': '[OK] Success',
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
        [OK] **Download Complete!**  
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
        st.warning(f"[WARNING] Skipping {len(file_paths) - len(valid_paths)} non-existent files")
    
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
        details_expander = st.expander("[Data] Upload Details", expanded=False)
    
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
                'status': '[OK] Success',
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
        [OK] **Upload Complete!**  
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
            platform_emoji = "[P]" if st.session_state.platform == 'pennsieve' else "[O]"
            platform_name = st.session_state.platform.title()
            st.caption(f"**Platform:** {platform_emoji} {platform_name}")
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
        st.caption("BIDSHub v3.1.1")


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
                'pennsieve': '[P] Pennsieve (Private datasets, upload support)',
                'openneuro': '[O] OpenNeuro (Public datasets, read-only)'
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
                'cloud_only': '[Cloud] Cloud only (browse & download remotely)',
                'local': '[L] Local (BIDS data already on disk)'
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
    
    if not datasets:
        st.info("No datasets configured yet. Add your first dataset below.")
    else:
        for dataset in datasets:
            platform_emoji_map = {
                'pennsieve': '[P]',
                'openneuro': '[O]',
                'dandi': '[D]',
                'xnat': '[X]',
                'hpc': '[H]',
                'remote_server': '[R]',
                'local': '[L]'
            }
            
            with st.expander(f"{platform_emoji_map.get(dataset['platform'], '[Data]')} {dataset['name']}", 
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
                                            
                                            # Add sessions
                                            for session in subject_data.get('sessions', []):
                                                st.session_state.db.add_subject_session(
                                                    subject_id=subject_id,
                                                    dataset_id=dataset['id'],
                                                    session=session
                                                )
                                            
                                            indexed_count += 1
                                        
                                        # Update last sync
                                        st.session_state.db.update_dataset(
                                            dataset['id'],
                                            last_sync_date=datetime.now()
                                        )
                                        
                                        st.success(f"[OK] Synced {indexed_count} subjects from {dataset['name']}")
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
                            st.warning(f"[WARNING] This will delete {len(subjects)} subjects and all associated data!")
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
        if st.button("[Search] Check Integrity", use_container_width=True):
            with st.spinner("Checking database integrity..."):
                issues = st.session_state.db.check_integrity()
                total_issues = sum(issues.values())
                
                if total_issues == 0:
                    st.success("[OK] Database is clean - no integrity issues found")
                else:
                    st.warning(f"[WARNING] Found {total_issues} integrity issue(s):")
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
                    st.success("[OK] Database maintenance complete!")
                    
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
        st.warning("[WARNING] Maximum of 5 datasets supported in v1.5.")
        return
    
    # Platform selection (v3.1.1+: Added HPC and Remote Server)
    col1, col2 = st.columns(2)
    
    with col1:
        new_platform = st.selectbox(
            "Platform",
            options=['pennsieve', 'openneuro', 'dandi', 'xnat', 'hpc', 'remote_server'],
            format_func=lambda x: {
                'pennsieve': '[P] Pennsieve',
                'openneuro': '[O] OpenNeuro',
                'dandi': '[D] DANDI',
                'xnat': '[X] XNAT',
                'hpc': '[H] HPC Cluster',
                'remote_server': '[R] Remote Server (SSH)'
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
    
    # Dataset configuration form
    with st.form("add_dataset_form"):
        dataset_name = st.text_input(
            "Dataset Name",
            placeholder="My Dataset",
            help="Unique name for this dataset"
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
                                st.warning("[WARNING] BIDS Validation Issues:")
                                st.text(validation_msg)
                                st.info(ErrorMessages.suggest_fix('NOT_BIDS_COMPLIANT', None))
                                
                                if st.checkbox("Add dataset anyway (not recommended)"):
                                    validation_passed = True
                                else:
                                    validation_passed = False
                                    st.error(ErrorMessages.NOT_BIDS_COMPLIANT)
                            else:
                                st.success("[OK] BIDS validation passed!")
                    
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
                            st.success(f"[OK] Dataset '{dataset_name}' added successfully!")
                            
                            # For local datasets, index subjects immediately
                            if data_location_mode == 'local' and root_path:
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
                                        
                                        # Next steps for local datasets
                                        st.markdown("**What's next?**")
                                        col1, col2 = st.columns(2)
                                        
                                        with col1:
                                            if st.button("Browse Subjects", type="primary", use_container_width=True, key="goto_subjects_local"):
                                                st.session_state.current_page = 'subjects'
                                                st.rerun()
                                        
                                        with col2:
                                            if st.button("View Dashboard", use_container_width=True, key="goto_dashboard_local"):
                                                st.session_state.current_page = 'dashboard'
                                                st.rerun()
                                        
                                    except Exception as e:
                                        st.error(f"Error indexing local dataset: {str(e)}")
                                        st.warning("Dataset added but subjects not indexed. Check BIDS structure.")
                            else:
                                # Cloud dataset - needs sync
                                st.info("For cloud datasets, go to 'Subjects' page and click 'Sync Subjects' to fetch metadata from the platform.")
                                
                                # Next steps for cloud datasets
                                st.markdown("**What's next?**")
                                col1, col2, col3 = st.columns(3)
                                
                                with col1:
                                    if st.button("Sync Subjects", type="primary", use_container_width=True, key="goto_subjects_cloud"):
                                        st.session_state.current_page = 'subjects'
                                        st.rerun()
                                
                                with col2:
                                    if st.button("View Dashboard", use_container_width=True, key="goto_dashboard_cloud"):
                                        st.session_state.current_page = 'dashboard'
                                        st.rerun()
                                
                                with col3:
                                    if st.button("Manage Datasets", use_container_width=True, key="goto_manage_cloud"):
                                        st.rerun()
                        else:
                            st.error("Failed to add dataset. Check database connection.")


def page_home():
    """Landing page for BIDSHub (v3.1.2+) - Hero layout with feature cards."""
    
    # Custom CSS for landing page
    st.markdown("""
        <style>
        /* Landing page styles */
        .main .block-container {
            background: linear-gradient(135deg, #eff6ff 0%, #ffffff 50%, #eff6ff 100%);
            max-width: 100% !important;
            padding: 2rem 2rem 4rem 2rem !important;
        }
        
        .hero-headline {
            font-size: 2.5rem;
            font-weight: 700;
            color: #111827;
            line-height: 1.2;
            margin-bottom: 1rem;
        }
        
        .hero-highlight {
            color: #003d7a;
        }
        
        .hero-subtitle {
            font-size: 1.125rem;
            color: #4b5563;
            line-height: 1.6;
            margin-bottom: 2rem;
        }
        
        .quick-feature {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin: 0.75rem 0;
            padding: 0.75rem;
            background: #f9fafb;
            border-radius: 0.5rem;
        }
        
        .quick-feature-icon {
            background-color: #eff6ff;
            padding: 0.5rem;
            border-radius: 0.5rem;
            min-width: 40px;
            min-height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.875rem;
            font-weight: 700;
            color: #002d72;
        }
        
        .visual-card {
            background: white;
            border-radius: 1rem;
            padding: 3rem 2rem;
            box-shadow: 0 20px 60px -15px rgba(0, 45, 114, 0.2);
            border: 1px solid #dbeafe;
            text-align: center;
            position: relative;
        }
        
        .bidshub-logo {
            font-size: 2.5rem;
            font-weight: 700;
            color: #ffffff;
            background-color: #002d72;
            margin: 2rem auto;
            padding: 2rem 3rem;
            border-radius: 1rem;
            box-shadow: 0 4px 12px rgba(0, 45, 114, 0.25);
            display: inline-block;
        }
        
        .logo-subtitle {
            color: #6b7280;
            font-size: 0.875rem;
            margin-top: 0.5rem;
        }
        
        .feature-card {
            background: white;
            border-radius: 1rem;
            padding: 1.5rem;
            box-shadow: 0 4px 20px rgba(0, 45, 114, 0.08);
            border: 1px solid #dbeafe;
            transition: all 0.3s ease;
            height: 100%;
        }
        
        .feature-card:hover {
            box-shadow: 0 12px 40px rgba(0, 45, 114, 0.15);
            transform: translateY(-4px);
        }
        
        .feature-icon-box {
            background-color: #eff6ff;
            width: 3rem;
            height: 3rem;
            border-radius: 0.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 1rem;
            font-size: 0.75rem;
            font-weight: 700;
            color: #002d72;
        }
        
        .feature-card-title {
            font-size: 1.25rem;
            font-weight: 700;
            color: #111827;
            margin-bottom: 0.5rem;
        }
        
        .feature-card-description {
            color: #6b7280;
            line-height: 1.6;
            font-size: 0.95rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Hero Section - Using Streamlit columns
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.markdown("""
            <h1 class="hero-headline">
                Multi-platform Neuroimaging
                <span class="hero-highlight">Dataset Management</span>
            </h1>
        """, unsafe_allow_html=True)
        
        st.markdown("""
            <p class="hero-subtitle">
                Advanced BIDS-compliant platform for browsing, filtering, and downloading 
                neuroimaging datasets from multiple sources with unified QC workflows and 
                built-in MRI viewing capabilities.
            </p>
        """, unsafe_allow_html=True)
        
        # Quick features
        st.markdown("""
            <div class="quick-feature">
                <div class="quick-feature-icon">•</div>
                <span>7 supported platforms (Pennsieve, OpenNeuro, DANDI, XNAT, HPC, Remote)</span>
            </div>
            <div class="quick-feature">
                <div class="quick-feature-icon">•</div>
                <span>Cross-platform metadata filtering with BIDS validation</span>
            </div>
            <div class="quick-feature">
                <div class="quick-feature-icon">•</div>
                <span>Clinical-grade quality control workflows</span>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
            <div class="visual-card">
                <div class="bidshub-logo">BIDSHub</div>
                <p class="logo-subtitle">BIDSHub Platform</p>
            </div>
        """, unsafe_allow_html=True)
    
    # Spacer
    st.markdown("<br>", unsafe_allow_html=True)
    
    # CTA Button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        datasets = []
        if st.session_state.db:
            datasets = st.session_state.db.get_all_datasets(status='active')
        
        if datasets and len(datasets) > 0:
            if st.button("Go to Dashboard →", type="primary", use_container_width=True, key="goto_dashboard"):
                st.session_state.current_page = 'dashboard'
                st.rerun()
        else:
            if st.button("Getting Started →", type="primary", use_container_width=True, key="getting_started"):
                st.session_state.current_page = 'dashboard'
                st.rerun()
    
    # Spacer
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # Feature Cards Section - Using Streamlit columns
    col1, col2, col3 = st.columns(3, gap="medium")
    
    with col1:
        st.markdown("""
            <div class="feature-card">
                <h4 class="feature-card-title">Secure & Private</h4>
                <p class="feature-card-description">
                    Data remains on your local machine. No cloud upload required. 
                    Full control over your sensitive neuroimaging datasets.
                </p>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
            <div class="feature-card">
                <h4 class="feature-card-title">Fast Processing</h4>
                <p class="feature-card-description">
                    Batch downloads with intelligent caching. Process multiple subjects 
                    simultaneously with optimized connection pooling.
                </p>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="feature-card">
            <h4 class="feature-card-title">Research Ready</h4>
            <p class="feature-card-description">
                Scan-level QC with Pennsieve sync. Validated for TBI and epilepsy 
                research with robust BIDS compliance checking.
            </p>
        </div>
        """, unsafe_allow_html=True)


def page_dashboard():
    """Main dashboard page."""
    render_breadcrumb('dashboard')
    st.markdown('<h1 class="main-header">BIDSHub</h1>', 
                unsafe_allow_html=True)
    
    # Show integrity warning if issues detected (v3.1.1+)
    if st.session_state.get('show_integrity_warning', False):
        issues = st.session_state.get('integrity_issues', {})
        total_issues = sum(issues.values())
        
        if total_issues > 0:
            with st.expander(f"[WARNING] Database Integrity Alert: {total_issues} issue(s) detected", expanded=True):
                for issue_type, count in issues.items():
                    if count > 0:
                        st.markdown(f"- **{issue_type.replace('_', ' ').title()}**: {count}")
                
                st.markdown("Go to **Manage Datasets** to run database maintenance.")
    
    # Get statistics
    stats = st.session_state.db.get_stats()
    
    # Show helpful message for first-time users (v3.1.1+)
    if stats.get('total_subjects', 0) == 0:
        st.info("Welcome to BIDSHub! Get started by adding your first dataset in **Manage Datasets**.")
    
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
            'pennsieve': '[P]',
            'openneuro': '[O]',
            'dandi': '[D]',
            'xnat': '[X]',
            'hpc': '[H]',
            'remote_server': '[R]'
        }
        
        selected_dataset_ids = st.multiselect(
            "Show subjects from:",
            options=[d['id'] for d in datasets],
            format_func=lambda x: next((f"{platform_emojis.get(d['platform'], '[Data]')} {d['name']}" 
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
    
    # Create DataFrame for display (paginated)
    df = create_subject_dataframe(paginated_subjects)
    
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
    
    subject_ids = [s['subject_id'] for s in paginated_subjects]
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
    
    # Initialize agent factory and download manager (v3.1.1+: with multi-platform destination)
    if 'agent_factory' not in st.session_state:
        from src.agent_factory import AgentFactory
        st.session_state.agent_factory = AgentFactory(st.session_state.db)
    
    if 'download_manager' not in st.session_state:
        from src.download_manager import DownloadManager
        st.session_state.download_manager = DownloadManager(
            ps_client=st.session_state.ps_client,
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
    st.markdown('<h2 class="section-header">[Folder] Download Destination</h2>', 
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
                    f"{platform_emojis.get(ds['platform'], '[Data]')} {ds['name']} ({ds['platform'].upper()})": ds['id'] 
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
                
                st.caption(f"[OK] Downloads will be pushed to: {selected_dataset['name']} ({selected_dataset['platform'].upper()})")
        else:
            st.session_state.download_dest_dataset_id = None
            st.session_state.download_dest_platform = None
    
    st.markdown("---")
    
    # Metadata Filtering Section
    st.markdown('<h2 class="section-header">[Filter] Filter by Metadata</h2>', 
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
            if st.button("[Data] Preview Filtered Results", use_container_width=True):
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
                    
                    st.info(f"[Search] Keyword search: found {len(keyword_matches)} matches for {', '.join(filter_criteria['keywords'])}")
                
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
                
                st.success(f"[OK] {len(filtered_ids)} subjects match your criteria")
                
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
        st.info("[L] Active Destination: Downloads saved to local storage only")
    
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
        st.caption(f"[Filter] Filters active: {len(filtered_ids)} subjects selected")
    
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
                        'Type': f"{'[Download]' if session_type == 'Download' else '[Upload]'} {session_type}",
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
                with st.expander("[Data] View Recent Sessions", expanded=False):
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
    st.markdown('<h2 class="section-header">[Settings] Settings</h2>', 
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
                'directory': '[Folder] Directory (select folder from local system)'
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
                    
                    with st.expander(f"[Folder] Preview: {len(files_in_dir)} files ({format_file_size(total_size)})"):
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
    tab1, tab2, tab3 = st.tabs(["[List] Manual QC", "[Auto] Automated QC", "[Cloud] Pennsieve Sync"])
    
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
                
                st.success(f"[OK] Automated QC complete: {pass_count} pass, {warn_count} warnings, {fail_count} fail")
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
        st.success("[OK] No automated QC issues detected")
    
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
            st.dataframe(pd.DataFrame(preview_data), use_container_width=True, hide_index=True)
            if len(unsynced_scans) > 10:
                st.caption(f"Showing 10 of {len(unsynced_scans)} unsynced records")
    
    st.markdown("---")
    
    # Export and Upload Actions
    st.markdown('<h2 class="section-header">Export & Upload QC Results</h2>', 
                unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button(" Export QC CSV", use_container_width=True, disabled=(unsynced_count == 0)):
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
                    st.success(f"[OK] QC CSV exported: {csv_filename}")
                    st.session_state.last_qc_csv_path = csv_path
                    
                    # Offer download
                    with open(csv_path, 'rb') as f:
                        st.download_button(
                            label="Download CSV",
                            data=f,
                            file_name=csv_filename,
                            mime='text/csv',
                            use_container_width=True
                        )
                else:
                    st.error("Failed to export QC CSV")
    
    with col2:
        # Check if we have credentials and a recent CSV
        has_csv = st.session_state.get('last_qc_csv_path') and Path(st.session_state.last_qc_csv_path).exists()
        has_credentials = selected_dataset.get('api_key_encrypted') and selected_dataset.get('api_secret_encrypted')
        
        upload_disabled = not (has_csv and has_credentials and unsynced_count > 0)
        
        if st.button("[Cloud] Push to Pennsieve", 
                    type="primary", 
                    use_container_width=True,
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
                        
                        st.success(f"[OK] QC results uploaded to Pennsieve!")
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
                # Database scans (cloud datasets)
                file_size = scan.get('file_size', 0)
                is_stub = scan.get('download_status') != 'completed'
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
                col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 2, 1])
                
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
                        if st.button("[OK]", key=f"qc_pass_{scan_id}_{idx}", help="Mark as Pass"):
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
                    # View button
                    if st.button("[View]", key=f"view_{scan_id}_{idx}", help="View in Viewer"):
                        st.session_state.selected_scan = scan
                        st.session_state.current_page = 'viewer'
                        st.rerun()
                
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
        if st.button("<- Back to Subjects", use_container_width=True):
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
    
    # Session scans - Dynamic session support
    if not st.session_state.bids_loader:
        st.warning("BIDS loader not initialized")
        return
    
    # Get dataset info
    dataset_id = subject.get('dataset_id')
    
    # Determine if using database scans (cloud) or BIDS loader (local)
    use_db_scans = False
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
            use_db_scans = platform in ['pennsieve', 'openneuro', 'dandi']
    
    # Get all sessions for subject (dynamic)
    all_sessions = []
    
    if use_db_scans:
        # Cloud datasets: query subject_sessions table
        sessions_info = st.session_state.db.get_subject_sessions(subject_id, dataset_id)
        all_sessions = [s['session_id'] for s in sessions_info if s.get('scan_count', 0) > 0]
        
        # Fallback: extract from scans table if subject_sessions empty
        if not all_sessions:
            all_scans = st.session_state.db.get_subject_scans(subject_id)
            all_sessions = list(set(scan.get('session') for scan in all_scans if scan.get('session')))
    else:
        # Local datasets: use BIDS loader
        all_sessions = st.session_state.bids_loader.get_sessions(subject_id)
    
    # Display each session dynamically
    if all_sessions:
        for session_id in sorted(all_sessions):
            # Get scans for this session
            if use_db_scans:
                scans = st.session_state.db.get_subject_scans(subject_id, session_id)
            else:
                scans = st.session_state.bids_loader.get_subject_scans(subject_id, session_id)
            
            # Display session using helper function
            display_session_scans(session_id, scans, subject_id, platform, dataset_remote_id, use_db_scans)
    else:
        st.info("No session data available for this subject")


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
    tab1, tab2, tab3 = st.tabs(["[Export] Export Custom Cohort", "[Data] QC Results", "[List] Subject Lists"])
    
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
                        use_container_width=True,
                        key="download_all"
                    )
        
        with col2:
            st.write("**Complete Subjects**")
            st.caption("2+ sessions")
            if st.button("Export Complete", use_container_width=True, key="export_complete"):
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


def page_transfer():
    """Data Transfer page with WinSCP-style dual-pane interface (v3.1.1+)."""
    render_page_header('transfer', show_back_to_dashboard=True)
    render_breadcrumb('transfer')
    st.markdown('<h1 class="main-header">Data Transfer</h1>', 
                unsafe_allow_html=True)
    
    if not st.session_state.db:
        st.warning("Please complete setup first")
        return
    
    # Initialize agent factory
    if 'agent_factory' not in st.session_state:
        from src.agent_factory import AgentFactory
        st.session_state.agent_factory = AgentFactory(st.session_state.db)
    
    factory = st.session_state.agent_factory
    
    # Get all datasets
    all_datasets = st.session_state.db.get_all_datasets(status='active')
    
    if not all_datasets or len(all_datasets) < 1:
        st.warning("No datasets configured. Add datasets in Manage Datasets page.")
        if st.button("Go to Manage Datasets"):
            st.session_state.current_page = 'manage_datasets'
            st.rerun()
        return
    
    platform_emojis = {
        'local': '[L]',
        'pennsieve': '[P]',
        'openneuro': '[O]',
        'dandi': '[D]',
        'xnat': '[X]',
        'hpc': '[H]',
        'remote_server': '[R]'
    }
    
    # Initialize transfer session state
    if 'transfer_selected_left' not in st.session_state:
        st.session_state.transfer_selected_left = []
    if 'transfer_selected_right' not in st.session_state:
        st.session_state.transfer_selected_right = []
    
    # Connection Settings (Collapsible)
    with st.expander("Connection Settings", expanded=False):
        st.markdown("### Platform Connections")
        st.caption("Configure connection details for platforms if needed")
        
        conn_col1, conn_col2 = st.columns(2)
        
        with conn_col1:
            st.markdown("**Source Connection**")
            st.caption("Connection details loaded from dataset configuration")
            st.info("Edit connections in Manage Datasets page")
        
        with conn_col2:
            st.markdown("**Destination Connection**")
            st.caption("Connection details loaded from dataset configuration")
            st.info("Edit connections in Manage Datasets page")
    
    st.markdown("---")
    
    # WinSCP-Style Dual Pane Interface
    st.markdown('<h2 class="section-header">File Browser</h2>', unsafe_allow_html=True)
    
    # Create dual-pane layout columns
    col1, col_arrow, col2 = st.columns([10, 1, 10])
    
    # LEFT PANE: Source Browser
    with col1:
        st.markdown("### Source Platform")
        
        source_dataset_options = {
            f"{platform_emojis.get(ds['platform'], '[Data]')} {ds['name']}": ds['id']
            for ds in all_datasets
        }
        
        selected_source_display = st.selectbox(
            "Choose source",
            options=list(source_dataset_options.keys()),
            key='transfer_source_dataset',
            label_visibility="collapsed"
        )
        
        source_dataset_id = source_dataset_options[selected_source_display]
        source_dataset = st.session_state.db.get_dataset(source_dataset_id)
        
        # Platform info badge
        st.markdown(f"**{source_dataset['platform'].upper()}** | {len(st.session_state.db.get_subjects_by_dataset(source_dataset_id))} subjects")
        
        # Source file browser with tree-like view
        source_subjects = st.session_state.db.get_subjects_by_dataset(source_dataset_id)
        
        if source_subjects:
            # Create scrollable file list container
            with st.container():
                st.markdown("**Subjects** (Select to transfer →)")
                
                # Display subjects in expandable format
                selected_subjects = []
                for subj in source_subjects[:20]:  # Limit to 20 for performance
                    sessions = st.session_state.db.get_subject_sessions(subj['subject_id'], source_dataset_id) or []
                    scan_count = sum([s.get('scan_count', 0) for s in sessions])
                    
                    # Checkbox for each subject with scan count
                    if st.checkbox(
                        f"{subj['subject_id']} ({scan_count} scans)",
                        key=f"src_{subj['subject_id']}",
                        value=False
                    ):
                        selected_subjects.append(subj['subject_id'])
                
                if len(source_subjects) > 20:
                    st.caption(f"Showing 20 of {len(source_subjects)} subjects. Use filters for more.")
        else:
            st.warning("No subjects indexed")
            st.info("Click 'Sync' in Manage Datasets to index subjects")
            selected_subjects = []
    
    # MIDDLE: Transfer Controls
    with col_arrow:
        st.markdown("<br>" * 8, unsafe_allow_html=True)
        
        # Transfer right button
        if st.button("→", key="transfer_right", help="Transfer selected subjects to destination", 
                    use_container_width=True, type="primary"):
            st.session_state.transfer_direction = 'right'
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Transfer left button (for bidirectional)
        if st.button("←", key="transfer_left", help="Transfer from destination to source",
                    use_container_width=True):
            st.session_state.transfer_direction = 'left'
    
    # RIGHT PANE: Destination Browser
    with col2:
        st.markdown("### Destination Platform")
        
        upload_capable_platforms = ['local', 'pennsieve', 'xnat', 'hpc', 'remote_server']
        
        dest_dataset_options = {
            f"{platform_emojis.get(ds['platform'], '[Data]')} {ds['name']}": ds['id']
            for ds in all_datasets
            if ds['id'] != source_dataset_id and ds['platform'] in upload_capable_platforms
        }
        
        if not dest_dataset_options:
            st.warning("No valid destinations")
            st.info("Add upload-capable datasets in Manage Datasets")
            dest_dataset = None
        else:
            selected_dest_display = st.selectbox(
                "Choose destination",
                options=list(dest_dataset_options.keys()),
                key='transfer_dest_dataset',
                label_visibility="collapsed"
            )
            
            dest_dataset_id = dest_dataset_options[selected_dest_display]
            dest_dataset = st.session_state.db.get_dataset(dest_dataset_id)
            
            # Platform info badge
            st.markdown(f"**{dest_dataset['platform'].upper()}** | {len(st.session_state.db.get_subjects_by_dataset(dest_dataset_id))} subjects")
            
            # Destination file browser
            dest_subjects = st.session_state.db.get_subjects_by_dataset(dest_dataset_id)
            
            with st.container():
                st.markdown("**Current Subjects**")
                
                if dest_subjects:
                    for subj in dest_subjects[:20]:
                        sessions = st.session_state.db.get_subject_sessions(subj['subject_id'], dest_dataset_id) or []
                        scan_count = sum([s.get('scan_count', 0) for s in sessions])
                        st.caption(f"{subj['subject_id']} ({scan_count} scans)")
                    
                    if len(dest_subjects) > 20:
                        st.caption(f"... and {len(dest_subjects) - 20} more")
                else:
                    st.info("No subjects yet")
    
    st.markdown("---")
    
    # TRANSFER OPTIONS (Collapsible)
    with st.expander("Transfer Options", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            transfer_mode = st.radio(
                "Transfer Mode",
                options=['direct', 'cached'],
                format_func=lambda x: 'Direct Stream' if x == 'direct' else 'Via Local Cache',
                key='transfer_mode',
                help="Direct: Stream between platforms. Cached: Download locally first."
            )
        
        with col2:
            preserve_structure = st.checkbox(
                "Preserve BIDS Structure",
                value=True,
                help="Maintain subject/session/modality folder structure"
            )
        
        with col3:
            verify_transfer = st.checkbox(
                "Verify Integrity",
                value=True,
                help="Verify checksums after transfer"
            )
    
    # TRANSFER PREVIEW & EXECUTE
    if selected_subjects and dest_dataset:
        st.markdown("---")
        st.markdown("### Transfer Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Subjects", len(selected_subjects))
        
        with col2:
            total_scans = 0
            for subject_id in selected_subjects:
                scans = st.session_state.db.get_scans_by_subject(subject_id, source_dataset_id)
                total_scans += len(scans)
            st.metric("Scans", total_scans)
        
        with col3:
            total_size = 0
            for subject_id in selected_subjects:
                scans = st.session_state.db.get_scans_by_subject(subject_id, source_dataset_id)
                for scan in scans:
                    total_size += scan.get('file_size', 0)
            
            from src.utils import format_file_size
            st.metric("Size", format_file_size(total_size))
        
        with col4:
            st.metric("Mode", "Direct" if transfer_mode == 'direct' else "Cached")
        
        # Transfer route
        st.info(f"{platform_emojis.get(source_dataset['platform'], '[Data]')} {source_dataset['name']} → {platform_emojis.get(dest_dataset['platform'], '[Data]')} {dest_dataset['name']}")
        
        # Execute button
        if st.button("Start Transfer", type="primary", use_container_width=True, key="execute_transfer"):
            execute_transfer(
                source_dataset=source_dataset,
                dest_dataset=dest_dataset,
                subject_ids=selected_subjects,
                transfer_mode=transfer_mode,
                preserve_structure=preserve_structure,
                verify=verify_transfer,
                factory=factory,
                database=st.session_state.db
            )
    
    else:
        if not selected_subjects:
            st.info("← Select subjects from source to begin transfer")
        elif not dest_dataset:
            st.warning("Configure a valid destination platform")
    
    st.markdown("---")
    
    # Transfer History
    st.markdown('<h2 class="section-header"> Recent Transfers</h2>', 
                unsafe_allow_html=True)
    
    # Query transfer history from metadata table
    try:
        history_query = """
            SELECT key, value FROM metadata 
            WHERE key LIKE 'transfer_session_%'
            ORDER BY updated_at DESC
            LIMIT 10
        """
        history_rows = st.session_state.db.execute_query(history_query, fetch=True)
        
        if history_rows:
            history_data = []
            for row in history_rows:
                import json
                transfer_info = json.loads(row['value'])
                history_data.append({
                    'Date': transfer_info.get('timestamp', 'Unknown')[:19],
                    'Source': transfer_info.get('source_name', 'Unknown'),
                    'Destination': transfer_info.get('dest_name', 'Unknown'),
                    'Subjects': transfer_info.get('successful', 0),
                    'Status': '[OK] Success' if transfer_info.get('failed', 0) == 0 else f"[WARNING] {transfer_info.get('failed', 0)} failed"
                })
            
            import pandas as pd
            history_df = pd.DataFrame(history_data)
            st.dataframe(history_df, use_container_width=True, hide_index=True)
        else:
            st.info("No transfer history yet")
    except Exception as e:
        st.warning(f"Could not load transfer history: {e}")


def execute_transfer(source_dataset: Dict, dest_dataset: Dict, subject_ids: List[str],
                    transfer_mode: str, preserve_structure: bool, verify: bool,
                    factory, database):
    """
    Execute bidirectional data transfer between platforms (v3.1.1+).
    
    Args:
        source_dataset: Source dataset dict
        dest_dataset: Destination dataset dict
        subject_ids: List of subject IDs to transfer
        transfer_mode: 'direct' or 'cached'
        preserve_structure: Whether to preserve BIDS structure
        verify: Whether to verify transfer integrity
        factory: AgentFactory instance
        database: Database instance
    """
    import time
    from src.utils import format_file_size
    from src.transfer_recovery import TransferRecovery
    
    # Initialize recovery manager
    recovery = TransferRecovery(max_retries=3, retry_delay=2.0)
    
    st.markdown("---")
    st.markdown('<h2 class="section-header"> Transfer in Progress</h2>', 
                unsafe_allow_html=True)
    
    # Create agents with standardized error handling (v3.1.1+)
    try:
        source_agent = factory.get_agent(source_dataset['id']) if source_dataset['platform'] != 'local' else None
        dest_agent = factory.get_agent(dest_dataset['id']) if dest_dataset['platform'] != 'local' else None
    except Exception as e:
        source_platform = source_dataset['platform']
        dest_platform = dest_dataset['platform']
        st.error(handle_agent_error(e, source_platform, 'agent creation'))
        st.error(ErrorMessages.get_platform_help(source_platform))
        return
    
    # Progress tracking
    progress_container = st.container()
    
    with progress_container:
        progress_bar = st.progress(0)
        status_col1, status_col2, status_col3 = st.columns(3)
        status_text = st.empty()
        details_expander = st.expander("[Data] Transfer Details", expanded=True)
    
    total_subjects = len(subject_ids)
    successful = 0
    failed = 0
    start_time = time.time()
    transfer_log = []
    
    # Process each subject
    for i, subject_id in enumerate(subject_ids):
        # Update status
        elapsed = time.time() - start_time
        if i > 0 and elapsed > 0:
            avg_time = elapsed / i
            eta_seconds = avg_time * (total_subjects - i)
            eta_str = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
        else:
            eta_str = "Calculating..."
        
        status_text.markdown(f"""
        **Transferring subject {i+1}/{total_subjects}**: `{subject_id}`  
        **Progress**: {(i/total_subjects)*100:.1f}% | **ETA**: {eta_str}
        """)
        
        with status_col1:
            st.metric("Subjects", f"{i}/{total_subjects}")
        with status_col2:
            st.metric("Success", successful)
        with status_col3:
            st.metric("Failed", failed, delta_color="inverse")
        
        subject_start_time = time.time()
        
        # Get scans for this subject
        scans = database.get_scans_by_subject(subject_id, source_dataset['id'])
        
        if not scans:
            failed += 1
            transfer_log.append({
                'subject': subject_id,
                'status': '[X] No scans found',
                'files': 0,
                'time': '0s'
            })
            continue
        
        # Transfer each scan
        transfer_success = True
        transferred_count = 0
        
        for scan in scans:
            try:
                # Determine source path
                if source_dataset['platform'] == 'local':
                    source_path = scan['file_path']
                else:
                    # For cloud platforms, need to download first
                    source_path = scan['file_path']
                
                # Determine destination path using standardized BIDS utils (v3.1.1+)
                file_obj = Path(scan['file_path'])
                
                if preserve_structure:
                    bids_path = extract_bids_path(scan['file_path'])
                else:
                    bids_path = file_obj.name
                
                # Execute transfer based on mode
                if transfer_mode == 'direct':
                    # Direct transfer (for SSH platforms)
                    if source_dataset['platform'] == 'local' and dest_dataset['platform'] in ['hpc', 'remote_server', 'xnat', 'pennsieve']:
                        # Local -> Destination
                        if dest_dataset['platform'] in ['hpc', 'remote_server']:
                            base_path = dest_dataset.get('dataset_id_external', '/data/bids')
                            dest_path = f"{base_path}/{bids_path}"
                            success, _ = recovery.retry_with_backoff(
                                dest_agent.upload_file,
                                f"Upload {file_obj.name}",
                                source_path,
                                dest_path
                            )
                        elif dest_dataset['platform'] == 'xnat':
                            success, _ = recovery.retry_with_backoff(
                                dest_agent.upload_file,
                                f"Upload {file_obj.name} to XNAT",
                                local_path=source_path,
                                project_id=dest_dataset.get('dataset_id_external'),
                                subject_id=subject_id
                            )
                        elif dest_dataset['platform'] == 'pennsieve':
                            remote_dir = str(Path(bids_path).parent)
                            success, _ = recovery.retry_with_backoff(
                                dest_agent.upload_file,
                                f"Upload {file_obj.name} to Pennsieve",
                                local_path=source_path,
                                dataset_name=dest_dataset.get('dataset_id_external') or dest_dataset['name'],
                                remote_path=remote_dir,
                                api_key=dest_dataset.get('api_key_encrypted'),
                                api_secret=dest_dataset.get('api_secret_encrypted')
                            )
                    
                    elif source_dataset['platform'] in ['hpc', 'remote_server'] and dest_dataset['platform'] == 'local':
                        # HPC/Remote -> Local
                        base_path = source_dataset.get('dataset_id_external', '/data/bids')
                        remote_path = f"{base_path}/{bids_path}"
                        local_dest = str(Path(dest_dataset.get('root_path', './data')) / bids_path)
                        
                        success, _ = recovery.retry_with_backoff(
                            source_agent.download_file,
                            f"Download {file_obj.name}",
                            remote_path,
                            local_dest
                        )
                    
                    else:
                        # For other combinations, use cached mode
                        transfer_mode = 'cached'
                        status_text.text(f"Direct transfer not supported, using cached mode")
                
                if transfer_mode == 'cached':
                    # Download to local temp, then upload
                    temp_dir = Path('./data/temp_transfer') / f"transfer_{int(time.time())}"
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    
                    temp_file = temp_dir / bids_path
                    temp_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Download from source (v3.1.1+ expanded support)
                    if source_dataset['platform'] == 'local':
                        # Copy local file
                        import shutil
                        shutil.copy2(source_path, str(temp_file))
                        download_success = True
                    
                    elif source_dataset['platform'] in ['hpc', 'remote_server']:
                        # SSH platforms
                        base_path = source_dataset.get('dataset_id_external', '/data/bids')
                        remote_path = f"{base_path}/{bids_path}"
                        download_success, _ = recovery.retry_with_backoff(
                            source_agent.download_file,
                            f"Download {file_obj.name}",
                            remote_path,
                            str(temp_file)
                        )
                    
                    elif source_dataset['platform'] == 'pennsieve':
                        # Pennsieve download
                        package_id = scan.get('package_id') or scan.get('scan_id')
                        if package_id:
                            download_success, _ = recovery.retry_with_backoff(
                                source_agent.download_file,
                                f"Download {file_obj.name} from Pennsieve",
                                package_id,
                                str(temp_file)
                            )
                        else:
                            download_success = False
                    
                    elif source_dataset['platform'] == 'openneuro':
                        # OpenNeuro download
                        download_success, _ = recovery.retry_with_backoff(
                            source_agent.download_file,
                            f"Download {file_obj.name} from OpenNeuro",
                            source_dataset.get('dataset_id_external'),
                            bids_path,
                            str(temp_file)
                        )
                    
                    elif source_dataset['platform'] == 'dandi':
                        # DANDI download (if file has asset ID)
                        asset_id = scan.get('asset_id') or scan.get('scan_id')
                        if asset_id:
                            download_success, _ = recovery.retry_with_backoff(
                                source_agent.download_file,
                                f"Download {file_obj.name} from DANDI",
                                asset_id,
                                str(temp_file)
                            )
                        else:
                            download_success = False
                    
                    elif source_dataset['platform'] == 'xnat':
                        # XNAT download
                        project_id = source_dataset.get('dataset_id_external')
                        experiment_id = scan.get('experiment_id') or f"{subject_id}_MR1"
                        scan_id = scan.get('scan_id') or scan.get('package_id')
                        
                        if project_id and experiment_id and scan_id:
                            # XNAT needs custom download logic
                            try:
                                import xnat
                                with xnat.connect(
                                    source_dataset.get('server_url'),
                                    user=source_dataset.get('api_key_encrypted'),
                                    password=source_dataset.get('api_secret_encrypted')
                                ) as session:
                                    exp = session.projects[project_id].subjects[subject_id].experiments[experiment_id]
                                    scan_obj = exp.scans[scan_id]
                                    
                                    for resource in scan_obj.resources.values():
                                        for file in resource.files.values():
                                            if file.label == file_obj.name:
                                                file.download(str(temp_file))
                                                download_success = True
                                                break
                            except Exception as e:
                                logger.error(f"XNAT download failed: {e}")
                                download_success = False
                        else:
                            download_success = False
                    
                    else:
                        download_success = False
                        status_text.warning(f"Cached transfer from {source_dataset['platform']} not supported")
                    
                    # Upload to destination
                    if download_success:
                        if dest_dataset['platform'] == 'local':
                            # Copy to local destination
                            import shutil
                            local_dest = Path(dest_dataset.get('root_path', './data')) / bids_path
                            local_dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(str(temp_file), str(local_dest))
                            success = True
                        elif dest_dataset['platform'] in ['hpc', 'remote_server']:
                            base_path = dest_dataset.get('dataset_id_external', '/data/bids')
                            dest_path = f"{base_path}/{bids_path}"
                            success, _ = recovery.retry_with_backoff(
                                dest_agent.upload_file,
                                f"Upload {file_obj.name}",
                                str(temp_file),
                                dest_path
                            )
                        elif dest_dataset['platform'] == 'xnat':
                            success, _ = recovery.retry_with_backoff(
                                dest_agent.upload_file,
                                f"Upload {file_obj.name} to XNAT",
                                local_path=str(temp_file),
                                project_id=dest_dataset.get('dataset_id_external'),
                                subject_id=subject_id
                            )
                        elif dest_dataset['platform'] == 'pennsieve':
                            remote_dir = str(Path(bids_path).parent)
                            success, _ = recovery.retry_with_backoff(
                                dest_agent.upload_file,
                                f"Upload {file_obj.name} to Pennsieve",
                                local_path=str(temp_file),
                                dataset_name=dest_dataset.get('dataset_id_external') or dest_dataset['name'],
                                remote_path=remote_dir,
                                api_key=dest_dataset.get('api_key_encrypted'),
                                api_secret=dest_dataset.get('api_secret_encrypted')
                            )
                    else:
                        success = False
                    
                    # Cleanup temp file
                    try:
                        temp_file.unlink()
                    except:
                        pass
                
                if success:
                    # Verify transfer integrity if requested (v3.1.1+)
                    if verify and transfer_mode == 'cached':
                        if dest_dataset['platform'] == 'local':
                            # Verify local file
                            local_dest = Path(dest_dataset.get('root_path', './data')) / bids_path
                            if not local_dest.exists():
                                st.warning(f"Transfer verification failed: {local_dest.name} not found")
                                transfer_success = False
                                break
                            
                            # Verify size
                            expected_size = scan.get('file_size', 0)
                            actual_size = local_dest.stat().st_size
                            
                            if expected_size > 0 and actual_size != expected_size:
                                st.warning(f"Size mismatch: {local_dest.name} (expected {expected_size}, got {actual_size})")
                                transfer_success = False
                                break
                    
                    transferred_count += 1
                else:
                    transfer_success = False
                    break
            
            except Exception as e:
                error_msg = handle_agent_error(e, source_dataset['platform'], 'transfer')
                st.error(f"Error transferring subject {subject_id}: {error_msg}")
                transfer_success = False
        
        subject_elapsed = time.time() - subject_start_time
        
        if transfer_success and transferred_count > 0:
            successful += 1
            transfer_log.append({
                'subject': subject_id,
                'status': '[OK] Success',
                'files': transferred_count,
                'time': f"{subject_elapsed:.1f}s"
            })
        else:
            failed += 1
            transfer_log.append({
                'subject': subject_id,
                'status': '[X] Failed',
                'files': transferred_count,
                'time': f"{subject_elapsed:.1f}s"
            })
        
        # Update progress
        progress_bar.progress(min((i + 1) / total_subjects, 0.99))
        
        # Update details
        with details_expander:
            if transfer_log:
                import pandas as pd
                log_df = pd.DataFrame(transfer_log)
                st.dataframe(log_df, use_container_width=True, hide_index=True)
    
    # Complete
    progress_bar.progress(1.0)
    total_elapsed = time.time() - start_time
    
    status_text.empty()
    
    if successful > 0:
        st.success(f"""
        [OK] **Transfer Complete!**  
        **Subjects**: {successful}/{total_subjects} ({(successful/total_subjects)*100:.1f}%)  
        **Time**: {int(total_elapsed // 60)}m {int(total_elapsed % 60)}s  
        **Avg Time/Subject**: {total_elapsed/successful:.1f}s
        """)
    
    if failed > 0:
        st.error(f"[X] {failed} subjects failed to transfer")
    
    # Save transfer session to history
    database.execute_query("""
        INSERT INTO metadata (key, value) 
        VALUES (?, ?)
    """, (
        f"transfer_session_{int(time.time())}",
        json.dumps({
            'timestamp': datetime.now().isoformat(),
            'source_platform': source_dataset['platform'],
            'source_name': source_dataset['name'],
            'dest_platform': dest_dataset['platform'],
            'dest_name': dest_dataset['name'],
            'total_subjects': total_subjects,
            'successful': successful,
            'failed': failed,
            'duration': total_elapsed,
            'mode': transfer_mode
        })
    ))
    
    # Show failed transfers if any
    failed_list = recovery.get_failed_transfers()
    if failed_list:
        st.warning(f"[WARNING] {len(failed_list)} file(s) failed after {recovery.max_retries + 1} attempts")
        with st.expander("View Failed Transfers"):
            for failure in failed_list:
                st.markdown(f"- **{failure['operation']}**: {failure['error']} ({failure['attempts']} attempts)")
    
    # Cleanup temp directory
    try:
        import shutil
        temp_dir = Path('./data/temp_transfer')
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    except:
        pass
    
    time.sleep(2)


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
        # Viewer page accessed via subject detail page
        st.info("Access viewer from Subject Detail page")
        page_home()
    else:
        page_home()


if __name__ == "__main__":
    main()
