"""Dataset setup + management pages (extracted from app.py)."""
from datetime import datetime
from pathlib import Path
from typing import Optional
import streamlit as st
from src.agent_factory import AgentFactory
from src.bids_loader import BIDSLoader
from src.bids_validator import validate_bids_dataset  # pre-existing: used but never imported in app.py
from src.database import Database
from src.error_messages import ErrorMessages
from src.openneuro_agent import OpenNeuroAgent, check_openneuro_connection
from src.pennsieve_client import PennsieveClient


def page_setup():
    """Setup page for first-time configuration."""
    from app import render_breadcrumb  # lazy: avoid circular import

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
    from app import render_breadcrumb, render_page_header  # lazy: avoid circular import

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


