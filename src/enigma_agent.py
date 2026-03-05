"""
ENIGMA Consortium Integration for BIDSHub.

IMPORTANT LIMITATION: ENIGMA does NOT provide raw subject-level imaging data.
It only provides meta-analytical summary statistics from large-scale studies.

This agent is included for completeness but has limited utility for BIDSHub's
primary use case (browsing and downloading individual subject scans).
"""

from pathlib import Path
from typing import Optional, Dict, List, Callable
import logging

from src.base_agent import BasePlatformAgent


logger = logging.getLogger(__name__)


class ENIGMAAgent(BasePlatformAgent):
    """
    Interface to ENIGMA (Enhancing NeuroImaging Genetics through Meta-Analysis).
    
    WARNING: ENIGMA does NOT provide raw subject-level data.
    
    ENIGMA provides:
    - Summary statistics from meta-analyses
    - Statistical maps across brain regions
    - Aggregated results (not individual scans)
    
    Use this agent only for accessing summary data, not for dataset
    download/management workflows.
    """
    
    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize ENIGMA agent.
        
        Args:
            api_token: Not required (ENIGMA data is public)
        """
        super().__init__(credentials={})
        self._verify_installation()
        
        logger.warning(
            "ENIGMA agent initialized. Note: ENIGMA does not provide "
            "raw subject-level data, only meta-analytical summaries."
        )
    
    def _verify_installation(self):
        """Verify enigmatoolbox is installed."""
        try:
            import enigmatoolbox
        except ImportError:
            raise RuntimeError(
                "ENIGMA Toolbox not found. Install with: pip install enigma-toolbox"
            )
    
    def verify_connection(self) -> bool:
        """
        Verify ENIGMA Toolbox is accessible.
        
        Returns:
            bool: True if library is installed (no authentication needed)
        """
        try:
            import enigmatoolbox
            logger.info("ENIGMA Toolbox available")
            return True
        except:
            return False
    
    def get_datasets(self) -> List[Dict]:
        """
        List available ENIGMA summary datasets.
        
        Returns:
            List of available summary statistics and meta-analyses
        """
        # ENIGMA provides summary data, not individual datasets
        return [
            {
                'id': 'cortical_thickness',
                'name': 'ENIGMA Cortical Thickness Meta-Analysis',
                'description': 'Summary statistics for cortical thickness across disorders',
                'type': 'summary_statistics',
                'subject_count': 'N/A (meta-analysis)'
            },
            {
                'id': 'subcortical_volumes',
                'name': 'ENIGMA Subcortical Volumes',
                'description': 'Meta-analytical results for subcortical structure volumes',
                'type': 'summary_statistics',
                'subject_count': 'N/A (meta-analysis)'
            },
            {
                'id': 'disorders',
                'name': 'ENIGMA Disorder-Specific Results',
                'description': 'Summary statistics across disorders (Schizophrenia, Bipolar, etc.)',
                'type': 'summary_statistics',
                'subject_count': 'N/A (meta-analysis)'
            }
        ]
    
    def get_dataset_structure(self, dataset_id: str) -> Dict:
        """
        Get structure for ENIGMA summary data.
        
        NOTE: ENIGMA does not have subject-level structure.
        
        Args:
            dataset_id: ENIGMA dataset identifier
            
        Returns:
            Empty structure (no subjects available)
        """
        logger.warning(
            "ENIGMA does not provide subject-level data. "
            "Use ENIGMA Toolbox directly for summary statistics."
        )
        
        return {
            'subjects': [],
            'total_scans': 0,
            'note': 'ENIGMA provides summary statistics only, not individual subjects',
            'available_data': 'Meta-analytical results, statistical maps'
        }
    
    def download_file(self,
                     file_id: str,
                     target_path: str,
                     progress_callback: Optional[Callable[[int, str], None]] = None) -> bool:
        """
        Download ENIGMA summary data.
        
        NOTE: Not applicable for traditional file downloads.
        Use ENIGMA Toolbox functions directly instead.
        
        Args:
            file_id: ENIGMA data identifier
            target_path: Target path (not used)
            progress_callback: Progress callback
            
        Returns:
            bool: False (operation not supported)
        """
        logger.error("ENIGMA does not support file downloads. Use ENIGMA Toolbox directly.")
        
        if progress_callback:
            progress_callback(0, "ENIGMA provides summary statistics only, not downloadable files")
        
        return False
    
    def get_bids_compliance(self) -> str:
        """ENIGMA does not provide BIDS datasets."""
        return 'none'
    
    def supports_upload(self) -> bool:
        """ENIGMA does not support data upload (meta-analysis consortium)."""
        return False
    
    def get_platform_info(self) -> Dict:
        """Get ENIGMA platform information."""
        return {
            'name': 'ENIGMA',
            'full_name': 'Enhancing NeuroImaging Genetics through Meta-Analysis',
            'type': 'meta_analysis_consortium',
            'bids_support': 'none',
            'upload_support': False,
            'requires_approval': False,  # Public summary data
            'data_types': ['summary_statistics', 'meta_analysis', 'statistical_maps'],
            'primary_focus': 'large-scale meta-analysis',
            'limitations': [
                'No raw subject-level data available',
                'No individual scan downloads',
                'Summary statistics only',
                'Not suitable for dataset management workflows'
            ],
            'recommendation': 'Use ENIGMA Toolbox directly for meta-analytical data',
            'note': 'ENIGMA integration deferred - limited utility for BIDSHub use case'
        }


def check_enigma_available() -> bool:
    """
    Check if ENIGMA Toolbox is installed.
    
    Returns:
        bool: True if available
    """
    try:
        import enigmatoolbox
        return True
    except:
        return False
