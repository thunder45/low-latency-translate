"""
Translation Pipeline Orchestrator.

This module coordinates the entire translation and broadcasting flow, from
checking listener counts to broadcasting synthesized audio to all listeners.
"""

import logging
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EmotionDynamics:
    """Emotion and speaking dynamics detected from audio."""
    
    emotion: str
    intensity: float
    rate_wpm: int
    volume_level: str


@dataclass
class ProcessingResult:
    """Result of processing a transcript through the pipeline."""
    
    success: bool
    languages_processed: List[str]
    languages_failed: List[str]
    cache_hit_rate: float
    broadcast_success_rate: float
    total_duration_ms: float
    listener_count: int
    error_message: Optional[str] = None


class TranslationPipelineOrchestrator:
    """
    Orchestrator for the translation and broadcasting pipeline.
    
    Coordinates all stages: listener count check, language discovery,
    translation, SSML generation, synthesis, and broadcasting.
    """
    
    def __init__(
        self,
        atomic_counter,
        connections_repository,
        translation_service,
        ssml_generator,
        synthesis_service,
        broadcast_handler
    ):
        """
        Initialize orchestrator with all required services.
        
        Args:
            atomic_counter: AtomicCounter for listener count operations
            connections_repository: Repository for connection queries
            translation_service: ParallelTranslationService
            ssml_generator: SSMLGenerator
            synthesis_service: ParallelSynthesisService
            broadcast_handler: BroadcastHandler
        """
        self.atomic_counter = atomic_counter
        self.connections_repository = connections_repository
        self.translation_service = translation_service
        self.ssml_generator = ssml_generator
        self.synthesis_service = synthesis_service
        self.broadcast_handler = broadcast_handler
    
    async def process_transcript(
        self,
        session_id: str,
        source_language: str,
        transcript_text: str,
        emotion_dynamics: EmotionDynamics
    ) -> ProcessingResult:
        """
        Process transcribed text through the entire pipeline.
        
        Args:
            session_id: Session identifier
            source_language: ISO 639-1 source language code
            transcript_text: Transcribed text to translate
            emotion_dynamics: Detected emotion and speaking dynamics
            
        Returns:
            ProcessingResult with success status and metrics
        """
        start_time = time.time()
        
        logger.info(
            f"Processing transcript for session {session_id}: "
            f"'{transcript_text[:50]}...'"
        )
        
        try:
            # Step 1: Check listener count (cost optimization)
            listener_count = await self._check_listener_count(session_id)
            
            if listener_count == 0:
                logger.info(
                    f"Skipping processing for session {session_id}: "
                    f"no active listeners"
                )
                return ProcessingResult(
                    success=True,
                    languages_processed=[],
                    languages_failed=[],
                    cache_hit_rate=0.0,
                    broadcast_success_rate=0.0,
                    total_duration_ms=(time.time() - start_time) * 1000,
                    listener_count=0
                )
            
            # Step 2: Get unique target languages
            target_languages = await self._get_target_languages(session_id)
            
            if not target_languages:
                logger.warning(
                    f"No target languages found for session {session_id}"
                )
                return ProcessingResult(
                    success=True,
                    languages_processed=[],
                    languages_failed=[],
                    cache_hit_rate=0.0,
                    broadcast_success_rate=0.0,
                    total_duration_ms=(time.time() - start_time) * 1000,
                    listener_count=listener_count
                )
            
            logger.info(
                f"Processing {len(target_languages)} target languages: "
                f"{target_languages}"
            )
            
            # Step 3: Parallel translation
            translations = await self._orchestrate_translation(
                source_language, transcript_text, target_languages
            )
            
            if not translations:
                logger.error(
                    f"All translations failed for session {session_id}"
                )
                return ProcessingResult(
                    success=False,
                    languages_processed=[],
                    languages_failed=list(target_languages),
                    cache_hit_rate=0.0,
                    broadcast_success_rate=0.0,
                    total_duration_ms=(time.time() - start_time) * 1000,
                    listener_count=listener_count,
                    error_message="All translations failed"
                )
            
            # Step 4: Generate SSML for all translations
            ssml_by_language = self._generate_ssml_for_all(
                translations, emotion_dynamics
            )
            
            # Step 5: Parallel synthesis
            audio_by_language = await self._orchestrate_synthesis(
                ssml_by_language, list(translations.keys())
            )
            
            if not audio_by_language:
                logger.error(
                    f"All synthesis operations failed for session {session_id}"
                )
                return ProcessingResult(
                    success=False,
                    languages_processed=[],
                    languages_failed=list(target_languages),
                    cache_hit_rate=0.0,
                    broadcast_success_rate=0.0,
                    total_duration_ms=(time.time() - start_time) * 1000,
                    listener_count=listener_count,
                    error_message="All synthesis operations failed"
                )
            
            # Step 6: Broadcast to listeners per language
            broadcast_results = await self._orchestrate_broadcast(
                session_id, audio_by_language
            )
            
            # Calculate metrics
            languages_processed = list(audio_by_language.keys())
            languages_failed = list(
                set(target_languages) - set(languages_processed)
            )
            
            total_broadcasts = sum(
                r.success_count + r.failure_count for r in broadcast_results
            )
            successful_broadcasts = sum(
                r.success_count for r in broadcast_results
            )
            broadcast_success_rate = (
                successful_broadcasts / total_broadcasts
                if total_broadcasts > 0 else 0.0
            )
            
            # Cache hit rate from translation service
            cache_hit_rate = getattr(
                self.translation_service, 'last_cache_hit_rate', 0.0
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            logger.info(
                f"Processing complete for session {session_id}: "
                f"{len(languages_processed)} languages processed, "
                f"{len(languages_failed)} failed, "
                f"broadcast success rate: {broadcast_success_rate:.2%}, "
                f"duration: {duration_ms:.2f}ms"
            )
            
            return ProcessingResult(
                success=True,
                languages_processed=languages_processed,
                languages_failed=languages_failed,
                cache_hit_rate=cache_hit_rate,
                broadcast_success_rate=broadcast_success_rate,
                total_duration_ms=duration_ms,
                listener_count=listener_count
            )
            
        except Exception as e:
            logger.error(
                f"Unexpected error processing transcript for session {session_id}: {e}",
                exc_info=True
            )
            return ProcessingResult(
                success=False,
                languages_processed=[],
                languages_failed=[],
                cache_hit_rate=0.0,
                broadcast_success_rate=0.0,
                total_duration_ms=(time.time() - start_time) * 1000,
                listener_count=0,
                error_message=str(e)
            )
    
    async def _check_listener_count(self, session_id: str) -> int:
        """
        Check listener count for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Current listener count (0 if session not found)
        """
        try:
            count = await self.atomic_counter.get_listener_count(session_id)
            return count if count is not None else 0
        except Exception as e:
            logger.error(
                f"Failed to check listener count for session {session_id}: {e}",
                exc_info=True
            )
            return 0
    
    async def _get_target_languages(self, session_id: str) -> Set[str]:
        """
        Get unique target languages for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Set of unique target language codes
        """
        try:
            languages = await self.connections_repository.get_unique_target_languages(
                session_id
            )
            return set(languages)
        except Exception as e:
            logger.error(
                f"Failed to get target languages for session {session_id}: {e}",
                exc_info=True
            )
            return set()
    
    async def _orchestrate_translation(
        self,
        source_language: str,
        text: str,
        target_languages: Set[str]
    ) -> Dict[str, str]:
        """
        Orchestrate parallel translation to all target languages.
        
        Args:
            source_language: Source language code
            text: Text to translate
            target_languages: Set of target language codes
            
        Returns:
            Dictionary mapping language code to translated text
        """
        try:
            translations = await self.translation_service.translate_to_languages(
                source_lang=source_language,
                text=text,
                target_languages=list(target_languages)
            )
            return translations
        except Exception as e:
            logger.error(
                f"Translation orchestration failed: {e}",
                exc_info=True
            )
            return {}
    
    def _generate_ssml_for_all(
        self,
        translations: Dict[str, str],
        emotion_dynamics: EmotionDynamics
    ) -> Dict[str, str]:
        """
        Generate SSML for all translated texts.
        
        Args:
            translations: Dictionary of language to translated text
            emotion_dynamics: Emotion and speaking dynamics
            
        Returns:
            Dictionary mapping language code to SSML text
        """
        ssml_by_language = {}
        
        for language, text in translations.items():
            try:
                ssml = self.ssml_generator.generate_ssml(text, emotion_dynamics)
                ssml_by_language[language] = ssml
            except Exception as e:
                logger.error(
                    f"SSML generation failed for language {language}: {e}",
                    exc_info=True
                )
        
        return ssml_by_language
    
    async def _orchestrate_synthesis(
        self,
        ssml_by_language: Dict[str, str],
        target_languages: List[str]
    ) -> Dict[str, bytes]:
        """
        Orchestrate parallel synthesis for all languages.
        
        Args:
            ssml_by_language: Dictionary of language to SSML text
            target_languages: List of target language codes
            
        Returns:
            Dictionary mapping language code to audio bytes
        """
        try:
            audio_by_language = await self.synthesis_service.synthesize_to_languages(
                ssml_by_language=ssml_by_language,
                target_languages=target_languages
            )
            return audio_by_language
        except Exception as e:
            logger.error(
                f"Synthesis orchestration failed: {e}",
                exc_info=True
            )
            return {}
    
    async def _orchestrate_broadcast(
        self,
        session_id: str,
        audio_by_language: Dict[str, bytes]
    ) -> List:
        """
        Orchestrate broadcasting to all listeners per language.
        
        Args:
            session_id: Session identifier
            audio_by_language: Dictionary of language to audio bytes
            
        Returns:
            List of BroadcastResult objects
        """
        broadcast_results = []
        
        for language, audio_data in audio_by_language.items():
            try:
                result = await self.broadcast_handler.broadcast_to_language(
                    session_id=session_id,
                    target_language=language,
                    audio_data=audio_data
                )
                broadcast_results.append(result)
            except Exception as e:
                logger.error(
                    f"Broadcast failed for language {language}: {e}",
                    exc_info=True
                )
        
        return broadcast_results
