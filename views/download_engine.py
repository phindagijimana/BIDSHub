"""Download/upload execution engine for the Download Manager page.

The per-platform download routines and the upload runner were split out of
``views/downloads.py`` so that module holds only the page UI. These functions
still drive Streamlit progress widgets, so they live under ``views/`` rather
than ``src/``. They are invoked from ``views.downloads.page_downloads``.
"""
from datetime import datetime
from pathlib import Path
from typing import List
import json
import os
import pandas as pd
import streamlit as st
from src.error_messages import ErrorMessages, handle_agent_error
from src.ui_calm import DOWNLOAD_QUEUE_PLATFORMS, quiet_queue_empty, toast_note


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
                st.dataframe(log_df, width='stretch', hide_index=True)
    
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
                st.dataframe(log_df, width='stretch', hide_index=True)
    
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
                st.dataframe(log_df, width='stretch', hide_index=True)
    
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
            st.dataframe(log_df, width='stretch', hide_index=True)
    
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
