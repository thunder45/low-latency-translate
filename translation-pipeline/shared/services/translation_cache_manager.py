"""
Translation Cache Manager.

This module provides caching functionality for translation results using DynamoDB.
Implements LRU eviction strategy and CloudWatch metrics emission.
"""

import hashlib
import time
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError


class TranslationCacheManager:
    """
    Manages translation caching in DynamoDB with LRU eviction.
    
    Provides cache-first lookup for translations to reduce AWS Translate costs
    and latency. Implements LRU eviction when cache exceeds maximum size.
    """
    
    def __init__(
        self,
        table_name: str,
        cache_ttl_seconds: int = 3600,
        max_cache_entries: int = 10000,
        cloudwatch_client=None,
        dynamodb_client=None
    ):
        """
        Initialize Translation Cache Manager.
        
        Args:
            table_name: DynamoDB table name for cached translations
            cache_ttl_seconds: TTL for cache entries in seconds (default: 3600)
            max_cache_entries: Maximum number of cache entries (default: 10000)
            cloudwatch_client: Optional CloudWatch client for testing
            dynamodb_client: Optional DynamoDB client for testing
        """
        self.table_name = table_name
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_cache_entries = max_cache_entries
        
        # Initialize AWS clients
        self.dynamodb = dynamodb_client or boto3.client('dynamodb')
        self.cloudwatch = cloudwatch_client or boto3.client('cloudwatch')
        
        # Metrics tracking
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_evictions = 0
    
    def get_cached_translation(
        self,
        source_lang: str,
        target_lang: str,
        text: str
    ) -> Optional[str]:
        """
        Retrieve cached translation if available.
        
        Args:
            source_lang: Source language code (ISO 639-1)
            target_lang: Target language code (ISO 639-1)
            text: Text to translate
            
        Returns:
            Cached translation or None if cache miss
        """
        # Generate cache key
        cache_key = self._generate_cache_key(source_lang, target_lang, text)
        
        try:
            # Query DynamoDB
            response = self.dynamodb.get_item(
                TableName=self.table_name,
                Key={'cacheKey': {'S': cache_key}}
            )
            
            if 'Item' in response:
                # Cache hit - update access tracking
                self._cache_hits += 1
                item = response['Item']
                
                # Update access count and timestamp
                current_time = int(time.time())
                access_count = int(item.get('accessCount', {}).get('N', '0')) + 1
                
                self.dynamodb.update_item(
                    TableName=self.table_name,
                    Key={'cacheKey': {'S': cache_key}},
                    UpdateExpression='SET accessCount = :count, lastAccessedAt = :time',
                    ExpressionAttributeValues={
                        ':count': {'N': str(access_count)},
                        ':time': {'N': str(current_time)}
                    }
                )
                
                return item['translatedText']['S']
            else:
                # Cache miss
                self._cache_misses += 1
                return None
                
        except ClientError as e:
            # Log error but don't fail - treat as cache miss
            print(f"Cache lookup error: {e}")
            self._cache_misses += 1
            return None
    
    def cache_translation(
        self,
        source_lang: str,
        target_lang: str,
        text: str,
        translation: str
    ) -> None:
        """
        Store translation in cache with TTL.
        
        Args:
            source_lang: Source language code (ISO 639-1)
            target_lang: Target language code (ISO 639-1)
            text: Source text
            translation: Translated text
        """
        # Check if eviction is needed
        self._check_and_evict_if_needed()
        
        # Generate cache key
        cache_key = self._generate_cache_key(source_lang, target_lang, text)
        
        # Calculate TTL
        current_time = int(time.time())
        ttl = current_time + self.cache_ttl_seconds
        
        try:
            # Store in DynamoDB
            self.dynamodb.put_item(
                TableName=self.table_name,
                Item={
                    'cacheKey': {'S': cache_key},
                    'sourceLanguage': {'S': source_lang},
                    'targetLanguage': {'S': target_lang},
                    'sourceText': {'S': text},
                    'translatedText': {'S': translation},
                    'createdAt': {'N': str(current_time)},
                    'accessCount': {'N': '1'},
                    'lastAccessedAt': {'N': str(current_time)},
                    'ttl': {'N': str(ttl)}
                }
            )
        except ClientError as e:
            # Log error but don't fail
            print(f"Cache storage error: {e}")
    
    def _generate_cache_key(
        self,
        source_lang: str,
        target_lang: str,
        text: str
    ) -> str:
        """
        Generate cache key: {source}:{target}:{hash16}.
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            text: Text to hash
            
        Returns:
            Cache key string
        """
        # Normalize text
        normalized_text = self._normalize_text(text)
        
        # Generate SHA-256 hash
        hash_obj = hashlib.sha256(normalized_text.encode('utf-8'))
        hash_hex = hash_obj.hexdigest()
        
        # Truncate to first 16 characters
        hash16 = hash_hex[:16]
        
        # Generate composite key
        return f"{source_lang}:{target_lang}:{hash16}"
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for consistent caching.
        
        Trims whitespace and converts to lowercase for consistent hashing.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text (trimmed, lowercase)
        """
        return text.strip().lower()
    
    def _check_and_evict_if_needed(self) -> None:
        """
        Check cache size and evict entries if limit exceeded.
        
        Implements LRU eviction strategy based on accessCount and lastAccessedAt.
        """
        try:
            # Get current cache size
            response = self.dynamodb.scan(
                TableName=self.table_name,
                Select='COUNT'
            )
            
            cache_size = response['Count']
            
            # Check if eviction needed
            if cache_size >= self.max_cache_entries:
                # Scan to get all items with access metrics
                scan_response = self.dynamodb.scan(
                    TableName=self.table_name,
                    ProjectionExpression='cacheKey, accessCount, lastAccessedAt'
                )
                
                items = scan_response['Items']
                
                # Sort by accessCount (ascending), then lastAccessedAt (ascending)
                sorted_items = sorted(
                    items,
                    key=lambda x: (
                        int(x.get('accessCount', {}).get('N', '0')),
                        int(x.get('lastAccessedAt', {}).get('N', '0'))
                    )
                )
                
                # Calculate how many to evict (10% of max)
                evict_count = max(1, int(self.max_cache_entries * 0.1))
                
                # Evict least recently used entries
                for item in sorted_items[:evict_count]:
                    cache_key = item['cacheKey']['S']
                    self.dynamodb.delete_item(
                        TableName=self.table_name,
                        Key={'cacheKey': {'S': cache_key}}
                    )
                    self._cache_evictions += 1
                    
        except ClientError as e:
            # Log error but don't fail
            print(f"Cache eviction error: {e}")
    
    def emit_metrics(self, namespace: str = 'TranslationPipeline') -> None:
        """
        Emit CloudWatch metrics for cache performance.
        
        Args:
            namespace: CloudWatch namespace for metrics
        """
        try:
            # Calculate cache hit rate
            total_requests = self._cache_hits + self._cache_misses
            hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0
            
            # Get current cache size
            response = self.dynamodb.scan(
                TableName=self.table_name,
                Select='COUNT'
            )
            cache_size = response['Count']
            
            # Emit metrics
            self.cloudwatch.put_metric_data(
                Namespace=namespace,
                MetricData=[
                    {
                        'MetricName': 'TranslationCacheHitRate',
                        'Value': hit_rate,
                        'Unit': 'Percent'
                    },
                    {
                        'MetricName': 'TranslationCacheSize',
                        'Value': cache_size,
                        'Unit': 'Count'
                    },
                    {
                        'MetricName': 'TranslationCacheEvictions',
                        'Value': self._cache_evictions,
                        'Unit': 'Count'
                    }
                ]
            )
            
            # Reset eviction counter after emission
            self._cache_evictions = 0
            
        except ClientError as e:
            # Log error but don't fail
            print(f"Metrics emission error: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get current cache statistics.
        
        Returns:
            Dictionary with cache hits, misses, and hit rate
        """
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests) if total_requests > 0 else 0
        
        return {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'total_requests': total_requests,
            'hit_rate': hit_rate,
            'evictions': self._cache_evictions
        }
