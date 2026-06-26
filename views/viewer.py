"""NIfTI viewer page (extracted from app.py)."""
import os
from pathlib import Path
import streamlit as st
from src.database import Database
from src.ui_calm import toast_ok


def page_viewer():
    """Standalone NIfTI Viewer page with file browser (v3.1.2+)."""
    from app import render_breadcrumb, render_page_header  # lazy: avoid circular import

    render_page_header('viewer', show_back_to_dashboard=True)
    render_breadcrumb('viewer')
    st.markdown('<h1 class="main-header">NIfTI Viewer</h1>', 
                unsafe_allow_html=True)
    
    # Top row: intro + file browser header side by side; browse controls stay compact above the viewer
    top_intro, top_fb = st.columns([1, 1], gap="medium")
    with top_intro:
        st.markdown("Browse and visualize any NIfTI image")
    with top_fb:
        st.markdown("### File Browser")
    
    # Initialize agent factory for DANDI downloads
    if 'agent_factory' not in st.session_state:
        from src.agent_factory import AgentFactory
        st.session_state.agent_factory = AgentFactory(st.session_state.db)
    
    browse_mode = st.radio(
        "Browse Mode",
        options=["From Indexed Datasets", "From File System"],
        horizontal=True,
        key="viewer_browse_mode"
    )
    
    st.markdown("---")
    
    if browse_mode == "From File System":
        st.markdown("**Browse Local Files**")
        fp_col, dir_col = st.columns([1, 1], gap="medium")
        with fp_col:
            file_path_input = st.text_input(
                "NIfTI File Path",
                placeholder="/path/to/file.nii.gz",
                help="Enter the full path to a NIfTI file (.nii or .nii.gz)",
                key="viewer_file_path"
            )
        with dir_col:
            if 'viewer_current_dir' not in st.session_state:
                st.session_state.viewer_current_dir = str(Path.home())
            current_dir = st.text_input(
                "Browse Directory",
                value=st.session_state.viewer_current_dir,
                key="viewer_dir_input",
                help="Enter directory path to browse"
            )
        
        if current_dir and os.path.isdir(current_dir):
            st.session_state.viewer_current_dir = current_dir
            
            try:
                nifti_files = []
                for item in sorted(os.listdir(current_dir)):
                    if item.endswith('.nii') or item.endswith('.nii.gz'):
                        full_path = os.path.join(current_dir, item)
                        if os.path.isfile(full_path):
                            nifti_files.append(item)
                
                if nifti_files:
                    st.markdown(f"**NIfTI Files in Directory** ({len(nifti_files)} found)")
                    list_col, btn_col = st.columns([3, 1], gap="medium")
                    with list_col:
                        selected_file = st.selectbox(
                            "Select File",
                            options=nifti_files,
                            key="viewer_file_select"
                        )
                    with btn_col:
                        st.markdown("")  # align with selectbox label
                        st.markdown("")
                        if selected_file:
                            file_path_input = os.path.join(current_dir, selected_file)
                            if st.button("Load in Viewer →", use_container_width=True, type="primary", key="viewer_load_fs_pick"):
                                st.session_state.viewer_selected_file = file_path_input
                                st.session_state.viewer_file_loaded = True
                                st.rerun()
                else:
                    st.info("No NIfTI files found in this directory")
            except PermissionError:
                st.error("Permission denied to read directory")
            except Exception as e:
                st.error(f"Error reading directory: {str(e)}")
        
        if file_path_input and os.path.exists(file_path_input):
            st.caption(f"File exists: {Path(file_path_input).name}")
            if st.button("Load from Path →", use_container_width=True, type="secondary", key="viewer_load_fs_path"):
                st.session_state.viewer_selected_file = file_path_input
                st.session_state.viewer_file_loaded = True
                st.rerun()
    
    else:
        st.markdown("**Browse Indexed Datasets**")
        if not st.session_state.db:
            st.warning("Database not initialized")
        else:
            all_datasets = st.session_state.db.get_all_datasets(status='active')
            if not all_datasets:
                st.info("No datasets available. Add datasets in Manage Datasets or switch to 'From File System' mode.")
            else:
                from src.utils import platform_label
                dataset_options = {f"[{platform_label(ds['platform'])}] {ds['name']}": ds['id'] for ds in all_datasets}
                c_ds, c_sub, c_ses, c_scan = st.columns([2, 1, 1, 1], gap="small")
                
                with c_ds:
                    selected_dataset_name = st.selectbox(
                        "Select Dataset",
                        options=list(dataset_options.keys()),
                        key="viewer_dataset_select"
                    )
                
                selected_dataset_id = dataset_options[selected_dataset_name] if selected_dataset_name else None
                subjects = (
                    st.session_state.db.get_all_subjects(filters={'dataset_id': selected_dataset_id})
                    if selected_dataset_id is not None else []
                )
                
                selected_subject_id = None
                with c_sub:
                    if not subjects:
                        st.caption("No subjects indexed. Sync in Manage Datasets or use File System mode.")
                    else:
                        subject_options = [s['subject_id'] for s in subjects]
                        selected_subject_id = st.selectbox(
                            "Select Subject",
                            options=subject_options,
                            key="viewer_subject_select"
                        )
                
                sessions = []
                selected_session_id = None
                if selected_subject_id and selected_dataset_id:
                    sessions = st.session_state.db.get_subject_sessions(selected_subject_id, selected_dataset_id)
                
                with c_ses:
                    if selected_subject_id and selected_dataset_id:
                        session_ids = [s['session_id'] for s in sessions]
                        if session_ids:
                            selected_session_id = st.selectbox(
                                "Select Session",
                                options=session_ids,
                                key="viewer_session_select"
                            )
                        elif not sessions:
                            st.caption(f"No sessions for {selected_subject_id}")
                
                scans = []
                nifti_scans = []
                scan_labels = []
                selected_scan_idx = None
                selected_dataset = None
                if selected_session_id and selected_subject_id and selected_dataset_id:
                    # Scope to the selected dataset: a BIDS label like 'sub-01'
                    # can exist in several datasets, and an unscoped lookup would
                    # resolve to another dataset's (possibly undownloaded) file.
                    scans = [
                        s for s in st.session_state.db.get_scans_by_subject(
                            selected_subject_id, dataset_id=selected_dataset_id
                        )
                        if s.get('session') == selected_session_id
                    ]
                    selected_dataset = next((d for d in all_datasets if d['id'] == selected_dataset_id), None)
                    is_openneuro = selected_dataset and selected_dataset.get('platform') == 'openneuro'
                    
                    if not scans:
                        if is_openneuro:
                            st.caption("OpenNeuro data must be downloaded locally before viewing here.")
                            with st.expander("How to view OpenNeuro scans", expanded=False):
                                st.markdown("""
                                1. Open **Download Manager**
                                2. Queue subjects or sessions and download
                                3. Return here and use **From File System** to open the files
                                """)
                        else:
                            st.caption(f"No scans found for session {selected_session_id}.")
                    
                    nifti_scans = [
                        s for s in scans
                        if s['file_path'].endswith('.nii') or s['file_path'].endswith('.nii.gz')
                    ]
                    if not nifti_scans and scans:
                        st.warning("No NIfTI files found in this session")
                    for scan in nifti_scans:
                        modality = scan.get('modality', 'unknown')
                        suffix = scan.get('suffix', '')
                        label = f"{modality}_{suffix}" if suffix else modality
                        scan_labels.append(label)
                
                with c_scan:
                    if nifti_scans:
                        selected_scan_idx = st.selectbox(
                            "Select Scan",
                            options=list(range(len(nifti_scans))),
                            format_func=lambda i: scan_labels[i],
                            key="viewer_scan_select"
                        )
                
                if nifti_scans and selected_scan_idx is not None:
                    selected_scan = nifti_scans[selected_scan_idx]
                    with st.expander("Selected scan details", expanded=False):
                        st.caption(f"File: {Path(selected_scan['file_path']).name}")
                        st.caption(f"Modality: {selected_scan.get('modality', 'N/A')}")
                        st.caption(f"Suffix: {selected_scan.get('suffix', 'N/A')}")
                    if st.button("Load in Viewer →", use_container_width=True, type="primary", key="viewer_load_indexed"):
                        st.session_state.viewer_selected_file = selected_scan['file_path']
                        st.session_state.viewer_dataset_id = selected_dataset_id
                        st.session_state.viewer_dataset_platform = selected_dataset.get('platform') if selected_dataset else None
                        st.session_state.viewer_file_loaded = True
                        st.rerun()
    
    st.markdown("---")
    st.markdown("### Viewer")
    
    # Check if file is loaded
    file_path = st.session_state.get('viewer_selected_file', '')
    file_loaded = 'viewer_file_loaded' in st.session_state and st.session_state.viewer_file_loaded
    
    # Handle DANDI files specially (need to download temporarily)
    local_file_path = file_path
    is_dandi = st.session_state.get('viewer_dataset_platform') == 'dandi'
    
    if file_loaded and file_path:
        if is_dandi and not os.path.exists(file_path):
            # DANDI file - need to download temporarily
            st.markdown(f"**File:** {Path(file_path).name}")
            st.caption(f"Platform: DANDI (streaming)")
            
            # Get dataset info
            dataset_id = st.session_state.get('viewer_dataset_id')
            dataset = st.session_state.db.get_dataset(dataset_id)
            dandiset_id = dataset['dataset_id_external']
            
            # Create temp directory
            temp_dir = Path('data/temp_viewer')
            temp_dir.mkdir(parents=True, exist_ok=True)
            local_file_path = temp_dir / Path(file_path).name
            
            # Check if already downloaded
            if not local_file_path.exists():
                with st.spinner(f"Downloading from DANDI... (this may take a moment for large files)"):
                    # Get agent for this dataset (platform determined automatically)
                    agent = st.session_state.agent_factory.get_agent(dataset_id)
                    
                    # Download file
                    success = agent.download_file(
                        dandiset_id=dandiset_id,
                        asset_path=file_path,
                        local_path=str(local_file_path)
                    )
                    
                    if not success:
                        st.error("Failed to download file from DANDI")
                        st.session_state.viewer_file_loaded = False
                        local_file_path = None
                    else:
                        toast_ok("File downloaded — ready to view.")
            else:
                st.caption("Using cached copy in temp folder.")
        
        elif not os.path.exists(file_path):
            st.error(f"File not found: {file_path}")
            st.session_state.viewer_file_loaded = False
            local_file_path = None
    
    # Display file info or empty state
    if file_loaded and local_file_path and os.path.exists(local_file_path):
        if not is_dandi:
            st.markdown(f"**File:** {Path(local_file_path).name}")
            st.caption(f"Path: {local_file_path}")
        
        # Check file size before attempting to load (max 500MB for browser-based viewing)
        file_size_mb = os.path.getsize(local_file_path) / (1024 * 1024)
        
        if file_size_mb > 500:
            st.warning(
                f"File too large for in-browser viewing ({file_size_mb:.1f} MB; limit 500 MB). "
                "Open it in FSLeyes, ITK-SNAP, or another desktop viewer instead."
            )
            file_loaded = False
        else:
            # Get file info using nibabel
            import nibabel as nib
            try:
                nifti_img = nib.load(str(local_file_path))
                img_data = nifti_img.get_fdata()
                
                col_info1, col_info2, col_info3 = st.columns(3)
                with col_info1:
                    st.metric("Dimensions", f"{img_data.shape[0]} × {img_data.shape[1]} × {img_data.shape[2]}")
                with col_info2:
                    voxel_sizes = nifti_img.header.get_zooms()
                    st.metric("Voxel Size (mm)", f"{voxel_sizes[0]:.2f} × {voxel_sizes[1]:.2f} × {voxel_sizes[2]:.2f}")
                with col_info3:
                    st.metric("Data Type", str(img_data.dtype))
            except Exception as e:
                st.error(f"Failed to load file info: {str(e)}")
    else:
        if not file_loaded:
            st.caption("No file loaded — use the browse controls above to select a NIfTI file.")
    
    st.markdown("---")
    
    # niivue viewer with 3-plane view (axial, sagittal, coronal)
    import streamlit.components.v1 as components
    import base64
    
    # Prepare file data for niivue (file size already checked above)
    if file_loaded and local_file_path and os.path.exists(local_file_path):
        # Read file and convert to base64 for embedding
        with open(local_file_path, 'rb') as f:
            file_bytes = f.read()
            file_b64 = base64.b64encode(file_bytes).decode()
        
        file_name = Path(local_file_path).name
        
        # niivue HTML with file loaded
        niivue_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    html, body {{ 
                        margin: 0; 
                        padding: 0; 
                        width: 100%;
                        height: 100%;
                        overflow: hidden;
                    }}
                        #canvas {{ 
                            width: 100vw; 
                            height: 720px;
                            display: block;
                        }}
                </style>
            </head>
            <body>
                <canvas id="canvas"></canvas>
                <script src="https://unpkg.com/@niivue/niivue@0.44.0/dist/niivue.umd.js"></script>
                <script>
                    // Convert base64 to ArrayBuffer
                    function base64ToArrayBuffer(base64) {{
                        const binaryString = atob(base64);
                        const bytes = new Uint8Array(binaryString.length);
                        for (let i = 0; i < binaryString.length; i++) {{
                            bytes[i] = binaryString.charCodeAt(i);
                        }}
                        return bytes.buffer;
                    }}
                    
                    // Initialize niivue with better defaults
                    const nv = new niivue.Niivue({{
                        show3Dcrosshair: true,
                        backColor: [0, 0, 0, 1],
                        crosshairColor: [0, 0.176, 0.447, 1],
                        textHeight: 0.05,
                        colorbarHeight: 0.05
                    }});
                    
                    nv.attachToCanvas(document.getElementById('canvas'));
                    
                    // Load NIfTI from base64 using Blob approach
                    const fileData = base64ToArrayBuffer('{file_b64}');
                    const blob = new Blob([fileData], {{ type: 'application/gzip' }});
                    const blobUrl = URL.createObjectURL(blob);
                    
                    const volumeList = [{{
                        url: blobUrl,
                        name: '{file_name}',
                        colormap: 'gray'
                    }}];
                    
                    nv.loadVolumes(volumeList).then(() => {{
                        nv.setSliceType(nv.sliceTypeMultiplanar);

                        // Ensure canvas fills and renders properly
                        setTimeout(() => {{
                            nv.drawScene();
                        }}, 100);
                        
                        console.log('NIfTI loaded successfully');
                        URL.revokeObjectURL(blobUrl);
                    }}).catch(err => {{
                        console.error('Error loading NIfTI:', err);
                        document.body.innerHTML = '<div style="padding: 20px; color: red;">Error loading NIfTI file: ' + err + '</div>';
                        URL.revokeObjectURL(blobUrl);
                    }});
                </script>
            </body>
            </html>
        """
    else:
        # niivue HTML with placeholder
        niivue_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body { 
                        margin: 0; 
                        padding: 0; 
                        display: flex; 
                        align-items: center; 
                        justify-content: center; 
                            height: 720px;
                            background-color: #f0f0f0;
                    }
                    .placeholder {
                        text-align: center;
                        color: #888;
                        font-family: sans-serif;
                    }
                    .placeholder h3 {
                        margin: 0 0 10px 0;
                        color: #555;
                    }
                    .views {
                        display: grid;
                        grid-template-columns: 1fr 1fr;
                        gap: 10px;
                        margin-top: 20px;
                    }
                    .view-box {
                        width: 150px;
                        height: 150px;
                        border: 2px dashed #ccc;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: #999;
                        font-size: 14px;
                    }
                </style>
            </head>
            <body>
                <div class="placeholder">
                    <h3>NIfTI Viewer Ready</h3>
                    <p>Load a NIfTI file from the browser to visualize</p>
                    <div class="views">
                        <div class="view-box">Axial</div>
                        <div class="view-box">Sagittal</div>
                        <div class="view-box">Coronal</div>
                        <div class="view-box">3D</div>
                    </div>
                </div>
            </body>
            </html>
        """
    
    # Render niivue viewer (full width below browse controls)
    components.html(niivue_html, height=800, scrolling=False)


