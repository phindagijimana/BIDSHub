"""
Pennsieve Client for Data Explorer.

Provides interface to Pennsieve platform for file metadata and downloads.
"""

from pennsieve import Pennsieve
from typing import Optional, Dict, List
import os
from pathlib import Path


class PennsieveClient:
    """Client for interacting with Pennsieve platform."""
    
    def __init__(self, api_key: str = None, api_secret: str = None,
                 dataset_name: str = None):
        """
        Initialize Pennsieve client.
        
        Args:
            api_key: Pennsieve API key (or from environment)
            api_secret: Pennsieve API secret (or from environment)
            dataset_name: Dataset name to connect to
        """
        # Use provided credentials or environment variables
        if api_key and api_secret:
            os.environ['PENNSIEVE_API_KEY'] = api_key
            os.environ['PENNSIEVE_API_SECRET'] = api_secret
        
        try:
            self.ps = Pennsieve()
            # Try to get user info if available (SDK version dependent)
            try:
                user_email = getattr(getattr(self.ps, 'context', None), 'user', None)
                if user_email:
                    print(f"[OK] Connected to Pennsieve as: {user_email.email}")
                else:
                    print("[OK] Connected to Pennsieve")
            except:
                print("[OK] Connected to Pennsieve")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Pennsieve: {e}")
        
        self.dataset = None
        if dataset_name:
            self.connect_dataset(dataset_name)
    
    def connect_dataset(self, dataset_name: str) -> bool:
        """
        Connect to a specific Pennsieve dataset.
        
        Args:
            dataset_name: Name of the dataset
            
        Returns:
            bool: True if successful
        """
        try:
            self.dataset = self.ps.get_dataset(dataset_name)
            print(f"[OK] Connected to dataset: {self.dataset.name}")
            print(f"  ID: {self.dataset.id}")
            print(f"  Storage: {self.format_size(self.dataset.storage)}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to connect to dataset '{dataset_name}': {e}")
            return False
    
    def list_datasets(self) -> List[str]:
        """
        List all available datasets for the user.
        
        Returns:
            List of dataset names
        """
        try:
            datasets = self.ps.datasets()
            return [ds.name for ds in datasets]
        except Exception as e:
            print(f"Error listing datasets: {e}")
            return []
    
    def get_file_info(self, file_path: str) -> Optional[Dict]:
        """
        Get file information from Pennsieve.
        
        Args:
            file_path: Relative path to file in dataset
            
        Returns:
            Dict with file information or None
        """
        if not self.dataset:
            print("Error: No dataset connected")
            return None
        
        try:
            # Try to find the package by name
            # Pennsieve stores files as "packages"
            file_name = Path(file_path).name
            
            # Search for the file
            items = self.dataset.items
            for item in items:
                if hasattr(item, 'name') and item.name == file_name:
                    return {
                        'name': item.name,
                        'id': item.id,
                        'size': getattr(item, 'size', 0),
                        'type': type(item).__name__,
                        'created_at': getattr(item, 'created_at', None),
                        'updated_at': getattr(item, 'updated_at', None)
                    }
            
            print(f"File not found in Pennsieve: {file_name}")
            return None
            
        except Exception as e:
            print(f"Error getting file info for {file_path}: {e}")
            return None
    
    def get_package(self, package_id: str):
        """
        Get a package by ID.
        
        Args:
            package_id: Pennsieve package ID
            
        Returns:
            Package object or None
        """
        if not self.dataset:
            print("Error: No dataset connected")
            return None
        
        try:
            return self.dataset.get_package(package_id)
        except Exception as e:
            print(f"Error getting package {package_id}: {e}")
            return None
    
    def get_package_size(self, package_id: str) -> int:
        """
        Get size of a package in bytes.
        
        Args:
            package_id: Pennsieve package ID
            
        Returns:
            Size in bytes, or 0 if not found
        """
        package = self.get_package(package_id)
        if package:
            return getattr(package, 'size', 0)
        return 0
    
    def read_stub_file(self, file_path: str) -> Optional[str]:
        """
        Read Pennsieve package ID from stub file.
        
        Pennsieve stub files contain the package ID that can be used
        to download the real file from Pennsieve.
        
        Args:
            file_path: Path to stub file
            
        Returns:
            Package ID string or None
        """
        try:
            with open(file_path, 'r') as f:
                content = f.read().strip()
                # Stub files typically contain just the package ID
                if content and len(content) < 200:  # Reasonable ID length
                    return content
            return None
        except Exception as e:
            print(f"Error reading stub file {file_path}: {e}")
            return None
    
    def download_file(self, package_id: str, destination: str) -> bool:
        """
        Download a file from Pennsieve.
        
        Args:
            package_id: Pennsieve package ID
            destination: Local destination path
            
        Returns:
            bool: True if successful
        """
        if not self.dataset:
            print("Error: No dataset connected")
            return False
        
        try:
            package = self.get_package(package_id)
            if not package:
                print(f"Package not found: {package_id}")
                return False
            
            # Ensure destination directory exists
            dest_dir = os.path.dirname(destination)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)
            
            # Download the package
            print(f"Downloading {package.name} to {destination}...")
            package.download(destination)
            
            # Verify download
            if os.path.exists(destination):
                size = os.path.getsize(destination)
                print(f"[OK] Downloaded {self.format_size(size)}")
                return True
            else:
                print("[ERROR] Download failed: File not created")
                return False
                
        except Exception as e:
            print(f"Error downloading {package_id}: {e}")
            return False
    
    def get_real_file_size_from_stub(self, stub_file_path: str) -> int:
        """
        Get the real file size from Pennsieve for a stub file.
        
        Args:
            stub_file_path: Path to local stub file
            
        Returns:
            Real file size in bytes, or 0 if not found
        """
        package_id = self.read_stub_file(stub_file_path)
        if package_id:
            return self.get_package_size(package_id)
        return 0
    
    @staticmethod
    def format_size(bytes: int) -> str:
        """
        Format byte size in human-readable format.
        
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
    
    def verify_connection(self) -> bool:
        """
        Verify Pennsieve connection and dataset access.
        
        Returns:
            bool: True if connected and can access dataset
        """
        try:
            # Check PS connection
            if not self.ps:
                return False
            
            # Check user (SDK version dependent)
            try:
                context = getattr(self.ps, 'context', None)
                if context and not getattr(context, 'user', None):
                    return False
            except:
                # If context check fails, assume connection is valid
                pass
            
            # Check dataset if connected
            if self.dataset:
                # Try to access dataset items
                _ = self.dataset.items
            
            return True
            
        except Exception as e:
            print(f"Connection verification failed: {e}")
            return False
    
    def get_dataset_stats(self) -> Dict:
        """
        Get dataset statistics.
        
        Returns:
            Dict with dataset stats
        """
        if not self.dataset:
            return {}
        
        try:
            stats = {
                'name': self.dataset.name,
                'id': self.dataset.id,
                'storage': self.dataset.storage,
                'storage_formatted': self.format_size(self.dataset.storage),
                'description': getattr(self.dataset, 'description', ''),
                'created_at': getattr(self.dataset, 'created_at', None),
                'updated_at': getattr(self.dataset, 'updated_at', None)
            }
            
            # Try to get package count
            try:
                items = self.dataset.items
                stats['package_count'] = len(items)
            except:
                stats['package_count'] = None
            
            return stats
            
        except Exception as e:
            print(f"Error getting dataset stats: {e}")
            return {}


# Example usage and testing
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Test connection
    try:
        client = PennsieveClient()
        
        print("\n" + "=" * 50)
        print("Available Datasets")
        print("=" * 50)
        
        datasets = client.list_datasets()
        for i, ds in enumerate(datasets, 1):
            print(f"{i}. {ds}")
        
        # If dataset name provided, connect to it
        if len(sys.argv) > 1:
            dataset_name = sys.argv[1]
            
            print("\n" + "=" * 50)
            print(f"Connecting to: {dataset_name}")
            print("=" * 50)
            
            if client.connect_dataset(dataset_name):
                stats = client.get_dataset_stats()
                print("\nDataset Statistics:")
                for key, value in stats.items():
                    if key not in ['id', 'description']:
                        print(f"  {key}: {value}")
                
                # Verify connection
                if client.verify_connection():
                    print("\n[OK] Connection verified")
                else:
                    print("\n[ERROR] Connection verification failed")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
