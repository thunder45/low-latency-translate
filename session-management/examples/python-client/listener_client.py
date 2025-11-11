"""
Listener Client Example (Python)

This example demonstrates how to implement a listener client in Python for testing purposes.
It includes:
- Anonymous WebSocket connection (no authentication)
- Connection refresh handling
- Audio reception and buffering
- Error handling and reconnection
"""

import asyncio
import json
import time
import base64
from typing import Optional, Callable, Dict, Any, List
import websockets


class ListenerClient:
    """
    Python listener client for testing WebSocket session management.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_endpoint = config['api_endpoint']
        self.session_id = config['session_id']
        self.target_language = config['target_language']
        
        self.ws = None
        self.connection_start_time = None
        self.refresh_threshold = 100 * 60  # 100 minutes in seconds
        self.is_refreshing = False
        self.heartbeat_task = None
        self.audio_buffer: List[str] = []
        self.event_handlers = {}

    async def connect(self):
        """
        Connect to WebSocket and join session.
        No authentication required for listeners.
        """
        ws_url = (
            f"{self.api_endpoint}?"
            f"action=joinSession&"
            f"sessionId={self.session_id}&"
            f"targetLanguage={self.target_language}"
        )

        try:
            self.ws = await websockets.connect(ws_url)
            self.connection_start_time = time.time()
            print('WebSocket connected')
            
            # Start heartbeat
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            # Start message handler
            asyncio.create_task(self._message_handler())
            
        except Exception as e:
            print(f'Connection failed: {e}')
            raise

    async def _message_handler(self):
        """
        Handle incoming WebSocket messages.
        """
        try:
            async for message in self.ws:
                await self._handle_message(message)
        except websockets.exceptions.ConnectionClosed as e:
            print(f'WebSocket connection closed: {e.code} {e.reason}')
            if not self.is_refreshing:
                await self._emit('disconnect', {'code': e.code, 'reason': e.reason})
                await self._attempt_reconnect()

    async def _handle_message(self, message: str):
        """
        Parse and handle incoming message.
        
        Args:
            message: JSON message string
        """
        try:
            data = json.loads(message)
            message_type = data.get('type')
            
            print(f'Received message: {message_type}')
            
            if message_type == 'sessionJoined':
                print(f"Joined session: {data['sessionId']}")
                print(f"Listening in: {data.get('targetLanguage', self.target_language)}")
                await self._emit('sessionJoined', data)
                
            elif message_type == 'audioData':
                # Received translated audio
                audio_data = data.get('audioData')
                await self._handle_audio_data(audio_data)
                
            elif message_type == 'heartbeatAck':
                await self._emit('heartbeat', data)
                
            elif message_type == 'connectionRefreshRequired':
                print('Connection refresh required')
                await self._handle_connection_refresh(data)
                
            elif message_type == 'connectionWarning':
                remaining = data.get('remainingMinutes', 0)
                print(f'Connection expires in {remaining} minutes')
                await self._emit('connectionWarning', data)
                
            elif message_type == 'sessionEnded':
                print('Session ended by speaker')
                await self._emit('sessionEnded', data)
                await self.disconnect()
                
            elif message_type == 'sessionPaused':
                print('Session paused')
                await self._emit('sessionPaused', data)
                
            elif message_type == 'sessionResumed':
                print('Session resumed')
                await self._emit('sessionResumed', data)
                
            elif message_type == 'error':
                print(f"Server error: {data.get('message')}")
                await self._emit('error', data)
                
            else:
                print(f'Unknown message type: {message_type}')
                
        except json.JSONDecodeError as e:
            print(f'Error parsing message: {e}')

    async def _handle_connection_refresh(self, message: Dict[str, Any]):
        """
        Handle connection refresh for unlimited session duration.
        
        Args:
            message: Refresh message from server
        """
        if self.is_refreshing:
            print('Refresh already in progress')
            return

        self.is_refreshing = True
        print('Starting connection refresh...')

        try:
            # 1. Establish new connection
            new_ws_url = (
                f"{self.api_endpoint}?"
                f"action=refreshConnection&"
                f"sessionId={self.session_id}&"
                f"targetLanguage={self.target_language}&"
                f"role=listener"
            )
            
            new_ws = await websockets.connect(new_ws_url)
            print('New connection established')
            
            # 2. Wait for refresh complete message
            async for msg in new_ws:
                data = json.loads(msg)
                if data.get('type') == 'connectionRefreshComplete':
                    print('Connection refresh complete')
                    
                    # 3. Buffer any remaining audio from old connection
                    # (In production, implement proper audio buffering)
                    
                    # 4. Close old connection
                    await self.ws.close(code=1000, reason='Connection refresh')
                    
                    # 5. Switch to new connection
                    self.ws = new_ws
                    self.connection_start_time = time.time()
                    self.is_refreshing = False
                    
                    # Restart message handler for new connection
                    asyncio.create_task(self._message_handler())
                    
                    await self._emit('connectionRefreshed', {'sessionId': self.session_id})
                    break
                    
        except Exception as e:
            print(f'Connection refresh failed: {e}')
            self.is_refreshing = False
            
            # Retry after 30 seconds
            await asyncio.sleep(30)
            await self._handle_connection_refresh(message)

    async def _handle_audio_data(self, audio_data: str):
        """
        Handle received audio data.
        
        Args:
            audio_data: Base64 encoded audio
        """
        # In production, decode and play audio
        # For testing, just log receipt
        print(f'Received audio chunk ({len(audio_data)} bytes)')
        await self._emit('audioReceived', {'audioData': audio_data})
        
        # Example: Decode audio
        try:
            audio_bytes = base64.b64decode(audio_data)
            # Process audio_bytes (play, save, etc.)
        except Exception as e:
            print(f'Error decoding audio: {e}')

    async def _heartbeat_loop(self):
        """
        Send heartbeat messages every 30 seconds.
        """
        while True:
            try:
                await asyncio.sleep(30)
                if self.ws and not self.ws.closed:
                    await self.ws.send(json.dumps({'action': 'heartbeat'}))
            except Exception as e:
                print(f'Heartbeat error: {e}')
                break

    async def _attempt_reconnect(self, retry_count: int = 0, max_retries: int = 5):
        """
        Attempt to reconnect after unexpected disconnect.
        
        Args:
            retry_count: Current retry attempt
            max_retries: Maximum number of retries
        """
        if retry_count >= max_retries:
            print('Max reconnection attempts reached')
            await self._emit('reconnectFailed', {})
            return

        # Exponential backoff with max 5 minutes
        backoff_delay = min(30 * (2 ** retry_count), 300)
        print(f'Attempting to reconnect in {backoff_delay}s (attempt {retry_count + 1}/{max_retries})')

        await asyncio.sleep(backoff_delay)

        try:
            await self.connect()
            print('Reconnected successfully')
            await self._emit('reconnected', {})
        except Exception as e:
            print(f'Reconnection failed: {e}')
            await self._attempt_reconnect(retry_count + 1, max_retries)

    async def change_language(self, new_language: str):
        """
        Change target language during session.
        
        Args:
            new_language: New target language code
        """
        if self.ws and not self.ws.closed:
            await self.ws.send(json.dumps({
                'action': 'changeLanguage',
                'sessionId': self.session_id,
                'targetLanguage': new_language
            }))
            self.target_language = new_language
            await self._emit('languageChanged', {'language': new_language})

    async def disconnect(self):
        """
        Disconnect from session.
        """
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            
        if self.ws and not self.ws.closed:
            await self.ws.close(code=1000, reason='Listener disconnected')
            
        self.ws = None
        self.connection_start_time = None
        await self._emit('disconnected', {})

    def on(self, event: str, handler: Callable):
        """
        Register event handler.
        
        Args:
            event: Event name
            handler: Callback function
        """
        if event not in self.event_handlers:
            self.event_handlers[event] = []
        self.event_handlers[event].append(handler)

    async def _emit(self, event: str, data: Dict[str, Any]):
        """
        Emit event to registered handlers.
        
        Args:
            event: Event name
            data: Event data
        """
        if event in self.event_handlers:
            for handler in self.event_handlers[event]:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)


# Usage Example
async def main():
    """
    Example usage of ListenerClient.
    """
    client = ListenerClient({
        'api_endpoint': 'wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod',
        'session_id': 'golden-eagle-427',  # Session ID from speaker
        'target_language': 'es'  # Spanish
    })

    # Setup event handlers
    def on_session_joined(data):
        print(f"Successfully joined session: {data['sessionId']}")
        print(f"Listening in: {data.get('targetLanguage', 'unknown')}")

    def on_audio_received(data):
        print('Received audio chunk')

    def on_session_ended(data):
        print('Session has ended')

    def on_session_paused(data):
        print('Session paused by speaker')

    def on_session_resumed(data):
        print('Session resumed by speaker')

    def on_connection_warning(data):
        print(f"Connection will expire in {data['remainingMinutes']} minutes")

    async def on_connection_refreshed(data):
        print('Connection refreshed successfully')

    def on_disconnect(data):
        print(f"Disconnected unexpectedly: {data.get('reason')}")

    async def on_reconnected(data):
        print('Reconnected successfully')

    def on_error(error):
        print(f'Client error: {error}')

    client.on('sessionJoined', on_session_joined)
    client.on('audioReceived', on_audio_received)
    client.on('sessionEnded', on_session_ended)
    client.on('sessionPaused', on_session_paused)
    client.on('sessionResumed', on_session_resumed)
    client.on('connectionWarning', on_connection_warning)
    client.on('connectionRefreshed', on_connection_refreshed)
    client.on('disconnect', on_disconnect)
    client.on('reconnected', on_reconnected)
    client.on('error', on_error)

    try:
        # Connect and join session
        await client.connect()
        
        # Keep connection alive to receive audio
        print('Listening for audio...')
        await asyncio.sleep(120)  # Listen for 2 minutes
        
        # Optional: Change language during session
        # await client.change_language('fr')  # Switch to French
        # await asyncio.sleep(60)
        
        # Disconnect
        await client.disconnect()
        
    except Exception as e:
        print(f'Error: {e}')


if __name__ == '__main__':
    asyncio.run(main())
