import { useEffect, useCallback } from 'react';
import { NotificationService } from '../services/NotificationService';
import type { Notification } from '../types/controls';

/**
 * Custom hook for subscribing to real-time notifications
 * Integrates NotificationService with UI components
 * 
 * Requirements: 1.5, 3.4, 8.2
 */
export function useNotifications(
  notificationService: NotificationService | null,
  sessionId: string | null,
  onNotification: (notification: Notification) => void
) {
  const handleNotification = useCallback(
    (notification: Notification) => {
      onNotification(notification);
    },
    [onNotification]
  );

  useEffect(() => {
    if (!notificationService || !sessionId) {
      return;
    }

    // Subscribe to session notifications
    const unsubscribe = notificationService.subscribeToSession(
      sessionId,
      handleNotification
    );

    // Cleanup subscription on unmount
    return () => {
      unsubscribe();
    };
  }, [notificationService, sessionId, handleNotification]);
}
