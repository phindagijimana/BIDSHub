"""
Quality Control Manager for BIDSHub.

Manages QC workflow including status tracking, notes, and history.
v3.1+: Added CSV export/import for Pennsieve integration.
"""

from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum
import csv
from pathlib import Path


class QCStatus(Enum):
    """QC status values."""
    PENDING = 'pending'
    PASS = 'pass'
    FAIL = 'fail'
    NEEDS_REVIEW = 'needs_review'


class QCManager:
    """Manager for quality control workflow."""
    
    def __init__(self, database):
        """
        Initialize QC manager.
        
        Args:
            database: Database instance
        """
        self.db = database
    
    def update_subject_qc(self, subject_id: str, qc_status: str,
                         notes: str = None, reviewed_by: str = None,
                         flagged: bool = None) -> bool:
        """
        Update QC status for a subject.
        
        Args:
            subject_id: Subject identifier
            qc_status: New QC status
            notes: QC notes
            reviewed_by: Reviewer identifier
            flagged: Whether to flag subject
            
        Returns:
            bool: True if successful
        """
        # Validate status
        valid_statuses = [s.value for s in QCStatus]
        if qc_status not in valid_statuses:
            print(f"Invalid QC status: {qc_status}")
            return False
        
        return self.db.update_subject_qc(
            subject_id=subject_id,
            qc_status=qc_status,
            notes=notes,
            reviewed_by=reviewed_by,
            flagged=flagged
        )
    
    def update_scan_qc(self, scan_id: int, qc_status: str,
                      notes: str = None, reviewed_by: str = None,
                      flagged: bool = None) -> bool:
        """
        Update QC status for a specific scan (v3.1+).
        
        Args:
            scan_id: Scan database ID
            qc_status: New QC status
            notes: QC notes
            reviewed_by: Reviewer identifier
            flagged: Whether to flag scan
            
        Returns:
            bool: True if successful
        """
        # Validate status
        valid_statuses = [s.value for s in QCStatus]
        if qc_status not in valid_statuses:
            print(f"Invalid QC status: {qc_status}")
            return False
        
        return self.db.update_scan_qc(
            scan_id=scan_id,
            qc_status=qc_status,
            notes=notes,
            reviewed_by=reviewed_by,
            flagged=flagged
        )
    
    def get_qc_summary(self) -> Dict:
        """
        Get QC summary statistics.
        
        Returns:
            Dictionary with QC stats
        """
        stats = self.db.get_stats()
        
        summary = {
            'total': stats.get('total_subjects', 0),
            'pending': stats.get('qc_pending', 0),
            'pass': stats.get('qc_pass', 0),
            'fail': stats.get('qc_fail', 0),
            'needs_review': stats.get('qc_review', 0)
        }
        
        # Calculate percentages
        total = summary['total']
        if total > 0:
            summary['pending_pct'] = (summary['pending'] / total) * 100
            summary['pass_pct'] = (summary['pass'] / total) * 100
            summary['fail_pct'] = (summary['fail'] / total) * 100
            summary['needs_review_pct'] = (summary['needs_review'] / total) * 100
            summary['reviewed_pct'] = ((total - summary['pending']) / total) * 100
        else:
            summary['pending_pct'] = 0
            summary['pass_pct'] = 0
            summary['fail_pct'] = 0
            summary['needs_review_pct'] = 0
            summary['reviewed_pct'] = 0
        
        return summary
    
    def get_subjects_by_qc_status(self, status: str) -> List[Dict]:
        """
        Get subjects filtered by QC status.
        
        Args:
            status: QC status to filter by
            
        Returns:
            List of subject dictionaries
        """
        if status == 'all':
            return self.db.get_all_subjects()
        
        filters = {'qc_status': status}
        return self.db.get_all_subjects(filters)
    
    def get_flagged_subjects(self) -> List[Dict]:
        """
        Get all flagged subjects.
        
        Returns:
            List of flagged subjects
        """
        filters = {'flagged': True}
        return self.db.get_all_subjects(filters)
    
    def flag_subject(self, subject_id: str, flagged: bool = True) -> bool:
        """
        Flag or unflag a subject.
        
        Args:
            subject_id: Subject identifier
            flagged: Whether to flag (True) or unflag (False)
            
        Returns:
            bool: True if successful
        """
        subject = self.db.get_subject(subject_id)
        if not subject:
            return False
        
        return self.db.update_subject_qc(
            subject_id=subject_id,
            qc_status=subject['qc_status'],
            flagged=flagged
        )
    
    def add_qc_note(self, subject_id: str, note: str,
                   reviewed_by: str = None) -> bool:
        """
        Add a QC note to a subject.
        
        Args:
            subject_id: Subject identifier
            note: Note text
            reviewed_by: Reviewer identifier
            
        Returns:
            bool: True if successful
        """
        subject = self.db.get_subject(subject_id)
        if not subject:
            return False
        
        # Append to existing notes
        existing_notes = subject.get('qc_notes', '') or ''
        if existing_notes:
            new_notes = f"{existing_notes}\n\n{datetime.now().strftime('%Y-%m-%d %H:%M')}: {note}"
        else:
            new_notes = f"{datetime.now().strftime('%Y-%m-%d %H:%M')}: {note}"
        
        return self.db.update_subject_qc(
            subject_id=subject_id,
            qc_status=subject['qc_status'],
            notes=new_notes,
            reviewed_by=reviewed_by
        )
    
    def get_qc_history(self, subject_id: str = None, limit: int = 50) -> List[Dict]:
        """
        Get QC history.
        
        Args:
            subject_id: Optional subject filter
            limit: Maximum number of records
            
        Returns:
            List of QC history records
        """
        return self.db.get_qc_history(subject_id, limit)
    
    def get_recent_qc_activity(self, limit: int = 10) -> List[Dict]:
        """
        Get recent QC activity.
        
        Args:
            limit: Maximum number of records
            
        Returns:
            List of recent QC changes
        """
        history = self.db.get_qc_history(limit=limit)
        
        # Format for display
        activity = []
        for record in history:
            activity.append({
                'subject_id': record['subject_id'],
                'old_status': record['old_status'],
                'new_status': record['new_status'],
                'reviewed_by': record.get('reviewed_by', 'Unknown'),
                'reviewed_date': record.get('reviewed_date'),
                'notes': record.get('notes', '')
            })
        
        return activity
    
    def bulk_update_qc(self, subject_ids: List[str], qc_status: str,
                      notes: str = None, reviewed_by: str = None) -> int:
        """
        Update QC status for multiple subjects.
        
        Args:
            subject_ids: List of subject identifiers
            qc_status: New QC status
            notes: QC notes
            reviewed_by: Reviewer identifier
            
        Returns:
            Number of subjects updated
        """
        count = 0
        for subject_id in subject_ids:
            success = self.update_subject_qc(
                subject_id=subject_id,
                qc_status=qc_status,
                notes=notes,
                reviewed_by=reviewed_by
            )
            if success:
                count += 1
        
        return count
    
    def export_qc_report(self) -> Dict:
        """
        Generate QC report for export.
        
        Returns:
            Dictionary with report data
        """
        summary = self.get_qc_summary()
        all_subjects = self.db.get_all_subjects()
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': summary,
            'subjects': []
        }
        
        for subject in all_subjects:
            report['subjects'].append({
                'subject_id': subject['subject_id'],
                'qc_status': subject.get('qc_status', 'pending'),
                'flagged': subject.get('flagged', False),
                'has_2wk': subject.get('has_2wk', False),
                'has_6mo': subject.get('has_6mo', False),
                'scan_count': subject.get('scan_count_2wk', 0) + subject.get('scan_count_6mo', 0),
                'qc_notes': subject.get('qc_notes', ''),
                'reviewed_by': subject.get('qc_reviewed_by', ''),
                'reviewed_date': subject.get('qc_reviewed_date', '')
            })
        
        return report
    
    def get_qc_progress(self) -> Dict:
        """
        Get QC progress metrics.
        
        Returns:
            Dictionary with progress information
        """
        summary = self.get_qc_summary()
        total = summary['total']
        reviewed = total - summary['pending']
        
        progress = {
            'total_subjects': total,
            'reviewed': reviewed,
            'pending': summary['pending'],
            'progress_pct': summary['reviewed_pct'],
            'pass_rate': (summary['pass'] / reviewed * 100) if reviewed > 0 else 0
        }
        
        return progress
    
    def export_qc_csv(self, dataset_id: int, output_path: str, 
                     include_pending: bool = False) -> bool:
        """
        Export scan-level QC results to CSV for Pennsieve upload (v3.1+).
        
        Args:
            dataset_id: Dataset ID to export QC for
            output_path: Path to save CSV file
            include_pending: Whether to include scans with pending QC status
            
        Returns:
            bool: True if successful
        """
        try:
            # Get all scans with QC data for this dataset
            conn = self.db._get_connection()
            cursor = conn.cursor()
            
            # Query scans with QC info
            if include_pending:
                status_filter = ""
            else:
                status_filter = "AND qc_status != 'pending'"
            
            query = f"""
                SELECT 
                    s.id as scan_id,
                    s.subject_id,
                    s.session as session_id,
                    s.modality,
                    s.suffix,
                    s.qc_status,
                    s.qc_notes,
                    s.reviewed_by,
                    s.reviewed_date,
                    s.flagged,
                    s.file_path
                FROM scans s
                WHERE s.dataset_id = ?
                {status_filter}
                ORDER BY s.subject_id, s.session, s.modality, s.suffix
            """
            
            cursor.execute(query, (dataset_id,))
            rows = cursor.fetchall()
            
            if not rows:
                print(f"No QC data to export for dataset {dataset_id}")
                return False
            
            # Write CSV
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'scan_id', 'subject_id', 'session_id', 'modality', 'suffix',
                    'qc_status', 'qc_notes', 'reviewed_by', 'reviewed_date',
                    'flagged', 'file_path'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for row in rows:
                    row_dict = dict(row)
                    
                    # Format boolean as string
                    row_dict['flagged'] = 'true' if row_dict['flagged'] else 'false'
                    
                    # Format date as ISO 8601
                    if row_dict['reviewed_date']:
                        if isinstance(row_dict['reviewed_date'], str):
                            row_dict['reviewed_date'] = row_dict['reviewed_date']
                        else:
                            row_dict['reviewed_date'] = row_dict['reviewed_date'].isoformat()
                    
                    # Handle None values
                    for key in row_dict:
                        if row_dict[key] is None:
                            row_dict[key] = ''
                    
                    writer.writerow(row_dict)
            
            conn.close()
            
            print(f"[OK] Exported {len(rows)} QC records to {output_path}")
            return True
            
        except Exception as e:
            print(f"Error exporting QC CSV: {e}")
            return False
    
    def import_qc_csv(self, csv_path: str, dataset_id: int,
                     merge: bool = True) -> Dict:
        """
        Import QC results from CSV (v3.1+).
        
        Args:
            csv_path: Path to CSV file
            dataset_id: Dataset ID to import for
            merge: If True, merge with existing QC data (latest timestamp wins)
                  If False, replace all QC data for dataset
            
        Returns:
            Dict with import statistics: {
                'imported': 10,
                'skipped': 2,
                'errors': 1,
                'messages': []
            }
        """
        stats = {
            'imported': 0,
            'skipped': 0,
            'errors': 0,
            'messages': []
        }
        
        try:
            if not Path(csv_path).exists():
                stats['messages'].append(f"File not found: {csv_path}")
                return stats
            
            with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # Validate headers
                required_fields = ['scan_id', 'subject_id', 'session_id', 'qc_status']
                if not all(field in reader.fieldnames for field in required_fields):
                    stats['messages'].append("Invalid CSV format: missing required columns")
                    return stats
                
                for row in reader:
                    try:
                        scan_id = int(row['scan_id'])
                        qc_status = row['qc_status'].strip()
                        
                        # Validate status
                        if not self.validate_qc_status(qc_status):
                            stats['skipped'] += 1
                            stats['messages'].append(f"Invalid status for scan {scan_id}: {qc_status}")
                            continue
                        
                        # Check if scan exists in our database
                        existing_qc = self.db.get_scan_qc(scan_id)
                        
                        if not existing_qc:
                            stats['skipped'] += 1
                            stats['messages'].append(f"Scan {scan_id} not found in database")
                            continue
                        
                        # Merge logic: if merge=True, check timestamps
                        if merge and existing_qc.get('reviewed_date'):
                            # Parse import date
                            import_date_str = row.get('reviewed_date', '').strip()
                            if import_date_str:
                                try:
                                    import_date = datetime.fromisoformat(import_date_str)
                                    existing_date = existing_qc['reviewed_date']
                                    
                                    if isinstance(existing_date, str):
                                        existing_date = datetime.fromisoformat(existing_date)
                                    
                                    # Skip if existing is newer
                                    if existing_date >= import_date:
                                        stats['skipped'] += 1
                                        continue
                                except:
                                    pass
                        
                        # Update scan QC
                        notes = row.get('qc_notes', '').strip() or None
                        reviewed_by = row.get('reviewed_by', '').strip() or None
                        flagged = row.get('flagged', '').lower() == 'true'
                        
                        success = self.db.update_scan_qc(
                            scan_id=scan_id,
                            qc_status=qc_status,
                            notes=notes,
                            reviewed_by=reviewed_by,
                            flagged=flagged
                        )
                        
                        if success:
                            stats['imported'] += 1
                        else:
                            stats['errors'] += 1
                            stats['messages'].append(f"Failed to update scan {scan_id}")
                    
                    except Exception as e:
                        stats['errors'] += 1
                        stats['messages'].append(f"Error processing row: {e}")
            
            stats['messages'].append(
                f"Import complete: {stats['imported']} imported, "
                f"{stats['skipped']} skipped, {stats['errors']} errors"
            )
            
            return stats
            
        except Exception as e:
            stats['messages'].append(f"Error importing CSV: {e}")
            return stats
    
    def get_unsynced_qc_count(self, dataset_id: int) -> int:
        """
        Get count of scans with QC data not yet synced to platform (v3.1+).
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            int: Number of unsynced scans
        """
        unsynced = self.db.get_unsynced_scans(dataset_id)
        return len(unsynced)
    
    def validate_qc_status(self, status: str) -> bool:
        """
        Validate if QC status is valid.
        
        Args:
            status: Status string to validate
            
        Returns:
            bool: True if valid
        """
        valid_statuses = [s.value for s in QCStatus]
        return status in valid_statuses


