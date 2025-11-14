"""Unit tests for Parallel Synthesis Service."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from botocore.exceptions import ClientError
from shared.services.parallel_synthesis_service import ParallelSynthesisService


class TestParallelSynthesisService:
    """Test suite for ParallelSynthesisService."""
    
    @pytest.fixture
    def mock_polly_client(self):
        """Create mock Polly client."""
        client = Mock()
        return client
    
    @pytest.fixture
    def service(self, mock_polly_client):
        """Create ParallelSynthesisService instance."""
        return ParallelSynthesisService(polly_client=mock_polly_client, timeout=2.0)
    
    # Test voice selection
    
    def test_get_voice_for_english(self, service):
        """Test voice selection for English."""
        voice = service._get_voice_for_language("en")
        assert voice == "Joanna"
    
    def test_get_voice_for_spanish(self, service):
        """Test voice selection for Spanish."""
        voice = service._get_voice_for_language("es")
        assert voice == "Lupe"
    
    def test_get_voice_for_french(self, service):
        """Test voice selection for French."""
        voice = service._get_voice_for_language("fr")
        assert voice == "Lea"
    
    def test_get_voice_for_german(self, service):
        """Test voice selection for German."""
        voice = service._get_voice_for_language("de")
        assert voice == "Vicki"
    
    def test_get_voice_for_unsupported_language_raises_error(self, service):
        """Test voice selection raises error for unsupported language."""
        with pytest.raises(ValueError, match="Language 'xx' not supported"):
            service._get_voice_for_language("xx")
    
    # Test single synthesis
    
    @pytest.mark.asyncio
    async def test_synthesize_single_success(self, service, mock_polly_client):
        """Test successful single language synthesis."""
        # Mock Polly response
        mock_audio_stream = Mock()
        mock_audio_stream.read.return_value = b'audio_data_here'
        mock_polly_client.synthesize_speech.return_value = {
            'AudioStream': mock_audio_stream
        }
        
        result = await service._synthesize_single("en", "<speak>Hello</speak>")
        
        assert result is not None
        language, audio_bytes = result
        assert language == "en"
        assert audio_bytes == b'audio_data_here'
        
        # Verify Polly was called correctly
        mock_polly_client.synthesize_speech.assert_called_once()
        call_args = mock_polly_client.synthesize_speech.call_args[1]
        assert call_args['Text'] == "<speak>Hello</speak>"
        assert call_args['TextType'] == 'ssml'
        assert call_args['OutputFormat'] == 'pcm'
        assert call_args['VoiceId'] == 'Joanna'
        assert call_args['Engine'] == 'neural'
        assert call_args['SampleRate'] == '16000'
    
    @pytest.mark.asyncio
    async def test_synthesize_single_with_client_error(self, service, mock_polly_client):
        """Test synthesis handles AWS Polly ClientError."""
        # Mock Polly error
        error_response = {'Error': {'Code': 'InvalidSsml', 'Message': 'Invalid SSML'}}
        mock_polly_client.synthesize_speech.side_effect = ClientError(
            error_response, 'SynthesizeSpeech'
        )
        
        result = await service._synthesize_single("en", "<speak>Bad SSML")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_synthesize_single_with_timeout(self, service, mock_polly_client):
        """Test synthesis handles timeout."""
        # Mock slow Polly response
        async def slow_call(*args, **kwargs):
            await asyncio.sleep(5)  # Longer than timeout
            return {'AudioStream': Mock()}
        
        with patch.object(service, '_call_polly', side_effect=slow_call):
            result = await service._synthesize_single("en", "<speak>Hello</speak>")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_synthesize_single_with_unsupported_language(self, service):
        """Test synthesis handles unsupported language."""
        result = await service._synthesize_single("xx", "<speak>Hello</speak>")
        
        assert result is None
    
    # Test parallel synthesis
    
    @pytest.mark.asyncio
    async def test_synthesize_to_languages_with_multiple_languages(self, service, mock_polly_client):
        """Test parallel synthesis for multiple languages."""
        # Mock Polly responses
        def mock_synthesize(Text, **kwargs):
            audio_stream = Mock()
            if 'Lupe' in str(kwargs.get('VoiceId')):
                audio_stream.read.return_value = b'spanish_audio'
            elif 'Lea' in str(kwargs.get('VoiceId')):
                audio_stream.read.return_value = b'french_audio'
            else:
                audio_stream.read.return_value = b'english_audio'
            return {'AudioStream': audio_stream}
        
        mock_polly_client.synthesize_speech.side_effect = mock_synthesize
        
        ssml_texts = {
            "en": "<speak>Hello</speak>",
            "es": "<speak>Hola</speak>",
            "fr": "<speak>Bonjour</speak>"
        }
        
        results = await service.synthesize_to_languages(ssml_texts)
        
        assert len(results) == 3
        assert "en" in results
        assert "es" in results
        assert "fr" in results
        assert results["es"] == b'spanish_audio'
        assert results["fr"] == b'french_audio'
    
    @pytest.mark.asyncio
    async def test_synthesize_to_languages_with_partial_failure(self, service, mock_polly_client):
        """Test parallel synthesis continues when one language fails."""
        # Mock Polly responses - one success, one failure
        call_count = [0]
        
        def mock_synthesize(Text, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call succeeds
                audio_stream = Mock()
                audio_stream.read.return_value = b'english_audio'
                return {'AudioStream': audio_stream}
            else:
                # Second call fails
                error_response = {'Error': {'Code': 'ServiceError'}}
                raise ClientError(error_response, 'SynthesizeSpeech')
        
        mock_polly_client.synthesize_speech.side_effect = mock_synthesize
        
        ssml_texts = {
            "en": "<speak>Hello</speak>",
            "es": "<speak>Hola</speak>"
        }
        
        results = await service.synthesize_to_languages(ssml_texts)
        
        # Should have one successful result
        assert len(results) == 1
        assert "en" in results
        assert "es" not in results
    
    @pytest.mark.asyncio
    async def test_synthesize_to_languages_with_empty_input(self, service):
        """Test parallel synthesis handles empty input."""
        results = await service.synthesize_to_languages({})
        
        assert results == {}
    
    @pytest.mark.asyncio
    async def test_synthesize_to_languages_with_all_failures(self, service, mock_polly_client):
        """Test parallel synthesis when all languages fail."""
        # Mock all calls to fail
        error_response = {'Error': {'Code': 'ServiceError'}}
        mock_polly_client.synthesize_speech.side_effect = ClientError(
            error_response, 'SynthesizeSpeech'
        )
        
        ssml_texts = {
            "en": "<speak>Hello</speak>",
            "es": "<speak>Hola</speak>"
        }
        
        results = await service.synthesize_to_languages(ssml_texts)
        
        assert results == {}
    
    @pytest.mark.asyncio
    async def test_synthesize_to_languages_with_session_id(self, service, mock_polly_client):
        """Test parallel synthesis includes session ID in logs."""
        # Mock Polly response
        mock_audio_stream = Mock()
        mock_audio_stream.read.return_value = b'audio_data'
        mock_polly_client.synthesize_speech.return_value = {
            'AudioStream': mock_audio_stream
        }
        
        ssml_texts = {"en": "<speak>Hello</speak>"}
        
        results = await service.synthesize_to_languages(
            ssml_texts,
            session_id="test-session-123"
        )
        
        assert len(results) == 1
        assert "en" in results
    
    # Test call_polly method
    
    @pytest.mark.asyncio
    async def test_call_polly_executes_in_thread_pool(self, service, mock_polly_client):
        """Test _call_polly runs boto3 call in thread pool."""
        mock_audio_stream = Mock()
        mock_audio_stream.read.return_value = b'audio'
        mock_polly_client.synthesize_speech.return_value = {
            'AudioStream': mock_audio_stream
        }
        
        response = await service._call_polly("Joanna", "<speak>Test</speak>")
        
        assert 'AudioStream' in response
        mock_polly_client.synthesize_speech.assert_called_once()
    
    # Test initialization
    
    def test_init_with_custom_client(self, mock_polly_client):
        """Test initialization with custom Polly client."""
        service = ParallelSynthesisService(polly_client=mock_polly_client)
        
        assert service.polly_client == mock_polly_client
        assert service.timeout == ParallelSynthesisService.DEFAULT_TIMEOUT
    
    def test_init_with_custom_timeout(self, mock_polly_client):
        """Test initialization with custom timeout."""
        service = ParallelSynthesisService(
            polly_client=mock_polly_client,
            timeout=10.0
        )
        
        assert service.timeout == 10.0
    
    def test_init_creates_default_client_if_none(self):
        """Test initialization creates default Polly client if none provided."""
        with patch('boto3.client') as mock_boto3_client:
            service = ParallelSynthesisService()
            
            mock_boto3_client.assert_called_once_with('polly')
            assert service.polly_client is not None
    
    # Test voice mapping completeness
    
    def test_neural_voices_mapping_has_common_languages(self, service):
        """Test neural voices mapping includes common languages."""
        common_languages = ["en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh"]
        
        for lang in common_languages:
            assert lang in service.NEURAL_VOICES
            assert isinstance(service.NEURAL_VOICES[lang], str)
            assert len(service.NEURAL_VOICES[lang]) > 0
