/**
 * MockWebSocket - Sophisticated WebSocket mock for testing
 * 
 * Simulates async WebSocket behavior including:
 * - Async connection establishment
 * - Event listener management
 * - State transitions
 * - Message sending/receiving
 * 
 * Test helpers:
 * - triggerEvent: Manually trigger event handlers
 * - simulateMessage: Send message to client
 * - simulateError: Trigger error event
 * - simulateClose: Close connection
 */

export class MockWebSocket {
  public url: string;
  public readyState: number = WebSocket.CONNECTING;
  public onopen: ((event: Event) => void) | null = null;
  public onclose: ((event: CloseEvent) => void) | null = null;
  public onerror: ((event: Event) => void) | null = null;
  public onmessage: ((event: MessageEvent) => void) | null = null;
  
  private eventListeners: Map<string, Set<EventListener>> = new Map();
  
  constructor(url: string) {
    this.url = url;
    
    // Simulate async connection
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      this.triggerEvent('open', new Event('open'));
    }, 0);
  }
  
  /**
   * Add event listener
   */
  addEventListener(type: string, listener: EventListener): void {
    if (!this.eventListeners.has(type)) {
      this.eventListeners.set(type, new Set());
    }
    this.eventListeners.get(type)!.add(listener);
  }
  
  /**
   * Remove event listener
   */
  removeEventListener(type: string, listener: EventListener): void {
    this.eventListeners.get(type)?.delete(listener);
  }
  
  /**
   * Send data through WebSocket
   */
  send(data: string | ArrayBuffer): void {
    if (this.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
  }
  
  /**
   * Close WebSocket connection
   */
  close(code?: number, reason?: string): void {
    this.readyState = WebSocket.CLOSING;
    setTimeout(() => {
      this.readyState = WebSocket.CLOSED;
      this.triggerEvent('close', new CloseEvent('close', { code, reason }));
    }, 0);
  }
  
  /**
   * Test helper: Trigger event handlers
   */
  triggerEvent(type: string, event: Event): void {
    // Call property handler (e.g., onopen, onmessage)
    const propertyHandler = (this as any)[`on${type}`];
    if (propertyHandler) {
      propertyHandler(event);
    }
    
    // Call addEventListener handlers
    this.eventListeners.get(type)?.forEach(listener => {
      listener(event);
    });
  }
  
  /**
   * Test helper: Simulate incoming message
   */
  simulateMessage(data: any): void {
    const message = new MessageEvent('message', {
      data: typeof data === 'string' ? data : JSON.stringify(data)
    });
    this.triggerEvent('message', message);
  }
  
  /**
   * Test helper: Simulate error
   */
  simulateError(error?: Error): void {
    this.triggerEvent('error', new Event('error'));
  }
  
  /**
   * Test helper: Simulate close
   */
  simulateClose(code: number = 1000, reason: string = ''): void {
    this.close(code, reason);
  }
}
