"""
Standardized Error Messages for BIDSHub (v3.1.1+).

Provides consistent, user-friendly error messages across all platforms.
"""

from typing import Dict


class ErrorMessages:
    """Centralized error message definitions."""
    
    # Connection errors
    CONNECTION_FAILED = {
        'pennsieve': "Failed to connect to Pennsieve. Check API Key/Secret and network connection.",
        'openneuro': "Failed to connect to OpenNeuro. Check internet connection.",
        'dandi': "Failed to connect to DANDI. Check API token (if using private dandisets) and network.",
        'xnat': "Failed to connect to XNAT. Verify server URL, username, and password.",
        'hpc': "Failed to connect to HPC. Check hostname, username, and SSH credentials.",
        'remote_server': "Failed to connect to remote server. Check hostname, username, and SSH credentials.",
        'local': "Failed to access local dataset. Check file path and permissions."
    }
    
    # Authentication errors
    AUTH_FAILED = {
        'pennsieve': "Authentication failed. Verify your API Key and Secret are correct.",
        'openneuro': "No authentication required for OpenNeuro (all datasets are public).",
        'dandi': "API token invalid. Get a new token from DANDI web interface.",
        'xnat': "Login failed. Check username and password.",
        'hpc': "SSH authentication failed. Verify username and password/key file.",
        'remote_server': "SSH authentication failed. Verify username and password/key file.",
        'local': "Permission denied. Check file system permissions."
    }
    
    # Dataset errors
    DATASET_NOT_FOUND = {
        'pennsieve': "Dataset not found in Pennsieve. Verify dataset name is correct.",
        'openneuro': "Dataset not found on OpenNeuro. Check dataset ID (e.g., 'ds000102').",
        'dandi': "Dandiset not found. Check dandiset ID (e.g., '000003').",
        'xnat': "Project not found in XNAT. Verify project ID.",
        'hpc': "Dataset path not found on HPC. Check dataset path is correct.",
        'remote_server': "Dataset path not found on server. Check dataset path is correct.",
        'local': "Dataset directory not found. Verify path exists."
    }
    
    # BIDS validation errors
    NOT_BIDS_COMPLIANT = "Dataset is not BIDS-compliant. Required: dataset_description.json and sub-* directories."
    MISSING_DATASET_DESCRIPTION = "Missing dataset_description.json file. This is required for BIDS datasets."
    NO_SUBJECTS_FOUND = "No subject directories (sub-*) found in dataset."
    INVALID_BIDS_STRUCTURE = "Invalid BIDS structure. Subjects must have session or modality folders."
    
    # Download errors
    DOWNLOAD_FAILED = "Download failed. Check network connection and try again."
    INSUFFICIENT_SPACE = "Insufficient disk space for download."
    FILE_NOT_FOUND = "File not found. It may have been moved or deleted."
    DOWNLOAD_INTERRUPTED = "Download interrupted. Progress has been saved."
    
    # Upload errors
    UPLOAD_FAILED = "Upload failed. Check credentials and destination permissions."
    UPLOAD_NOT_SUPPORTED = "Upload not supported for this platform (read-only)."
    DESTINATION_FULL = "Destination storage is full."
    
    # Transfer errors
    TRANSFER_FAILED = "Transfer failed. Check source and destination connections."
    INCOMPATIBLE_PLATFORMS = "Direct transfer not supported between these platforms. Use cached mode."
    TRANSFER_INTERRUPTED = "Transfer interrupted. Some files may have been transferred."
    
    # QC errors
    QC_PUSH_FAILED = "Failed to push QC data to Pennsieve. Check connection and permissions."
    QC_CSV_INVALID = "QC CSV format is invalid. Check column headers and data."
    
    # General errors
    OPERATION_CANCELLED = "Operation cancelled by user."
    TIMEOUT = "Operation timed out. Check network connection or try again later."
    UNKNOWN_ERROR = "An unexpected error occurred. Check logs for details."
    
    @staticmethod
    def format_error(error_type: str, platform: str = None, details: str = None) -> str:
        """
        Format error message with optional platform context and details.
        
        Args:
            error_type: Error type (e.g., 'CONNECTION_FAILED')
            platform: Optional platform name
            details: Optional additional details
            
        Returns:
            str: Formatted error message
        """
        # Get base message
        error_dict = getattr(ErrorMessages, error_type, None)
        
        if isinstance(error_dict, dict) and platform:
            base_msg = error_dict.get(platform, ErrorMessages.UNKNOWN_ERROR)
        elif isinstance(error_dict, str):
            base_msg = error_dict
        else:
            base_msg = ErrorMessages.UNKNOWN_ERROR
        
        # Append details if provided
        if details:
            return f"{base_msg}\n\nDetails: {details}"
        
        return base_msg
    
    @staticmethod
    def get_platform_help(platform: str) -> str:
        """
        Get platform-specific help message.
        
        Args:
            platform: Platform name
            
        Returns:
            str: Help message
        """
        help_messages = {
            'pennsieve': "Need help? Visit: https://docs.pennsieve.io/docs/pennsieve-agent",
            'openneuro': "Need help? Visit: https://openneuro.org/faq",
            'dandi': "Need help? Visit: https://www.dandiarchive.org/handbook/",
            'xnat': "Need help? Contact your XNAT administrator.",
            'hpc': "Need help? Contact your HPC support team.",
            'remote_server': "Need help? Contact your system administrator.",
            'local': "Need help? Check file permissions: ls -la /path/to/dataset"
        }
        
        return help_messages.get(platform, "Check PLATFORM_REQUIREMENTS.md for detailed setup instructions.")
    
    @staticmethod
    def suggest_fix(error_type: str, platform: str) -> str:
        """
        Suggest a fix for common errors.
        
        Args:
            error_type: Error type
            platform: Platform name
            
        Returns:
            str: Suggested fix
        """
        fixes = {
            ('CONNECTION_FAILED', 'pennsieve'): "Try: 1) Verify credentials in Pennsieve web app, 2) Check 'pennsieve whoami' in terminal, 3) Reinstall: pip install --upgrade pennsieve",
            ('CONNECTION_FAILED', 'xnat'): "Try: 1) Test login in web browser first, 2) Check if server requires VPN, 3) Verify URL includes https://",
            ('CONNECTION_FAILED', 'hpc'): "Try: 1) Test SSH manually: ssh user@host, 2) Check VPN connection, 3) Verify key permissions: chmod 600 ~/.ssh/key",
            ('CONNECTION_FAILED', 'remote_server'): "Try: 1) Test SSH manually: ssh user@host, 2) Check firewall rules, 3) Verify server is reachable: ping hostname",
            ('NOT_BIDS_COMPLIANT', None): "Fix: 1) Add dataset_description.json, 2) Rename folders to sub-XX format, 3) Organize as sub-XX/[ses-YY/]modality/files.nii.gz",
            ('DOWNLOAD_FAILED', None): "Try: 1) Check network stability, 2) Verify file still exists, 3) Retry download, 4) Check disk space",
            ('UPLOAD_FAILED', None): "Try: 1) Verify destination has write permissions, 2) Check storage quota, 3) Retry upload, 4) Check file size limits"
        }
        
        fix = fixes.get((error_type, platform)) or fixes.get((error_type, None))
        return fix or "Check logs for more details and consult PLATFORM_REQUIREMENTS.md"


def handle_agent_error(e: Exception, platform: str, operation: str) -> str:
    """
    Convert agent exception to user-friendly error message.
    
    Args:
        e: Exception object
        platform: Platform name
        operation: Operation being performed (e.g., 'download', 'connect')
        
    Returns:
        str: User-friendly error message
    """
    error_str = str(e).lower()
    
    # Connection errors
    if 'connection' in error_str or 'timeout' in error_str:
        msg = ErrorMessages.format_error('CONNECTION_FAILED', platform)
        return f"{msg}\n\n{ErrorMessages.suggest_fix('CONNECTION_FAILED', platform)}"
    
    # Authentication errors
    if 'auth' in error_str or 'credential' in error_str or 'permission denied' in error_str:
        msg = ErrorMessages.format_error('AUTH_FAILED', platform)
        return f"{msg}\n\n{ErrorMessages.suggest_fix('CONNECTION_FAILED', platform)}"
    
    # Not found errors
    if 'not found' in error_str or '404' in error_str:
        return ErrorMessages.format_error('DATASET_NOT_FOUND', platform)
    
    # Default
    return ErrorMessages.format_error('UNKNOWN_ERROR', details=str(e))
