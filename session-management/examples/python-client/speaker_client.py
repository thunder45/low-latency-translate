"""
Speaker Client Example (Python)

This example demonstrates how to implement a speaker client in Python for testing purposes.
It includes:
- Cognito authentication
- WebSocket connection management
- Connection refresh handling
- Audio streaming simulation
- Error handling and reconnection
"""

import asyncio
import json
import time
import base64
from typing import Optional, Callable, Dict, Any
import websockets
import boto3
from botocore.exceptions import ClientError


class SpeakerClient:
    """
    Python speaker client for testing WebSocket session management.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_endpoint = config['api_endpoint']
        self.cognito_user_pool_id = config['cognito_user_pool_id']
        self.cognito_client_id = config['cognito_client_id']
        self.source_language = config.get('source_language', 'en')
        self.quality_tier = config.get('quality_tier', 'standard')
        self.region = config.get('region', 'us-east-1')
        
        self.ws = None
        self.jwt_token = None
        self.session_id = None
        self.connection_start_time = None
        self.refresh_threshold = 100 * 60  # 100 minutes in seconds
        self.is_refreshing = False
        self.heartbeat_task = None
        self.event_handlers = {}
        
        # Initialize Cognito client
        self.cognito_client = boto3.client(
            'cognito-idp',
            region_name=self.region
        )

    async def authenticate(self, username: str, password: str) -> str:
        """
        Authenticate with Cognito and get JWT token.
        
        Args:
            username: Cognito username
            password: User password
            
        Returns:
            JWT ID token
        """
        try:
            response = self.cognito_client.initiate_auth(
                AuthFlow='USER_PASSWORD_AUTH',
                ClientId=self.cognito_client_id,
                AuthParameters={
                    'USERNAME': username,
                    'PASSWORD': password
                }
            )
            
            self.jwt_token = response['AuthenticationResult']['IdToken']
            print('Authentication successful')
            return self.jwt_token
            
        except ClientError as e:
            print(f'Authentication failed: {e}')
            raise

    async def connect(self):
        """
        Connect to WebSocket and create session.
        """
        if not self.jwt_token:
            raise ValueError('Must authenticate before connecting')

        ws_url = (
            f"{self.api_endpoint}?"
            f"action=createSession&"
            f"sourceLanguage={self.source_language}&"
            f"qualityTier={self.quality_tier}&"
            f"token={self.jwt_token}"
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
        except websockets.exceptions.ConnectionClosed:
            print('WebSocket connection closed')
            await self._emit('disconnect', {})

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
            
            if message_type == 'sessionCreated':
                self.session_id = data['sessionId']
                print(f'Session created: {self.session_id}')
                await self._emit('sessionCreated', data)
                
            elif message_type == 'heartbeatAck':
                await self._emit('heartbeat', data)
                
            elif message_type == 'connectionRefreshRequired':
                print('Connection refresh required')
                await self._handle_connection_refresh(data)
                
            elif message_type == 'connectionWarning':
                remaining = data.get('remainingMinutes', 0)
                print(f'Connection expires in {remaining} minutes')
                await self._emit('connectionWarning', data)
                
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
                f"role=speaker&"
                f"token={self.jwt_token}"
            )
            
            new_ws = await websockets.connect(new_ws_url)
            print('New connection established')
            
            # 2. Wait for refresh complete message
            async for msg in new_ws:
                data = json.loads(msg)
                if data.get('type') == 'connectionRefreshComplete':
                    print('Connection refresh complete')
                    
                    # 3. Close old connection
                    await self.ws.close(code=1000, reason='Connection refresh')
                    
                    # 4. Switch to new connection
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

    async def send_audio(self, audio_data: bytes):
        """
        Send audio data to server.
        
        Args:
            audio_data: Raw audio bytes
        """
        if self.ws and not self.ws.closed:
            # Encode audio as base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            message = json.dumps({
                'action': 'sendAudio',
                'sessionId': self.session_id,
                'audioData': audio_base64
            })
            
            await self.ws.send(message)
        else:
            print('WebSocket not ready')

    async def pause(self):
        """
        Pause audio streaming.
        """
        if self.ws and not self.ws.closed:
            await self.ws.send(json.dumps({
                'action': 'controlSession',
                'sessionId': self.session_id,
                'command': 'pause'
            }))
            await self._emit('paused', {})

    async def resume(self):
        """
        Resume audio streaming.
        """
        if self.ws and not self.ws.closed:
            await self.ws.send(json.dumps({
                'action': 'controlSession',
                'sessionId': self.session_id,
                'command': 'resume'
            }))
            await self._emit('resumed', {})

    async def disconnect(self):
        """
        End session and disconnect.
        """
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            
        if self.ws and not self.ws.closed:
            await self.ws.close(code=1000, reason='Session ended by speaker')
            
        self.ws = None
        self.session_id = None
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
    Example usage of SpeakerClient.
    """
    client = SpeakerClient({
        'api_endpoint': 'wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod',
        'cognito_user_pool_id': 'us-east-1_ABC123XYZ',
        'cognito_client_id': '1a2b3c4d5e6f7g8h9i0j',
        'source_language': 'en',
        'quality_tier': 'standard',
        'region': 'us-east-1'
    })

    # Setup event handlers
    def on_session_created(data):
        print(f"Session ID: {data['sessionId']}")
        print(f"Share this ID with listeners: {data['sessionId']}")

    def on_connection_warning(data):
        print(f"Connection will expire in {data['remainingMinutes']} minutes")

    async def on_connection_refreshed(data):
        print('Connection refreshed successfully')

    def on_error(error):
        print(f'Client error: {error}')

    client.on('sessionCreated', on_session_created)
    client.on('connectionWarning', on_connection_warning)
    client.on('connectionRefreshed', on_connection_refreshed)
    client.on('error', on_error)

    try:
        # Authenticate
        await client.authenticate('username', 'password')
        
        # Connect and create session
        await client.connect()
        
        # Simulate audio streaming
        print('Streaming audio...')
        for i in range(10):
            # Simulate audio chunk (replace with actual audio data)
            audio_chunk = b'fake_audio_data_' + str(i).encode()
            await client.send_audio(audio_chunk)
            await asyncio.sleep(1)
        
        # Keep connection alive for testing
        await asyncio.sleep(60)
        
        # Disconnect
        await client.disconnect()
        
    except Exception as e:
        print(f'Error: {e}')


if __name__ == '__main__':
    asyncio.run(main())
