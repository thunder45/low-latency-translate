import { useCallback, useEffect, useState } from 'react';
import { useSpeakerStore } from '../../../shared/store/speakerStore';
import { SpeakerService } from '../services/SpeakerService';

/**
 * Custom hook that integrates SpeakerService with UI controls
 * Provides optimistic UI updates with rollback on failure
 */
export function useSpeakerControls(speakerService: SpeakerService | null) {
  const {
    isPaused,
    isMuted,
    inputVolume,
    setPaused,
    setMuted,
    setInputVolume,
  } = useSpeakerStore();

  const [isProcessing, setIsProcessing] = useState(false);

  /**
   * Toggle pause with optimistic update
   */
  const handlePauseToggle = useCallback(async () => {
    if (!speakerService || isProcessing) return;

    const previousState = isPaused;
    setIsProcessing(true);

    try {
      // Optimistic update
      setPaused(!previousState);

      // Call service
      await speakerService.togglePause();
    } catch (error) {
      // Rollback on failure
      console.error('Failed to toggle pause:', error);
      setPaused(previousState);
    } finally {
      setIsProcessing(false);
    }
  }, [speakerService, isPaused, isProcessing, setPaused]);

  /**
   * Toggle mute with optimistic update
   */
  const handleMuteToggle = useCallback(async () => {
    if (!speakerService || isProcessing) return;

    const previousState = isMuted;
    setIsProcessing(true);

    try {
      // Optimistic update
      setMuted(!previousState);

      // Call service
      await speakerService.toggleMute();
    } catch (error) {
      // Rollback on failure
      console.error('Failed to toggle mute:', error);
      setMuted(previousState);
    } finally {
      setIsProcessing(false);
    }
  }, [speakerService, isMuted, isProcessing, setMuted]);

  /**
   * Change volume with optimistic update
   */
  const handleVolumeChange = useCallback(async (volume: number) => {
    if (!speakerService) return;

    const previousVolume = inputVolume;

    try {
      // Optimistic update
      setInputVolume(volume);

      // Call service (debounced internally)
      await speakerService.setVolume(volume);
    } catch (error) {
      // Rollback on failure
      console.error('Failed to change volume:', error);
      setInputVolume(previousVolume);
    }
  }, [speakerService, inputVolume, setInputVolume]);

  /**
   * End session
   */
  const handleEndSession = useCallback(async () => {
    if (!speakerService) return;

    try {
      await speakerService.endSession();
    } catch (error) {
      console.error('Failed to end session:', error);
      throw error;
    }
  }, [speakerService]);

  return {
    isPaused,
    isMuted,
    inputVolume,
    isProcessing,
    handlePauseToggle,
    handleMuteToggle,
    handleVolumeChange,
    handleEndSession,
  };
}
