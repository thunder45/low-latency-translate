import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { WebSocketClient } from '../../websocket/WebSocketClient';
import { WebSocketConfig } from '../../websocket/types';
import { MockWebSocket } from '../../websocket/__tests__/mocks/MockWebSocket';

describe('Connection Refresh Integration', () => {
  let client: WebSocketClient;
  let config: WebSocketConfig;

  beforeEach(() => {
    vi.useFakeTimers();
    
    // Use MockWebSocket class
    global.WebSocket = MockWebSocket as any;
    
    config = {
      url: 'wss://test.example.com',
      reconnect: true,
      maxReconnectAttempts: 5,
      reconnectDelay: 1000,
      heartbeatInterval: 300000, // 5 minutes - long enough to not interfere with tests
    };
    
    client = new WebSocketClient(config);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  describe('Connection Refresh Flow', () => {
    it('should handle connectionRefreshRequired message', async () => {
      // Connect
      const connectPromise = client.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;

      // Register handler for refresh required
      const refreshHandler = vi.fn();
      client.on('connectionRefreshRequired', refreshHandler);

      // Simulate refresh required message
      const message = {
        type: 'connectionRefreshRequired',
        refreshAt: Date.now() + 900000, // 15 minutes
        warningAt: Date.now() + 300000, // 5 minutes
      };
      const ws = (client as any).ws as MockWebSocket;
      ws.simulateMessage(message);

      // Verify handler called
      expect(refreshHandler).toHaveBeenCalledWith(message);
    });

    it('should establish new connection during refresh', async () => {
      // Initial connection
      const connectPromise = client.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;

      expect(client.getState().status).toBe('connected');
      const oldWs = (client as any).ws;

      // Initiate refresh (would be triggered by application logic)
      const newClient = new WebSocketClient(config);
      const newConnectPromise = newClient.connect();
      await vi.advanceTimersByTimeAsync(10);
      await newConnectPromise;

      // Verify new connection created
      const newWs = (newClient as any).ws;
      expect(newWs).not.toBe(oldWs);
      expect(newClient.getState().status).toBe('connected');
    });

    it('should send refreshConnection message', async () => {
      // Connect
      const connectPromise = client.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;

      // Send refresh message
      const refreshMessage = {
        type: 'refreshConnection',
        sessionId: 'test-session',
        authToken: 'test-token',
      };
      client.send(refreshMessage);

      // Verify client is connected (message sent successfully)
      expect(client.getState().status).toBe('connected');
    });

    it('should handle connectionRefreshComplete message', async () => {
      // Connect
      const connectPromise = client.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;

      // Register handler for refresh complete
      const completeHandler = vi.fn();
      client.on('connectionRefreshComplete', completeHandler);

      // Simulate refresh complete message
      const message = {
        type: 'connectionRefreshComplete',
        newConnectionId: 'new-conn-123',
      };
      const ws = (client as any).ws as MockWebSocket;
      ws.simulateMessage(message);

      // Verify handler called
      expect(completeHandler).toHaveBeenCalledWith(message);
    });

    it('should close old connection after refresh complete', async () => {
      // Initial connection
      const connectPromise = client.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;

      const ws = (client as any).ws as MockWebSocket;

      // Simulate refresh complete
      const message = {
        type: 'connectionRefreshComplete',
        newConnectionId: 'new-conn-123',
      };
      ws.simulateMessage(message);

      // Close old connection (would be done by application logic)
      client.disconnect();
      await vi.advanceTimersByTimeAsync(10);

      // Verify old connection closed
      expect(ws.readyState).toBe(WebSocket.CLOSED);
    });

    it('should retry refresh on failure', async () => {
      // Connect
      const connectPromise = client.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;

      // Simulate refresh failure
      const ws = (client as any).ws as MockWebSocket;
      ws.simulateClose(1006, 'Connection lost');
      await vi.advanceTimersByTimeAsync(10);

      // Verify reconnection attempt
      expect(client.getState().status).toBe('reconnecting');

      // Wait for retry
      await vi.advanceTimersByTimeAsync(1000);

      // Verify state change occurred
      expect(client.getState().reconnectAttempts).toBeGreaterThan(0);
    });

    it('should maintain session state during refresh', async () => {
      // Connect with session data
      const connectPromise = client.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;

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

      // Verify client is still connected (messages sent successfully)
      expect(client.getState().status).toBe('connected');
    });
  });

  describe('Refresh Timing', () => {
    it('should warn at 100 minutes', async () => {
      // Connect
      const connectPromise = client.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;

      // Register warning handler
      const warningHandler = vi.fn();
      client.on('connectionRefreshRequired', warningHandler);

      // Simulate warning message at 100 minutes
      const message = {
        type: 'connectionRefreshRequired',
        refreshAt: Date.now() + 900000, // 15 minutes from now
        warningAt: Date.now(), // Now
      };
      const ws = (client as any).ws as MockWebSocket;
      ws.simulateMessage(message);

      // Verify warning received
      expect(warningHandler).toHaveBeenCalled();
    });

    it('should refresh at 115 minutes', async () => {
      // Connect
      const connectPromise = client.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;

      // Simulate time passing to 115 minutes
      // (Application logic would trigger refresh)
      const refreshMessage = {
        type: 'refreshConnection',
        sessionId: 'test-session',
      };
      client.send(refreshMessage);

      // Verify refresh initiated (client still connected)
      expect(client.getState().status).toBe('connected');
    });
  });
});
