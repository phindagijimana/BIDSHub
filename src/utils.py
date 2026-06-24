"""
Utility functions for BIDSHub.
"""

import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


# Canonical, human-readable display name for each platform. Used anywhere the
# UI shows a "[Platform]" tag so casing/spelling stay consistent across pages.
PLATFORM_LABELS = {
    'pennsieve': 'Pennsieve',
    'openneuro': 'OpenNeuro',
    'dandi': 'DANDI',
    'xnat': 'XNAT',
    'hpc': 'HPC',
    'remote_server': 'Remote',
    'local': 'Local',
}


def platform_label(platform: Optional[str]) -> str:
    """Return a consistent display label for a platform key.

    Falls back to a Title-cased version of the raw key for any platform not in
    the map, so a new/unknown platform still renders reasonably.
    """
    if not platform:
        return 'Unknown'
    return PLATFORM_LABELS.get(platform.lower(), platform.replace('_', ' ').title())


def format_file_size(bytes: int) -> str:
    """
    Format bytes to human-readable size.
    
    Args:
        bytes: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    if bytes == 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} PB"


def format_timestamp(dt: datetime) -> str:
    """
    Format timestamp for display.
    
    Args:
        dt: Datetime object
        
    Returns:
        Formatted string
    """
    if not dt:
        return "Never"
    
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except:
            return dt
    
    now = datetime.now()
    diff = now - dt
    
    if diff.days == 0:
        if diff.seconds < 60:
            return "Just now"
        elif diff.seconds < 3600:
            mins = diff.seconds // 60
            return f"{mins} minute{'s' if mins > 1 else ''} ago"
        else:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.days == 1:
        return "Yesterday"
    elif diff.days < 7:
        return f"{diff.days} days ago"
    else:
        return dt.strftime("%b %d, %Y")


def export_to_csv(data: List[Dict], filename: str) -> pd.DataFrame:
    """
    Convert list of dicts to DataFrame for export.
    
    Args:
        data: List of dictionaries
        filename: Output filename
        
    Returns:
        pandas DataFrame
    """
    df = pd.DataFrame(data)
    return df


def validate_bids_directory(path: str) -> tuple[bool, str]:
    """
    Validate if directory is a valid BIDS dataset.
    
    Args:
        path: Path to directory
        
    Returns:
        Tuple of (is_valid, message)
    """
    path_obj = Path(path)
    
    if not path_obj.exists():
        return False, "Directory does not exist"
    
    if not path_obj.is_dir():
        return False, "Path is not a directory"
    
    # Check for dataset_description.json
    desc_file = path_obj / 'dataset_description.json'
    if not desc_file.exists():
        return False, "Missing dataset_description.json"
    
    # Check for at least one subject directory
    subject_dirs = list(path_obj.glob('sub-*'))
    if not subject_dirs:
        return False, "No subject directories found (sub-*)"
    
    return True, f"Valid BIDS dataset with {len(subject_dirs)} subjects"


def calculate_completeness(subjects: List[Dict]) -> Dict:
    """
    Calculate dataset completeness statistics.
    
    Args:
        subjects: List of subject dictionaries
        
    Returns:
        Dictionary with completeness stats
    """
    if not subjects:
        return {
            'total': 0,
            'complete': 0,
            'incomplete': 0,
            'completeness_pct': 0
        }
    
    total = len(subjects)
    complete = sum(1 for s in subjects if s.get('has_2wk') and s.get('has_6mo'))
    incomplete = total - complete
    
    return {
        'total': total,
        'complete': complete,
        'incomplete': incomplete,
        'completeness_pct': (complete / total * 100) if total > 0 else 0
    }


def filter_subjects(subjects: List[Dict], filters: Dict) -> List[Dict]:
    """
    Filter subjects based on criteria.
    
    Args:
        subjects: List of subject dictionaries
        filters: Dictionary with filter criteria
                'search': Search query string
                'qc_status': QC status filter
                'session': Session filter ('2WK', '6MO', 'both')
                'completeness': 'complete', 'incomplete', or 'all'
                
    Returns:
        Filtered list of subjects
    """
    filtered = subjects
    
    # Search filter
    if filters.get('search'):
        query = filters['search'].lower()
        filtered = [s for s in filtered if query in s['subject_id'].lower()]
    
    # QC status filter
    if filters.get('qc_status') and filters['qc_status'] != 'all':
        filtered = [s for s in filtered 
                   if s.get('qc_status') == filters['qc_status']]
    
    # Session filter
    if filters.get('session'):
        session = filters['session']
        if session == '2WK':
            filtered = [s for s in filtered if s.get('has_2wk')]
        elif session == '6MO':
            filtered = [s for s in filtered if s.get('has_6mo')]
        elif session == 'both':
            filtered = [s for s in filtered 
                       if s.get('has_2wk') and s.get('has_6mo')]
    
    # Completeness filter
    if filters.get('completeness'):
        comp = filters['completeness']
        if comp == 'complete':
            filtered = [s for s in filtered 
                       if s.get('has_2wk') and s.get('has_6mo')]
        elif comp == 'incomplete':
            filtered = [s for s in filtered 
                       if not (s.get('has_2wk') and s.get('has_6mo'))]
    
    return filtered


def enrich_subjects_for_display(subjects: List[Dict], db) -> List[Dict]:
    """Add display fields the v3 ``subjects`` table no longer stores (v3.1.2+).

    The Browse Subjects and QC tables need per-subject demographics, session
    labels, scan counts and modalities, but the ``subjects`` table only holds
    identity + QC columns. This mutates each subject dict in place, pulling:

    - sessions / scan_count / modalities from the database
      (:meth:`Database.get_display_stats_for_dataset`), and
    - age / sex / diagnosis from each dataset's ``participants.tsv``.

    Queries/file reads are batched per dataset, so cost scales with the number
    of distinct datasets, not subjects. Safe to call with mixed-dataset lists.
    """
    from collections import defaultdict
    from src.metadata_handler import MetadataHandler

    by_dataset = defaultdict(list)
    for s in subjects:
        by_dataset[s.get('dataset_id')].append(s)

    for dataset_id, rows in by_dataset.items():
        stats = {}
        participants = {}
        if dataset_id is not None and db is not None:
            try:
                stats = db.get_display_stats_for_dataset(dataset_id)
            except Exception:
                stats = {}
            try:
                dataset = db.get_dataset(dataset_id)
                root = dataset.get('root_path') if dataset else None
                if root:
                    participants = MetadataHandler.parse_participants_tsv(
                        str(Path(root) / 'participants.tsv')
                    )
            except Exception:
                participants = {}

        for s in rows:
            label = s.get('subject_id', '')
            st_ = stats.get(label, {})
            s['session_labels'] = st_.get('session_labels', 'None')
            s['scan_count'] = st_.get('scan_count', 0)
            s['modalities_list'] = st_.get('modalities', [])

            meta = participants.get(label)
            if not meta and s.get('local_subject_id'):
                meta = participants.get(f"sub-{s['local_subject_id']}")
            if meta:
                if s.get('age') is None:
                    s['age'] = meta.get('age')
                if s.get('sex') is None:
                    s['sex'] = meta.get('sex')
                if s.get('diagnosis') is None:
                    s['diagnosis'] = meta.get('diagnosis')

    return subjects


def get_session_labels(subject: Dict) -> str:
    """
    Get formatted session labels for a subject.

    Args:
        subject: Subject dictionary

    Returns:
        Comma-separated session labels
    """
    # Preferred: enriched label string from enrich_subjects_for_display()
    if subject.get('session_labels'):
        return subject['session_labels']

    # Or a list of session dicts/strings (e.g. from get_subjects_with_sessions)
    sessions_val = subject.get('sessions')
    if isinstance(sessions_val, list) and sessions_val:
        labels = [
            (s.get('session_id') if isinstance(s, dict) else str(s))
            for s in sessions_val
        ]
        labels = [l for l in labels if l]
        if labels:
            return ', '.join(labels)

    # Legacy fixed-session columns (pre-v3 datasets)
    sessions = []
    if subject.get('has_2wk'):
        sessions.append('2WK')
    if subject.get('has_6mo'):
        sessions.append('6MO')

    return ', '.join(sessions) if sessions else 'None'


def get_scan_count(subject: Dict) -> str:
    """
    Get formatted scan count for a subject.
    
    Args:
        subject: Subject dictionary
        
    Returns:
        Formatted scan count string
    """
    count_2wk = subject.get('scan_count_2wk', 0)
    count_6mo = subject.get('scan_count_6mo', 0)
    total = count_2wk + count_6mo
    
    return f"{total} ({count_2wk}/{count_6mo})"


def check_disk_space(path: str, required_bytes: int) -> tuple[bool, str]:
    """
    Check if there's enough disk space.
    
    Args:
        path: Path to check
        required_bytes: Required space in bytes
        
    Returns:
        Tuple of (is_sufficient, message)
    """
    import shutil
    
    try:
        stat = shutil.disk_usage(path)
        available = stat.free
        
        if available >= required_bytes:
            return True, f"{format_file_size(available)} available"
        else:
            return False, f"Only {format_file_size(available)} available, need {format_file_size(required_bytes)}"
    except Exception as e:
        return False, f"Error checking disk space: {e}"


def _format_modalities(subject: Dict) -> str:
    """Format modalities as a compact string.

    Prefers the enriched ``modalities_list`` (distinct BIDS datatypes from the
    scans table); falls back to the legacy per-modality boolean flags.
    """
    mods = subject.get('modalities_list')
    if isinstance(mods, (list, tuple, set)) and mods:
        pretty = {'anat': 'T1/T2', 'func': 'fMRI', 'dwi': 'DWI', 'fmap': 'FMAP'}
        return ', '.join(pretty.get(m, m) for m in mods)

    modalities = []
    if subject.get('has_anat'):
        modalities.append('T1/T2')
    if subject.get('has_func'):
        modalities.append('fMRI')
    if subject.get('has_dwi'):
        modalities.append('DWI')
    if subject.get('has_fmap'):
        modalities.append('FMAP')
    return ', '.join(modalities) if modalities else ''


def create_subject_dataframe(subjects: List[Dict]) -> pd.DataFrame:
    """
    Create a pandas DataFrame from subjects list for display.
    
    Args:
        subjects: List of subject dictionaries
        
    Returns:
        pandas DataFrame
    """
    if not subjects:
        return pd.DataFrame()
    
    # Check if multi-dataset (subjects have dataset info)
    has_dataset_info = any('_dataset_name' in s for s in subjects)
    
    df_data = []
    for subject in subjects:
        row = {}
        
        # Add Dataset column first if multi-dataset
        if has_dataset_info:
            platform = subject.get('_dataset_platform', '')
            dataset_name = subject.get('_dataset_name', 'Unknown')
            row['Dataset'] = f"[{platform_label(platform)}] {dataset_name}"
        
        # Standard columns
        row.update({
            'Subject ID': subject['subject_id'],
            'Age': subject.get('age', ''),
            'Sex': subject.get('sex', ''),
            'Diagnosis': subject.get('diagnosis', ''),
            'QC Status': subject.get('qc_status', 'pending').title(),
            'Sessions': get_session_labels(subject),
            'Scans': f"{subject.get('scan_count', subject.get('scan_count_2wk', 0) + subject.get('scan_count_6mo', 0))}",
            'Modalities': _format_modalities(subject),
            'Flagged': 'Yes' if subject.get('flagged') else ''
        })
        
        df_data.append(row)
    
    return pd.DataFrame(df_data)


def parse_pennsieve_stub(file_path: str) -> Optional[str]:
    """
    Parse Pennsieve package ID from stub file.
    
    Args:
        file_path: Path to stub file
        
    Returns:
        Package ID or None
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read().strip()
            if content and len(content) < 200:
                return content
    except:
        pass
    return None


