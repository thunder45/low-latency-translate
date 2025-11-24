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
    isSpeakerPaused,
    isSpeakerMuted,
    bufferedDuration,
    isBuffering,
    isBufferOverflow,
  } = useListenerStore();

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
      
      // Fetch session metadata via HTTP API to get KVS fields
      const { SessionHttpService } = await import('../../../shared/services/SessionHttpService');
      const httpService = new SessionHttpService({
        apiBaseUrl: appConfig.httpApiUrl,
        timeout: 5000,
      });
      
      console.log('[ListenerApp] Fetching session metadata...');
      const sessionMetadata = await httpService.getSession(newSessionId);
      console.log('[ListenerApp] Session metadata retrieved:', sessionMetadata.sessionId);
      
      if (!sessionMetadata.kvsChannelArn || !sessionMetadata.kvsSignalingEndpoints) {
        throw new Error('Session metadata missing KVS configuration');
      }
      
      if (!appConfig.cognito?.identityPoolId) {
        throw new Error('Missing Cognito Identity Pool ID in configuration. Please set VITE_COGNITO_IDENTITY_POOL_ID');
      }
      
      // Create WebSocket client (for control messages only, no JWT required for listeners)
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
      
      // Create listener service with KVS config
      const serviceConfig: ListenerServiceConfig = {
        wsUrl: appConfig.websocketUrl,
        sessionId: newSessionId,
        targetLanguage,
        jwtToken: '', // Listeners don't need JWT for WebRTC (anonymous access via Identity Pool)
        // KVS WebRTC configuration
        kvsChannelArn: sessionMetadata.kvsChannelArn,
        kvsSignalingEndpoint: sessionMetadata.kvsSignalingEndpoints.WSS,
        region: appConfig.awsRegion,
        identityPoolId: appConfig.cognito.identityPoolId,
        userPoolId: appConfig.cognito.userPoolId,
      };
      
      const service = new ListenerService(serviceConfig);
      setListenerService(service);
      
      // Initialize service (WebSocket connection for control messages)
      await service.initialize();
      
      // Start WebRTC audio reception
      await service.startListening();
      
      console.log('[ListenerApp] Listener service initialized and listening');
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
