"""
Transfer Recovery and Error Handling for BIDSHub (v3.1.1+).

Provides retry logic, partial failure handling, and rollback for data transfers.
"""

import time
import logging
from typing import Callable, Optional, Dict, Any
from pathlib import Path
import shutil

logger = logging.getLogger(__name__)


class TransferRecovery:
    """Manages transfer error recovery and retry logic."""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 2.0,
                 backoff_multiplier: float = 2.0):
        """
        Initialize transfer recovery manager.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (seconds)
            backoff_multiplier: Multiplier for exponential backoff
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_multiplier = backoff_multiplier
        self.failed_transfers = []
    
    def retry_with_backoff(self, operation: Callable, operation_name: str,
                          *args, **kwargs) -> tuple[bool, Optional[Any]]:
        """
        Execute operation with retry and exponential backoff.
        
        Args:
            operation: Function to execute
            operation_name: Descriptive name for logging
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation
            
        Returns:
            tuple: (success: bool, result: Any)
        """
        delay = self.retry_delay
        
        for attempt in range(self.max_retries + 1):
            try:
                result = operation(*args, **kwargs)
                
                # Check if result indicates success
                if result or result is None:
                    if attempt > 0:
                        logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")
                    return True, result
                else:
                    raise Exception(f"{operation_name} returned failure")
                    
            except Exception as e:
                if attempt < self.max_retries:
                    logger.warning(
                        f"{operation_name} failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    delay *= self.backoff_multiplier
                else:
                    logger.error(f"{operation_name} failed after {self.max_retries + 1} attempts: {e}")
                    self.failed_transfers.append({
                        'operation': operation_name,
                        'error': str(e),
                        'attempts': attempt + 1
                    })
                    return False, None
        
        return False, None
    
    def create_checkpoint(self, checkpoint_path: str, state: Dict) -> bool:
        """
        Create a checkpoint file for transfer state.
        
        Args:
            checkpoint_path: Path to checkpoint file
            state: State dictionary to save
            
        Returns:
            bool: True if checkpoint created
        """
        try:
            import json
            checkpoint_file = Path(checkpoint_path)
            checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(checkpoint_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            logger.info(f"Checkpoint created: {checkpoint_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}")
            return False
    
    def load_checkpoint(self, checkpoint_path: str) -> Optional[Dict]:
        """
        Load transfer state from checkpoint file.
        
        Args:
            checkpoint_path: Path to checkpoint file
            
        Returns:
            dict: State dictionary, or None if not found
        """
        try:
            import json
            checkpoint_file = Path(checkpoint_path)
            
            if not checkpoint_file.exists():
                return None
            
            with open(checkpoint_file, 'r') as f:
                state = json.load(f)
            
            logger.info(f"Checkpoint loaded: {checkpoint_path}")
            return state
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    def rollback_transfer(self, files_to_remove: list[str]) -> int:
        """
        Rollback partial transfer by removing files.
        
        Args:
            files_to_remove: List of file paths to remove
            
        Returns:
            int: Number of files successfully removed
        """
        removed = 0
        
        for file_path in files_to_remove:
            try:
                file_obj = Path(file_path)
                
                if file_obj.exists():
                    if file_obj.is_file():
                        file_obj.unlink()
                        removed += 1
                        logger.info(f"Rolled back: {file_path}")
                    elif file_obj.is_dir():
                        shutil.rmtree(file_path)
                        removed += 1
                        logger.info(f"Rolled back directory: {file_path}")
                        
            except Exception as e:
                logger.warning(f"Failed to rollback {file_path}: {e}")
        
        return removed
    
    def get_failed_transfers(self) -> list[Dict]:
        """
        Get list of failed transfers.
        
        Returns:
            list: List of failed transfer dicts
        """
        return self.failed_transfers.copy()
    
    def clear_failed_transfers(self):
        """Clear failed transfers list."""
        self.failed_transfers.clear()
    
    def resume_transfer(self, checkpoint_path: str, 
                       transfer_function: Callable,
                       *args, **kwargs) -> tuple[bool, Optional[Any]]:
        """
        Resume a transfer from checkpoint.
        
        Args:
            checkpoint_path: Path to checkpoint file
            transfer_function: Function to execute for transfer
            *args: Positional arguments for transfer_function
            **kwargs: Keyword arguments for transfer_function
            
        Returns:
            tuple: (success: bool, result: Any)
        """
        checkpoint = self.load_checkpoint(checkpoint_path)
        
        if checkpoint:
            logger.info(f"Resuming transfer from checkpoint: {checkpoint}")
            # Pass checkpoint to transfer function if it accepts it
            if 'checkpoint' not in kwargs:
                kwargs['checkpoint'] = checkpoint
        
        return self.retry_with_backoff(
            transfer_function,
            f"Transfer resume from {checkpoint_path}",
            *args,
            **kwargs
        )


def safe_file_operation(operation: Callable, operation_name: str,
                       max_retries: int = 2) -> tuple[bool, Optional[Any]]:
    """
    Execute file operation with retry (quick helper).
    
    Args:
        operation: Function to execute
        operation_name: Name for logging
        max_retries: Maximum retries
        
    Returns:
        tuple: (success: bool, result: Any)
    """
    recovery = TransferRecovery(max_retries=max_retries, retry_delay=1.0)
    return recovery.retry_with_backoff(operation, operation_name)