# Helper functions

def format_qc_history_entry(entry: Dict) -> str:
    """
    Format a QC history entry for display.
    
    Args:
        entry: QC history entry dictionary
        
    Returns:
        Formatted string
    """
    subject = entry['subject_id']
    old = entry['old_status'] or 'none'
    new = entry['new_status']
    reviewer = entry.get('reviewed_by', 'Unknown')
    
    from src.utils import format_timestamp
    time_str = format_timestamp(entry.get('reviewed_date'))
    
    return f"{subject}: {old} -> {new} (by {reviewer}, {time_str})"


def calculate_qc_metrics(subjects: List[Dict]) -> Dict:
    """
    Calculate QC metrics for a list of subjects.
    
    Args:
        subjects: List of subject dictionaries
        
    Returns:
        Dictionary with metrics
    """
    if not subjects:
        return {
            'total': 0,
            'pending': 0,
            'pass': 0,
            'fail': 0,
            'needs_review': 0
        }
    
    metrics = {
        'total': len(subjects),
        'pending': sum(1 for s in subjects if s.get('qc_status') == 'pending'),
        'pass': sum(1 for s in subjects if s.get('qc_status') == 'pass'),
        'fail': sum(1 for s in subjects if s.get('qc_status') == 'fail'),
        'needs_review': sum(1 for s in subjects if s.get('qc_status') == 'needs_review'),
        'flagged': sum(1 for s in subjects if s.get('flagged'))
    }
    
    return metrics


# Testing
if __name__ == "__main__":
    print("QC Manager - Test Module")
    print("=" * 50)
    
    # Test QC statuses
    print("\nValid QC Statuses:")
    for status in QCStatus:
        print(f"  - {status.value}")
    
    # Test validation
    print("\nStatus Validation:")
    test_statuses = ['pending', 'pass', 'invalid', 'fail']
    for status in test_statuses:
        qm = QCManager(None)  # No database for testing
        is_valid = qm.validate_qc_status(status)
        print(f"  '{status}': {'[OK] Valid' if is_valid else '[ERROR] Invalid'}")
    
    # Test metrics calculation
    print("\nMetrics Calculation:")
    test_subjects = [
        {'subject_id': 'sub-01', 'qc_status': 'pending'},
        {'subject_id': 'sub-02', 'qc_status': 'pass'},
        {'subject_id': 'sub-03', 'qc_status': 'pass'},
        {'subject_id': 'sub-04', 'qc_status': 'needs_review'},
    ]
    metrics = calculate_qc_metrics(test_subjects)
    for key, value in metrics.items():
        print(f"  {key}: {value}")
