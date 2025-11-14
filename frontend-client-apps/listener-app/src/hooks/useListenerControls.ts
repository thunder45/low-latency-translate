import { useCallback, useEffect, useState } from 'react';
import { useListenerStore } from '../../../shared/store/listenerStore';
import { ListenerService } from '../services/ListenerService';

/**
 * Custom hook that integrates ListenerService with UI controls
 * Provides optimistic UI updates with rollback on failure
 */
export function useListenerControls(listenerService: ListenerService | null) {
  const {
    isPaused,
    isMuted,
    playbackVolume: volume,
    targetLanguage: currentLanguage,
    setPaused,
    setMuted,
    setPlaybackVolume: setVolume,
    setTargetLanguage: setCurrentLanguage,
  } = useListenerStore();

  const [isProcessing, setIsProcessing] = useState(false);

  /**
   * Toggle pause with optimistic update
   */
  const handlePauseToggle = useCallback(async () => {
    if (!listenerService || isProcessing) return;

    const previousState = isPaused;
    setIsProcessing(true);

    try {
      // Optimistic update
      setPaused(!previousState);

      // Call service
      await listenerService.togglePause();
    } catch (error) {
      // Rollback on failure
      console.error('Failed to toggle pause:', error);
      setPaused(previousState);
    } finally {
      setIsProcessing(false);
    }
  }, [listenerService, isPaused, isProcessing, setPaused]);

  /**
   * Toggle mute with optimistic update
   */
  const handleMuteToggle = useCallback(async () => {
    if (!listenerService || isProcessing) return;

    const previousState = isMuted;
    setIsProcessing(true);

    try {
      // Optimistic update
      setMuted(!previousState);

      // Call service
      await listenerService.toggleMute();
    } catch (error) {
      // Rollback on failure
      console.error('Failed to toggle mute:', error);
      setMuted(previousState);
    } finally {
      setIsProcessing(false);
    }
  }, [listenerService, isMuted, isProcessing, setMuted]);

  /**
   * Change volume with optimistic update
   */
  const handleVolumeChange = useCallback(async (newVolume: number) => {
    if (!listenerService) return;

    const previousVolume = volume;

    try {
      // Optimistic update
      setVolume(newVolume);

      // Call service (debounced internally)
      await listenerService.setVolume(newVolume);
    } catch (error) {
      // Rollback on failure
      console.error('Failed to change volume:', error);
      setVolume(previousVolume);
    }
  }, [listenerService, volume, setVolume]);

  /**
   * Change language with optimistic update
   */
  const handleLanguageChange = useCallback(async (languageCode: string) => {
    if (!listenerService || isProcessing) return;

    const previousLanguage = currentLanguage;
    setIsProcessing(true);

    try {
      // Optimistic update
      setCurrentLanguage(languageCode);

      // Call service
      await listenerService.switchLanguage(languageCode);
    } catch (error) {
      // Rollback on failure
      console.error('Failed to change language:', error);
      setCurrentLanguage(previousLanguage);
    } finally {
      setIsProcessing(false);
    }
  }, [listenerService, currentLanguage, isProcessing, setCurrentLanguage]);

  return {
    isPaused,
    isMuted,
    volume,
    currentLanguage,
    isProcessing,
    handlePauseToggle,
    handleMuteToggle,
    handleVolumeChange,
    handleLanguageChange,
  };
}
