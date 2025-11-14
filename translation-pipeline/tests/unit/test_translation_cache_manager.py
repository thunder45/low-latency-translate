"""
Unit tests for Translation Cache Manager.

Tests cache key generation, normalization, lookup, storage, LRU eviction,
and CloudWatch metrics emission.
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from shared.services.translation_cache_manager import TranslationCacheManager


class TestCacheKeyGeneration:
    """Test cache key generation and text normalization."""
    
    def test_generate_cache_key_format(self):
        """Test cache key follows {source}:{target}:{hash16} format."""
        manager = TranslationCacheManager(
            table_name='test-table',
            dynamodb_client=Mock(),
            cloudwatch_client=Mock()
        )
        
        key = manager._generate_cache_key('en', 'es', 'Hello World')
        
        # Verify format
        parts = key.split(':')
        assert len(parts) == 3
        assert parts[0] == 'en'
        assert parts[1] == 'es'
        assert len(parts[2]) == 16  # Hash truncated to 16 chars
    
    def test_normalize_text_trims_whitespace(self):
        """Test text normalization trims leading/trailing whitespace."""
        manager = TranslationCacheManager(
            table_name='test-table',
            dynamodb_client=Mock(),
            cloudwatch_client=Mock()
        )
        
        normalized = manager._normalize_text('  Hello World  ')
        assert normalized == 'hello world'
    
    def test_normalize_text_converts_to_lowercase(self):
        """Test text normalization converts to lowercase."""
        manager = TranslationCacheManager(
            table_name='test-table',
            dynamodb_client=Mock(),
            cloudwatch_client=Mock()
        )
        
        normalized = manager._normalize_text('HELLO WORLD')
        assert normalized == 'hello world'

    def test_same_text_different_case_generates_same_key(self):
        """Test that text with different cases generates same cache key."""
        manager = TranslationCacheManager(
            table_name='test-table',
            dynamodb_client=Mock(),
            cloudwatch_client=Mock()
        )
        
        key1 = manager._generate_cache_key('en', 'es', 'Hello World')
        key2 = manager._generate_cache_key('en', 'es', 'hello world')
        key3 = manager._generate_cache_key('en', 'es', 'HELLO WORLD')
        
        assert key1 == key2 == key3
    
    def test_different_text_generates_different_key(self):
        """Test that different text generates different cache keys."""
        manager = TranslationCacheManager(
            table_name='test-table',
            dynamodb_client=Mock(),
            cloudwatch_client=Mock()
        )
        
        key1 = manager._generate_cache_key('en', 'es', 'Hello')
        key2 = manager._generate_cache_key('en', 'es', 'World')
        
        assert key1 != key2
    
    def test_different_languages_generate_different_keys(self):
        """Test that different language pairs generate different keys."""
        manager = TranslationCacheManager(
            table_name='test-table',
            dynamodb_client=Mock(),
            cloudwatch_client=Mock()
        )
        
        key1 = manager._generate_cache_key('en', 'es', 'Hello')
        key2 = manager._generate_cache_key('en', 'fr', 'Hello')
        key3 = manager._generate_cache_key('es', 'en', 'Hello')
        
        assert key1 != key2 != key3


class TestCacheLookupAndStorage:
    """Test cache lookup and storage operations."""
    
    def test_get_cached_translation_with_cache_hit(self):
        """Test cache lookup returns translation on cache hit."""
        mock_dynamodb = Mock()
        mock_dynamodb.get_item.return_value = {
            'Item': {
                'cacheKey': {'S': 'en:es:abc123'},
                'translatedText': {'S': 'Hola Mundo'},
                'accessCount': {'N': '5'}
            }
        }
        mock_dynamodb.update_item.return_value = {}
        
        manager = TranslationCacheManager(
            table_name='test-table',
            dynamodb_client=mock_dynamodb,
            cloudwatch_client=Mock()
        )
        
        result = manager.get_cached_translation('en', 'es', 'Hello World')
        
        assert result == 'Hola Mundo'
        assert manager._cache_hits == 1
        assert manager._cache_misses == 0

    def test_get_cached_translation_with_cache_miss(self):
        """Test cache lookup returns None on cache miss."""
        mock_dynamodb = Mock()
        mock_dynamodb.get_item.return_value = {}  # No 'Item' key
        
        manager = TranslationCacheManager(
            table_name='test-table',
            dynamodb_client=mock_dynamodb,
            cloudwatch_client=Mock()
        )
        
        result = manager.get_cached_translation('en', 'es', 'Hello World')
        
        assert result is None
        assert manager._cache_hits == 0
        assert manager._cache_misses == 1
    
    def test_get_cached_translation_updates_access_count(self):
        """Test cache hit updates accessCount and lastAccessedAt."""
        mock_dynamodb = Mock()
        mock_dynamodb.get_item.return_value = {
            'Item': {
                'cacheKey': {'S': 'en:es:abc123'},
                'translatedText': {'S': 'Hola Mundo'},
                'accessCount': {'N': '5'}
            }
        }
        mock_dynamodb.update_item.return_value = {}
        
        manager = TranslationCacheManager(
            table_name='test-table',
            dynamodb_client=mock_dynamodb,
            cloudwatch_client=Mock()
        )
        
        manager.get_cached_translation('en', 'es', 'Hello World')
        
        # Verify update_item was called
        mock_dynamodb.update_item.assert_called_once()
        call_args = mock_dynamodb.update_item.call_args
        
        # Verify accessCount incremented to 6
        assert call_args[1]['ExpressionAttributeValues'][':count']['N'] == '6'
    
    def test_cache_translation_stores_with_ttl(self):
        """Test cache_translation stores entry with TTL."""
        mock_dynamodb = Mock()
        mock_dynamodb.scan.return_value = {'Count': 100}  # Below limit
        mock_dynamodb.put_item.return_value = {}
        
        manager = TranslationCacheManager(
            table_name='test-table',
            cache_ttl_seconds=3600,
            dynamodb_client=mock_dynamodb,
            cloudwatch_client=Mock()
        )
        
        manager.cache_translation('en', 'es', 'Hello World', 'Hola Mundo')
        
        # Verify put_item was called
        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        item = call_args[1]['Item']
        
        # Verify required fields
        assert item['sourceLanguage']['S'] == 'en'
        assert item['targetLanguage']['S'] == 'es'
        assert item['sourceText']['S'] == 'Hello World'
        assert item['translatedText']['S'] == 'Hola Mundo'
        assert item['accessCount']['N'] == '1'
        assert 'ttl' in item


class TestLRUEviction:
    """Test LRU eviction logic."""
    
    def test_eviction_triggered_when_limit_exceeded(self):
        """Test eviction occurs when cache exceeds max entries."""
        mock_dynamodb = Mock()
        # First scan for size check returns count at limit
        # Second scan for eviction returns items
        mock_dynamodb.scan.side_effect = [
            {'Count': 10000},  # At limit
            {
                'Items': [
                    {
                        'cacheKey': {'S': 'key1'},
                        'accessCount': {'N': '1'},
                        'lastAccessedAt': {'N': '1000'}
                    },
                    {
                        'cacheKey': {'S': 'key2'},
                        'accessCount': {'N': '2'},
                        'lastAccessedAt': {'N': '2000'}
                    }
                ]
            }
        ]
        mock_dynamodb.delete_item.return_value = {}
        mock_dynamodb.put_item.return_value = {}
        
        manager = TranslationCacheManager(
            table_name='test-table',
            max_cache_entries=10000,
            dynamodb_client=mock_dynamodb,
            cloudwatch_client=Mock()
        )
        
        manager.cache_translation('en', 'es', 'Test', 'Prueba')
        
        # Verify delete_item was called (eviction occurred)
        assert mock_dynamodb.delete_item.called
        assert manager._cache_evictions > 0

    def test_eviction_prioritizes_lowest_access_count(self):
        """Test eviction removes entries with lowest accessCount first."""
        mock_dynamodb = Mock()
        mock_dynamodb.scan.side_effect = [
            {'Count': 10000},
            {
                'Items': [
                    {
                        'cacheKey': {'S': 'low_access'},
                        'accessCount': {'N': '1'},
                        'lastAccessedAt': {'N': '3000'}
                    },
                    {
                        'cacheKey': {'S': 'high_access'},
                        'accessCount': {'N': '100'},
                        'lastAccessedAt': {'N': '2000'}
                    }
                ]
            }
        ]
        mock_dynamodb.delete_item.return_value = {}
        mock_dynamodb.put_item.return_value = {}
        
        manager = TranslationCacheManager(
            table_name='test-table',
            max_cache_entries=10000,
            dynamodb_client=mock_dynamodb,
            cloudwatch_client=Mock()
        )
        
        manager.cache_translation('en', 'es', 'Test', 'Prueba')
        
        # Verify low_access was deleted first
        delete_calls = mock_dynamodb.delete_item.call_args_list
        first_deleted_key = delete_calls[0][1]['Key']['cacheKey']['S']
        assert first_deleted_key == 'low_access'


class TestMetricsEmission:
    """Test CloudWatch metrics emission."""
    
    def test_emit_metrics_calculates_hit_rate(self):
        """Test metrics emission calculates correct hit rate."""
        mock_cloudwatch = Mock()
        mock_dynamodb = Mock()
        mock_dynamodb.scan.return_value = {'Count': 5000}
        
        manager = TranslationCacheManager(
            table_name='test-table',
            dynamodb_client=mock_dynamodb,
            cloudwatch_client=mock_cloudwatch
        )
        
        # Simulate cache operations
        manager._cache_hits = 75
        manager._cache_misses = 25
        
        manager.emit_metrics()
        
        # Verify put_metric_data was called
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args
        metrics = call_args[1]['MetricData']
        
        # Find hit rate metric
        hit_rate_metric = next(m for m in metrics if m['MetricName'] == 'TranslationCacheHitRate')
        assert hit_rate_metric['Value'] == 75.0  # 75 hits / 100 total = 75%

    def test_emit_metrics_includes_cache_size(self):
        """Test metrics emission includes current cache size."""
        mock_cloudwatch = Mock()
        mock_dynamodb = Mock()
        mock_dynamodb.scan.return_value = {'Count': 7500}
        
        manager = TranslationCacheManager(
            table_name='test-table',
            dynamodb_client=mock_dynamodb,
            cloudwatch_client=mock_cloudwatch
        )
        
        manager.emit_metrics()
        
        call_args = mock_cloudwatch.put_metric_data.call_args
        metrics = call_args[1]['MetricData']
        
        # Find cache size metric
        size_metric = next(m for m in metrics if m['MetricName'] == 'TranslationCacheSize')
        assert size_metric['Value'] == 7500
    
    def test_emit_metrics_includes_evictions(self):
        """Test metrics emission includes eviction count."""
        mock_cloudwatch = Mock()
        mock_dynamodb = Mock()
        mock_dynamodb.scan.return_value = {'Count': 5000}
        
        manager = TranslationCacheManager(
            table_name='test-table',
            dynamodb_client=mock_dynamodb,
            cloudwatch_client=mock_cloudwatch
        )
        
        manager._cache_evictions = 150
        manager.emit_metrics()
        
        call_args = mock_cloudwatch.put_metric_data.call_args
        metrics = call_args[1]['MetricData']
        
        # Find evictions metric
        evictions_metric = next(m for m in metrics if m['MetricName'] == 'TranslationCacheEvictions')
        assert evictions_metric['Value'] == 150
    
    def test_get_cache_stats_returns_correct_values(self):
        """Test get_cache_stats returns accurate statistics."""
        manager = TranslationCacheManager(
            table_name='test-table',
            dynamodb_client=Mock(),
            cloudwatch_client=Mock()
        )
        
        manager._cache_hits = 80
        manager._cache_misses = 20
        manager._cache_evictions = 10
        
        stats = manager.get_cache_stats()
        
        assert stats['cache_hits'] == 80
        assert stats['cache_misses'] == 20
        assert stats['total_requests'] == 100
        assert stats['hit_rate'] == 0.8
        assert stats['evictions'] == 10
