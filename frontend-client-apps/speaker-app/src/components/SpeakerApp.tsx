import React, { useState, useEffect } from 'react';
import { SpeakerService, SpeakerServiceConfig } from '../services/SpeakerService';
import { NotificationService } from '../../../shared/services/NotificationService';
import { SessionCreator, SessionConfig } from './SessionCreator';
import { SessionDisplay } from './SessionDisplay';
import { AudioVisualizer } from './AudioVisualizer';
import { BroadcastControlsContainer } from './BroadcastControlsContainer';
import { useSpeakerStore } from '../../../shared/store/speakerStore';
import { SessionCreationOrchestrator, ERROR_MESSAGES } from '../../../shared/utils/SessionCreationOrchestrator';
import { AuthGuard } from './AuthGuard';

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
  const [userEmail, setUserEmail] = useState<string | null>(null);
  
  const { sessionId, isConnected, listenerCount, languageDistribution } = useSpeakerStore();

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
    console.log('Logging out...');
    try {
      // Cleanup services first
      if (speakerService) {
        speakerService.cleanup();
      }
      if (orchestrator) {
        orchestrator.abort();
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
      // Get JWT token from storage
      const { TokenStorage } = await import('../../../shared/services/TokenStorage');
      const { getConfig } = await import('../../../shared/utils/config');
      
      const appConfig = getConfig();
      const tokenStorage = TokenStorage.getInstance();
      await tokenStorage.initialize(appConfig.encryptionKey);
      const tokens = await tokenStorage.getTokens();
      
      if (!tokens || !tokens.idToken) {
        setCreationError('Please log in to create a session');
        setIsCreatingSession(false);
        return;
      }
      
      const jwtToken = tokens.idToken;

      // Create auth service for token refresh
      const { CognitoAuthService } = await import('../../../shared/services/CognitoAuthService');
      const authService = new CognitoAuthService({
        userPoolId: appConfig.cognito!.userPoolId,
        clientId: appConfig.cognito!.clientId,
        region: appConfig.awsRegion,
      });
      
      // Create orchestrator with real JWT token
      const newOrchestrator = new SessionCreationOrchestrator({
        wsUrl: appConfig.websocketUrl,
        httpApiUrl: appConfig.httpApiUrl,
        jwtToken, // Real JWT token from Cognito
        sourceLanguage: config.sourceLanguage,
        qualityTier: config.qualityTier,
        timeout: 5000,
        retryAttempts: 3,
        authService: authService, // Pass auth service for token refresh
        tokenStorage: tokenStorage, // Pass token storage for token refresh
      });
      
      setOrchestrator(newOrchestrator);
      
      // Create session
      const result = await newOrchestrator.createSession();
      
      if (!result.success) {
        setCreationError(result.error || ERROR_MESSAGES.UNKNOWN_ERROR);
        setIsCreatingSession(false);
        return;
      }
      
      // Session created successfully - store session data first
      useSpeakerStore.getState().setSession(
        result.sessionId!,
        config.sourceLanguage,
        config.qualityTier
      );
      
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
      
      // Small delay to ensure WebSocket is fully ready
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // Start broadcasting
      await service.startBroadcast();
      
      setIsCreatingSession(false);
    } catch (error) {
      console.error('Failed to create session:', error);
      
      setCreationError(
        error instanceof Error ? error.message : ERROR_MESSAGES.UNKNOWN_ERROR
      );
      
      setIsCreatingSession(false);
      
      // DON'T abort orchestrator here - it would disconnect the WebSocket
      // The WebSocket is now owned by SpeakerService
      // Just cleanup the service if it was created
      if (speakerService) {
        speakerService.cleanup();
        setSpeakerService(null);
      }
    }
  };

  /**
   * Cleanup on unmount ONLY
   */
  useEffect(() => {
    console.debug('SpeakerApp mounted');
    return () => {
      console.debug('SpeakerApp unmounting - cleaning up resources');
      // Abort any ongoing session creation
      if (orchestrator) {
        orchestrator.abort();
      }
      
      // Cleanup services
      if (speakerService) {
        speakerService.cleanup();
      }
    };
  }, []); // Empty deps - only run on mount/unmount, not when services change!

  return (
    <AuthGuard>
      <div className="speaker-app">
        <header className="app-header">
          <div className="header-content">
            <h1>Speaker Broadcast</h1>
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

        .controls-section {
          margin-bottom: 2rem;
        }

        .visualizer-section {
          margin-bottom: 2rem;
        }
      `}</style>
      </div>
    </AuthGuard>
  );
};
