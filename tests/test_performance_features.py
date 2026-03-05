"""
Tests for Performance & Scalability Features (v3.1.1+)

Tests pagination, caching, batch processing, and database optimizations.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import Database
from src.cache_manager import CacheManager, BatchProcessor
from src.download_manager import DownloadManager


class TestPagination:
    """Test pagination functionality."""
    
    def test_get_subjects_with_pagination(self, test_db):
        """Test that pagination returns correct subset of subjects."""
        db = test_db
        
        # Add 100 test subjects
        dataset_id = 1
        for i in range(100):
            db.add_subject(
                subject_id=f"sub-{i:03d}",
                dataset_id=dataset_id,
                local_subject_id=f"sub-{i:03d}"
            )
        
        # Test pagination
        page1 = db.get_all_subjects(limit=25, offset=0)
        page2 = db.get_all_subjects(limit=25, offset=25)
        page3 = db.get_all_subjects(limit=25, offset=50)
        
        assert len(page1) == 25, "First page should have 25 subjects"
        assert len(page2) == 25, "Second page should have 25 subjects"
        assert len(page3) == 25, "Third page should have 25 subjects"
        
        # Verify no overlap between pages
        page1_ids = {s['subject_id'] for s in page1}
        page2_ids = {s['subject_id'] for s in page2}
        assert len(page1_ids.intersection(page2_ids)) == 0, "Pages should not overlap"
    
    def test_get_subjects_count(self, test_db):
        """Test subject counting for pagination."""
        db = test_db
        
        # Add subjects
        dataset_id = 1
        for i in range(50):
            db.add_subject(
                subject_id=f"sub-{i:03d}",
                dataset_id=dataset_id,
                local_subject_id=f"sub-{i:03d}"
            )
        
        count = db.get_subjects_count(dataset_id=dataset_id)
        assert count == 50, f"Expected 50 subjects, got {count}"
    
    def test_pagination_with_filters(self, test_db):
        """Test pagination with QC filters."""
        db = test_db
        
        dataset_id = 1
        # Add subjects with different QC statuses
        subject_ids = []
        for i in range(30):
            db.add_subject(
                subject_id=f"sub-{i:03d}",
                dataset_id=dataset_id,
                local_subject_id=f"sub-{i:03d}"
            )
            subject_ids.append(f"sub-{i:03d}")
        
        # Mark first 10 as pass using the database ID
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        for i in range(10):
            cursor.execute("""
                UPDATE subjects SET qc_status = 'pass', qc_notes = 'Good quality'
                WHERE local_subject_id = ? AND dataset_id = ?
            """, (f"sub-{i:03d}", dataset_id))
        conn.commit()
        conn.close()
        
        # Test filtered pagination
        pass_subjects = db.get_all_subjects(
            filters={'qc_status': 'pass'},
            limit=5,
            offset=0
        )
        
        assert len(pass_subjects) == 5, "Should return 5 pass subjects"
        assert all(s['qc_status'] == 'pass' for s in pass_subjects), "All should have pass status"


class TestCacheManager:
    """Test caching functionality."""
    
    def test_cache_initialization(self):
        """Test cache manager initialization."""
        cache = CacheManager(max_size=10, ttl_seconds=60)
        
        assert cache.max_size == 10
        assert cache.ttl_seconds == 60
        assert len(cache.cache) == 0
    
    def test_cache_set_and_get(self):
        """Test basic cache operations."""
        cache = CacheManager(max_size=5, ttl_seconds=300)
        
        # Set values
        cache.set('key1', {'data': 'value1'})
        cache.set('key2', [1, 2, 3])
        
        # Get values
        assert cache.get('key1') == {'data': 'value1'}
        assert cache.get('key2') == [1, 2, 3]
        assert cache.get('nonexistent') is None
    
    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = CacheManager(max_size=3, ttl_seconds=300)
        
        # Fill cache
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')
        
        # Add fourth item (should evict key1)
        cache.set('key4', 'value4')
        
        assert cache.get('key1') is None, "Oldest entry should be evicted"
        assert cache.get('key2') == 'value2'
        assert cache.get('key3') == 'value3'
        assert cache.get('key4') == 'value4'
    
    def test_cache_ttl_expiration(self):
        """Test TTL expiration."""
        import time
        
        cache = CacheManager(max_size=10, ttl_seconds=1)
        cache.set('key1', 'value1')
        
        # Should be available immediately
        assert cache.get('key1') == 'value1'
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Should be expired
        assert cache.get('key1') is None, "Entry should expire after TTL"
    
    def test_cache_invalidation(self):
        """Test cache invalidation."""
        cache = CacheManager(max_size=10, ttl_seconds=300)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        
        # Invalidate single key
        cache.invalidate('key1')
        assert cache.get('key1') is None
        assert cache.get('key2') == 'value2'
    
    def test_cache_pattern_invalidation(self):
        """Test pattern-based invalidation."""
        cache = CacheManager(max_size=10, ttl_seconds=300)
        
        cache.set('subjects_1', 'data1')
        cache.set('subjects_2', 'data2')
        cache.set('datasets_1', 'data3')
        
        # Invalidate all subjects keys
        cache.invalidate_pattern('subjects_')
        
        assert cache.get('subjects_1') is None
        assert cache.get('subjects_2') is None
        assert cache.get('datasets_1') == 'data3', "Other keys should remain"
    
    def test_cache_clear(self):
        """Test clearing entire cache."""
        cache = CacheManager(max_size=10, ttl_seconds=300)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        
        cache.clear()
        
        assert cache.get('key1') is None
        assert cache.get('key2') is None
        assert len(cache.cache) == 0
    
    def test_cache_stats(self):
        """Test cache statistics."""
        cache = CacheManager(max_size=10, ttl_seconds=300)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        
        stats = cache.get_stats()
        
        assert stats['size'] == 2
        assert stats['max_size'] == 10
        assert stats['ttl_seconds'] == 300
        assert stats['utilization'] == 0.2  # 2/10
    
    def test_cached_query(self):
        """Test cached query wrapper."""
        cache = CacheManager(max_size=10, ttl_seconds=300)
        
        call_count = [0]  # Mutable to track calls
        
        def expensive_query():
            call_count[0] += 1
            return {'result': 'data'}
        
        # First call executes query
        result1 = cache.cached_query('test_key', expensive_query)
        assert result1 == {'result': 'data'}
        assert call_count[0] == 1
        
        # Second call uses cache
        result2 = cache.cached_query('test_key', expensive_query)
        assert result2 == {'result': 'data'}
        assert call_count[0] == 1, "Query should not be called again (cached)"


class TestBatchProcessor:
    """Test batch processing functionality."""
    
    def test_chunk_list(self):
        """Test list chunking."""
        items = list(range(25))
        chunks = list(BatchProcessor.chunk_list(items, chunk_size=10))
        
        assert len(chunks) == 3, "Should have 3 chunks"
        assert len(chunks[0]) == 10
        assert len(chunks[1]) == 10
        assert len(chunks[2]) == 5
    
    def test_chunk_list_exact_division(self):
        """Test chunking when size divides evenly."""
        items = list(range(30))
        chunks = list(BatchProcessor.chunk_list(items, chunk_size=10))
        
        assert len(chunks) == 3
        assert all(len(chunk) == 10 for chunk in chunks)
    
    def test_batch_download_subjects(self):
        """Test batch download simulation."""
        subjects = [f"sub-{i:03d}" for i in range(25)]
        
        downloaded = []
        
        def mock_download(subject):
            downloaded.append(subject)
            return True
        
        successful, failed = BatchProcessor.batch_download_subjects(
            subjects,
            mock_download,
            batch_size=10
        )
        
        assert successful == 25
        assert failed == 0
        assert len(downloaded) == 25
    
    def test_batch_download_with_failures(self):
        """Test batch download with some failures."""
        subjects = [f"sub-{i:03d}" for i in range(10)]
        
        def mock_download_with_failures(subject):
            # Fail on sub-003 and sub-007
            if subject in ['sub-003', 'sub-007']:
                return False
            return True
        
        successful, failed = BatchProcessor.batch_download_subjects(
            subjects,
            mock_download_with_failures,
            batch_size=5
        )
        
        assert successful == 8
        assert failed == 2


class TestDatabaseOptimizations:
    """Test database performance optimizations."""
    
    def test_add_subject_prevents_duplicates(self, test_db):
        """Test that adding same subject updates instead of duplicating."""
        db = test_db
        
        # Add subject first time
        db.add_subject(
            subject_id='sub-001',
            dataset_id=1,
            local_subject_id='sub-001'
        )
        
        # Add same subject again
        db.add_subject(
            subject_id='sub-001',
            dataset_id=1,
            local_subject_id='sub-001'
        )
        
        # Check only one exists
        subjects = db.get_all_subjects()
        matching = [s for s in subjects if s['subject_id'] == 'sub-001']
        
        assert len(matching) == 1, "Should not create duplicate subject"
    
    def test_add_subject_prevents_duplicate_on_readd(self, test_db):
        """Test that re-adding a subject doesn't create duplicates."""
        db = test_db
        
        # Add subject first time
        db.add_subject(
            subject_id='sub-001',
            dataset_id=1,
            local_subject_id='sub-001'
        )
        
        # Get count
        initial_count = len(db.get_all_subjects())
        
        # Re-add same subject with different metadata
        db.add_subject(
            subject_id='sub-001',
            dataset_id=1,
            local_subject_id='sub-001'
        )
        
        # Count should remain same
        final_count = len(db.get_all_subjects())
        
        assert final_count == initial_count, "Should not create duplicate subject on re-add"


