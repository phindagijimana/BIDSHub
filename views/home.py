"""Home / landing page (extracted from app.py)."""
import streamlit as st
from src.bids_loader import BIDSLoader


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
                <div class="quick-feature-icon">✓</div>
                <span>7 supported platforms (Pennsieve, OpenNeuro, DANDI, XNAT, HPC, Remote)</span>
            </div>
            <div class="quick-feature">
                <div class="quick-feature-icon">✓</div>
                <span>Cross-platform metadata filtering with BIDS validation</span>
            </div>
            <div class="quick-feature">
                <div class="quick-feature-icon">✓</div>
                <span>Scan-level quality control with Pennsieve sync</span>
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

            # Demo mode: register the bundled synthetic BIDS dataset and
            # jump straight to the dashboard. Lets a first-time user see
            # the app working before configuring any remote credentials.
            from src.sample_dataset import (
                SAMPLE_BIDS_ROOT,
                load_sample_dataset,
                sample_dataset_available,
            )
            from src.bids_loader import BIDSLoader

            if sample_dataset_available() and st.session_state.db:
                st.markdown(
                    "<p style='text-align:center; color:#6b7280; margin-top:0.75rem; "
                    "margin-bottom:0.5rem; font-size:0.9rem;'>"
                    "or, no account yet?</p>",
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Try with sample data",
                    use_container_width=True,
                    key="try_sample_data",
                    help="Loads a small synthetic BIDS dataset bundled with the repo. "
                         "Nothing leaves your machine.",
                ):
                    with st.spinner("Loading sample dataset..."):
                        ds_id, n_subjects, err = load_sample_dataset(
                            st.session_state.db, BIDSLoader
                        )
                    if err:
                        st.error(err)
                    else:
                        st.session_state.active_dataset_id = ds_id
                        st.session_state.dataset_name = "BIDSHub Sample"
                        st.session_state.bids_root = str(SAMPLE_BIDS_ROOT)
                        st.session_state.current_page = 'dashboard'
                        st.success(f"Loaded sample dataset with {n_subjects} subjects.")
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



