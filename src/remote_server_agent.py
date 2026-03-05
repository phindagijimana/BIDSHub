"""
Remote Server Agent for BIDSHub.

Provides interface to access BIDS datasets on remote servers via SSH/SFTP.
Generic SSH/SFTP client for any remote Linux/Unix server with BIDS data.
"""

import paramiko
from pathlib import Path
from typing import Optional, Dict, List, Callable
import logging
import json
import stat
import os

logger = logging.getLogger(__name__)


class RemoteServerAgent:
    """Interface to remote servers for BIDS dataset access via SSH/SFTP."""
    
    def __init__(self, host: str, username: str, password: str = None,
                 key_file: str = None, port: int = 22):
        """
        Initialize remote server agent with SSH connection.
        
        Args:
            host: Server hostname or IP (e.g., 'data.lab.edu', '192.168.1.100')
            username: SSH username
            password: SSH password (optional if using key)
            key_file: Path to SSH private key file (optional)
            port: SSH port (default: 22)
        """
        self.host = host
        self.username = username
        self.password = password
        self.key_file = key_file
        self.port = port
        
        self.ssh_client = None
        self.sftp_client = None
        self._connection_active = False
        
        self._verify_installation()
    
    def _verify_installation(self):
        """Verify paramiko is installed."""
        try:
            import paramiko
        except ImportError:
            raise RuntimeError(
                "Paramiko library not found. Install with: pip install paramiko"
            )
    
    def _ensure_connected(self) -> bool:
        """
        Ensure SSH connection is active (v3.1.1+ connection pooling).
        
        Reuses existing connection if active, otherwise creates new one.
        
        Returns:
            bool: True if connection is ready
        """
        # Check if connection is still alive
        if self._connection_active and self.ssh_client:
            try:
                transport = self.ssh_client.get_transport()
                if transport and transport.is_active():
                    return True
            except:
                pass
        
        # Connection dead or never established, reconnect
        return self.connect()
    
    def connect(self) -> bool:
        """
        Establish SSH connection to remote server.
        
        Returns:
            bool: True if connection successful
        """
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect with password or key
            if self.key_file:
                self.ssh_client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    key_filename=self.key_file,
                    timeout=10
                )
            elif self.password:
                self.ssh_client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=10
                )
            else:
                raise ValueError("Either password or key_file must be provided")
            
            # Open SFTP channel
            self.sftp_client = self.ssh_client.open_sftp()
            
            self._connection_active = True
            logger.info(f"Connected to remote server: {self.host}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to {self.host}: {e}")
            self._connection_active = False
            return False
    
    def disconnect(self):
        """Close SSH/SFTP connection."""
        if self.sftp_client:
            self.sftp_client.close()
            self.sftp_client = None
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None
        self._connection_active = False
    
    def verify_connection(self) -> bool:
        """
        Verify SSH connection works.
        
        Returns:
            bool: True if connection successful
        """
        try:
            if not self._ensure_connected():
                return False
            
            # Test connection with simple command
            stdin, stdout, stderr = self.ssh_client.exec_command('echo "test"')
            output = stdout.read().decode().strip()
            
            return output == "test"
            
        except Exception as e:
            logger.error(f"Connection verification failed: {e}")
            return False
    
    def list_bids_datasets(self, base_path: str) -> List[Dict]:
        """
        List available BIDS datasets on remote server.
        
        Args:
            base_path: Base directory to search for BIDS datasets
            
        Returns:
            List of dataset dicts with name, path, and description
        """
        datasets = []
        
        try:
            if not self._ensure_connected():
                return []
            
            # Look for dataset_description.json files
            stdin, stdout, stderr = self.ssh_client.exec_command(
                f'find {base_path} -maxdepth 3 -name "dataset_description.json" -type f 2>/dev/null | head -20'
            )
            
            dataset_json_files = stdout.read().decode().strip().split('\n')
            
            for json_file in dataset_json_files:
                if not json_file:
                    continue
                
                dataset_dir = str(Path(json_file).parent)
                
                # Read dataset_description.json via SFTP
                try:
                    with self.sftp_client.open(json_file, 'r') as f:
                        dataset_info = json.load(f)
                    
                    datasets.append({
                        'name': dataset_info.get('Name', Path(dataset_dir).name),
                        'path': dataset_dir,
                        'description': dataset_info.get('BIDSVersion', 'Unknown'),
                        'authors': dataset_info.get('Authors', [])
                    })
                except:
                    # Fallback if can't read JSON
                    datasets.append({
                        'name': Path(dataset_dir).name,
                        'path': dataset_dir,
                        'description': 'BIDS dataset'
                    })
            
            return datasets
            
        except Exception as e:
            logger.error(f"Error listing datasets: {e}")
            return []
    
    def get_subjects_with_metadata(self, dataset_path: str) -> List[Dict]:
        """
        Fetch subject list with metadata from remote BIDS dataset.
        
        Args:
            dataset_path: Path to BIDS dataset on remote server
            
        Returns:
            List of dicts with subject info
        """
        try:
            if not self._ensure_connected():
                return []
            
            # List subject directories
            stdin, stdout, stderr = self.ssh_client.exec_command(
                f'ls -1 {dataset_path} | grep "^sub-"'
            )
            
            subjects = stdout.read().decode().strip().split('\n')
            subjects = [s.strip() for s in subjects if s.strip()]
            
            result = []
            
            for subject_id in subjects:
                # List sessions for this subject using standardized approach (v3.1.1+)
                subject_path = f"{dataset_path}/{subject_id}"
                stdin, stdout, stderr = self.ssh_client.exec_command(
                    f'ls -1 {subject_path} 2>/dev/null | grep "^ses-" || echo ""'
                )
                
                sessions = stdout.read().decode().strip().split('\n')
                sessions = [s.strip() for s in sessions if s.strip() and s != '']
                
                # Detect modalities to populate has_* flags
                has_anat = False
                has_func = False
                has_dwi = False
                has_fmap = False
                
                if sessions:
                    # Multi-session: check first session for modalities
                    test_session = sessions[0]
                    stdin, stdout, stderr = self.ssh_client.exec_command(
                        f'ls -1 {subject_path}/{test_session} 2>/dev/null'
                    )
                    modalities = stdout.read().decode().strip().split('\n')
                    has_anat = 'anat' in modalities
                    has_func = 'func' in modalities
                    has_dwi = 'dwi' in modalities
                    has_fmap = 'fmap' in modalities
                else:
                    # Sessionless: check subject root for modalities
                    stdin, stdout, stderr = self.ssh_client.exec_command(
                        f'ls -1 {subject_path} 2>/dev/null'
                    )
                    modalities = stdout.read().decode().strip().split('\n')
                    has_anat = 'anat' in modalities
                    has_func = 'func' in modalities
                    has_dwi = 'dwi' in modalities
                    has_fmap = 'fmap' in modalities
                
                result.append({
                    'subject_id': subject_id,
                    'age': None,
                    'sex': None,
                    'diagnosis': None,
                    'participant_group': None,
                    'handedness': None,
                    'site': None,
                    'sessions': sessions if sessions else [],
                    'has_anat': has_anat,
                    'has_func': has_func,
                    'has_dwi': has_dwi,
                    'has_fmap': has_fmap,
                    'metadata': {}
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching subjects: {e}")
            return []
    
    def download_file(self, remote_path: str, local_path: str,
                     progress_callback: Callable[[int, int], None] = None) -> bool:
        """
        Download a file from remote server via SFTP.
        
        Args:
            remote_path: Full path on remote server
            local_path: Local destination path
            progress_callback: Optional callback(bytes_transferred, total_bytes)
            
        Returns:
            bool: True if download successful
        """
        try:
            if not self._ensure_connected():
                return False
            
            # Create local directory
            local_file = Path(local_path)
            local_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Get file size for progress
            file_stat = self.sftp_client.stat(remote_path)
            file_size = file_stat.st_size
            
            # Download with progress callback
            def progress(transferred, total):
                if progress_callback:
                    progress_callback(transferred, total)
            
            self.sftp_client.get(
                remotepath=remote_path,
                localpath=local_path,
                callback=progress if progress_callback else None
            )
            
            logger.info(f"Downloaded {remote_path} to {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False
    
    def download_subject(self, dataset_path: str, subject_id: str,
                        target_dir: str, sessions: List[str] = None,
                        progress_callback: Callable[[str], None] = None) -> bool:
        """
        Download all data for a subject from remote server.
        
        Args:
            dataset_path: BIDS dataset path on remote server
            subject_id: Subject identifier (e.g., 'sub-01')
            target_dir: Local target directory
            sessions: Optional list of sessions to download (default: all)
            progress_callback: Optional callback(message)
            
        Returns:
            bool: True if download successful
        """
        try:
            if not self._ensure_connected():
                return False
            
            subject_path = f"{dataset_path}/{subject_id}"
            
            # Check if subject exists
            try:
                self.sftp_client.stat(subject_path)
            except FileNotFoundError:
                logger.error(f"Subject not found: {subject_path}")
                return False
            
            if progress_callback:
                progress_callback(f"Downloading {subject_id}")
            
            # Download entire subject directory
            self._download_directory(subject_path, f"{target_dir}/{subject_id}", progress_callback)
            
            return True
            
        except Exception as e:
            logger.error(f"Subject download failed: {e}")
            return False
    
    def _download_directory(self, remote_dir: str, local_dir: str,
                           progress_callback: Callable[[str], None] = None):
        """
        Recursively download a directory via SFTP.
        
        Args:
            remote_dir: Remote directory path
            local_dir: Local directory path
            progress_callback: Optional callback(message)
        """
        os.makedirs(local_dir, exist_ok=True)
        
        for item in self.sftp_client.listdir_attr(remote_dir):
            remote_path = f"{remote_dir}/{item.filename}"
            local_path = f"{local_dir}/{item.filename}"
            
            if stat.S_ISDIR(item.st_mode):
                # Recursively download subdirectory
                self._download_directory(remote_path, local_path, progress_callback)
            else:
                # Download file
                if progress_callback:
                    progress_callback(f"Downloading {item.filename}")
                
                self.sftp_client.get(remote_path, local_path)
    
    def get_file_size(self, remote_path: str) -> int:
        """
        Get file size on remote server.
        
        Args:
            remote_path: Remote file path
            
        Returns:
            int: File size in bytes
        """
        try:
            if not self._ensure_connected():
                return 0
            
            file_stat = self.sftp_client.stat(remote_path)
            return file_stat.st_size
            
        except Exception as e:
            logger.error(f"Error getting file size: {e}")
            return 0
    
    def upload_file(self, local_path: str, remote_path: str, 
                   progress_callback: Callable[[int, int], None] = None) -> bool:
        """
        Upload a file to remote server via SFTP (v3.1.1+).
        
        Args:
            local_path: Local file path
            remote_path: Remote destination path (full path including filename)
            progress_callback: Optional callback(bytes_transferred, total_bytes)
            
        Returns:
            bool: True if upload successful
        """
        try:
            if not self._ensure_connected():
                return False
            
            local_file = Path(local_path)
            if not local_file.exists():
                logger.error(f"Local file not found: {local_path}")
                return False
            
            # Create remote directory if needed
            remote_dir = str(Path(remote_path).parent)
            try:
                self.sftp_client.stat(remote_dir)
            except FileNotFoundError:
                # Create parent directories recursively
                self._create_remote_directory(remote_dir)
            
            # Get file size
            file_size = local_file.stat().st_size
            
            # Upload with progress callback
            def progress(transferred, total):
                if progress_callback:
                    progress_callback(transferred, total)
            
            self.sftp_client.put(
                localpath=local_path,
                remotepath=remote_path,
                callback=progress if progress_callback else None
            )
            
            logger.info(f"Uploaded {local_path} to {remote_path}")
            return True
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False
    
    def _create_remote_directory(self, remote_path: str):
        """
        Create remote directory recursively via SFTP.
        
        Args:
            remote_path: Remote directory path to create
        """
        dirs_to_create = []
        current_path = remote_path
        
        # Find first existing parent
        while current_path and current_path != '/':
            try:
                self.sftp_client.stat(current_path)
                break
            except FileNotFoundError:
                dirs_to_create.append(current_path)
                current_path = str(Path(current_path).parent)
        
        # Create directories from parent to child
        for directory in reversed(dirs_to_create):
            try:
                self.sftp_client.mkdir(directory)
            except:
                pass


# Helper function
def check_remote_server_availability() -> bool:
    """
    Check if paramiko (SSH library) is installed.
    
    Returns:
        bool: True if available
    """
    try:
        import paramiko
        return True
    except ImportError:
        return False
