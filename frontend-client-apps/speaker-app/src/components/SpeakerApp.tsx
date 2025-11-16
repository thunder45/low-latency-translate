import React, { useState, useEffect } from 'react';
import { SpeakerService, SpeakerServiceConfig } from '../services/SpeakerService';
import { NotificationService } from '../../../shared/services/NotificationService';
import { WebSocketClient } from '../../../shared/websocket/WebSocketClient';
import { BroadcastControlsContainer } from './BroadcastControlsContainer';
import { SessionCreator } from './SessionCreator';
import { SessionDisplay } from './SessionDisplay';
import { AudioVisualizer } from './AudioVisualizer';
import { useSpeakerStore } from '../../../shared/store/speakerStore';

/**
 * Main speaker application component
 * Integrates all components with services and state management
 * 
 * Requirements: 1.1-1.5, 3.1-3.5, 5.1-5.5, 8.1-8.4
 */
export const SpeakerApp: React.FC = () => {
  const [speakerService, setSpeakerService] = useState<SpeakerService | null>(null);
  const [notificationService, setNotificationService] = useState<NotificationService | null>(null);
  const [wsClient, setWsClient] = useState<WebSocketClient | null>(null);
  
  const { sessionId, isConnected, listenerCount, languageDistribution } = useSpeakerStore();

  /**
   * Initialize services when session is created
   */
  const handleSessionCreated = async (
    _sessionId: string,
    sourceLanguage: string,
    qualityTier: 'standard' | 'premium'
  ) => {
    try {
      // Get configuration from environment
      const { getConfig } = await import('../../../shared/utils/config');
      const config = getConfig();
      
      // Get JWT token from auth service (placeholder)
      const jwtToken = 'placeholder-jwt-token'; // TODO: Get from AuthService
      
      // Create WebSocket client
      const client = new WebSocketClient({
        url: config.websocketUrl,
        token: jwtToken,
        heartbeatInterval: 30000,
        reconnect: true,
        reconnectDelay: 1000,
        maxReconnectAttempts: 5,
      });
      
      setWsClient(client);
      
      // Create notification service
      const notifService = new NotificationService(client);
      setNotificationService(notifService);
      
      // Create speaker service
      const serviceConfig: SpeakerServiceConfig = {
        wsUrl: config.websocketUrl,
        jwtToken,
        sourceLanguage,
        qualityTier,
      };
      
      const service = new SpeakerService(serviceConfig);
      setSpeakerService(service);
      
      // Initialize service
      await service.initialize();
      
      // Start broadcasting
      await service.startBroadcast();
    } catch (error) {
      console.error('Failed to initialize speaker service:', error);
    }
  };

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      if (speakerService) {
        speakerService.cleanup();
      }
      if (wsClient) {
        wsClient.disconnect();
      }
    };
  }, [speakerService, wsClient]);

  return (
    <div className="speaker-app">
      <header className="app-header">
        <h1>Speaker Broadcast</h1>
      </header>

      <main className="app-main">
        {!sessionId ? (
          <SessionCreator
            jwtToken="placeholder-jwt-token"
            onSessionCreated={handleSessionCreated}
            onSendMessage={(msg) => wsClient?.send(msg)}
          />
        ) : (
          <>
            <SessionDisplay 
              sessionId={sessionId} 
              listenerCount={listenerCount}
              languageDistribution={languageDistribution}
            />
            
            <div className="controls-section">
              <BroadcastControlsContainer
                speakerService={speakerService}
                notificationService={notificationService}
              />
            </div>
            
            <div className="visualizer-section">
              <AudioVisualizer
                isTransmitting={isConnected}
                inputLevel={speakerService?.getInputLevel() || 0}
              />
            </div>
          </>
        )}
      </main>

      <style>{`
        .speaker-app {
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

        .controls-section {
          margin-bottom: 2rem;
        }

        .visualizer-section {
          margin-bottom: 2rem;
        }
      `}</style>
    </div>
  );
};
