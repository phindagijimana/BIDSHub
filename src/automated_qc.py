"""
Automated Quality Control for BIDS Datasets.

Runs automated checks on subjects and scans to detect technical issues.
Separate from manual QC which requires human review.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime


class AutomatedQC:
    """Run automated quality checks on BIDS subjects and scans."""
    
    def __init__(self, bids_loader, database):
        """
        Initialize automated QC system.
        
        Args:
            bids_loader: BIDSLoader instance
            database: Database instance
        """
        self.bids_loader = bids_loader
        self.db = database
        
        # Expected scans for completeness check
        self.expected_modalities = ['T1w', 'T2w', 'FLAIR', 'DWI']
    
    def run_subject_qc(self, subject_id: str) -> Dict:
        """
        Run all automated checks for a subject (all sessions).
        
        Args:
            subject_id: Subject identifier
            
        Returns:
            dict: {
                'status': 'pass' | 'warning' | 'fail',
                'checks': {...},
                'issues': [...],
                'warnings': [...],
                'sessions': {'2WK': {...}, '6MO': {...}}
            }
        """
        results = {
            'status': 'pass',
            'issues': [],
            'warnings': [],
            'sessions': {},
            'summary': {}
        }
        
        # Get subject info
        subject = self.db.get_subject(subject_id)
        if not subject:
            results['status'] = 'fail'
            results['issues'].append('Subject not found in database')
            return results
        
        # Check each session
        sessions_to_check = []
        if subject.get('has_2wk'):
            sessions_to_check.append('2WK')
        if subject.get('has_6mo'):
            sessions_to_check.append('6MO')
        
        for session in sessions_to_check:
            session_result = self._check_session(subject_id, session)
            results['sessions'][session] = session_result
            
            # Aggregate issues and warnings
            results['issues'].extend(session_result.get('issues', []))
            results['warnings'].extend(session_result.get('warnings', []))
        
        # Determine overall status
        if results['issues']:
            results['status'] = 'fail'
        elif results['warnings']:
            results['status'] = 'warning'
        else:
            results['status'] = 'pass'
        
        # Summary
        total_scans = sum(s.get('scan_count', 0) for s in results['sessions'].values())
        downloaded_scans = sum(s.get('downloaded', 0) for s in results['sessions'].values())
        stub_scans = sum(s.get('stubs', 0) for s in results['sessions'].values())
        
        results['summary'] = {
            'total_scans': total_scans,
            'downloaded': downloaded_scans,
            'stubs': stub_scans,
            'issue_count': len(results['issues']),
            'warning_count': len(results['warnings'])
        }
        
        return results
    
    def _check_session(self, subject_id: str, session: str) -> Dict:
        """
        Run automated checks for a specific session.
        
        Args:
            subject_id: Subject identifier
            session: Session name (e.g., '2WK', '6MO')
            
        Returns:
            dict: Session check results
        """
        results = {
            'scan_count': 0,
            'downloaded': 0,
            'stubs': 0,
            'missing': 0,
            'issues': [],
            'warnings': [],
            'modalities': {}
        }
        
        try:
            scans = self.bids_loader.get_subject_scans(subject_id, session)
            results['scan_count'] = len(scans)
            
            if not scans:
                results['warnings'].append(f"No scans found for session {session}")
                return results
            
            # Check each scan
            for scan in scans:
                file_path = Path(scan['file_path'])
                suffix = scan.get('suffix', 'unknown')
                
                # Track modality
                if suffix not in results['modalities']:
                    results['modalities'][suffix] = {'count': 0, 'downloaded': 0, 'stubs': 0}
                results['modalities'][suffix]['count'] += 1
                
                # Check 1: File exists
                if not file_path.exists():
                    results['issues'].append(f"{session}/{suffix}: File not found")
                    results['missing'] += 1
                    continue
                
                # Check 2: Is it a stub or downloaded?
                if self.bids_loader.is_stub_file(str(file_path)):
                    results['stubs'] += 1
                    results['modalities'][suffix]['stubs'] += 1
                    results['warnings'].append(f"{session}/{suffix}: Stub file (not downloaded)")
                else:
                    results['downloaded'] += 1
                    results['modalities'][suffix]['downloaded'] += 1
                    
                    # Check 3: File size reasonable
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    if size_mb < 1:
                        results['issues'].append(f"{session}/{suffix}: Suspiciously small ({size_mb:.2f} MB)")
                    elif size_mb > 500:
                        results['warnings'].append(f"{session}/{suffix}: Large file ({size_mb:.0f} MB)")
                    
                    # Check 4: JSON sidecar exists
                    json_path = file_path.with_suffix('.json')
                    if not json_path.exists():
                        results['warnings'].append(f"{session}/{suffix}: Missing JSON sidecar")
            
            # Check 5: Expected modalities present
            found_modalities = list(results['modalities'].keys())
            for expected in self.expected_modalities:
                if expected not in found_modalities:
                    results['warnings'].append(f"{session}: Missing recommended scan {expected}")
            
        except Exception as e:
            results['issues'].append(f"Error checking session {session}: {str(e)}")
        
        return results
    
    def run_batch_qc(self, 
                     subject_ids: List[str],
                     progress_callback: Callable[[int, int, str], None] = None) -> Dict:
        """
        Run automated QC on multiple subjects.
        
        Args:
            subject_ids: List of subject IDs to check
            progress_callback: Optional callback(current, total, subject_id)
            
        Returns:
            dict: {
                'subject_id': {qc_results},
                ...
            }
        """
        results = {}
        total = len(subject_ids)
        
        for i, subject_id in enumerate(subject_ids):
            if progress_callback:
                progress_callback(i + 1, total, subject_id)
            
            subject_results = self.run_subject_qc(subject_id)
            results[subject_id] = subject_results
            
            # Update database
            self._save_qc_results(subject_id, subject_results)
        
        return results
    
    def _save_qc_results(self, subject_id: str, results: Dict):
        """
        Save automated QC results to database.
        
        Args:
            subject_id: Subject identifier
            results: QC results dictionary
        """
        try:
            self.db.update_automated_qc(
                subject_id=subject_id,
                status=results['status'],
                results=json.dumps(results)
            )
        except Exception as e:
            print(f"Error saving QC results for {subject_id}: {e}")
    
    def get_qc_summary(self) -> Dict:
        """
        Get summary statistics for automated QC across all subjects.
        
        Returns:
            dict: Summary statistics
        """
        subjects = self.db.get_all_subjects()
        
        summary = {
            'total': len(subjects),
            'pass': 0,
            'warning': 0,
            'fail': 0,
            'pending': 0
        }
        
        for subject in subjects:
            status = subject.get('automated_qc_status', 'pending')
            if status in summary:
                summary[status] += 1
        
        # Calculate percentages
        if summary['total'] > 0:
            for key in ['pass', 'warning', 'fail', 'pending']:
                summary[f'{key}_pct'] = (summary[key] / summary['total']) * 100
        
        return summary
    
    def get_subjects_by_status(self, status: str) -> List[Dict]:
        """
        Get subjects filtered by automated QC status.
        
        Args:
            status: 'pass' | 'warning' | 'fail' | 'pending'
            
        Returns:
            List of subject dictionaries
        """
        subjects = self.db.get_all_subjects()
        return [s for s in subjects if s.get('automated_qc_status') == status]
    
    def get_flagged_subjects(self) -> List[Dict]:
        """
        Get subjects with automated QC issues (fail or warning).
        
        Returns:
            List of subject dictionaries
        """
        subjects = self.db.get_all_subjects()
        return [s for s in subjects 
                if s.get('automated_qc_status') in ['fail', 'warning']]
