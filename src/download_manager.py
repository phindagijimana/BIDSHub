"""
Download Manager for Data Explorer.

Handles concurrent downloads from Pennsieve with progress tracking
and queue management.
"""

import os
import threading
import time
from pathlib import Path
from typing import List, Dict, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime
import queue


class DownloadManager:
    """Manages concurrent downloads from Pennsieve."""
    
    def __init__(self, ps_client, database, max_concurrent=3):
        """
        Initialize download manager.
        
        Args:
            ps_client: PennsieveClient instance
            database: Database instance
            max_concurrent: Maximum concurrent downloads
        """
        self.ps_client = ps_client
        self.db = database
        self.max_concurrent = max_concurrent
        
        # Thread pool for downloads
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        
        # Active downloads tracking
        self.active_downloads: Dict[int, Future] = {}
        self.download_progress: Dict[int, float] = {}
        
        # Control flags
        self.is_paused = False
        self.stop_requested = False
        
        # Lock for thread safety
        self.lock = threading.Lock()
    
    def add_to_queue(self, scan_id: int, subject_id: str, 
                    file_path: str, package_id: str,
                    file_size: int = 0, priority: int = 0) -> bool:
        """
        Add a file to the download queue.
        
        Args:
            scan_id: Scan ID in database
            subject_id: Subject identifier
            file_path: Local file path for download
            package_id: Pennsieve package ID
            file_size: File size in bytes
            priority: Download priority (higher = first)
            
        Returns:
            bool: True if added successfully
        """
        try:
            queue_id = self.db.add_to_download_queue(
                scan_id=scan_id,
                subject_id=subject_id,
                file_path=file_path,
                file_size_bytes=file_size,
                priority=priority
            )
            return queue_id is not None
        except Exception as e:
            print(f"Error adding to queue: {e}")
            return False
    
    def get_queue_items(self, status: str = None) -> List[Dict]:
        """
        Get items from download queue.
        
        Args:
            status: Optional status filter
            
        Returns:
            List of queue items
        """
        return self.db.get_download_queue(status)
    
    def get_queued_count(self) -> int:
        """Get count of queued items."""
        items = self.get_queue_items('queued')
        return len(items)
    
    def get_total_queue_size(self) -> int:
        """Get total size of queued downloads in bytes."""
        items = self.get_queue_items('queued')
        return sum(item.get('file_size_bytes', 0) for item in items)
    
    def start_downloads(self, callback: Callable = None) -> bool:
        """
        Start processing the download queue.
        
        Args:
            callback: Optional callback function for progress updates
            
        Returns:
            bool: True if started successfully
        """
        if self.is_paused:
            self.resume_downloads()
            return True
        
        try:
            # Get queued items
            queued = self.get_queue_items('queued')
            
            if not queued:
                return False
            
            # Submit download tasks
            for item in queued[:self.max_concurrent]:
                self._submit_download(item, callback)
            
            return True
            
        except Exception as e:
            print(f"Error starting downloads: {e}")
            return False
    
    def _submit_download(self, queue_item: Dict, callback: Callable = None):
        """Submit a download task to the executor."""
        queue_id = queue_item['id']
        
        # Submit to thread pool
        future = self.executor.submit(
            self._download_file,
            queue_item,
            callback
        )
        
        # Track active download
        with self.lock:
            self.active_downloads[queue_id] = future
            self.download_progress[queue_id] = 0.0
    
    def _download_file(self, queue_item: Dict, callback: Callable = None) -> bool:
        """
        Download a single file (runs in thread).
        
        Args:
            queue_item: Queue item dictionary
            callback: Progress callback function
            
        Returns:
            bool: True if successful
        """
        queue_id = queue_item['id']
        scan_id = queue_item['scan_id']
        file_path = queue_item['file_path']
        
        try:
            # Update status to downloading
            self.db.update_queue_status(queue_id, 'downloading')
            
            # Get package ID from scan
            scan = self.db.get_subject_scans(queue_item['subject_id'])
            package_id = None
            for s in scan:
                if s['id'] == scan_id:
                    package_id = s.get('pennsieve_package_id')
                    break
            
            if not package_id:
                # Try to read from stub file
                if os.path.exists(file_path):
                    from src.utils import parse_pennsieve_stub
                    package_id = parse_pennsieve_stub(file_path)
            
            if not package_id:
                raise ValueError("Package ID not found")
            
            # Create destination directory
            dest_dir = os.path.dirname(file_path)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)
            
            # Download from Pennsieve
            success = self.ps_client.download_file(package_id, file_path)
            
            if success:
                # Update scan status
                self.db.update_scan_status(
                    scan_id=scan_id,
                    is_downloaded=True,
                    download_date=datetime.now()
                )
                
                # Update queue status
                self.db.update_queue_status(queue_id, 'completed')
                
                # Update progress
                with self.lock:
                    self.download_progress[queue_id] = 100.0
                
                if callback:
                    callback(queue_id, 100.0, 'completed')
                
                return True
            else:
                raise Exception("Download failed")
                
        except Exception as e:
            print(f"Download failed for queue item {queue_id}: {e}")
            
            # Update queue status
            self.db.update_queue_status(
                queue_id,
                'failed',
                error_message=str(e)
            )
            
            if callback:
                callback(queue_id, 0, 'failed')
            
            return False
            
        finally:
            # Remove from active downloads
            with self.lock:
                if queue_id in self.active_downloads:
                    del self.active_downloads[queue_id]
            
            # Start next queued download if available
            if not self.is_paused:
                self._start_next_download(callback)
    
    def _start_next_download(self, callback: Callable = None):
        """Start the next queued download if available."""
        queued = self.get_queue_items('queued')
        
        if queued and len(self.active_downloads) < self.max_concurrent:
            next_item = queued[0]
            self._submit_download(next_item, callback)
    
    def pause_downloads(self):
        """Pause all downloads."""
        self.is_paused = True
        
        # Update status of downloading items to paused
        downloading = self.get_queue_items('downloading')
        for item in downloading:
            self.db.update_queue_status(item['id'], 'paused')
    
    def resume_downloads(self, callback: Callable = None):
        """Resume paused downloads."""
        self.is_paused = False
        
        # Update paused items back to queued
        paused = self.get_queue_items('paused')
        for item in paused:
            self.db.update_queue_status(item['id'], 'queued')
        
        # Start downloads
        self.start_downloads(callback)
    
    def clear_queue(self, status: str = None) -> int:
        """
        Clear items from queue.
        
        Args:
            status: Optional status to clear (default: all non-active)
            
        Returns:
            Number of items cleared
        """
        # For MVP, we'll clear by deleting from database
        # This is a simplified implementation
        items = self.get_queue_items(status) if status else self.get_queue_items()
        
        # Only clear non-downloading items
        cleared = 0
        for item in items:
            if item['status'] != 'downloading':
                # In a real implementation, we'd have a delete method
                # For now, we'll update to a 'cleared' status
                self.db.update_queue_status(item['id'], 'cleared')
                cleared += 1
        
        return cleared
    
    def remove_from_queue(self, queue_id: int) -> bool:
        """
        Remove a specific item from queue.
        
        Args:
            queue_id: Queue item ID
            
        Returns:
            bool: True if removed
        """
        try:
            self.db.update_queue_status(queue_id, 'removed')
            return True
        except Exception as e:
            print(f"Error removing from queue: {e}")
            return False
    
    def get_download_stats(self) -> Dict:
        """
        Get download statistics.
        
        Returns:
            Dictionary with download stats
        """
        all_items = self.get_queue_items()
        
        stats = {
            'total': len(all_items),
            'queued': len([i for i in all_items if i['status'] == 'queued']),
            'downloading': len([i for i in all_items if i['status'] == 'downloading']),
            'completed': len([i for i in all_items if i['status'] == 'completed']),
            'failed': len([i for i in all_items if i['status'] == 'failed']),
            'paused': len([i for i in all_items if i['status'] == 'paused']),
        }
        
        # Calculate sizes
        stats['queued_size'] = sum(
            i.get('file_size_bytes', 0) 
            for i in all_items if i['status'] == 'queued'
        )
        
        stats['completed_size'] = sum(
            i.get('file_size_bytes', 0) 
            for i in all_items if i['status'] == 'completed'
        )
        
        # Calculate progress
        if stats['total'] > 0:
            stats['progress_pct'] = (stats['completed'] / stats['total']) * 100
        else:
            stats['progress_pct'] = 0
        
        return stats
    
    def get_active_downloads(self) -> List[Dict]:
        """Get list of currently downloading items."""
        return self.get_queue_items('downloading')
    
    def is_downloading(self) -> bool:
        """Check if any downloads are active."""
        return len(self.active_downloads) > 0
    
    def shutdown(self):
        """Shutdown the download manager."""
        self.stop_requested = True
        self.executor.shutdown(wait=True)


