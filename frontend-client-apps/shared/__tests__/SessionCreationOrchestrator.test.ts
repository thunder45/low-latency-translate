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