class TestDownloadManagerBatching:
    """Test download manager batch optimization."""
    
    def test_batch_mode_enabled(self):
        """Test that batch mode can be enabled."""
        dm = DownloadManager(
            database=None,
            max_concurrent=3
        )
        
        assert hasattr(dm, 'batch_size'), "Should have batch_size attribute"
        assert dm.batch_size == 10, "Default batch size should be 10"
    
    def test_batch_size_configuration(self):
        """Test batch size configuration."""
        dm = DownloadManager(database=None, max_concurrent=3)
        dm.batch_size = 15
        
        assert dm.batch_size == 15, "Batch size should be configurable"


def test_performance_integration(test_db):
    """Integration test for all performance features."""
    # This tests that all components work together
    
    # 1. Database pagination
    for i in range(100):
        test_db.add_subject(
            subject_id=f"sub-{i:03d}",
            dataset_id=1,
            local_subject_id=f"sub-{i:03d}"
        )
    
    # 2. Cache manager
    cache = CacheManager(max_size=50, ttl_seconds=300)
    
    # Cache first page query
    def get_page_1():
        return test_db.get_all_subjects(limit=25, offset=0)
    
    page1_cached = cache.cached_query('page_1', get_page_1)
    page1_direct = test_db.get_all_subjects(limit=25, offset=0)
    
    assert len(page1_cached) == len(page1_direct)
    
    # 3. Batch processor
    all_subjects = test_db.get_all_subjects()
    chunks = list(BatchProcessor.chunk_list(all_subjects, chunk_size=10))
    
    assert len(chunks) == 10, "Should have 10 chunks of 10 subjects each"
    
    print("Performance integration test passed!")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
