import { useState, useEffect, useCallback } from 'react';
import { WebSocketClient } from '../websocket/WebSocketClient';
import { RetryHandler } from '../utils/RetryHandler';

/**
 * Configuration for connection refresh
 */
export interface ConnectionRefreshConfig {
  warningTime: number; // Time in minutes to show warning (default: 100)
  refreshTime: number; // Time in minutes to initiate refresh (default: 115)
  maxRetries: number; // Maximum retry attempts (default: 5)
}

/**
 * Connection refresh state
 */
export interface ConnectionRefreshState {
  showWarning: boolean;
  timeUntilRefresh: number; // Minutes until refresh
  isRefreshing: boolean;
  refreshFailed: boolean;
}

/**
 * Hook for managing connection refresh before 2-hour timeout
 * Handles automatic refresh at 115 minutes with warning at 100 minutes
 */
export function useConnectionRefresh(
  wsClient: WebSocketClient | null,
  sessionStartTime: number | null,
  config: Partial<ConnectionRefreshConfig> = {}
): ConnectionRefreshState {
  const defaultConfig: ConnectionRefreshConfig = {
    warningTime: 100,
    refreshTime: 115,
    maxRetries: 5,
  };

  const finalConfig = { ...defaultConfig, ...config };

  const [state, setState] = useState<ConnectionRefreshState>({
    showWarning: false,
    timeUntilRefresh: 0,
    isRefreshing: false,
    refreshFailed: false,
  });

  const [retryHandler] = useState(() => new RetryHandler({
    maxAttempts: finalConfig.maxRetries,
    initialDelay: 1000,
    maxDelay: 4000,
    backoffMultiplier: 2,
  }));

  /**
   * Perform connection refresh
   */
  const performRefresh = useCallback(async () => {
    if (!wsClient) return;

    setState(prev => ({ ...prev, isRefreshing: true }));

    try {
      await retryHandler.execute(async () => {
        // Send refresh connection request
        wsClient.send({
          action: 'refreshConnection',
        });

        // Wait for confirmation
        return new Promise<void>((resolve, reject) => {
          const timeout = setTimeout(() => {
            reject(new Error('Refresh timeout'));
          }, 10000);

          wsClient.on('connectionRefreshComplete', () => {
            clearTimeout(timeout);
            resolve();
          });
        });
      });

      setState(prev => ({
        ...prev,
        isRefreshing: false,
        showWarning: false,
        refreshFailed: false,
      }));
    } catch (error) {
      console.error('Connection refresh failed:', error);
      setState(prev => ({
        ...prev,
        isRefreshing: false,
        refreshFailed: true,
      }));
    }
  }, [wsClient, retryHandler]);

  /**
   * Monitor session duration and trigger refresh
   */
  useEffect(() => {
    if (!sessionStartTime || !wsClient) return;

    const checkInterval = setInterval(() => {
      const elapsedMinutes = (Date.now() - sessionStartTime) / (1000 * 60);

      // Show warning at configured time
      if (elapsedMinutes >= finalConfig.warningTime && elapsedMinutes < finalConfig.refreshTime) {
        const timeUntilRefresh = finalConfig.refreshTime - elapsedMinutes;
        setState(prev => ({
          ...prev,
          showWarning: true,
          timeUntilRefresh: Math.ceil(timeUntilRefresh),
        }));
      }

      // Initiate refresh at configured time
      if (elapsedMinutes >= finalConfig.refreshTime && !state.isRefreshing && !state.refreshFailed) {
        performRefresh();
      }
    }, 10000); // Check every 10 seconds

    return () => clearInterval(checkInterval);
  }, [sessionStartTime, wsClient, finalConfig, state.isRefreshing, state.refreshFailed, performRefresh]);

  /**
   * Listen for server-initiated refresh requests
   */
  useEffect(() => {
    if (!wsClient) return;

    const handleRefreshRequired = (message: any) => {
      setState(prev => ({
        ...prev,
        showWarning: true,
        timeUntilRefresh: 20, // Server sends this 20 minutes before timeout
      }));
    };

    wsClient.on('connectionRefreshRequired', handleRefreshRequired);

    return () => {
      wsClient.off('connectionRefreshRequired');
    };
  }, [wsClient]);

  return state;
}
