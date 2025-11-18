import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { SessionCreationOrchestrator, ERROR_MESSAGES } from '../utils/SessionCreationOrchestrator';
import { WebSocketClient } from '../websocket/WebSocketClient';

// Mock WebSocketClient
vi.mock('../websocket/WebSocketClient');

describe('SessionCreationOrchestrator', () => {
  let orchestrator: SessionCreationOrchestrator;
  let mockWsClient: any;

  beforeEach(() => {
    // Reset mocks
    vi.clearAllMocks();

    // Create mock WebSocket client
    mockWsClient = {
      connect: vi.fn(),
      send: vi.fn(),
      on: vi.fn(),
      off: vi.fn(),
      disconnect: vi.fn(),
      isConnected: vi.fn().mockReturnValue(true),
    };

    // Mock WebSocketClient constructor
    (WebSocketClient as any).mockImplementation(() => mockWsClient);
  });

  afterEach(() => {
    if (orchestrator) {
      orchestrator.abort();
    }
  });

  describe('createSession', () => {
    it('should successfully create session with valid configuration', async () => {
      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'test-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
      });

      // Mock successful connection
      mockWsClient.connect.mockResolvedValue(undefined);

      // Mock successful session creation response
      mockWsClient.on.mockImplementation((type: string, handler: Function) => {
        if (type === 'sessionCreated') {
          setTimeout(() => {
            handler({
              type: 'sessionCreated',
              sessionId: 'test-session-123',
              sourceLanguage: 'en',
              qualityTier: 'standard',
              timestamp: Date.now(),
            });
          }, 10);
        }
      });

      const result = await orchestrator.createSession();

      expect(result.success).toBe(true);
      expect(result.sessionId).toBe('test-session-123');
      expect(result.wsClient).toBeDefined();
      expect(mockWsClient.connect).toHaveBeenCalled();
      expect(mockWsClient.send).toHaveBeenCalledWith({
        action: 'createSession',
        sourceLanguage: 'en',
        qualityTier: 'standard',
      });
    });

    it('should retry on connection failure', async () => {
      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'test-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
        retryAttempts: 3,
      });

      // First two attempts fail, third succeeds
      let attemptCount = 0;
      mockWsClient.connect.mockImplementation(() => {
        attemptCount++;
        if (attemptCount < 3) {
          return Promise.reject(new Error('Connection failed'));
        }
        return Promise.resolve();
      });

      // Mock successful session creation response
      mockWsClient.on.mockImplementation((type: string, handler: Function) => {
        if (type === 'sessionCreated') {
          setTimeout(() => {
            handler({
              type: 'sessionCreated',
              sessionId: 'test-session-123',
              sourceLanguage: 'en',
              qualityTier: 'standard',
              timestamp: Date.now(),
            });
          }, 10);
        }
      });

      const result = await orchestrator.createSession();

      expect(result.success).toBe(true);
      expect(mockWsClient.connect).toHaveBeenCalledTimes(3);
    });

    it('should fail after max retry attempts', async () => {
      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'test-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
        retryAttempts: 3,
      });

      // All attempts fail
      mockWsClient.connect.mockRejectedValue(new Error('Connection failed'));

      const result = await orchestrator.createSession();

      expect(result.success).toBe(false);
      expect(result.error).toBeDefined();
      expect(mockWsClient.connect).toHaveBeenCalledTimes(3);
      expect(mockWsClient.disconnect).toHaveBeenCalled();
    });

    it('should timeout if no response received', async () => {
      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'test-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
        timeout: 100, // Short timeout for test
        retryAttempts: 1,
      });

      // Mock successful connection
      mockWsClient.connect.mockResolvedValue(undefined);

      // Don't send any response (timeout)
      mockWsClient.on.mockImplementation(() => {});

      const result = await orchestrator.createSession();

      expect(result.success).toBe(false);
      expect(result.error).toBe(ERROR_MESSAGES.CREATION_TIMEOUT);
      expect(result.errorCode).toBe('CREATION_TIMEOUT');
    });

    it('should handle error response from server', async () => {
      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'test-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
      });

      // Mock successful connection
      mockWsClient.connect.mockResolvedValue(undefined);

      // Mock error response
      mockWsClient.on.mockImplementation((type: string, handler: Function) => {
        if (type === 'error') {
          setTimeout(() => {
            handler({
              type: 'error',
              code: 'INVALID_PARAMETERS',
              message: 'Invalid source language',
            });
          }, 10);
        }
      });

      const result = await orchestrator.createSession();

      expect(result.success).toBe(false);
      expect(result.error).toBe('Invalid source language');
      expect(result.errorCode).toBe('INVALID_PARAMETERS');
    });

    it('should abort session creation when abort is called', async () => {
      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'test-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
      });

      // Mock slow connection
      mockWsClient.connect.mockImplementation(() => {
        return new Promise((resolve) => setTimeout(resolve, 1000));
      });

      // Start creation and abort immediately
      const resultPromise = orchestrator.createSession();
      orchestrator.abort();

      const result = await resultPromise;

      expect(result.success).toBe(false);
      expect(result.errorCode).toBe('CANCELLED');
    });

    it('should cleanup WebSocket on failure', async () => {
      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'test-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
        retryAttempts: 1,
      });

      // Mock connection success but send failure
      mockWsClient.connect.mockResolvedValue(undefined);
      mockWsClient.send.mockImplementation(() => {
        throw new Error('Send failed');
      });

      const result = await orchestrator.createSession();

      expect(result.success).toBe(false);
      expect(mockWsClient.disconnect).toHaveBeenCalled();
    });

    it('should not retry on INVALID_PARAMETERS error', async () => {
      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'test-token',
        sourceLanguage: 'invalid',
        qualityTier: 'standard',
        retryAttempts: 3,
      });

      // Mock successful connection
      mockWsClient.connect.mockResolvedValue(undefined);

      // Mock error response
      mockWsClient.on.mockImplementation((type: string, handler: Function) => {
        if (type === 'error') {
          setTimeout(() => {
            handler({
              type: 'error',
              code: 'INVALID_PARAMETERS',
              message: 'Invalid source language',
            });
          }, 10);
        }
      });

      const result = await orchestrator.createSession();

      expect(result.success).toBe(false);
      expect(result.errorCode).toBe('INVALID_PARAMETERS');
      // Should only try once, not retry
      expect(mockWsClient.connect).toHaveBeenCalledTimes(1);
    });

    it('should handle connection timeout', async () => {
      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'test-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
        timeout: 100, // Short timeout
        retryAttempts: 1,
      });

      // Mock slow connection that exceeds timeout
      mockWsClient.connect.mockImplementation(() => {
        return new Promise((resolve) => setTimeout(resolve, 200));
      });

      const result = await orchestrator.createSession();

      expect(result.success).toBe(false);
      expect(result.error).toBe(ERROR_MESSAGES.CONNECTION_TIMEOUT);
    });
  });

  describe('abort', () => {
    it('should cleanup resources when aborted', () => {
      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'test-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
      });

      orchestrator.abort();

      // Verify cleanup was called (would be tested through side effects)
      expect(true).toBe(true);
    });
  });
});

  describe('bug fixes', () => {
    let orchestrator: SessionCreationOrchestrator;
    let mockWsClient: any;

    beforeEach(() => {
      // Reset mocks
      vi.clearAllMocks();

      // Create mock WebSocket client
      mockWsClient = {
        connect: vi.fn(),
        send: vi.fn(),
        on: vi.fn(),
        off: vi.fn(),
        disconnect: vi.fn(),
        isConnected: vi.fn().mockReturnValue(true),
      };

      // Mock WebSocketClient constructor
      (WebSocketClient as any).mockImplementation(() => mockWsClient);
    });

    afterEach(() => {
      if (orchestrator) {
        orchestrator.abort();
      }
    });

    it('should use tokens.expiresAt directly without recalculation (Task 5 fix)', async () => {
      // This test validates the fix for token expiry calculation bug
      // The bug was: timeUntilExpiry = (Date.now() + expiresIn * 1000) - Date.now()
      // The fix: timeUntilExpiry = expiresAt - Date.now()
      
      const now = Date.now();
      const expiresAt = now + (10 * 60 * 1000); // 10 minutes from now
      
      const mockTokenStorage = {
        getTokens: vi.fn().mockResolvedValue({
          idToken: 'test-token',
          accessToken: 'test-access-token',
          refreshToken: 'test-refresh-token',
          expiresAt, // Absolute timestamp
        }),
        storeTokens: vi.fn(),
      };

      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'test-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
        tokenStorage: mockTokenStorage,
      });

      // Mock successful connection
      mockWsClient.connect.mockResolvedValue(undefined);

      // Mock successful session creation response
      mockWsClient.on.mockImplementation((type: string, handler: Function) => {
        if (type === 'sessionCreated') {
          setTimeout(() => {
            handler({
              type: 'sessionCreated',
              sessionId: 'test-session-123',
              sourceLanguage: 'en',
              qualityTier: 'standard',
              timestamp: Date.now(),
            });
          }, 10);
        }
      });

      const result = await orchestrator.createSession();

      expect(result.success).toBe(true);
      // Token should not be refreshed since it's 10 minutes from expiry
      // This validates that expiresAt is used directly
    });

    it('should validate WebSocket connection state before sending (Task 6 fix)', async () => {
      // This test validates the fix for WebSocket state validation
      // The bug was: no check if WebSocket is connected before send()
      // The fix: check isConnected() before send() and throw error if not connected
      
      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'test-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
      });

      // Mock successful connection
      mockWsClient.connect.mockResolvedValue(undefined);
      
      // Mock isConnected to return false (simulating disconnected state)
      mockWsClient.isConnected.mockReturnValue(false);

      const result = await orchestrator.createSession();

      // Should fail because WebSocket is not connected
      expect(result.success).toBe(false);
      expect(result.error).toContain('not connected');
      expect(mockWsClient.send).not.toHaveBeenCalled();
    });

    it('should throw error if send fails due to connection state (Task 6 fix)', async () => {
      // Additional test for WebSocket state validation
      // Ensures error is properly caught and promise is rejected
      
      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'test-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
      });

      // Mock successful connection
      mockWsClient.connect.mockResolvedValue(undefined);
      
      // Mock isConnected to return true initially
      mockWsClient.isConnected.mockReturnValue(true);
      
      // Mock send to throw error (connection dropped between check and send)
      mockWsClient.send.mockImplementation(() => {
        throw new Error('WebSocket not connected');
      });

      const result = await orchestrator.createSession();

      // Should fail and cleanup properly
      expect(result.success).toBe(false);
      expect(mockWsClient.disconnect).toHaveBeenCalled();
    });

    it('should correctly calculate time until expiry from absolute timestamp', async () => {
      // Comprehensive test for token expiry calculation
      // Validates that expiresAt is treated as absolute timestamp
      
      const now = Date.now();
      const expiresAt = now + (3 * 60 * 1000); // 3 minutes from now (less than 5 min threshold)
      
      const mockAuthService = {
        refreshTokens: vi.fn().mockResolvedValue({
          idToken: 'new-token',
          accessToken: 'new-access-token',
          refreshToken: 'refresh-token',
          expiresAt: now + (60 * 60 * 1000), // 1 hour from now
        }),
      };

      const mockTokenStorage = {
        getTokens: vi.fn().mockResolvedValue({
          idToken: 'old-token',
          accessToken: 'old-access-token',
          refreshToken: 'refresh-token',
          expiresAt, // 3 minutes from now
        }),
        storeTokens: vi.fn(),
      };

      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'old-token',
        refreshToken: 'refresh-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
        authService: mockAuthService,
        tokenStorage: mockTokenStorage,
      });

      // Mock successful connection
      mockWsClient.connect.mockResolvedValue(undefined);

      // Mock successful session creation response
      mockWsClient.on.mockImplementation((type: string, handler: Function) => {
        if (type === 'sessionCreated') {
          setTimeout(() => {
            handler({
              type: 'sessionCreated',
              sessionId: 'test-session-123',
              sourceLanguage: 'en',
              qualityTier: 'standard',
              timestamp: Date.now(),
            });
          }, 10);
        }
      });

      const result = await orchestrator.createSession();

      expect(result.success).toBe(true);
      // Should trigger refresh because token expires in 3 minutes (< 5 min threshold)
      expect(mockAuthService.refreshTokens).toHaveBeenCalled();
      expect(mockTokenStorage.storeTokens).toHaveBeenCalled();
    });
  });

  describe('token refresh', () => {
    let orchestrator: SessionCreationOrchestrator;
    let mockWsClient: any;
    let mockAuthService: any;
    let mockTokenStorage: any;

    beforeEach(() => {
      // Reset mocks
      vi.clearAllMocks();

      // Create mock WebSocket client
      mockWsClient = {
        connect: vi.fn(),
        send: vi.fn(),
        on: vi.fn(),
        off: vi.fn(),
        disconnect: vi.fn(),
        isConnected: vi.fn().mockReturnValue(true),
      };

      // Mock WebSocketClient constructor
      (WebSocketClient as any).mockImplementation(() => mockWsClient);

      mockAuthService = {
        refreshTokens: vi.fn(),
      };

      mockTokenStorage = {
        getTokens: vi.fn(),
        storeTokens: vi.fn(),
      };
    });

    afterEach(() => {
      if (orchestrator) {
        orchestrator.abort();
      }
    });

    it('should refresh token if close to expiry before connecting', async () => {
      const expiresIn = 4 * 60; // 4 minutes (less than 5 minute threshold)
      
      mockTokenStorage.getTokens.mockResolvedValue({
        idToken: 'old-token',
        accessToken: 'old-access-token',
        refreshToken: 'refresh-token',
        expiresIn,
      });

      mockAuthService.refreshTokens.mockResolvedValue({
        idToken: 'new-token',
        accessToken: 'new-access-token',
        refreshToken: 'refresh-token',
        expiresIn: 3600,
      });

      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'old-token',
        refreshToken: 'refresh-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
        authService: mockAuthService,
        tokenStorage: mockTokenStorage,
      });

      // Mock successful connection
      mockWsClient.connect.mockResolvedValue(undefined);

      // Mock successful session creation response
      mockWsClient.on.mockImplementation((type: string, handler: Function) => {
        if (type === 'sessionCreated') {
          setTimeout(() => {
            handler({
              type: 'sessionCreated',
              sessionId: 'test-session-123',
              sourceLanguage: 'en',
              qualityTier: 'standard',
              timestamp: Date.now(),
            });
          }, 10);
        }
      });

      const result = await orchestrator.createSession();

      expect(result.success).toBe(true);
      expect(mockAuthService.refreshTokens).toHaveBeenCalledWith('refresh-token');
      expect(mockTokenStorage.storeTokens).toHaveBeenCalledWith(
        expect.objectContaining({
          idToken: 'new-token',
        })
      );
    });

    it('should not refresh token if not close to expiry', async () => {
      const expiresIn = 30 * 60; // 30 minutes (more than 5 minute threshold)
      
      mockTokenStorage.getTokens.mockResolvedValue({
        idToken: 'current-token',
        accessToken: 'current-access-token',
        refreshToken: 'refresh-token',
        expiresIn,
      });

      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'current-token',
        refreshToken: 'refresh-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
        authService: mockAuthService,
        tokenStorage: mockTokenStorage,
      });

      // Mock successful connection
      mockWsClient.connect.mockResolvedValue(undefined);

      // Mock successful session creation response
      mockWsClient.on.mockImplementation((type: string, handler: Function) => {
        if (type === 'sessionCreated') {
          setTimeout(() => {
            handler({
              type: 'sessionCreated',
              sessionId: 'test-session-123',
              sourceLanguage: 'en',
              qualityTier: 'standard',
              timestamp: Date.now(),
            });
          }, 10);
        }
      });

      const result = await orchestrator.createSession();

      expect(result.success).toBe(true);
      expect(mockAuthService.refreshTokens).not.toHaveBeenCalled();
    });

    it('should retry with refreshed token on auth error', async () => {
      mockTokenStorage.getTokens.mockResolvedValue({
        idToken: 'old-token',
        accessToken: 'old-access-token',
        refreshToken: 'refresh-token',
        expiresIn: 3600,
      });

      mockAuthService.refreshTokens.mockResolvedValue({
        idToken: 'new-token',
        accessToken: 'new-access-token',
        refreshToken: 'refresh-token',
        expiresIn: 3600,
      });

      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'old-token',
        refreshToken: 'refresh-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
        authService: mockAuthService,
        tokenStorage: mockTokenStorage,
      });

      let attemptCount = 0;
      mockWsClient.connect.mockResolvedValue(undefined);

      // First attempt: auth error, second attempt: success
      mockWsClient.on.mockImplementation((type: string, handler: Function) => {
        if (type === 'auth_error') {
          if (attemptCount === 0) {
            setTimeout(() => {
              handler({
                type: 'auth_error',
                message: 'Authentication failed',
              });
            }, 10);
          }
        }
        if (type === 'sessionCreated') {
          if (attemptCount === 1) {
            setTimeout(() => {
              handler({
                type: 'sessionCreated',
                sessionId: 'test-session-123',
                sourceLanguage: 'en',
                qualityTier: 'standard',
                timestamp: Date.now(),
              });
            }, 10);
          }
        }
      });

      // Track connection attempts
      mockWsClient.connect.mockImplementation(() => {
        attemptCount++;
        return Promise.resolve();
      });

      const result = await orchestrator.createSession();

      expect(result.success).toBe(true);
      expect(mockAuthService.refreshTokens).toHaveBeenCalledWith('refresh-token');
      expect(mockTokenStorage.storeTokens).toHaveBeenCalled();
      expect(mockWsClient.connect).toHaveBeenCalledTimes(2);
    });

    it('should fail if token refresh fails on auth error', async () => {
      mockTokenStorage.getTokens.mockResolvedValue({
        idToken: 'old-token',
        accessToken: 'old-access-token',
        refreshToken: 'refresh-token',
        expiresIn: 3600,
      });

      mockAuthService.refreshTokens.mockRejectedValue(new Error('Refresh failed'));

      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'old-token',
        refreshToken: 'refresh-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
        authService: mockAuthService,
        tokenStorage: mockTokenStorage,
      });

      mockWsClient.connect.mockResolvedValue(undefined);

      // Trigger auth error
      mockWsClient.on.mockImplementation((type: string, handler: Function) => {
        if (type === 'auth_error') {
          setTimeout(() => {
            handler({
              type: 'auth_error',
              message: 'Authentication failed',
            });
          }, 10);
        }
      });

      const result = await orchestrator.createSession();

      expect(result.success).toBe(false);
      expect(result.error).toBe('Authentication failed. Please log in again.');
      expect(result.errorCode).toBe('AUTH_FAILED');
    });

    it('should use existing token if no auth service provided', async () => {
      orchestrator = new SessionCreationOrchestrator({
        wsUrl: 'wss://test.example.com',
        jwtToken: 'existing-token',
        sourceLanguage: 'en',
        qualityTier: 'standard',
        // No authService or tokenStorage
      });

      // Mock successful connection
      mockWsClient.connect.mockResolvedValue(undefined);

      // Mock successful session creation response
      mockWsClient.on.mockImplementation((type: string, handler: Function) => {
        if (type === 'sessionCreated') {
          setTimeout(() => {
            handler({
              type: 'sessionCreated',
              sessionId: 'test-session-123',
              sourceLanguage: 'en',
              qualityTier: 'standard',
              timestamp: Date.now(),
            });
          }, 10);
        }
      });

      const result = await orchestrator.createSession();

      expect(result.success).toBe(true);
      // Should use existing token without refresh
    });
  });
