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
  
  const {
    sessionId,
    isConnected,
    isSpeakerPaused,
    isSpeakerMuted,
    bufferedDuration,
    isBuffering,
  } = useListenerStore();

  /**
   * Initialize services when session is joined
   */
  const handleSessionJoined = async (
    newSessionId: string,
    targetLanguage: string
  ) => {
    try {
      // Get WebSocket URL from environment
      const wsUrl = process.env.REACT_APP_WS_URL || 'wss://api.example.com';
      
      // Create WebSocket client (no auth required for listeners)
      const client = new WebSocketClient({
        url: wsUrl,
        heartbeatInterval: 30000,
        reconnect: true,
        reconnectDelay: 1000,
        maxReconnectAttempts: 5,
      });
      
      setWsClient(client);
      
      // Create notification service
      const notifService = new NotificationService(client);
      setNotificationService(notifService);
      
      // Create listener service
      const config: ListenerServiceConfig = {
        wsUrl,
        sessionId: newSessionId,
        targetLanguage,
      };
      
      const service = new ListenerService(config);
      setListenerService(service);
      
      // Initialize service
      await service.initialize();
      
      // Start playback
      await service.startPlayback();
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
    <div className="listener-app">
      <header className="app-header">
        <h1>Listener Playback</h1>
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
                  { code: 'en', name: 'English' },
                  { code: 'es', name: 'Spanish' },
                  { code: 'fr', name: 'French' },
                  { code: 'de', name: 'German' },
                  { code: 'it', name: 'Italian' },
                  { code: 'pt', name: 'Portuguese' },
                  { code: 'ja', name: 'Japanese' },
                  { code: 'ko', name: 'Korean' },
                  { code: 'zh', name: 'Chinese' },
                  { code: 'ar', name: 'Arabic' },
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
          text-align: center;
          color: white;
          margin-bottom: 2rem;
        }

        .app-header h1 {
          font-size: 2.5rem;
          margin: 0;
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
  );
};
