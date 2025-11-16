import React, { useCallback } from 'react';
import { PlaybackControls } from './PlaybackControls';
import { useListenerControls } from '../hooks/useListenerControls';
import { useListenerStore } from '../../../shared/store/listenerStore';
import { useNotifications } from '../../../shared/hooks/useNotifications';
import { ListenerService } from '../services/ListenerService';
import { NotificationService } from '../../../shared/services/NotificationService';
import type { Notification } from '../../../shared/types/controls';

interface PlaybackControlsContainerProps {
  listenerService: ListenerService | null;
  notificationService: NotificationService | null;
}

/**
 * Container component that connects PlaybackControls to ListenerService
 * Handles state management integration, optimistic UI updates, and real-time notifications
 * 
 * Requirements: 2.1-2.5, 4.1-4.5, 6.1-6.5, 8.1-8.4
 */
export const PlaybackControlsContainer: React.FC<PlaybackControlsContainerProps> = ({
  listenerService,
  notificationService,
}) => {
  const { sessionId, setSpeakerPaused, setSpeakerMuted } = useListenerStore();
  
  const {
    isPaused,
    isMuted,
    volume,
    handlePauseToggle,
    handleMuteToggle,
    handleVolumeChange,
  } = useListenerControls(listenerService);

  // Handle real-time notifications from speaker
  const handleNotification = useCallback((notification: Notification) => {
    console.log('Received notification:', notification);
    
    // Update speaker state based on notifications
    if (notification.type === 'broadcastPaused') {
      setSpeakerPaused(true);
    } else if (notification.type === 'broadcastResumed') {
      setSpeakerPaused(false);
    } else if (notification.type === 'broadcastMuted') {
      setSpeakerMuted(true);
    } else if (notification.type === 'broadcastUnmuted') {
      setSpeakerMuted(false);
    }
  }, [setSpeakerPaused, setSpeakerMuted]);

  // Subscribe to real-time notifications
  useNotifications(notificationService, sessionId, handleNotification);

  return (
    <PlaybackControls
      isPaused={isPaused}
      isMuted={isMuted}
      volume={volume}
      onPauseToggle={handlePauseToggle}
      onMuteToggle={handleMuteToggle}
      onVolumeChange={handleVolumeChange}
    />
  );
};
