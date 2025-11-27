import React, { useState, useEffect } from 'react';
import { ListenerService, ListenerServiceConfig } from '../services/ListenerService';
import { NotificationService } from '../../../shared/services/NotificationService';
import { WebSocketClient } from '../../../shared/websocket/WebSocketClient';
import { PlaybackControlsContainer } from './PlaybackControlsContainer';
import { SessionJoiner } from './SessionJoiner';
import { SpeakerStatus } from './SpeakerStatus';
import { BufferIndicator } from './BufferIndicator';
import { LanguageSelector } from './LanguageSelector';
import { useListenerStore } from '../../../shared/store/listenerStore';
import { AuthGuard } from './AuthGuard';

/**
 * Main listener application component
 * Integrates all components with services and state management
 * 
 * Requirements: 2.1-2.5, 4.1-4.5, 6.1-6.5, 7.1-7.5, 8.1-8.4
 */
export const ListenerApp: React.FC = () => {
  const [listenerService, setListenerService] = useState<ListenerService | null>(null);
  const [notificationService, setNotificationService] = useState<NotificationService | null>(null);
  const [wsClient, setWsClient] = useState<WebSocketClient | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  
  const {
    sessionId,
    isSpeakerPaused,
    isSpeakerMuted,
    bufferedDuration,
    isBuffering,
    isBufferOverflow,
  } = useListenerStore();

  /**
   * Load user info on mount
   */
  useEffect(() => {
    const loadUserInfo = async () => {
      try {
        const { TokenStorage } = await import('../../../shared/services/TokenStorage');
        const { getConfig } = await import('../../../shared/utils/config');
        
        const config = getConfig();
        const tokenStorage = TokenStorage.getInstance();
        await tokenStorage.initialize(config.encryptionKey);
        const tokens = await tokenStorage.getTokens();
        
        if (tokens && tokens.idToken) {
          // Decode JWT to get user info (simple base64 decode of payload)
          const payload = tokens.idToken.split('.')[1];
          const decoded = JSON.parse(atob(payload));
          if (decoded.email) {
            setUserEmail(decoded.email);
          }
        }
      } catch (error) {
        console.error('Failed to load user info:', error);
      }
    };

    loadUserInfo();
  }, []);

  /**
   * Handle logout
   */
  const handleLogout = async () => {
    try {
      // Cleanup services first
      if (listenerService) {
        listenerService.cleanup();
      }
      if (wsClient) {
        wsClient.disconnect();
      }

      // Clear tokens
      const { TokenStorage } = await import('../../../shared/services/TokenStorage');
      const { getConfig } = await import('../../../shared/utils/config');
      
      const config = getConfig();
      const tokenStorage = TokenStorage.getInstance();
      await tokenStorage.initialize(config.encryptionKey);
      await tokenStorage.clearTokens();
      
      // Reload page to show login form
      window.location.reload();
    } catch (error) {
      console.error('Logout failed:', error);
      // Force reload even if logout fails
      window.location.reload();
    }
  };

  /**
   * Initialize services when session is joined
   */
  const handleSessionJoined = async (
    newSessionId: string,
    targetLanguage: string
  ) => {
    try {
      // Get configuration from environment
      const { getConfig } = await import('../../../shared/utils/config');
      const appConfig = getConfig();
      
      // Get JWT token from storage for authenticated KVS access
      const { TokenStorage } = await import('../../../shared/services/TokenStorage');
      const tokenStorage = TokenStorage.getInstance();
      await tokenStorage.initialize(appConfig.encryptionKey);
      const tokens = await tokenStorage.getTokens();
      
      if (!tokens || !tokens.idToken) {
        throw new Error('Please log in to join a session');
      }
      
      const jwtToken = tokens.idToken;
      
      // Create WebSocket client (for control messages)
      const client = new WebSocketClient({
        url: appConfig.websocketUrl,
        heartbeatInterval: 30000,
        reconnect: true,
        reconnectDelay: 1000,
        maxReconnectAttempts: 5,
      });
      
      setWsClient(client);
      
      // Create notification service
      const notifService = new NotificationService(client);
      setNotificationService(notifService);
      
      // Create listener service with S3 playback configuration
      const serviceConfig: ListenerServiceConfig = {
        wsUrl: appConfig.websocketUrl,
        sessionId: newSessionId,
        targetLanguage,
        jwtToken, // JWT token (optional for listeners)
      };
      
      const service = new ListenerService(serviceConfig);
      setListenerService(service);
      
      // Initialize service (WebSocket connection)
      await service.initialize();
      
      // Start S3 audio playback
      await service.startListening();
      
      console.log('[ListenerApp] Listener service initialized and ready for audio');
    } catch (error) {
      console.error('Failed to initialize listener service:', error);
    }
  };

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      if (listenerService) {
        listenerService.cleanup();
      }
      if (wsClient) {
        wsClient.disconnect();
      }
    };
  }, [listenerService, wsClient]);

  return (
    <AuthGuard>
      <div className="listener-app">
        <header className="app-header">
          <div className="header-content">
            <h1>Listener Playback</h1>
            <div className="user-section">
              {userEmail && (
                <span className="user-email">{userEmail}</span>
              )}
              <button
                onClick={handleLogout}
                className="logout-button"
                title="Logout"
              >
                Logout
              </button>
            </div>
          </div>
        </header>

      <main className="app-main">
        {!sessionId ? (
          <SessionJoiner
            onSessionJoined={handleSessionJoined}
            onSendMessage={(msg) => wsClient?.send(msg)}
          />
        ) : (
          <>
            <div className="status-section">
              <SpeakerStatus
                isPaused={isSpeakerPaused}
                isMuted={isSpeakerMuted}
              />
              
              <BufferIndicator
                bufferedDuration={bufferedDuration}
                isBuffering={isBuffering}
                bufferOverflow={isBufferOverflow}
              />
            </div>
            
            <div className="controls-section">
              <PlaybackControlsContainer
                listenerService={listenerService}
                notificationService={notificationService}
              />
            </div>
            
            <div className="language-section">
              <LanguageSelector
                currentLanguage={useListenerStore.getState().targetLanguage || 'en'}
                availableLanguages={[
                  'en',
                  'es',
                  'fr',
                  'de',
                  'it',
                  'pt',
                  'ja',
                  'ko',
                  'zh',
                  'ar',
                ]}
                onLanguageChange={async (lang) => {
                  if (listenerService) {
                    await listenerService.switchLanguage(lang);
                  }
                }}
              />
            </div>
          </>
        )}
      </main>

      <style>{`
        .listener-app {
          min-height: 100vh;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          padding: 2rem;
        }

        .app-header {
          color: white;
          margin-bottom: 2rem;
        }

        .header-content {
          max-width: 800px;
          margin: 0 auto;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .app-header h1 {
          font-size: 2.5rem;
          margin: 0;
        }

        .user-section {
          display: flex;
          align-items: center;
          gap: 1rem;
        }

        .user-email {
          font-size: 0.9rem;
          opacity: 0.9;
        }

        .logout-button {
          padding: 0.5rem 1rem;
          font-size: 0.9rem;
          font-weight: 500;
          color: white;
          background-color: rgba(255, 255, 255, 0.2);
          border: 1px solid rgba(255, 255, 255, 0.3);
          border-radius: 4px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .logout-button:hover {
          background-color: rgba(255, 255, 255, 0.3);
          border-color: rgba(255, 255, 255, 0.5);
        }

        .logout-button:active {
          transform: scale(0.98);
        }

        .app-main {
          max-width: 800px;
          margin: 0 auto;
        }

        .status-section {
          display: flex;
          gap: 1rem;
          margin-bottom: 2rem;
        }

        .controls-section {
          margin-bottom: 2rem;
        }

        .language-section {
          margin-bottom: 2rem;
        }
      `}</style>
      </div>
    </AuthGuard>
  );
};