def estimate_download_time(file_size_bytes: int, 
                          bandwidth_mbps: float = 10.0) -> float:
    """
    Estimate download time in seconds.
    
    Args:
        file_size_bytes: File size in bytes
        bandwidth_mbps: Bandwidth in Mbps
        
    Returns:
        Estimated time in seconds
    """
    # Convert bandwidth to bytes per second
    bytes_per_second = (bandwidth_mbps * 1024 * 1024) / 8
    
    # Calculate time
    seconds = file_size_bytes / bytes_per_second
    
    return seconds


def check_available_space(path: str) -> int:
    """
    Check available disk space at path.
    
    Args:
        path: Directory path
        
    Returns:
        Available space in bytes
    """
    import shutil
    stat = shutil.disk_usage(path)
    return stat.free


# Testing
if __name__ == "__main__":
    print("Download Manager - Test Module")
    print("=" * 50)
    
    # Test estimation
    file_sizes = [
        1024**2,      # 1 MB
        100 * 1024**2,  # 100 MB
        1024**3,      # 1 GB
    ]
    
    print("\nDownload Time Estimates (10 Mbps):")
    for size in file_sizes:
        from src.utils import format_file_size
        time_sec = estimate_download_time(size, 10.0)
        time_min = time_sec / 60
        print(f"  {format_file_size(size):>10} → {time_min:.1f} minutes")
    
    # Test disk space
    print("\nDisk Space:")
    space = check_available_space('.')
    from src.utils import format_file_size
    print(f"  Available: {format_file_size(space)}")
