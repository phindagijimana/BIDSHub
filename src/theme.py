"""
UI Theme for Data Explorer.

Chase Bank-inspired professional navy blue and white theme.
"""

import streamlit as st


class Theme:
    """Theme constants - Chase Bank inspired navy blue and white."""
    
    # Primary colors - Chase Bank style
    NAVY_DARKEST = "#001f4d"
    NAVY_DARK = "#002d72"        # Chase primary navy
    NAVY_PRIMARY = "#003d7a"     # Main brand color
    NAVY_MEDIUM = "#0057a3"
    NAVY_LIGHT = "#1a5a9e"
    NAVY_SUBTLE = "#e6f0f9"
    WHITE = "#ffffff"
    
    # Status colors
    SUCCESS = "#10b981"          # Green
    WARNING = "#f59e0b"          # Amber
    ERROR = "#ef4444"            # Red
    INFO = "#3b82f6"             # Blue
    
    # Gray scale
    GRAY_50 = "#f9fafb"
    GRAY_100 = "#f3f4f6"
    GRAY_300 = "#d1d5db"
    GRAY_600 = "#4b5563"
    GRAY_900 = "#111827"
    
    # Status labels (NO EMOJIS)
    STATUS_LABELS = {
        'pending': 'Pending',
        'pass': 'Pass',
        'fail': 'Fail',
        'needs_review': 'Needs Review',
        'downloaded': 'Downloaded',
        'downloading': 'Downloading',
        'stub': 'Stub',
        'failed': 'Failed',
        'queued': 'Queued',
        'completed': 'Completed'
    }
    
    # Status colors mapping
    STATUS_COLORS = {
        'pending': WARNING,
        'pass': SUCCESS,
        'fail': ERROR,
        'needs_review': INFO,
        'downloaded': SUCCESS,
        'downloading': INFO,
        'stub': GRAY_600,
        'failed': ERROR,
        'queued': GRAY_600,
        'completed': SUCCESS
    }


def apply_custom_theme():
    """Apply Chase Bank-inspired navy blue and white theme to Streamlit."""
    st.markdown("""
        <style>
        /* Main theme colors - Chase Bank inspired */
        :root {
            --primary-color: #002d72;
            --primary-accent: #003d7a;
            --background-color: #ffffff;
            --secondary-background-color: #f9fafb;
            --text-color: #111827;
        }
        
        /* Remove default Streamlit padding */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        
        /* Header styling - NO EMOJIS */
        .main-header {
            color: #002d72;
            font-size: 32px;
            font-weight: 600;
            border-bottom: 3px solid #002d72;
            padding-bottom: 10px;
            margin-bottom: 20px;
            letter-spacing: -0.5px;
        }
        
        /* Section headers - NO EMOJIS */
        .section-header {
            color: #002d72;
            font-size: 20px;
            font-weight: 600;
            margin-top: 30px;
            margin-bottom: 15px;
            letter-spacing: -0.3px;
        }
        
        .subsection-header {
            color: #111827;
            font-size: 16px;
            font-weight: 600;
            margin-top: 20px;
            margin-bottom: 10px;
        }
        
        /* Metric cards - Chase Bank style */
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 2px solid #002d72;
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 1px 2px rgba(0, 45, 114, 0.08);
        }
        
        div[data-testid="stMetric"] label {
            color: #4b5563 !important;
            font-weight: 500;
            font-size: 14px;
        }
        
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: #002d72 !important;
            font-weight: 700 !important;
            font-size: 32px !important;
        }
        
        /* Buttons - Chase Bank style */
        .stButton > button {
            background-color: #002d72;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 10px 24px;
            font-weight: 600;
            font-size: 14px;
            transition: background-color 0.2s;
            letter-spacing: 0.3px;
        }
        
        .stButton > button:hover {
            background-color: #003d7a;
            border: none;
        }
        
        .stButton > button:active {
            background-color: #001f4d;
        }
        
        /* Secondary button style */
        .stButton.secondary > button {
            background-color: #ffffff;
            color: #002d72;
            border: 2px solid #002d72;
        }
        
        .stButton.secondary > button:hover {
            background-color: #e6f0f9;
        }
        
        /* DataFrames - Chase Bank style */
        .dataframe {
            border: 1px solid #d1d5db !important;
            border-radius: 8px;
        }
        
        .dataframe thead tr th {
            background-color: #002d72 !important;
            color: #ffffff !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            padding: 12px !important;
            border: none !important;
        }
        
        .dataframe tbody tr:nth-child(even) {
            background-color: #f9fafb;
        }
        
        .dataframe tbody tr:hover {
            background-color: #e6f0f9;
        }
        
        .dataframe tbody tr td {
            padding: 10px 12px !important;
            border: none !important;
            border-bottom: 1px solid #f3f4f6 !important;
        }
        
        /* Input fields - Professional style */
        .stTextInput input, .stTextArea textarea, .stSelectbox select {
            border: 1px solid #d1d5db !important;
            border-radius: 6px !important;
            font-size: 14px !important;
            padding: 8px 12px !important;
        }
        
        .stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox select:focus {
            border-color: #002d72 !important;
            box-shadow: 0 0 0 2px rgba(0, 45, 114, 0.1) !important;
        }
        
        /* Progress bars - Navy theme */
        .stProgress > div > div {
            background-color: #f3f4f6;
        }
        
        .stProgress > div > div > div {
            background-color: #002d72;
        }
        
        /* Sidebar - Professional style */
        section[data-testid="stSidebar"] {
            background-color: #fafafa;
            border-right: 1px solid #e5e7eb;
        }
        
        section[data-testid="stSidebar"] .sidebar-content {
            color: #111827;
        }
        
        /* Success/Info/Warning/Error boxes */
        .stSuccess {
            background-color: rgba(16, 185, 129, 0.1);
            border-left: 4px solid #10b981;
            padding: 12px;
            border-radius: 4px;
        }
        
        .stInfo {
            background-color: rgba(59, 130, 246, 0.1);
            border-left: 4px solid #3b82f6;
            padding: 12px;
            border-radius: 4px;
        }
        
        .stWarning {
            background-color: rgba(245, 158, 11, 0.1);
            border-left: 4px solid #f59e0b;
            padding: 12px;
            border-radius: 4px;
        }
        
        .stError {
            background-color: rgba(239, 68, 68, 0.1);
            border-left: 4px solid #ef4444;
            padding: 12px;
            border-radius: 4px;
        }
        
        /* Tabs - Professional style */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            background-color: #ffffff;
            border: 1px solid #d1d5db;
            border-radius: 6px 6px 0 0;
            padding: 10px 20px;
            color: #4b5563;
            font-weight: 500;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #002d72;
            color: #ffffff;
            border-color: #002d72;
        }
        
        /* Expander - Professional style */
        .streamlit-expanderHeader {
            background-color: #f9fafb;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            font-weight: 600;
            color: #002d72;
        }
        
        /* Links - Navy theme */
        a {
            color: #002d72;
            text-decoration: none;
            border-bottom: 1px solid #d1d5db;
        }
        
        a:hover {
            border-bottom-color: #002d72;
        }
        
        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Divider */
        hr {
            border: none;
            border-top: 1px solid #e5e7eb;
            margin: 24px 0;
        }
        
        /* Code blocks */
        code {
            background-color: #f3f4f6;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            color: #002d72;
        }
        
        pre {
            background-color: #f9fafb;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            padding: 12px;
        }
        </style>
    """, unsafe_allow_html=True)


