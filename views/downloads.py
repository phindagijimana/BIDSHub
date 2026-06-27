"""Download manager page + download/upload execution (extracted from app.py)."""
from datetime import datetime
from pathlib import Path
from typing import List
import json
import os
import pandas as pd
import streamlit as st
from src.agent_factory import AgentFactory
from src.error_messages import ErrorMessages, handle_agent_error
from src.metadata_filter import MetadataFilter
from src.pennsieve_agent import check_available_space
from src.theme import format_file_size
from src.ui_calm import DOWNLOAD_QUEUE_PLATFORMS, quiet_queue_empty, toast_note, toast_ok


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




def page_downloads():
    """Download manager page."""
    from app import get_available_sessions, render_breadcrumb, render_page_header  # lazy

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


