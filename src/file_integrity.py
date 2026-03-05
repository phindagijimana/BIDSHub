"""
File Integrity Verification for BIDSHub (v3.1.1+).

Provides checksum calculation and verification for downloads and transfers.
"""

import hashlib
from pathlib import Path
from typing import Optional, Callable, Dict
import logging

logger = logging.getLogger(__name__)


def calculate_checksum(file_path: str, algorithm: str = 'sha256',
                      progress_callback: Callable[[int, int], None] = None) -> Optional[str]:
    """
    Calculate checksum for a file.
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm (md5, sha1, sha256, sha512)
        progress_callback: Optional callback(bytes_read, total_bytes)
        
    Returns:
        str: Hexadecimal checksum string, or None if error
    """
    try:
        file_obj = Path(file_path)
        
        if not file_obj.exists():
            logger.error(f"File not found: {file_path}")
            return None
        
        # Get file size for progress
        file_size = file_obj.stat().st_size
        
        # Initialize hash object
        if algorithm == 'md5':
            hasher = hashlib.md5()
        elif algorithm == 'sha1':
            hasher = hashlib.sha1()
        elif algorithm == 'sha256':
            hasher = hashlib.sha256()
        elif algorithm == 'sha512':
            hasher = hashlib.sha512()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        # Read file in chunks and update hash
        bytes_read = 0
        chunk_size = 8192  # 8KB chunks
        
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                hasher.update(chunk)
                bytes_read += len(chunk)
                
                if progress_callback and file_size > 0:
                    progress_callback(bytes_read, file_size)
        
        return hasher.hexdigest()
        
    except Exception as e:
        logger.error(f"Checksum calculation failed for {file_path}: {e}")
        return None


def verify_checksum(file_path: str, expected_checksum: str,
                   algorithm: str = 'sha256') -> bool:
    """
    Verify file checksum matches expected value.
    
    Args:
        file_path: Path to file
        expected_checksum: Expected checksum (hexadecimal string)
        algorithm: Hash algorithm used
        
    Returns:
        bool: True if checksum matches
    """
    try:
        actual_checksum = calculate_checksum(file_path, algorithm)
        
        if not actual_checksum:
            return False
        
        # Case-insensitive comparison
        return actual_checksum.lower() == expected_checksum.lower()
        
    except Exception as e:
        logger.error(f"Checksum verification failed: {e}")
        return False


def verify_file_size(file_path: str, expected_size: int,
                    tolerance_bytes: int = 0) -> bool:
    """
    Verify file size matches expected value.
    
    Args:
        file_path: Path to file
        expected_size: Expected size in bytes
        tolerance_bytes: Acceptable size difference (default: 0 = exact match)
        
    Returns:
        bool: True if size matches within tolerance
    """
    try:
        file_obj = Path(file_path)
        
        if not file_obj.exists():
            logger.error(f"File not found: {file_path}")
            return False
        
        actual_size = file_obj.stat().st_size
        size_diff = abs(actual_size - expected_size)
        
        if size_diff <= tolerance_bytes:
            return True
        else:
            logger.warning(
                f"Size mismatch for {file_path}: "
                f"expected {expected_size}, got {actual_size} "
                f"(diff: {size_diff} bytes)"
            )
            return False
        
    except Exception as e:
        logger.error(f"Size verification failed: {e}")
        return False


def quick_verify(file_path: str, expected_size: int = None,
                expected_checksum: str = None,
                algorithm: str = 'sha256') -> Dict[str, bool]:
    """
    Quick verification of file integrity.
    
    Args:
        file_path: Path to file
        expected_size: Optional expected size
        expected_checksum: Optional expected checksum
        algorithm: Hash algorithm for checksum
        
    Returns:
        dict: {'exists': bool, 'size_ok': bool, 'checksum_ok': bool}
    """
    result = {
        'exists': False,
        'size_ok': None,
        'checksum_ok': None
    }
    
    file_obj = Path(file_path)
    result['exists'] = file_obj.exists()
    
    if not result['exists']:
        return result
    
    if expected_size is not None:
        result['size_ok'] = verify_file_size(file_path, expected_size)
    
    if expected_checksum is not None:
        result['checksum_ok'] = verify_checksum(file_path, expected_checksum, algorithm)
    
    return result


def create_checksum_file(file_path: str, algorithm: str = 'sha256') -> Optional[str]:
    """
    Create a checksum file alongside the data file.
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm
        
    Returns:
        str: Path to checksum file, or None if error
    """
    try:
        checksum = calculate_checksum(file_path, algorithm)
        
        if not checksum:
            return None
        
        # Create checksum file with same name + .{algorithm} extension
        checksum_file = f"{file_path}.{algorithm}"
        
        with open(checksum_file, 'w') as f:
            f.write(f"{checksum}  {Path(file_path).name}\n")
        
        logger.info(f"Created checksum file: {checksum_file}")
        return checksum_file
        
    except Exception as e:
        logger.error(f"Failed to create checksum file: {e}")
        return None


def verify_from_checksum_file(file_path: str, checksum_file: str = None,
                              algorithm: str = 'sha256') -> bool:
    """
    Verify file against a checksum file.
    
    Args:
        file_path: Path to file
        checksum_file: Path to checksum file (default: file_path.{algorithm})
        algorithm: Hash algorithm
        
    Returns:
        bool: True if checksum matches
    """
    try:
        if not checksum_file:
            checksum_file = f"{file_path}.{algorithm}"
        
        checksum_path = Path(checksum_file)
        
        if not checksum_path.exists():
            logger.warning(f"Checksum file not found: {checksum_file}")
            return False
        
        # Read expected checksum
        with open(checksum_file, 'r') as f:
            line = f.readline().strip()
            expected_checksum = line.split()[0]  # Format: "checksum  filename"
        
        return verify_checksum(file_path, expected_checksum, algorithm)
        
    except Exception as e:
        logger.error(f"Checksum file verification failed: {e}")
        return False
