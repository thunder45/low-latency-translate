"""Unit tests for PollyClient."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError
from io import BytesIO

from emotion_dynamics.clients.polly_client import PollyClient
from emotion_dynamics.exceptions import SynthesisError


class TestPollyClient:
    """Test suite for PollyClient."""
    
    @pytest.fixture
    def mock_polly_client(self):
        """Fixture for mocked boto3 Polly client."""
        with patch('emotion_dynamics.clients.polly_client.boto3.client') as mock_client:
            mock_polly = Mock()
            mock_client.return_value = mock_polly
            yield mock_polly
    
    @pytest.fixture
    def polly_client(self, mock_polly_client):
        """Fixture for PollyClient instance with mocked boto3 client."""
        return PollyClient(region_name='us-east-1')
    
    def test_initialization_success(self, mock_polly_client):
        """Test successful initialization of PollyClient."""
        client = PollyClient(region_name='us-east-1')
        
        assert client is not None
        assert client.max_retries == PollyClient.DEFAULT_MAX_RETRIES
        assert client.base_delay == PollyClient.DEFAULT_BASE_DELAY
        assert client.max_delay == PollyClient.DEFAULT_MAX_DELAY
    
    def test_initialization_with_custom_retry_config(self, mock_polly_client):
        """Test initialization with custom retry configuration."""
        client = PollyClient(
            region_name='us-west-2',
            max_retries=5,
            base_delay=0.2,
            max_delay=3.0
        )
        
        assert client.max_retries == 5
        assert client.base_delay == 0.2
        assert client.max_delay == 3.0
    
    def test_synthesize_speech_with_ssml_success(self, polly_client, mock_polly_client):
        """Test successful SSML synthesis with mocked Polly."""
        # Mock successful response
        mock_audio_stream = BytesIO(b'fake_audio_data')
        mock_response = {
            'AudioStream': mock_audio_stream
        }
        mock_polly_client.synthesize_speech.return_value = mock_response
        
        ssml_text = '<speak><prosody rate="medium" volume="medium">Hello world</prosody></speak>'
        
        audio_data = polly_client.synthesize_speech(
            text=ssml_text,
            voice_id='Joanna',
            text_type='ssml'
        )
        
        assert audio_data == b'fake_audio_data'
        
        # Verify Polly was called with correct parameters
        mock_polly_client.synthesize_speech.assert_called_once()
        call_args = mock_polly_client.synthesize_speech.call_args[1]
        assert call_args['Text'] == ssml_text
        assert call_args['TextType'] == 'ssml'
        assert call_args['VoiceId'] == 'Joanna'
        assert call_args['Engine'] == 'neural'
        assert call_args['OutputFormat'] == 'mp3'
        assert call_args['SampleRate'] == '24000'
    
    def test_synthesize_speech_with_plain_text_success(self, polly_client, mock_polly_client):
        """Test successful plain text synthesis."""
        # Mock successful response
        mock_audio_stream = BytesIO(b'fake_audio_data')
        mock_response = {
            'AudioStream': mock_audio_stream
        }
        mock_polly_client.synthesize_speech.return_value = mock_response
        
        text = "Hello world"
        
        audio_data = polly_client.synthesize_speech(
            text=text,
            voice_id='Matthew',
            text_type='text'
        )
        
        assert audio_data == b'fake_audio_data'
        
        # Verify Polly was called with correct parameters
        call_args = mock_polly_client.synthesize_speech.call_args[1]
        assert call_args['Text'] == text
        assert call_args['TextType'] == 'text'
        assert call_args['VoiceId'] == 'Matthew'
    
    def test_fallback_to_plain_text_on_ssml_rejection(self, polly_client, mock_polly_client):
        """Test fallback to plain text when SSML is rejected."""
        ssml_text = '<speak><prosody rate="medium" volume="medium">Hello world</prosody></speak>'
        
        # First call fails with InvalidSsmlException
        error_response = {'Error': {'Code': 'InvalidSsmlException', 'Message': 'Invalid SSML'}}
        mock_polly_client.synthesize_speech.side_effect = [
            ClientError(error_response, 'SynthesizeSpeech'),
            {'AudioStream': BytesIO(b'fallback_audio_data')}
        ]
        
        audio_data = polly_client.synthesize_speech(
            text=ssml_text,
            voice_id='Joanna',
            text_type='ssml'
        )
        
        assert audio_data == b'fallback_audio_data'
        
        # Verify Polly was called twice (SSML then plain text)
        assert mock_polly_client.synthesize_speech.call_count == 2
        
        # First call with SSML
        first_call_args = mock_polly_client.synthesize_speech.call_args_list[0][1]
        assert first_call_args['TextType'] == 'ssml'
        
        # Second call with plain text
        second_call_args = mock_polly_client.synthesize_speech.call_args_list[1][1]
        assert second_call_args['TextType'] == 'text'
        assert second_call_args['Text'] == 'Hello world'  # Extracted from SSML
    
    def test_retry_logic_with_throttling_error(self, polly_client, mock_polly_client):
        """Test retry logic with mocked throttling errors."""
        # First two calls fail with ThrottlingException, third succeeds
        error_response = {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}}
        mock_polly_client.synthesize_speech.side_effect = [
            ClientError(error_response, 'SynthesizeSpeech'),
            ClientError(error_response, 'SynthesizeSpeech'),
            {'AudioStream': BytesIO(b'success_audio_data')}
        ]
        
        with patch('emotion_dynamics.clients.polly_client.time.sleep'):  # Mock sleep to speed up test
            audio_data = polly_client.synthesize_speech(
                text='Test text',
                text_type='text'
            )
        
        assert audio_data == b'success_audio_data'
        assert mock_polly_client.synthesize_speech.call_count == 3
    
    def test_retry_exhaustion_raises_synthesis_error(self, polly_client, mock_polly_client):
        """Test that exhausting retries raises SynthesisError."""
        # All calls fail with ThrottlingException
        error_response = {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}}
        mock_polly_client.synthesize_speech.side_effect = ClientError(error_response, 'SynthesizeSpeech')
        
        with patch('emotion_dynamics.clients.polly_client.time.sleep'):  # Mock sleep to speed up test
            with pytest.raises(SynthesisError) as exc_info:
                polly_client.synthesize_speech(
                    text='Test text',
                    text_type='text'
                )
        
        assert 'after 3 retries' in str(exc_info.value)
        assert mock_polly_client.synthesize_speech.call_count == 4  # Initial + 3 retries
    
    def test_non_retryable_error_raises_immediately(self, polly_client, mock_polly_client):
        """Test that non-retryable errors raise immediately without retries."""
        # Fail with non-retryable error
        error_response = {'Error': {'Code': 'InvalidParameterException', 'Message': 'Invalid parameter'}}
        mock_polly_client.synthesize_speech.side_effect = ClientError(error_response, 'SynthesizeSpeech')
        
        with pytest.raises(SynthesisError) as exc_info:
            polly_client.synthesize_speech(
                text='Test text',
                text_type='text'
            )
        
        assert 'InvalidParameterException' in str(exc_info.value)
        assert mock_polly_client.synthesize_speech.call_count == 1  # No retries
    
    def test_audio_stream_handling(self, polly_client, mock_polly_client):
        """Test proper handling of audio stream response."""
        # Create a mock audio stream with multiple chunks
        audio_chunks = [b'chunk1', b'chunk2', b'chunk3']
        mock_audio_stream = Mock()
        mock_audio_stream.read.return_value = b''.join(audio_chunks)
        
        mock_response = {
            'AudioStream': mock_audio_stream
        }
        mock_polly_client.synthesize_speech.return_value = mock_response
        
        audio_data = polly_client.synthesize_speech(
            text='Test text',
            text_type='text'
        )
        
        assert audio_data == b'chunk1chunk2chunk3'
        mock_audio_stream.read.assert_called_once()
    
    def test_voice_configuration(self, polly_client, mock_polly_client):
        """Test voice configuration with different voice IDs."""
        mock_audio_stream = BytesIO(b'audio_data')
        mock_response = {'AudioStream': mock_audio_stream}
        mock_polly_client.synthesize_speech.return_value = mock_response
        
        voice_ids = ['Joanna', 'Matthew', 'Amy', 'Brian']
        
        for voice_id in voice_ids:
            polly_client.synthesize_speech(
                text='Test text',
                voice_id=voice_id,
                text_type='text'
            )
            
            call_args = mock_polly_client.synthesize_speech.call_args[1]
            assert call_args['VoiceId'] == voice_id
    
    def test_mp3_format_and_sample_rate(self, polly_client, mock_polly_client):
        """Test MP3 format and 24000 Hz sample rate configuration."""
        mock_audio_stream = BytesIO(b'audio_data')
        mock_response = {'AudioStream': mock_audio_stream}
        mock_polly_client.synthesize_speech.return_value = mock_response
        
        polly_client.synthesize_speech(
            text='Test text',
            text_type='text'
        )
        
        call_args = mock_polly_client.synthesize_speech.call_args[1]
        assert call_args['OutputFormat'] == 'mp3'
        assert call_args['SampleRate'] == '24000'
    
    def test_custom_output_format_and_sample_rate(self, polly_client, mock_polly_client):
        """Test custom output format and sample rate."""
        mock_audio_stream = BytesIO(b'audio_data')
        mock_response = {'AudioStream': mock_audio_stream}
        mock_polly_client.synthesize_speech.return_value = mock_response
        
        polly_client.synthesize_speech(
            text='Test text',
            text_type='text',
            output_format='ogg_vorbis',
            sample_rate='16000'
        )
        
        call_args = mock_polly_client.synthesize_speech.call_args[1]
        assert call_args['OutputFormat'] == 'ogg_vorbis'
        assert call_args['SampleRate'] == '16000'
    
    def test_neural_engine_configuration(self, polly_client, mock_polly_client):
        """Test neural engine configuration."""
        mock_audio_stream = BytesIO(b'audio_data')
        mock_response = {'AudioStream': mock_audio_stream}
        mock_polly_client.synthesize_speech.return_value = mock_response
        
        polly_client.synthesize_speech(
            text='Test text',
            text_type='text'
        )
        
        call_args = mock_polly_client.synthesize_speech.call_args[1]
        assert call_args['Engine'] == 'neural'
    
    def test_empty_text_raises_synthesis_error(self, polly_client):
        """Test that empty text raises SynthesisError."""
        with pytest.raises(SynthesisError) as exc_info:
            polly_client.synthesize_speech(text='', text_type='text')
        
        assert 'cannot be empty' in str(exc_info.value)
    
    def test_whitespace_only_text_raises_synthesis_error(self, polly_client):
        """Test that whitespace-only text raises SynthesisError."""
        with pytest.raises(SynthesisError) as exc_info:
            polly_client.synthesize_speech(text='   \n\t  ', text_type='text')
        
        assert 'cannot be empty' in str(exc_info.value)
    
    def test_extract_text_from_ssml_simple(self, polly_client):
        """Test extracting plain text from simple SSML."""
        ssml = '<speak>Hello world</speak>'
        
        text = polly_client._extract_text_from_ssml(ssml)
        
        assert text == 'Hello world'
    
    def test_extract_text_from_ssml_with_prosody(self, polly_client):
        """Test extracting plain text from SSML with prosody tags."""
        ssml = '<speak><prosody rate="medium" volume="medium">Hello world</prosody></speak>'
        
        text = polly_client._extract_text_from_ssml(ssml)
        
        assert text == 'Hello world'
    
    def test_extract_text_from_ssml_with_entities(self, polly_client):
        """Test extracting plain text from SSML with XML entities."""
        ssml = '<speak>Tom &amp; Jerry: &lt;Episode&gt; &quot;The Chase&quot;</speak>'
        
        text = polly_client._extract_text_from_ssml(ssml)
        
        assert text == 'Tom & Jerry: <Episode> "The Chase"'
    
    def test_extract_text_from_ssml_with_multiple_tags(self, polly_client):
        """Test extracting plain text from SSML with multiple nested tags."""
        ssml = '<speak><prosody rate="fast"><emphasis>Important</emphasis> message</prosody></speak>'
        
        text = polly_client._extract_text_from_ssml(ssml)
        
        assert text == 'Important message'
    
    def test_extract_text_from_ssml_with_whitespace(self, polly_client):
        """Test extracting plain text from SSML with extra whitespace."""
        ssml = '<speak>  Hello   \n  world  \t  </speak>'
        
        text = polly_client._extract_text_from_ssml(ssml)
        
        assert text == 'Hello world'
    
    def test_exponential_backoff_delay_calculation(self, polly_client, mock_polly_client):
        """Test that exponential backoff delays increase correctly."""
        error_response = {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}}
        mock_polly_client.synthesize_speech.side_effect = [
            ClientError(error_response, 'SynthesizeSpeech'),
            ClientError(error_response, 'SynthesizeSpeech'),
            ClientError(error_response, 'SynthesizeSpeech'),
            {'AudioStream': BytesIO(b'success_audio_data')}
        ]
        
        sleep_times = []
        
        def mock_sleep(duration):
            sleep_times.append(duration)
        
        with patch('emotion_dynamics.clients.polly_client.time.sleep', side_effect=mock_sleep):
            polly_client.synthesize_speech(text='Test text', text_type='text')
        
        # Verify delays increase exponentially (with jitter)
        assert len(sleep_times) == 3
        # First delay should be around base_delay (0.1s ± 25%)
        assert 0.075 <= sleep_times[0] <= 0.125
        # Second delay should be around 2 * base_delay (0.2s ± 25%)
        assert 0.15 <= sleep_times[1] <= 0.25
        # Third delay should be around 4 * base_delay (0.4s ± 25%)
        assert 0.3 <= sleep_times[2] <= 0.5
    
    def test_max_delay_cap(self, mock_polly_client):
        """Test that delay is capped at max_delay."""
        # Create client with small max_delay
        client = PollyClient(region_name='us-east-1', max_delay=0.3)
        
        error_response = {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}}
        mock_polly_client.synthesize_speech.side_effect = [
            ClientError(error_response, 'SynthesizeSpeech'),
            ClientError(error_response, 'SynthesizeSpeech'),
            ClientError(error_response, 'SynthesizeSpeech'),
            {'AudioStream': BytesIO(b'success_audio_data')}
        ]
        
        sleep_times = []
        
        def mock_sleep(duration):
            sleep_times.append(duration)
        
        with patch('emotion_dynamics.clients.polly_client.time.sleep', side_effect=mock_sleep):
            client.synthesize_speech(text='Test text', text_type='text')
        
        # All delays should be capped at max_delay (with jitter)
        for delay in sleep_times:
            assert delay <= 0.3 * 1.25  # max_delay + 25% jitter
    
    def test_service_failure_exception_retry(self, polly_client, mock_polly_client):
        """Test retry on ServiceFailureException."""
        error_response = {'Error': {'Code': 'ServiceFailureException', 'Message': 'Service failure'}}
        mock_polly_client.synthesize_speech.side_effect = [
            ClientError(error_response, 'SynthesizeSpeech'),
            {'AudioStream': BytesIO(b'success_audio_data')}
        ]
        
        with patch('emotion_dynamics.clients.polly_client.time.sleep'):
            audio_data = polly_client.synthesize_speech(text='Test text', text_type='text')
        
        assert audio_data == b'success_audio_data'
        assert mock_polly_client.synthesize_speech.call_count == 2
    
    def test_service_unavailable_exception_retry(self, polly_client, mock_polly_client):
        """Test retry on ServiceUnavailableException."""
        error_response = {'Error': {'Code': 'ServiceUnavailableException', 'Message': 'Service unavailable'}}
        mock_polly_client.synthesize_speech.side_effect = [
            ClientError(error_response, 'SynthesizeSpeech'),
            {'AudioStream': BytesIO(b'success_audio_data')}
        ]
        
        with patch('emotion_dynamics.clients.polly_client.time.sleep'):
            audio_data = polly_client.synthesize_speech(text='Test text', text_type='text')
        
        assert audio_data == b'success_audio_data'
        assert mock_polly_client.synthesize_speech.call_count == 2
    
    def test_ssml_marks_not_supported_fallback(self, polly_client, mock_polly_client):
        """Test fallback on SsmlMarksNotSupportedForInputTypeException."""
        ssml_text = '<speak><prosody rate="medium" volume="medium">Hello world</prosody></speak>'
        
        error_response = {
            'Error': {
                'Code': 'SsmlMarksNotSupportedForInputTypeException',
                'Message': 'SSML marks not supported'
            }
        }
        mock_polly_client.synthesize_speech.side_effect = [
            ClientError(error_response, 'SynthesizeSpeech'),
            {'AudioStream': BytesIO(b'fallback_audio_data')}
        ]
        
        audio_data = polly_client.synthesize_speech(
            text=ssml_text,
            text_type='ssml'
        )
        
        assert audio_data == b'fallback_audio_data'
        assert mock_polly_client.synthesize_speech.call_count == 2
    
    def test_unexpected_exception_raises_synthesis_error(self, polly_client, mock_polly_client):
        """Test that unexpected exceptions are wrapped in SynthesisError."""
        mock_polly_client.synthesize_speech.side_effect = Exception("Unexpected error")
        
        with pytest.raises(SynthesisError) as exc_info:
            polly_client.synthesize_speech(text='Test text', text_type='text')
        
        assert 'Unexpected error' in str(exc_info.value)
    
    def test_get_available_voices_success(self, polly_client, mock_polly_client):
        """Test getting available voices."""
        mock_voices = [
            {'Id': 'Joanna', 'Name': 'Joanna', 'LanguageCode': 'en-US'},
            {'Id': 'Matthew', 'Name': 'Matthew', 'LanguageCode': 'en-US'}
        ]
        mock_polly_client.describe_voices.return_value = {'Voices': mock_voices}
        
        voices = polly_client.get_available_voices()
        
        assert len(voices) == 2
        assert voices[0]['Id'] == 'Joanna'
        assert voices[1]['Id'] == 'Matthew'
    
    def test_get_available_voices_with_language_filter(self, polly_client, mock_polly_client):
        """Test getting available voices filtered by language."""
        mock_voices = [
            {'Id': 'Joanna', 'Name': 'Joanna', 'LanguageCode': 'en-US'}
        ]
        mock_polly_client.describe_voices.return_value = {'Voices': mock_voices}
        
        voices = polly_client.get_available_voices(language_code='en-US')
        
        assert len(voices) == 1
        mock_polly_client.describe_voices.assert_called_once_with(
            LanguageCode='en-US',
            Engine='neural'
        )
    
    def test_get_available_voices_error_returns_empty_list(self, polly_client, mock_polly_client):
        """Test that get_available_voices returns empty list on error."""
        error_response = {'Error': {'Code': 'ServiceFailureException', 'Message': 'Service failure'}}
        mock_polly_client.describe_voices.side_effect = ClientError(error_response, 'DescribeVoices')
        
        voices = polly_client.get_available_voices()
        
        assert voices == []
    
    def test_long_text_synthesis(self, polly_client, mock_polly_client):
        """Test synthesis with long text (3000 characters)."""
        long_text = "This is a test sentence. " * 120  # ~3000 characters
        
        mock_audio_stream = BytesIO(b'long_audio_data')
        mock_response = {'AudioStream': mock_audio_stream}
        mock_polly_client.synthesize_speech.return_value = mock_response
        
        audio_data = polly_client.synthesize_speech(
            text=long_text,
            text_type='text'
        )
        
        assert audio_data == b'long_audio_data'
        
        call_args = mock_polly_client.synthesize_speech.call_args[1]
        assert len(call_args['Text']) >= 3000
    
    def test_unicode_text_synthesis(self, polly_client, mock_polly_client):
        """Test synthesis with Unicode characters."""
        unicode_text = "Hello 世界! Привет мир! مرحبا بالعالم!"
        
        mock_audio_stream = BytesIO(b'unicode_audio_data')
        mock_response = {'AudioStream': mock_audio_stream}
        mock_polly_client.synthesize_speech.return_value = mock_response
        
        audio_data = polly_client.synthesize_speech(
            text=unicode_text,
            text_type='text'
        )
        
        assert audio_data == b'unicode_audio_data'
        
        call_args = mock_polly_client.synthesize_speech.call_args[1]
        assert call_args['Text'] == unicode_text
    
    def test_concurrent_synthesis_requests(self, polly_client, mock_polly_client):
        """Test handling of concurrent synthesis requests."""
        # Create a new BytesIO for each call
        def create_response(*args, **kwargs):
            return {'AudioStream': BytesIO(b'audio_data')}
        
        mock_polly_client.synthesize_speech.side_effect = create_response
        
        # Simulate concurrent requests
        for i in range(10):
            audio_data = polly_client.synthesize_speech(
                text=f'Test text {i}',
                text_type='text'
            )
            assert audio_data == b'audio_data'
        
        assert mock_polly_client.synthesize_speech.call_count == 10
    
    def test_default_parameters(self, polly_client, mock_polly_client):
        """Test that default parameters are used when not specified."""
        mock_audio_stream = BytesIO(b'audio_data')
        mock_response = {'AudioStream': mock_audio_stream}
        mock_polly_client.synthesize_speech.return_value = mock_response
        
        polly_client.synthesize_speech(text='Test text')
        
        call_args = mock_polly_client.synthesize_speech.call_args[1]
        assert call_args['VoiceId'] == PollyClient.DEFAULT_VOICE_ID
        assert call_args['TextType'] == 'ssml'
        assert call_args['OutputFormat'] == PollyClient.DEFAULT_OUTPUT_FORMAT
        assert call_args['SampleRate'] == PollyClient.DEFAULT_SAMPLE_RATE
        assert call_args['Engine'] == PollyClient.DEFAULT_ENGINE
