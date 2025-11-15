"""
Unit tests for WebSocket message parser.
"""

import pytest
import base64
import json
from shared.utils.websocket_parser import (
    WebSocketMessageParser,
    WebSocketParseError,
    parse_websocket_audio_event
)


class TestWebSocketMessageParser:
    """Test suite for WebSocketMessageParser."""
    
    def test_parse_audio_message_with_json_body(self):
        """Test parsing audio message with JSON body."""
        parser = WebSocketMessageParser()
        
        audio_data = b"test audio data"
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')
        
        event = {
            'requestContext': {
                'connectionId': 'conn-123'
            },
            'body': json.dumps({'data': audio_b64}),
            'isBase64Encoded': False
        }
        
        connection_id, audio_bytes = parser.parse_audio_message(event)
        
        assert connection_id == 'conn-123'
        assert audio_bytes == audio_data
    
    def test_parse_audio_message_with_binary_body(self):
        """Test parsing audio message with binary body."""
        parser = WebSocketMessageParser()
        
        audio_data = b"test audio data"
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')
        
        event = {
            'requestContext': {
                'connectionId': 'conn-456'
            },
            'body': audio_b64,
            'isBase64Encoded': True
        }
        
        connection_id, audio_bytes = parser.parse_audio_message(event)
        
        assert connection_id == 'conn-456'
        assert audio_bytes == audio_data
    
    def test_parse_audio_message_missing_connection_id(self):
        """Test parsing fails when connectionId is missing."""
        parser = WebSocketMessageParser()
        
        event = {
            'requestContext': {},
            'body': json.dumps({'data': 'test'})
        }
        
        with pytest.raises(WebSocketParseError, match="Missing connectionId"):
            parser.parse_audio_message(event)
    
    def test_parse_audio_message_missing_body(self):
        """Test parsing fails when body is missing."""
        parser = WebSocketMessageParser()
        
        event = {
            'requestContext': {
                'connectionId': 'conn-123'
            }
        }
        
        with pytest.raises(WebSocketParseError, match="Missing message body"):
            parser.parse_audio_message(event)
    
    def test_parse_audio_message_invalid_json(self):
        """Test parsing fails with invalid JSON."""
        parser = WebSocketMessageParser()
        
        event = {
            'requestContext': {
                'connectionId': 'conn-123'
            },
            'body': 'invalid json',
            'isBase64Encoded': False
        }
        
        with pytest.raises(WebSocketParseError, match="Invalid JSON"):
            parser.parse_audio_message(event)
    
    def test_parse_audio_message_missing_data_field(self):
        """Test parsing fails when data field is missing."""
        parser = WebSocketMessageParser()
        
        event = {
            'requestContext': {
                'connectionId': 'conn-123'
            },
            'body': json.dumps({'other': 'field'}),
            'isBase64Encoded': False
        }
        
        with pytest.raises(WebSocketParseError, match="Missing 'data' field"):
            parser.parse_audio_message(event)
    
    def test_parse_audio_message_invalid_base64(self):
        """Test parsing fails with invalid base64."""
        parser = WebSocketMessageParser()
        
        event = {
            'requestContext': {
                'connectionId': 'conn-123'
            },
            'body': json.dumps({'data': 'not-valid-base64!!!'}),
            'isBase64Encoded': False
        }
        
        with pytest.raises(WebSocketParseError, match="Invalid base64"):
            parser.parse_audio_message(event)
    
    def test_validate_message_format_valid(self):
        """Test message format validation with valid message."""
        parser = WebSocketMessageParser()
        
        event = {
            'requestContext': {
                'connectionId': 'conn-123'
            },
            'body': 'some body'
        }
        
        assert parser.validate_message_format(event) is True
    
    def test_validate_message_format_missing_request_context(self):
        """Test message format validation fails without requestContext."""
        parser = WebSocketMessageParser()
        
        event = {
            'body': 'some body'
        }
        
        assert parser.validate_message_format(event) is False
    
    def test_validate_message_format_missing_connection_id(self):
        """Test message format validation fails without connectionId."""
        parser = WebSocketMessageParser()
        
        event = {
            'requestContext': {},
            'body': 'some body'
        }
        
        assert parser.validate_message_format(event) is False
    
    def test_parse_websocket_audio_event_convenience_function(self):
        """Test convenience function for parsing."""
        audio_data = b"test audio"
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')
        
        event = {
            'requestContext': {
                'connectionId': 'conn-789'
            },
            'body': json.dumps({'data': audio_b64})
        }
        
        connection_id, audio_bytes = parse_websocket_audio_event(event)
        
        assert connection_id == 'conn-789'
        assert audio_bytes == audio_data