def render_status_badge(status: str) -> str:
    """
    Render a status badge with appropriate color.
    
    Args:
        status: Status string
        
    Returns:
        HTML string for status badge
    """
    label = Theme.STATUS_LABELS.get(status, status.title())
    color = Theme.STATUS_COLORS.get(status, Theme.GRAY_600)
    
    return f"""
        <span style="
            display: inline-block;
            padding: 4px 12px;
            border-radius: 4px;
            background-color: {color};
            color: #ffffff;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        ">{label}</span>
    """


def format_file_size(bytes: int) -> str:
    """
    Format bytes to human-readable size.
    
    Args:
        bytes: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} PB"


def show_loading(message: str = "Loading..."):
    """Show loading spinner with message."""
    with st.spinner(message):
        pass


# Test theme if run directly
if __name__ == "__main__":
    st.set_page_config(
        page_title="Data Explorer - Theme Test",
        page_icon="🔬",
        layout="wide"
    )
    
    apply_custom_theme()
    
    st.markdown('<h1 class="main-header">Data Explorer - Theme Test</h1>', 
                unsafe_allow_html=True)
    
    st.markdown('<h2 class="section-header">Metrics</h2>', 
                unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Subjects", "660")
    col2.metric("Sessions", "1,319")
    col3.metric("Scans", "8,820")
    
    st.markdown('<h2 class="section-header">Status Badges</h2>', 
                unsafe_allow_html=True)
    
    for status in ['pending', 'pass', 'fail', 'needs_review', 
                   'downloaded', 'stub', 'queued', 'completed']:
        st.markdown(render_status_badge(status), unsafe_allow_html=True)
        st.write("")
    
    st.markdown('<h2 class="section-header">Buttons</h2>', 
                unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    col1.button("Primary Button")
    col2.button("Secondary Button")
    
    st.markdown('<h2 class="section-header">Alerts</h2>', 
                unsafe_allow_html=True)
    
    st.success("Success message")
    st.info("Info message")
    st.warning("Warning message")
    st.error("Error message")
    
    st.markdown('<h2 class="section-header">File Sizes</h2>', 
                unsafe_allow_html=True)
    
    sizes = [1024, 1024**2, 1024**3, 1024**4]
    for size in sizes:
        st.write(f"{size} bytes = {format_file_size(size)}")
