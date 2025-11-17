import React, { useState, useEffect } from 'react';
import { SpeakerService, SpeakerServiceConfig } from '../services/SpeakerService';
import { NotificationService } from '../../../shared/services/NotificationService';
import { SessionCreator, SessionConfig } from './SessionCreator';
import { SessionDisplay } from './SessionDisplay';
import { AudioVisualizer } from './AudioVisualizer';
import { BroadcastControlsContainer } from './BroadcastControlsContainer';
import { useSpeakerStore } from '../../../shared/store/speakerStore';
import { SessionCreationOrchestrator, ERROR_MESSAGES } from '../../../shared/utils/SessionCreationOrchestrator';

/**
 * Main speaker application component
 * Integrates all components with services and state management
 * 
 * Requirements: 1.1-1.5, 3.1-3.5, 5.1-5.5, 8.1-8.4
 */
export const SpeakerApp: React.FC = () => {
  const [speakerService, setSpeakerService] = useState<SpeakerService | null>(null);
  const [notificationService, setNotificationService] = useState<NotificationService | null>(null);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [creationError, setCreationError] = useState<string | null>(null);
  const [orchestrator, setOrchestrator] = useState<SessionCreationOrchestrator | null>(null);
  
  const { sessionId, isConnected, listenerCount, languageDistribution } = useSpeakerStore();

  /**
   * Handle session creation with orchestrator
   */
  const handleCreateSession = async (config: SessionConfig): Promise<void> => {
    // Prevent multiple simultaneous creation attempts
    if (isCreatingSession) {
      return;
    }

    setIsCreatingSession(true);
    setCreationError(null);

    try {
      // Get configuration from environment
      const { getConfig } = await import('../../../shared/utils/config');
      const appConfig = getConfig();
      
      // Get JWT token from auth service (placeholder)
      const jwtToken = 'placeholder-jwt-token'; // TODO: Get from AuthService
      
      // Create orchestrator
      const newOrchestrator = new SessionCreationOrchestrator({
        wsUrl: appConfig.websocketUrl,
        jwtToken,
        sourceLanguage: config.sourceLanguage,
        qualityTier: config.qualityTier,
        timeout: 5000,
        retryAttempts: 3,
      });
      
      setOrchestrator(newOrchestrator);
      
      // Create session
      const result = await newOrchestrator.createSession();
      
      if (!result.success) {
        setCreationError(result.error || ERROR_MESSAGES.UNKNOWN_ERROR);
        setIsCreatingSession(false);
        return;
      }
      
      // Session created successfully
      
      // Create notification service
      const notifService = new NotificationService(result.wsClient!);
      setNotificationService(notifService);
      
      // Create speaker service with connected WebSocket client
      const serviceConfig: SpeakerServiceConfig = {
        wsUrl: appConfig.websocketUrl,
        jwtToken,
        sourceLanguage: config.sourceLanguage,
        qualityTier: config.qualityTier,
      };
      
      const service = new SpeakerService(serviceConfig, result.wsClient!);
      setSpeakerService(service);
      
      // Initialize service
      await service.initialize();
      
      // Start broadcasting
      await service.startBroadcast();
      
      setIsCreatingSession(false);
    } catch (error) {
      console.error('Failed to create session:', error);
      setCreationError(
        error instanceof Error ? error.message : ERROR_MESSAGES.UNKNOWN_ERROR
      );
      setIsCreatingSession(false);
      
      // Cleanup orchestrator
      if (orchestrator) {
        orchestrator.abort();
      }
    }
  };

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      // Abort any ongoing session creation
      if (orchestrator) {
        orchestrator.abort();
      }
      
      // Cleanup services
      if (speakerService) {
        speakerService.cleanup();
      }
    };
  }, [speakerService, orchestrator]);

  return (
    <div className="speaker-app">
      <header className="app-header">
        <h1>Speaker Broadcast</h1>
      </header>

      <main className="app-main">
        {!sessionId ? (
          <SessionCreator
            onCreateSession={handleCreateSession}
            isCreating={isCreatingSession}
            error={creationError}
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
