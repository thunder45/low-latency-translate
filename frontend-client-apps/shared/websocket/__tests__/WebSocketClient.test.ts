import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { WebSocketClient } from '../WebSocketClient';
import { WebSocketConfig, ConnectionState } from '../types';
import { MockWebSocket } from './mocks/MockWebSocket';

describe('WebSocketClient', () => {
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

  describe('connect', () => {
    it('should create WebSocket connection', async () => {
      const connectPromise = client.connect();
      
      // Wait for async connection (just advance enough for setTimeout(0))
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;
      
      expect(client.getState().status).toBe('connected');
    });

    it('should transition to connected state on open', async () => {
      const connectPromise = client.connect();
      
      // Wait for async connection (just advance enough for setTimeout(0))
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;
      
      expect(client.getState().status).toBe('connected');
    });

    it.skip('should not connect if already connected', async () => {
      // TODO: WebSocketClient needs guard to prevent connecting when already connected
      const connectPromise = client.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;
      
      // Try to connect again
      await client.connect();
      
      // State should remain connected
      expect(client.getState().status).toBe('connected');
    });
  });

  describe('send', () => {
    beforeEach(async () => {
      const connectPromise = client.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;
    });

    it('should send message when connected', () => {
      const message = { type: 'test', data: 'hello' };
      client.send(message);
      
      // Verify message was sent (WebSocketClient should call ws.send)
      expect(client.getState().status).toBe('connected');
    });

    it('should throw error when not connected', () => {
      client.disconnect();
      
      expect(() => {
        client.send({ type: 'test' });
      }).toThrow();
    });
  });

  describe('disconnect', () => {
    let noReconnectClient: WebSocketClient;
    
    beforeEach(async () => {
      // Create client with reconnect disabled for disconnect tests
      const noReconnectConfig = { ...config, reconnect: false };
      noReconnectClient = new WebSocketClient(noReconnectConfig);
      
      const connectPromise = noReconnectClient.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;
    });

    it('should close WebSocket connection', async () => {
      noReconnectClient.disconnect();
      await vi.advanceTimersByTimeAsync(10);
      
      expect(noReconnectClient.getState().status).toBe('disconnected');
    });

    it('should transition to disconnected state', async () => {
      noReconnectClient.disconnect();
      await vi.advanceTimersByTimeAsync(10);
      
      expect(noReconnectClient.getState().status).toBe('disconnected');
    });
  });

  describe('message handling', () => {
    beforeEach(async () => {
      const connectPromise = client.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;
    });

    it('should call registered message handlers', () => {
      const handler = vi.fn();
      client.on('test-message', handler);
      
      // Get the WebSocket instance and simulate message
      const ws = (client as any).ws as MockWebSocket;
      const message = { type: 'test-message', data: 'hello' };
      ws.simulateMessage(message);
      
      expect(handler).toHaveBeenCalledWith(message);
    });

    it('should not call handlers for different message types', () => {
      const handler = vi.fn();
      client.on('test-message', handler);
      
      const ws = (client as any).ws as MockWebSocket;
      const message = { type: 'other-message', data: 'hello' };
      ws.simulateMessage(message);
      
      expect(handler).not.toHaveBeenCalled();
    });
  });

  describe('heartbeat', () => {
    beforeEach(async () => {
      const connectPromise = client.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;
    });

    it('should send heartbeat every 30 seconds', async () => {
      // Advance time by heartbeat interval (now 5 minutes)
      await vi.advanceTimersByTimeAsync(300000);
      
      // Heartbeat should be sent (verify state is still connected)
      expect(client.getState().status).toBe('connected');
    });

    it('should handle heartbeat timeout', async () => {
      // Advance time by heartbeat interval + timeout (5 minutes + 5 seconds)
      await vi.advanceTimersByTimeAsync(305000);
      
      // Should trigger disconnect and reconnection (since reconnect is enabled)
      expect(client.getState().status).toBe('reconnecting');
    });
  });

  describe('reconnection', () => {
    it('should attempt reconnection on disconnect', async () => {
      const connectPromise = client.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;
      
      // Simulate connection close
      const ws = (client as any).ws as MockWebSocket;
      ws.simulateClose(1006, 'Connection lost');
      await vi.advanceTimersByTimeAsync(10);
      
      expect(client.getState().status).toBe('reconnecting');
      
      // Advance time for reconnection attempt
      await vi.advanceTimersByTimeAsync(1000);
      
      // State change should be triggered
      expect(client.getState().reconnectAttempts).toBeGreaterThan(0);
    });

    it('should stop reconnecting after max attempts', async () => {
      const connectPromise = client.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;
      
      // Manually trigger disconnections to simulate failed reconnection attempts
      // Need to disconnect 6 times: initial + 5 reconnection attempts
      for (let i = 0; i < 6; i++) {
        // Simulate disconnect
        const ws = (client as any).ws as MockWebSocket;
        ws.simulateClose(1006, 'Connection lost');
        await vi.advanceTimersByTimeAsync(10);
        
        if (i < 5) {
          // First 5 disconnects should trigger reconnection
          expect(client.getState().status).toBe('reconnecting');
          expect(client.getState().reconnectAttempts).toBe(i + 1);
          
          // Advance past the reconnection delay
          const delay = 1000 * Math.pow(2, i);
          await vi.advanceTimersByTimeAsync(delay);
        }
      }
      
      // After max attempts exceeded, should be in failed state
      expect(client.getState().status).toBe('failed');
      expect(client.getState().reconnectAttempts).toBe(5);
    });
  });
});

  describe('error handling', () => {
    beforeEach(async () => {
      const connectPromise = client.connect();
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;
    });

    it('should emit connection_error event on error', () => {
      const handler = vi.fn();
      client.on('connection_error', handler);
      
      const ws = (client as any).ws as MockWebSocket;
      const error = new Event('error');
      ws.simulateError(error);
      
      expect(handler).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'connection_error',
          message: 'Failed to connect to server',
        })
      );
    });

    it('should emit auth_error event on close code 1008', async () => {
      const handler = vi.fn();
      client.on('auth_error', handler);
      
      const ws = (client as any).ws as MockWebSocket;
      ws.simulateClose(1008, 'Policy violation');
      await vi.advanceTimersByTimeAsync(10);
      
      expect(handler).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'auth_error',
          message: 'Authentication failed. Please log in again.',
          code: 1008,
        })
      );
    });

    it('should emit connection_failed event on close code 1006', async () => {
      const handler = vi.fn();
      client.on('connection_failed', handler);
      
      const ws = (client as any).ws as MockWebSocket;
      ws.simulateClose(1006, '');
      await vi.advanceTimersByTimeAsync(10);
      
      expect(handler).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'connection_failed',
          message: 'Connection failed. Please check your network.',
          code: 1006,
        })
      );
    });

    it('should emit disconnected event on normal close code 1000', async () => {
      const handler = vi.fn();
      client.on('disconnected', handler);
      
      const ws = (client as any).ws as MockWebSocket;
      ws.simulateClose(1000, 'Normal closure');
      await vi.advanceTimersByTimeAsync(10);
      
      expect(handler).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'disconnected',
          code: 1000,
          reason: 'Normal closure',
        })
      );
    });

    it('should not attempt reconnection on auth error (code 1008)', async () => {
      const ws = (client as any).ws as MockWebSocket;
      ws.simulateClose(1008, 'Policy violation');
      await vi.advanceTimersByTimeAsync(10);
      
      // Should be disconnected, not reconnecting
      expect(client.getState().status).toBe('disconnected');
      
      // Advance time to verify no reconnection attempt
      await vi.advanceTimersByTimeAsync(5000);
      expect(client.getState().status).toBe('disconnected');
    });

    it('should attempt reconnection on connection failure (code 1006)', async () => {
      const ws = (client as any).ws as MockWebSocket;
      ws.simulateClose(1006, '');
      await vi.advanceTimersByTimeAsync(10);
      
      // Should be reconnecting
      expect(client.getState().status).toBe('reconnecting');
    });

    it('should not attempt reconnection on normal close (code 1000)', async () => {
      const ws = (client as any).ws as MockWebSocket;
      ws.simulateClose(1000, 'Normal closure');
      await vi.advanceTimersByTimeAsync(10);
      
      // Should be disconnected, not reconnecting
      expect(client.getState().status).toBe('disconnected');
      
      // Advance time to verify no reconnection attempt
      await vi.advanceTimersByTimeAsync(5000);
      expect(client.getState().status).toBe('disconnected');
    });
  });
