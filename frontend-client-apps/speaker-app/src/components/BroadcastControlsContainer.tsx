import React, { useCallback } from 'react';
import { BroadcastControls } from './BroadcastControls';
import { useSpeakerControls } from '../hooks/useSpeakerControls';
import { useSpeakerStore } from '../../../shared/store/speakerStore';
import { useNotifications } from '../../../shared/hooks/useNotifications';
import { SpeakerService } from '../services/SpeakerService';
import { NotificationService } from '../../../shared/services/NotificationService';
import type { Notification } from '../../../shared/types/controls';

interface BroadcastControlsContainerProps {
  speakerService: SpeakerService | null;
  notificationService: NotificationService | null;
}

/**
 * Container component that connects BroadcastControls to SpeakerService
 * Handles state management integration, optimistic UI updates, and real-time notifications
 * 
 * Requirements: 1.1-1.5, 3.1-3.5, 5.1-5.5, 8.1-8.4
 */
export const BroadcastControlsContainer: React.FC<BroadcastControlsContainerProps> = ({
  speakerService,
  notificationService,
}) => {
  const { sessionId } = useSpeakerStore();
  
  const {
    isPaused,
    isMuted,
    inputVolume,
    handlePauseToggle,
    handleMuteToggle,
    handleVolumeChange,
    handleEndSession,
  } = useSpeakerControls(speakerService);

  // Handle real-time notifications from listeners
  const handleNotification = useCallback((notification: Notification) => {
    console.log('Received notification:', notification);
    
    // Handle listener state changes
    if (notification.type === 'listener_joined' || notification.type === 'listener_left') {
      // Listener count updates are handled by SpeakerService via WebSocket
      // This is just for logging/debugging
    }
  }, []);

  // Subscribe to real-time notifications
  useNotifications(notificationService, sessionId, handleNotification);

  return (
    <BroadcastControls
      isPaused={isPaused}
      isMuted={isMuted}
      inputVolume={inputVolume}
      onPauseToggle={handlePauseToggle}
      onMuteToggle={handleMuteToggle}
      onVolumeChange={handleVolumeChange}
      onEndSession={handleEndSession}
    />
  );
};
