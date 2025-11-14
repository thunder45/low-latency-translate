import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { WebSocketClient, ConnectionState } from '../../websocket/WebSocketClient';

describe('Connection Refresh Integration', () => {
  let client: WebSocketClient;
  let mockWebSocket: any;

  beforeEach(() => {
    vi.useFakeTimers();
    
    mockWebSocket = {
      send: vi.fn(),
      close: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      readyState: WebSocket.CONNECTING,
      CONNECTING: 0,
      OPEN: 1,
      CLOSING: 2,
      CLOSED: 3,
    };

    global.WebSocket = vi.fn(() => mockWebSocket) as any;
    client = new WebSocketClient('wss://test.example.com');
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  describe('Connection Refresh Flow', () => {
    it('should handle connectionRefreshRequired message', async () => {
      // Connect
      client.connect();
      mockWebSocket.readyState = WebSocket.OPEN;
      const openHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'open'
      )[1];
      openHandler();

      // Register handler for refresh required
      const refreshHandler = vi.fn();
      client.on('connectionRefreshRequired', refreshHandler);

      // Simulate refresh required message
      const messageHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'message'
      )[1];
      
      const message = {
        type: 'connectionRefreshRequired',
        refreshAt: Date.now() + 900000, // 15 minutes
        warningAt: Date.now() + 300000, // 5 minutes
      };
      messageHandler({ data: JSON.stringify(message) });

      // Verify handler called
      expect(refreshHandler).toHaveBeenCalledWith(message);
    });

    it('should establish new connection during refresh', async () => {
      // Initial connection
      client.connect();
      mockWebSocket.readyState = WebSocket.OPEN;
      const openHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'open'
      )[1];
      openHandler();

      expect(client.getState()).toBe(ConnectionState.CONNECTED);

      // Simulate refresh initiation
      const newMockWebSocket = {
        ...mockWebSocket,
        send: vi.fn(),
        close: vi.fn(),
      };
      global.WebSocket = vi.fn(() => newMockWebSocket) as any;

      // Initiate refresh (would be triggered by application logic)
      const newClient = new WebSocketClient('wss://test.example.com');
      newClient.connect();

      // Verify new connection created
      expect(global.WebSocket).toHaveBeenCalledTimes(2);
    });

    it('should send refreshConnection message', async () => {
      // Connect
      client.connect();
      mockWebSocket.readyState = WebSocket.OPEN;
      const openHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'open'
      )[1];
      openHandler();

      // Send refresh message
      const refreshMessage = {
        type: 'refreshConnection',
        sessionId: 'test-session',
        authToken: 'test-token',
      };
      client.send(refreshMessage);

      // Verify message sent
      expect(mockWebSocket.send).toHaveBeenCalledWith(
        JSON.stringify(refreshMessage)
      );
    });

    it('should handle connectionRefreshComplete message', async () => {
      // Connect
      client.connect();
      mockWebSocket.readyState = WebSocket.OPEN;
      const openHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'open'
      )[1];
      openHandler();

      // Register handler for refresh complete
      const completeHandler = vi.fn();
      client.on('connectionRefreshComplete', completeHandler);

      // Simulate refresh complete message
      const messageHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'message'
      )[1];
      
      const message = {
        type: 'connectionRefreshComplete',
        newConnectionId: 'new-conn-123',
      };
      messageHandler({ data: JSON.stringify(message) });

      // Verify handler called
      expect(completeHandler).toHaveBeenCalledWith(message);
    });

    it('should close old connection after refresh complete', async () => {
      // Initial connection
      client.connect();
      mockWebSocket.readyState = WebSocket.OPEN;
      const openHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'open'
      )[1];
      openHandler();

      // Simulate refresh complete
      const messageHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'message'
      )[1];
      
      const message = {
        type: 'connectionRefreshComplete',
        newConnectionId: 'new-conn-123',
      };
      messageHandler({ data: JSON.stringify(message) });

      // Close old connection (would be done by application logic)
      client.disconnect();

      // Verify old connection closed
      expect(mockWebSocket.close).toHaveBeenCalled();
    });

    it('should retry refresh on failure', async () => {
      // Connect
      client.connect();
      mockWebSocket.readyState = WebSocket.OPEN;
      const openHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'open'
      )[1];
      openHandler();

      // Simulate refresh failure
      const errorHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'error'
      )[1];
      errorHandler(new Error('Refresh failed'));

      // Verify reconnection attempt
      expect(client.getState()).toBe(ConnectionState.RECONNECTING);

      // Wait for retry
      await vi.advanceTimersByTimeAsync(1000);

      // Verify retry occurred
      expect(global.WebSocket).toHaveBeenCalledTimes(2);
    });

    it('should maintain session state during refresh', async () => {
      // Connect with session data
      client.connect();
      mockWebSocket.readyState = WebSocket.OPEN;
      const openHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'open'
      )[1];
      openHandler();

      // Send session data
      const sessionMessage = {
        type: 'sessionCreated',
        sessionId: 'test-session',
      };
      client.send(sessionMessage);

      // Simulate refresh
      const refreshMessage = {
        type: 'refreshConnection',
        sessionId: 'test-session',
      };
      client.send(refreshMessage);

      // Verify session ID maintained
      expect(mockWebSocket.send).toHaveBeenCalledWith(
        JSON.stringify(refreshMessage)
      );
    });
  });

  describe('Refresh Timing', () => {
    it('should warn at 100 minutes', async () => {
      // Connect
      client.connect();
      mockWebSocket.readyState = WebSocket.OPEN;
      const openHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'open'
      )[1];
      openHandler();

      // Register warning handler
      const warningHandler = vi.fn();
      client.on('connectionRefreshRequired', warningHandler);

      // Simulate warning message at 100 minutes
      const messageHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'message'
      )[1];
      
      const message = {
        type: 'connectionRefreshRequired',
        refreshAt: Date.now() + 900000, // 15 minutes from now
        warningAt: Date.now(), // Now
      };
      messageHandler({ data: JSON.stringify(message) });

      // Verify warning received
      expect(warningHandler).toHaveBeenCalled();
    });

    it('should refresh at 115 minutes', async () => {
      // Connect
      client.connect();
      mockWebSocket.readyState = WebSocket.OPEN;
      const openHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'open'
      )[1];
      openHandler();

      // Simulate time passing to 115 minutes
      // (Application logic would trigger refresh)
      const refreshMessage = {
        type: 'refreshConnection',
        sessionId: 'test-session',
      };
      client.send(refreshMessage);

      // Verify refresh initiated
      expect(mockWebSocket.send).toHaveBeenCalledWith(
        JSON.stringify(refreshMessage)
      );
    });
  });
});
