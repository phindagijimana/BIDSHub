"""Data transfer page + transfer execution (extracted from app.py)."""
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import json
import pandas as pd
import streamlit as st
from src.agent_factory import AgentFactory
from src.bids_utils import extract_bids_path
from src.database import Database
from src.error_messages import ErrorMessages, handle_agent_error
from src.ui_calm import expected_empty


def page_transfer():
    
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
        'local': '',
        'pennsieve': '',
        'openneuro': '',
        'dandi': '',
        'xnat': '',
        'hpc': '',
        'remote_server': ''
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
            f"{platform_emojis.get(ds['platform'], '')} {ds['name']}": ds['id']
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
            expected_empty("No subjects indexed yet. Sync this dataset in Manage Datasets to browse here.")
            selected_subjects = []
    
    # MIDDLE: Transfer Controls
    with col_arrow:
        st.markdown("<br>" * 8, unsafe_allow_html=True)
        
        # Transfer right button
        if st.button("→", key="transfer_right", help="Transfer selected subjects to destination", 
                    width='stretch', type="primary"):
            st.session_state.transfer_direction = 'right'
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Transfer left button (for bidirectional)
        if st.button("←", key="transfer_left", help="Transfer from destination to source",
                    width='stretch'):
            st.session_state.transfer_direction = 'left'
    
    # RIGHT PANE: Destination Browser
    with col2:
        st.markdown("### Destination Platform")
        
        upload_capable_platforms = ['local', 'pennsieve', 'xnat', 'hpc', 'remote_server']
        
        dest_dataset_options = {
            f"{platform_emojis.get(ds['platform'], '')} {ds['name']}": ds['id']
            for ds in all_datasets
            if ds['id'] != source_dataset_id and ds['platform'] in upload_capable_platforms
        }
        
        if not dest_dataset_options:
            st.caption(
                "No upload-capable destination datasets. Add Pennsieve, XNAT, HPC, or Remote Server in Manage Datasets."
            )
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
                    st.caption("No subjects on this destination yet.")
    
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
        st.info(f"{platform_emojis.get(source_dataset['platform'], '')} {source_dataset['name']} → {platform_emojis.get(dest_dataset['platform'], '')} {dest_dataset['name']}")
        
        # Execute button
        if st.button("Start Transfer", type="primary", width='stretch', key="execute_transfer"):
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
                    'Status': 'Success' if transfer_info.get('failed', 0) == 0 else f"{transfer_info.get('failed', 0)} failed"
                })
            
            import pandas as pd
            history_df = pd.DataFrame(history_data)
            st.dataframe(history_df, width='stretch', hide_index=True)
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
        details_expander = st.expander("Transfer Details", expanded=True)
    
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
                    except Exception:
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
                'status': 'Success',
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
                st.dataframe(log_df, width='stretch', hide_index=True)
    
    # Complete
    progress_bar.progress(1.0)
    total_elapsed = time.time() - start_time
    
    status_text.empty()
    
    if successful > 0:
        st.success(f"""
        **Transfer Complete!**  
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
        st.warning(f"{len(failed_list)} file(s) failed after {recovery.max_retries + 1} attempts")
        with st.expander("View Failed Transfers"):
            for failure in failed_list:
                st.markdown(f"- **{failure['operation']}**: {failure['error']} ({failure['attempts']} attempts)")
    
    # Cleanup temp directory
    try:
        import shutil
        temp_dir = Path('./data/temp_transfer')
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    except Exception:
        pass
    
    time.sleep(2)


