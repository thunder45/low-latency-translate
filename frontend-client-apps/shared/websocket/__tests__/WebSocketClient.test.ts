import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { WebSocketClient, ConnectionState } from '../WebSocketClient';

describe('WebSocketClient', () => {
  let client: WebSocketClient;
  let mockWebSocket: any;

  beforeEach(() => {
    vi.useFakeTimers();
    
    // Create mock WebSocket
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

    // Mock WebSocket constructor
    global.WebSocket = vi.fn(() => mockWebSocket) as any;
    
    client = new WebSocketClient('wss://test.example.com');
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  describe('connect', () => {
    it('should create WebSocket connection', () => {
      client.connect();
      
      expect(global.WebSocket).toHaveBeenCalledWith('wss://test.example.com');
      expect(client.getState()).toBe(ConnectionState.CONNECTING);
    });

    it('should set up event listeners', () => {
      client.connect();
      
      expect(mockWebSocket.addEventListener).toHaveBeenCalledWith('open', expect.any(Function));
      expect(mockWebSocket.addEventListener).toHaveBeenCalledWith('close', expect.any(Function));
      expect(mockWebSocket.addEventListener).toHaveBeenCalledWith('error', expect.any(Function));
      expect(mockWebSocket.addEventListener).toHaveBeenCalledWith('message', expect.any(Function));
    });

    it('should transition to connected state on open', () => {
      client.connect();
      
      // Simulate open event
      const openHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'open'
      )[1];
      mockWebSocket.readyState = WebSocket.OPEN;
      openHandler();
      
      expect(client.getState()).toBe(ConnectionState.CONNECTED);
    });

    it('should not connect if already connected', () => {
      client.connect();
      mockWebSocket.readyState = WebSocket.OPEN;
      
      const openHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'open'
      )[1];
      openHandler();
      
      // Try to connect again
      client.connect();
      
      // Should only have been called once
      expect(global.WebSocket).toHaveBeenCalledTimes(1);
    });
  });

  describe('send', () => {
    beforeEach(() => {
      client.connect();
      mockWebSocket.readyState = WebSocket.OPEN;
      const openHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'open'
      )[1];
      openHandler();
    });

    it('should send message when connected', () => {
      const message = { type: 'test', data: 'hello' };
      client.send(message);
      
      expect(mockWebSocket.send).toHaveBeenCalledWith(JSON.stringify(message));
    });

    it('should throw error when not connected', () => {
      client.disconnect();
      
      expect(() => {
        client.send({ type: 'test' });
      }).toThrow();
    });
  });

  describe('disconnect', () => {
    beforeEach(() => {
      client.connect();
      mockWebSocket.readyState = WebSocket.OPEN;
    });

    it('should close WebSocket connection', () => {
      client.disconnect();
      
      expect(mockWebSocket.close).toHaveBeenCalled();
    });

    it('should transition to disconnected state', () => {
      client.disconnect();
      
      const closeHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'close'
      )[1];
      mockWebSocket.readyState = WebSocket.CLOSED;
      closeHandler();
      
      expect(client.getState()).toBe(ConnectionState.DISCONNECTED);
    });
  });

  describe('message handling', () => {
    beforeEach(() => {
      client.connect();
      mockWebSocket.readyState = WebSocket.OPEN;
      const openHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'open'
      )[1];
      openHandler();
    });

    it('should call registered message handlers', () => {
      const handler = vi.fn();
      client.on('test-message', handler);
      
      // Simulate message event
      const messageHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'message'
      )[1];
      
      const message = { type: 'test-message', data: 'hello' };
      messageHandler({ data: JSON.stringify(message) });
      
      expect(handler).toHaveBeenCalledWith(message);
    });

    it('should handle multiple handlers for same message type', () => {
      const handler1 = vi.fn();
      const handler2 = vi.fn();
      
      client.on('test-message', handler1);
      client.on('test-message', handler2);
      
      const messageHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'message'
      )[1];
      
      const message = { type: 'test-message', data: 'hello' };
      messageHandler({ data: JSON.stringify(message) });
      
      expect(handler1).toHaveBeenCalledWith(message);
      expect(handler2).toHaveBeenCalledWith(message);
    });

    it('should not call handlers for different message types', () => {
      const handler = vi.fn();
      client.on('test-message', handler);
      
      const messageHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'message'
      )[1];
      
      const message = { type: 'other-message', data: 'hello' };
      messageHandler({ data: JSON.stringify(message) });
      
      expect(handler).not.toHaveBeenCalled();
    });
  });

  describe('heartbeat', () => {
    beforeEach(() => {
      client.connect();
      mockWebSocket.readyState = WebSocket.OPEN;
      const openHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'open'
      )[1];
      openHandler();
    });

    it('should send heartbeat every 30 seconds', async () => {
      // Advance time by 30 seconds
      await vi.advanceTimersByTimeAsync(30000);
      
      expect(mockWebSocket.send).toHaveBeenCalledWith(
        JSON.stringify({ type: 'heartbeat' })
      );
    });

    it('should trigger reconnection on heartbeat timeout', async () => {
      const reconnectSpy = vi.spyOn(client as any, 'reconnect');
      
      // Advance time by 30 seconds (heartbeat sent)
      await vi.advanceTimersByTimeAsync(30000);
      
      // Advance time by 5 more seconds (timeout)
      await vi.advanceTimersByTimeAsync(5000);
      
      expect(reconnectSpy).toHaveBeenCalled();
    });
  });

  describe('reconnection', () => {
    it('should attempt reconnection with exponential backoff', async () => {
      client.connect();
      
      // Simulate connection failure
      const errorHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'error'
      )[1];
      errorHandler();
      
      const closeHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'close'
      )[1];
      mockWebSocket.readyState = WebSocket.CLOSED;
      closeHandler();
      
      expect(client.getState()).toBe(ConnectionState.RECONNECTING);
      
      // First reconnection attempt after 1s
      await vi.advanceTimersByTimeAsync(1000);
      expect(global.WebSocket).toHaveBeenCalledTimes(2);
      
      // Simulate failure again
      errorHandler();
      closeHandler();
      
      // Second reconnection attempt after 2s
      await vi.advanceTimersByTimeAsync(2000);
      expect(global.WebSocket).toHaveBeenCalledTimes(3);
    });

    it('should stop reconnecting after max attempts', async () => {
      client.connect();
      
      const errorHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'error'
      )[1];
      const closeHandler = mockWebSocket.addEventListener.mock.calls.find(
        (call: any) => call[0] === 'close'
      )[1];
      
      // Simulate 5 failed connection attempts
      for (let i = 0; i < 5; i++) {
        errorHandler();
        mockWebSocket.readyState = WebSocket.CLOSED;
        closeHandler();
        await vi.advanceTimersByTimeAsync(30000); // Max delay
      }
      
      expect(client.getState()).toBe(ConnectionState.FAILED);
    });
  });
});
