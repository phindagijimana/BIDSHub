"""
Cache Manager for Performance Optimization (v3.1.1+).

Provides in-memory caching for frequently accessed metadata.
"""

import time
from typing import Dict, Optional, Any
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """LRU cache for database queries and API responses."""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        """
        Initialize cache manager.
        
        Args:
            max_size: Maximum number of cache entries
            ttl_seconds: Time-to-live for cache entries (default: 5 minutes)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        
        # Check if expired
        if time.time() - entry['timestamp'] > self.ttl_seconds:
            del self.cache[key]
            return None
        
        # Move to end (LRU)
        self.cache.move_to_end(key)
        return entry['value']
    
    def set(self, key: str, value: Any):
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        # Remove oldest if at capacity
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        
        self.cache[key] = {
            'value': value,
            'timestamp': time.time()
        }
    
    def invalidate(self, key: str):
        """Remove key from cache."""
        if key in self.cache:
            del self.cache[key]
    
    def invalidate_pattern(self, pattern: str):
        """Remove all keys matching pattern."""
        keys_to_remove = [k for k in self.cache.keys() if pattern in k]
        for key in keys_to_remove:
            del self.cache[key]
    
    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            dict: Cache stats
        """
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'ttl_seconds': self.ttl_seconds,
            'utilization': len(self.cache) / self.max_size if self.max_size > 0 else 0
        }
    
    def cached_query(self, key: str, query_func, *args, **kwargs) -> Any:
        """
        Execute query with caching.
        
        Args:
            key: Cache key
            query_func: Function to execute if cache miss
            *args: Positional arguments for query_func
            **kwargs: Keyword arguments for query_func
            
        Returns:
            Query result (cached or fresh)
        """
        # Try cache first
        cached = self.get(key)
        if cached is not None:
            logger.debug(f"Cache hit: {key}")
            return cached
        
        # Cache miss - execute query
        logger.debug(f"Cache miss: {key}")
        result = query_func(*args, **kwargs)
        
        # Store in cache
        self.set(key, result)
        
        return result


class BatchProcessor:
    """Optimize batch operations for large datasets."""
    
    @staticmethod
    def chunk_list(items: list, chunk_size: int = 100):
        """
        Split list into chunks.
        
        Args:
            items: List to chunk
            chunk_size: Size of each chunk
            
        Yields:
            List chunks
        """
        for i in range(0, len(items), chunk_size):
            yield items[i:i + chunk_size]
    
    @staticmethod
    def batch_download_subjects(subjects: list, download_func, 
                                batch_size: int = 10,
                                progress_callback = None):
        """
        Download subjects in optimized batches.
        
        Args:
            subjects: List of subjects to download
            download_func: Function to download single subject
            batch_size: Subjects per batch
            progress_callback: Optional progress callback
            
        Returns:
            tuple: (successful: int, failed: int)
        """
        successful = 0
        failed = 0
        
        for i, batch in enumerate(BatchProcessor.chunk_list(subjects, batch_size)):
            for subject in batch:
                try:
                    if download_func(subject):
                        successful += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"Batch download error: {e}")
                    failed += 1
                
                if progress_callback:
                    total = len(subjects)
                    current = successful + failed
                    progress_callback(current, total)
        
        return successful, failed
