"""
Pennsieve Agent Integration for Data Explorer.

Wraps Pennsieve CLI commands for dataset mapping, downloads, and uploads.
Provides Python interface for GUI interactions.
"""

import subprocess
import shutil
import os
from pathlib import Path
from typing import Optional, Dict, List, Callable
import json


class PennsieveAgent:
    """Interface to Pennsieve Agent CLI for map, download, and upload operations."""
    
    def __init__(self):
        """Initialize and verify Pennsieve Agent is installed."""
        self.agent_path = self._find_pennsieve_agent()
        if not self.agent_path:
            raise RuntimeError(
                "Pennsieve Agent not found. Install with: pip install pennsieve"
            )
    
    def _find_pennsieve_agent(self) -> Optional[str]:
        """Find Pennsieve Agent executable."""
        agent = shutil.which('pennsieve')
        if agent:
            # Verify it works
            try:
                result = subprocess.run(
                    [agent, '--version'],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return agent
            except Exception:
                pass
        return None
    
    def _build_env(self, api_key: str, api_secret: str) -> dict:
        """Build environment with Pennsieve credentials."""
        env = os.environ.copy()
        env['PENNSIEVE_API_KEY'] = api_key
        env['PENNSIEVE_API_SECRET'] = api_secret
        return env
    
    def verify_connection(self, api_key: str, api_secret: str) -> bool:
        """
        Verify Pennsieve credentials work.
        
        Args:
            api_key: Pennsieve API key
            api_secret: Pennsieve API secret
            
        Returns:
            bool: True if connection successful
        """
        try:
            env = self._build_env(api_key, api_secret)
            
            result = subprocess.run(
                [self.agent_path, 'whoami'],
                capture_output=True,
                text=True,
                env=env,
                timeout=10
            )
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"Connection verification failed: {e}")
            return False
    
    # ===== DOWNLOAD OPERATIONS =====
    
    def map_dataset(self, 
                    dataset_name: str, 
                    target_path: str,
                    api_key: str,
                    api_secret: str,
                    progress_callback: Callable[[str], None] = None) -> bool:
        """
        Map Pennsieve dataset structure locally without downloading files.
        Creates folder structure with empty stub files.
        
        Args:
            dataset_name: Name of Pennsieve dataset
            target_path: Local directory to create structure
            api_key: Pennsieve API key
            api_secret: Pennsieve API secret
            progress_callback: Optional callback(message) for progress updates
            
        Returns:
            bool: True if mapping successful
        """
        try:
            if progress_callback:
                progress_callback(f"Starting dataset mapping: {dataset_name}")
            
            env = self._build_env(api_key, api_secret)
            
            # Ensure target path doesn't exist (pennsieve requirement)
            target = Path(target_path)
            if target.exists():
                if progress_callback:
                    progress_callback("Target path exists, using existing structure")
                return True
            
            # Run: pennsieve map <dataset> <path>
            cmd = [self.agent_path, 'map', dataset_name, str(target_path)]
            
            if progress_callback:
                progress_callback(f"Executing: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            # Stream output
            for line in process.stdout:
                line = line.strip()
                if line and progress_callback:
                    progress_callback(line)
            
            process.wait()
            
            if process.returncode == 0:
                if progress_callback:
                    progress_callback("✓ Dataset mapping complete")
                return True
            else:
                error = process.stderr.read()
                if progress_callback:
                    progress_callback(f"✗ Mapping failed: {error}")
                print(f"Mapping error: {error}")
                return False
                
        except Exception as e:
            if progress_callback:
                progress_callback(f"✗ Error: {e}")
            print(f"Exception during mapping: {e}")
            return False
    
    def pull_file(self,
                  file_path: str,
                  api_key: str,
                  api_secret: str,
                  progress_callback: Callable[[Optional[float], str], None] = None) -> bool:
        """
        Download a specific file from mapped dataset.
        
        Args:
            file_path: Path to file in mapped structure
            api_key: Pennsieve API key
            api_secret: Pennsieve API secret
            progress_callback: Optional callback(progress_pct, message) for updates
            
        Returns:
            bool: True if download successful
        """
        try:
            if progress_callback:
                progress_callback(0, f"Downloading: {Path(file_path).name}")
            
            env = self._build_env(api_key, api_secret)
            
            # Run: pennsieve map pull <file_path>
            cmd = [self.agent_path, 'map', 'pull', str(file_path)]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            # Parse progress from output
            for line in process.stdout:
                line = line.strip()
                
                if not line:
                    continue
                
                # Try to parse progress percentage
                if '%' in line:
                    try:
                        pct_str = line.split('%')[0].split()[-1]
                        pct = float(pct_str)
                        if progress_callback:
                            progress_callback(pct, line)
                    except (ValueError, IndexError):
                        if progress_callback:
                            progress_callback(None, line)
                elif progress_callback:
                    progress_callback(None, line)
            
            process.wait()
            
            if process.returncode == 0:
                if progress_callback:
                    progress_callback(100, "✓ Download complete")
                return True
            else:
                error = process.stderr.read()
                if progress_callback:
                    progress_callback(0, f"✗ Download failed: {error}")
                print(f"Download error: {error}")
                return False
                
        except Exception as e:
            if progress_callback:
                progress_callback(0, f"✗ Error: {e}")
            print(f"Exception during download: {e}")
            return False
    
    def batch_pull(self,
                   file_paths: List[str],
                   api_key: str,
                   api_secret: str,
                   progress_callback: Callable[[int, int, str], None] = None) -> Dict:
        """
        Download multiple files with progress tracking.
        
        Args:
            file_paths: List of file paths to download
            api_key: Pennsieve API key
            api_secret: Pennsieve API secret
            progress_callback: Optional callback(completed, total, current_file)
            
        Returns:
            dict: {'successful': int, 'failed': int, 'errors': list}
        """
        results = {'successful': 0, 'failed': 0, 'errors': []}
        total = len(file_paths)
        
        for i, file_path in enumerate(file_paths):
            file_name = Path(file_path).name
            
            if progress_callback:
                progress_callback(i, total, file_name)
            
            def file_progress_callback(pct, msg):
                # Nested callback for individual file progress
                if progress_callback and pct is not None:
                    overall_pct = ((i + pct/100) / total) * 100
                    progress_callback(i, total, f"{file_name}: {pct:.0f}%")
            
            success = self.pull_file(file_path, api_key, api_secret, file_progress_callback)
            
            if success:
                results['successful'] += 1
            else:
                results['failed'] += 1
                results['errors'].append(file_path)
        
        if progress_callback:
            progress_callback(total, total, "Complete")
        
        return results
    
    # ===== UPLOAD OPERATIONS =====
    
    def upload_file(self,
                    local_path: str,
                    dataset_name: str,
                    remote_path: str,
                    api_key: str,
                    api_secret: str,
                    progress_callback: Callable[[Optional[float], str], None] = None) -> bool:
        """
        Upload a file to Pennsieve dataset.
        
        Args:
            local_path: Path to local file
            dataset_name: Target Pennsieve dataset name
            remote_path: Remote directory path (e.g., "derivatives/sub-001/")
            api_key: Pennsieve API key
            api_secret: Pennsieve API secret
            progress_callback: Optional callback(progress_pct, message)
            
        Returns:
            bool: True if upload successful
        """
        try:
            local_file = Path(local_path)
            
            if not local_file.exists():
                if progress_callback:
                    progress_callback(0, f"✗ File not found: {local_path}")
                return False
            
            if progress_callback:
                progress_callback(0, f"Uploading: {local_file.name}")
            
            env = self._build_env(api_key, api_secret)
            
            # Set working dataset first
            subprocess.run(
                [self.agent_path, 'dataset', dataset_name],
                env=env,
                capture_output=True,
                timeout=10
            )
            
            # Run: pennsieve upload <local_path> -d <remote_path>
            cmd = [self.agent_path, 'upload', str(local_path)]
            if remote_path:
                cmd.extend(['-d', remote_path])
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            # Parse progress from output
            for line in process.stdout:
                line = line.strip()
                
                if not line:
                    continue
                
                # Parse upload progress
                if '%' in line or 'Uploading' in line:
                    try:
                        if '%' in line:
                            pct_str = line.split('%')[0].split()[-1]
                            pct = float(pct_str)
                            if progress_callback:
                                progress_callback(pct, line)
                        else:
                            if progress_callback:
                                progress_callback(None, line)
                    except (ValueError, IndexError):
                        if progress_callback:
                            progress_callback(None, line)
                elif progress_callback:
                    progress_callback(None, line)
            
            process.wait()
            
            if process.returncode == 0:
                if progress_callback:
                    progress_callback(100, "✓ Upload complete")
                return True
            else:
                error = process.stderr.read()
                if progress_callback:
                    progress_callback(0, f"✗ Upload failed: {error}")
                print(f"Upload error: {error}")
                return False
                
        except Exception as e:
            if progress_callback:
                progress_callback(0, f"✗ Error: {e}")
            print(f"Exception during upload: {e}")
            return False
    
    def batch_upload(self,
                     file_paths: List[str],
                     dataset_name: str,
                     remote_base_path: str,
                     api_key: str,
                     api_secret: str,
                     progress_callback: Callable[[int, int, str], None] = None) -> Dict:
        """
        Upload multiple files with progress tracking.
        
        Args:
            file_paths: List of local file paths to upload
            dataset_name: Target Pennsieve dataset
            remote_base_path: Base remote directory
            api_key: Pennsieve API key
            api_secret: Pennsieve API secret
            progress_callback: Optional callback(completed, total, current_file)
            
        Returns:
            dict: {'successful': int, 'failed': int, 'errors': list}
        """
        results = {'successful': 0, 'failed': 0, 'errors': []}
        total = len(file_paths)
        
        for i, file_path in enumerate(file_paths):
            file_name = Path(file_path).name
            
            if progress_callback:
                progress_callback(i, total, file_name)
            
            def file_progress_callback(pct, msg):
                if progress_callback and pct is not None:
                    progress_callback(i, total, f"{file_name}: {pct:.0f}%")
            
            success = self.upload_file(
                file_path,
                dataset_name,
                remote_base_path,
                api_key,
                api_secret,
                file_progress_callback
            )
            
            if success:
                results['successful'] += 1
            else:
                results['failed'] += 1
                results['errors'].append(file_path)
        
        if progress_callback:
            progress_callback(total, total, "Upload complete")
        
        return results
    
    # ===== FILE STATUS OPERATIONS =====
    
    def get_file_status(self, file_path: str) -> Dict:
        """
        Check if file is mapped, downloaded, or not mapped.
        
        Args:
            file_path: Path to check
            
        Returns:
            dict: {
                'status': 'not_mapped' | 'mapped' | 'downloaded',
                'size': bytes,
                'exists': bool
            }
        """
        path = Path(file_path)
        
        if not path.exists():
            return {
                'status': 'not_mapped',
                'size': 0,
                'exists': False
            }
        
        size = path.stat().st_size
        
        # If file size > 0, it's downloaded
        # If size == 0, it's a stub (mapped but not downloaded)
        if size > 0:
            return {
                'status': 'downloaded',
                'size': size,
                'exists': True
            }
        else:
            return {
                'status': 'mapped',
                'size': 0,
                'exists': True
            }
    
    def is_stub_file(self, file_path: str) -> bool:
        """
        Check if file is a stub (mapped but not downloaded).
        
        Args:
            file_path: Path to check
            
        Returns:
            bool: True if file is a stub
        """
        path = Path(file_path)
        return path.exists() and path.stat().st_size == 0
    
    def get_remote_dataset_structure(self,
                                     dataset_name: str,
                                     api_key: str,
                                     api_secret: str) -> Dict:
        """
        Get dataset structure from Pennsieve without downloading.
        Uses 'pennsieve list' to browse remote files.
        
        Args:
            dataset_name: Name of Pennsieve dataset
            api_key: Pennsieve API key
            api_secret: Pennsieve API secret
            
        Returns:
            dict: {
                'subjects': [list of subject IDs],
                'sessions': {subject_id: [sessions]},
                'files': {subject_id: {session: [files]}}
            }
        """
        try:
            env = self._build_env(api_key, api_secret)
            
            # Set active dataset
            subprocess.run(
                [self.agent_path, 'use', dataset_name],
                env=env,
                capture_output=True,
                timeout=10
            )
            
            # List all files in dataset
            result = subprocess.run(
                [self.agent_path, 'ls', '-l'],
                env=env,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"Failed to list dataset: {result.stderr}")
                return {'subjects': [], 'sessions': {}, 'files': {}}
            
            # Parse output to extract BIDS structure
            structure = {
                'subjects': set(),
                'sessions': {},
                'files': {}
            }
            
            lines = result.stdout.split('\n')
            for line in lines:
                # Look for BIDS-like paths (sub-XXX/ses-XXX/...)
                if 'sub-' in line:
                    parts = line.split('/')
                    for i, part in enumerate(parts):
                        if part.startswith('sub-'):
                            subject_id = part.replace('sub-', '')
                            structure['subjects'].add(subject_id)
                            
                            # Look for session
                            if i + 1 < len(parts) and parts[i + 1].startswith('ses-'):
                                session = parts[i + 1].replace('ses-', '')
                                if subject_id not in structure['sessions']:
                                    structure['sessions'][subject_id] = set()
                                structure['sessions'][subject_id].add(session)
            
            # Convert sets to lists
            structure['subjects'] = sorted(list(structure['subjects']))
            structure['sessions'] = {k: sorted(list(v)) for k, v in structure['sessions'].items()}
            
            return structure
            
        except Exception as e:
            print(f"Error getting remote structure: {e}")
            return {'subjects': [], 'sessions': {}, 'files': {}}
    
    def get_directory_status(self, directory_path: str) -> Dict:
        """
        Get status summary for all files in a directory.
        
        Args:
            directory_path: Directory to analyze
            
        Returns:
            dict: {
                'total_files': int,
                'mapped': int,
                'downloaded': int,
                'not_mapped': int,
                'total_size': bytes
            }
        """
        dir_path = Path(directory_path)
        
        if not dir_path.exists():
            return {
                'total_files': 0,
                'mapped': 0,
                'downloaded': 0,
                'not_mapped': 0,
                'total_size': 0
            }
        
        stats = {
            'total_files': 0,
            'mapped': 0,
            'downloaded': 0,
            'not_mapped': 0,
            'total_size': 0
        }
        
        # Recursively check all files
        for file_path in dir_path.rglob('*'):
            if file_path.is_file():
                stats['total_files'] += 1
                status = self.get_file_status(str(file_path))
                
                if status['status'] == 'downloaded':
                    stats['downloaded'] += 1
                    stats['total_size'] += status['size']
                elif status['status'] == 'mapped':
                    stats['mapped'] += 1
        
        stats['not_mapped'] = stats['total_files'] - stats['mapped'] - stats['downloaded']
        
        return stats


# Helper function for checking available space
def check_available_space(path: str = '.') -> int:
    """
    Check available disk space.
    
    Args:
        path: Path to check (defaults to current directory)
        
    Returns:
        int: Available space in bytes
    """
    try:
        stat = os.statvfs(path)
        return stat.f_bavail * stat.f_frsize
    except (OSError, AttributeError):
        # Windows fallback
        try:
            import shutil
            usage = shutil.disk_usage(path)
            return usage.free
        except Exception:
            return 0
