"""
Broadcast Handler for distributing audio to listeners.

This module provides the BroadcastHandler class that fans out translated audio
to all listeners of a specific language using the API Gateway Management API.
Includes retry logic, stale connection cleanup, and concurrency control.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class BroadcastResult:
    """Result of broadcasting audio to listeners."""
    
    success_count: int
    failure_count: int
    stale_connections_removed: int
    total_duration_ms: float
    language: str


class BroadcastHandler:
    """
    Handler for broadcasting audio to listeners.
    
    Fans out translated audio to all listeners of a specific language using
    the API Gateway Management API with retry logic and concurrency control.
    """
    
    def __init__(
        self,
        api_gateway_client,
        connections_repository,
        max_concurrent_broadcasts: int = 100,
        max_retries: int = 2,
        retry_backoff_ms: int = 100
    ):
        """
        Initialize broadcast handler.
        
        Args:
            api_gateway_client: API Gateway Management API client
            connections_repository: Repository for connection data
            max_concurrent_broadcasts: Maximum concurrent PostToConnection calls
            max_retries: Maximum retry attempts for retryable errors
            retry_backoff_ms: Base backoff time in milliseconds for retries
        """
        self.api_gateway_client = api_gateway_client
        self.connections_repository = connections_repository
        self.max_concurrent_broadcasts = max_concurrent_broadcasts
        self.max_retries = max_retries
        self.retry_backoff_ms = retry_backoff_ms
        self.semaphore = asyncio.Semaphore(max_concurrent_broadcasts)
    
    async def broadcast_to_language(
        self,
        session_id: str,
        target_language: str,
        audio_data: bytes
    ) -> BroadcastResult:
        """
        Broadcast audio to all listeners of a specific language.
        
        Args:
            session_id: Session identifier
            target_language: Target language code (ISO 639-1)
            audio_data: PCM audio bytes to broadcast
            
        Returns:
            BroadcastResult with success/failure counts and metrics
        """
        start_time = time.time()
        
        # Query listeners for this language
        connection_ids = await self._get_listeners_for_language(
            session_id, target_language
        )
        
        if not connection_ids:
            logger.info(
                f"No listeners for language {target_language} in session {session_id}"
            )
            return BroadcastResult(
                success_count=0,
                failure_count=0,
                stale_connections_removed=0,
                total_duration_ms=0.0,
                language=target_language
            )
        
        logger.info(
            f"Broadcasting to {len(connection_ids)} listeners "
            f"for language {target_language} in session {session_id}"
        )
        
        # Broadcast to all connections in parallel
        tasks = [
            self._send_to_connection(connection_id, audio_data, session_id)
            for connection_id in connection_ids
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes and failures
        success_count = sum(1 for r in results if r is True)
        failure_count = sum(1 for r in results if r is False)
        stale_count = sum(1 for r in results if isinstance(r, Exception))
        
        duration_ms = (time.time() - start_time) * 1000
        
        logger.info(
            f"Broadcast complete for {target_language}: "
            f"{success_count} success, {failure_count} failed, "
            f"{stale_count} stale connections removed, "
            f"duration: {duration_ms:.2f}ms"
        )
        
        return BroadcastResult(
            success_count=success_count,
            failure_count=failure_count,
            stale_connections_removed=stale_count,
            total_duration_ms=duration_ms,
            language=target_language
        )
    
    async def _get_listeners_for_language(
        self,
        session_id: str,
        target_language: str
    ) -> List[str]:
        """
        Query listeners for a specific language using GSI.
        
        Args:
            session_id: Session identifier
            target_language: Target language code
            
        Returns:
            List of connection IDs
        """
        try:
            return await self.connections_repository.get_listeners_by_language(
                session_id, target_language
            )
        except Exception as e:
            logger.error(
                f"Failed to query listeners for {target_language}: {e}",
                exc_info=True
            )
            return []
    
    async def _send_to_connection(
        self,
        connection_id: str,
        audio_data: bytes,
        session_id: str,
        retry_count: int = 0
    ) -> bool:
        """
        Send audio to a single connection with retry logic.
        
        Args:
            connection_id: WebSocket connection ID
            audio_data: PCM audio bytes
            session_id: Session identifier for cleanup
            retry_count: Current retry attempt number
            
        Returns:
            True if successful, False if failed after retries
            
        Raises:
            Exception: If connection is stale (GoneException)
        """
        async with self.semaphore:
            try:
                await self.api_gateway_client.post_to_connection(
                    ConnectionId=connection_id,
                    Data=audio_data
                )
                return True
                
            except self.api_gateway_client.exceptions.GoneException:
                # Connection no longer exists - remove from database
                logger.warning(
                    f"Stale connection detected: {connection_id}, removing"
                )
                await self._handle_gone_exception(connection_id, session_id)
                raise  # Re-raise to count as stale connection
                
            except (
                self.api_gateway_client.exceptions.LimitExceededException,
                Exception  # Catch 500 errors and other retryable errors
            ) as e:
                # Retryable errors
                if retry_count < self.max_retries:
                    backoff_time = (
                        self.retry_backoff_ms * (2 ** retry_count) / 1000.0
                    )
                    logger.warning(
                        f"Broadcast to {connection_id} failed (attempt {retry_count + 1}), "
                        f"retrying in {backoff_time}s: {e}"
                    )
                    await asyncio.sleep(backoff_time)
                    return await self._send_to_connection(
                        connection_id, audio_data, session_id, retry_count + 1
                    )
                else:
                    logger.error(
                        f"Broadcast to {connection_id} failed after "
                        f"{self.max_retries} retries: {e}"
                    )
                    return False
    
    async def _handle_gone_exception(
        self,
        connection_id: str,
        session_id: str
    ) -> None:
        """
        Remove stale connection from database.
        
        Args:
            connection_id: Stale connection ID
            session_id: Session identifier
        """
        try:
            await self.connections_repository.remove_connection(
                connection_id, session_id
            )
            logger.info(f"Removed stale connection: {connection_id}")
        except Exception as e:
            logger.error(
                f"Failed to remove stale connection {connection_id}: {e}",
                exc_info=True
            )
