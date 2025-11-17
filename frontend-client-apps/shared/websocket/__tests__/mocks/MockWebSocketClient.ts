/**
 * MockWebSocketClient - Mock WebSocketClient with EventEmitter pattern
 * 
 * Provides emit() method for triggering event handlers in tests.
 * Useful for testing components that depend on WebSocketClient.
 */

import { vi } from 'vitest';

export class MockWebSocketClient {
  private handlers: Map<string, Function[]> = new Map();
  
  // Mock methods
  connect = vi.fn().mockResolvedValue(undefined);
  disconnect = vi.fn();
  send = vi.fn().mockResolvedValue(undefined); // Return resolved promise by default
  getState = vi.fn().mockReturnValue({ status: 'connected', reconnectAttempts: 0 });
  isConnected = vi.fn().mockReturnValue(true);
  onStateChange = vi.fn();
  onDisconnect = vi.fn();
  onError = vi.fn();
  
  /**
   * Register event handler
   */
  on(event: string, handler: Function): void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, []);
    }
    this.handlers.get(event)!.push(handler);
  }
  
  /**
   * Unregister event handler
   */
  off(event: string, handler: Function): void {
    const handlers = this.handlers.get(event);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index !== -1) {
        handlers.splice(index, 1);
      }
    }
  }
  
  /**
   * Emit event to registered handlers
   * This is the key method for testing - allows tests to trigger event handlers
   */
  emit(event: string, ...args: any[]): void {
    const handlers = this.handlers.get(event);
    if (handlers) {
      handlers.forEach(handler => handler(...args));
    }
  }
  
  /**
   * Clear all handlers
   */
  clearHandlers(): void {
    this.handlers.clear();
  }
  
  /**
   * Get handler count for an event
   */
  getHandlerCount(event: string): number {
    return this.handlers.get(event)?.length || 0;
  }
}