# Testing
if __name__ == "__main__":
    # Test file size formatting
    print("File Size Formatting:")
    sizes = [0, 1023, 1024, 1024**2, 1024**3, 1024**4]
    for size in sizes:
        print(f"  {size:15d} bytes = {format_file_size(size)}")
    
    # Test timestamp formatting
    print("\nTimestamp Formatting:")
    from datetime import timedelta
    now = datetime.now()
    times = [
        now,
        now - timedelta(seconds=30),
        now - timedelta(minutes=5),
        now - timedelta(hours=2),
        now - timedelta(days=1),
        now - timedelta(days=5),
        now - timedelta(days=30)
    ]
    for t in times:
        print(f"  {format_timestamp(t)}")
    
    # Test completeness calculation
    print("\nCompleteness Calculation:")
    test_subjects = [
        {'subject_id': 'sub-01', 'has_2wk': True, 'has_6mo': True},
        {'subject_id': 'sub-02', 'has_2wk': True, 'has_6mo': False},
        {'subject_id': 'sub-03', 'has_2wk': True, 'has_6mo': True},
    ]
    stats = calculate_completeness(test_subjects)
    print(f"  Total: {stats['total']}")
    print(f"  Complete: {stats['complete']}")
    print(f"  Completeness: {stats['completeness_pct']:.1f}%")
