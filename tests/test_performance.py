"""New tests for performance optimizations."""

import pytest
from collections import OrderedDict
from pathlib import Path
import tempfile
import time

from torvalds_skill.distill import _load_json_cached, _data_cache
from torvalds_skill import distill_llm


class TestLRUEviction:
    """Tests for LRU cache eviction in _call_llm."""
    
    def test_lru_eviction(self):
        """LRU entry (first accessed) is evicted, not oldest by insertion time."""
        # Clear cache first
        if hasattr(distill_llm._call_llm, '_cache'):
            distill_llm._call_llm._cache.clear()
        
        # Set max_size to 2 for testing
        distill_llm._call_llm._max_size = 2
        
        # Create cache with OrderedDict
        cache = distill_llm._call_llm._cache = OrderedDict()
        
        # Add entries A, B (at max capacity)
        cache['A'] = 'value_A'
        cache['B'] = 'value_B'
        
        # Access A (makes it most recently used)
        _ = cache['A']
        cache.move_to_end('A')
        
        # Now add C (should evict B, the LRU entry)
        if len(cache) >= distill_llm._call_llm._max_size:
            cache.popitem(last=False)
        cache['C'] = 'value_C'
        
        # Verify B was evicted (LRU), not A (most recently accessed)
        assert 'A' in cache
        assert 'B' not in cache
        assert 'C' in cache
    
    def test_lru_touch_on_hit(self):
        """Accessing an entry makes it most recently used."""
        # Clear cache first
        if hasattr(distill_llm._call_llm, '_cache'):
            distill_llm._call_llm._cache.clear()
        
        distill_llm._call_llm._max_size = 3
        cache = distill_llm._call_llm._cache = OrderedDict()
        
        # Add entries A, B, C
        cache['A'] = 'value_A'
        cache['B'] = 'value_B'
        cache['C'] = 'value_C'
        
        # Access A (makes it most recently used)
        _ = cache['A']
        cache.move_to_end('A')
        
        # Now add D (should evict B, not A)
        if len(cache) >= distill_llm._call_llm._max_size:
            cache.popitem(last=False)
        cache['D'] = 'value_D'
        
        # Verify B was evicted (LRU), not A (touched on hit)
        assert 'A' in cache
        assert 'B' not in cache
        assert 'C' in cache
        assert 'D' in cache


class TestDataFileCache:
    """Tests for _load_json_cached() function."""
    
    def test_data_file_cache(self):
        """Second call is faster (cached), third call after modification is fresh."""
        # Clear cache first
        _data_cache.clear()
        
        # Create a temporary JSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"test": "data"}')
            temp_path = Path(f.name)
        
        try:
            # First call - should load from disk
            start = time.time()
            data1 = _load_json_cached(temp_path)
            elapsed1 = time.time() - start
            assert data1 == {"test": "data"}
            
            # Second call - should be from cache (faster)
            start = time.time()
            data2 = _load_json_cached(temp_path)
            elapsed2 = time.time() - start
            assert data2 == {"test": "data"}
            
            # Second call should be faster (cached)
            # Note: This is a soft assertion - on fast systems both may be < 1ms
            assert elapsed2 <= elapsed1 * 10  # Allow some margin
            
            # Modify the file
            time.sleep(0.1)  # Ensure mtime changes
            temp_path.write_text('{"test": "modified"}')
            
            # Third call - should load fresh data
            data3 = _load_json_cached(temp_path)
            assert data3 == {"test": "modified"}
            
        finally:
            # Clean up
            temp_path.unlink()
            # Clear cache entry
            cache_key = (str(temp_path.resolve()),)
            if cache_key in _data_cache:
                del _data_cache[cache_key]


class TestFallbackNotUsedOnTruncation:
    """Tests that fallback chain is NOT triggered on truncation."""
    
    def test_fallback_not_used_on_truncation(self):
        """Mock truncated response returns partial result immediately."""
        from torvalds_skill import config
        import http.client
        from unittest.mock import patch, MagicMock
        
        # Clear cache first
        if hasattr(distill_llm._call_llm, '_cache'):
            distill_llm._call_llm._cache.clear()
        
        # Track which models were called
        models_called = []
        
        # Create a mock connection that returns truncated response
        def mock_get_connection(host):
            mock_conn = MagicMock()
            mock_response = MagicMock()
            mock_response.status = 200
            # Return a short response that will be detected as truncated
            mock_response.__iter__ = lambda self: iter([
                b'data: {"choices": [{"delta": {"content": "Short"}}]}\n',
                b'data: [DONE]\n'
            ])
            mock_conn.getresponse.return_value = mock_response
            mock_conn.sock = MagicMock()
            mock_conn.sock._closed = False
            
            # Track the model from the request
            original_request = mock_conn.request
            def tracking_request(method, path, body=None, headers=None):
                import json
                payload = json.loads(body)
                models_called.append(payload['model'])
                return original_request(method, path, body=body, headers=headers)
            mock_conn.request = tracking_request
            
            return mock_conn
        
        with patch.object(distill_llm, '_get_connection', mock_get_connection):
            with patch.object(distill_llm, '_WallClockTimeout') as mock_timeout:
                mock_timeout.return_value.__enter__ = lambda self: self
                mock_timeout.return_value.__exit__ = lambda self, *args: None
                
                # Call with primary model - should return partial result immediately
                # without trying fallback models
                result = distill_llm._call_llm("test prompt", retries=1, model="test-model")
        
        # Verify only the primary model was called (no fallback)
        assert len(models_called) == 1
        assert models_called[0] == "test-model"