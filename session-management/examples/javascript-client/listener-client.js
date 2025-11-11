/**
 * Listener Client Example
 * 
 * This example demonstrates how to implement a listener client that:
 * - Joins an existing session (no authentication required)
 * - Receives translated audio
 * - Handles connection refresh for unlimited session duration
 * - Manages audio playback buffer
 * - Handles errors and reconnection
 */

class ListenerClient {
  constructor(config) {
    this.config = {
      apiEndpoint: config.apiEndpoint, // wss://abc123.execute-api.us-east-1.amazonaws.com/prod
      sessionId: config.sessionId,
      targetLanguage: config.targetLanguage,
      ...config
    };
    
    this.ws = null;
    this.connectionStartTime = null;
    this.refreshThreshold = 100 * 60 * 1000; // 100 minutes in milliseconds
    this.isRefreshing = false;
    this.audioBuffer = [];
    this.eventHandlers = {};
    this.audioContext = null;
    this.audioQueue = [];
  }

  /**
   * Connect to WebSocket and join session
   */
  async connect() {
    return new Promise((resolve, reject) => {
      const wsUrl = `${this.config.apiEndpoint}?action=joinSession&sessionId=${this.config.sessionId}&targetLanguage=${this.config.targetLanguage}`;
      
      this.ws = new WebSocket(wsUrl);
      this.connectionStartTime = Date.now();

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(event, resolve, reject);
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };

      this.ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        this.stopHeartbeat();
        
        if (event.code !== 1000 && !this.isRefreshing) {
          // Unexpected disconnect, attempt to reconnect
          this.emit('disconnect', { code: event.code, reason: event.reason });
          this.attemptReconnect();
        }
      };
    });
  }

  /**
   * Handle incoming WebSocket messages
   */
  handleMessage(event, resolve, reject) {
    try {
      const message = JSON.parse(event.data);
      console.log('Received message:', message.type);

      switch (message.type) {
        case 'sessionJoined':
          console.log('Joined session:', message.sessionId);
          this.emit('sessionJoined', message);
          resolve(message);
          break;

        case 'audioData':
          // Received translated audio
          this.handleAudioData(message.audioData);
          break;

        case 'heartbeatAck':
          this.emit('heartbeat', message);
          break;

        case 'connectionRefreshRequired':
          console.log('Connection refresh required');
          this.handleConnectionRefresh(message);
          break;

        case 'connectionWarning':
          console.warn(`Connection expires in ${message.remainingMinutes} minutes`);
          this.emit('connectionWarning', message);
          break;

        case 'sessionEnded':
          console.log('Session ended by speaker');
          this.emit('sessionEnded', message);
          this.disconnect();
          break;

        case 'sessionPaused':
          console.log('Session paused');
          this.emit('sessionPaused', message);
          break;

        case 'sessionResumed':
          console.log('Session resumed');
          this.emit('sessionResumed', message);
          break;

        case 'error':
          console.error('Server error:', message.message);
          this.emit('error', message);
          if (reject) reject(new Error(message.message));
          break;

        default:
          console.log('Unknown message type:', message.type);
      }
    } catch (error) {
      console.error('Error parsing message:', error);
    }
  }

  /**
   * Handle connection refresh for unlimited session duration
   */
  async handleConnectionRefresh(message) {
    if (this.isRefreshing) {
      console.log('Refresh already in progress');
      return;
    }

    this.isRefreshing = true;
    console.log('Starting connection refresh...');

    try {
      // 1. Establish new connection while keeping old one for audio playback
      const newWsUrl = `${this.config.apiEndpoint}?action=refreshConnection&sessionId=${this.config.sessionId}&targetLanguage=${this.config.targetLanguage}&role=listener`;
      const newWs = new WebSocket(newWsUrl);

      newWs.onopen = () => {
        console.log('New connection established');
      };

      newWs.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        
        if (msg.type === 'connectionRefreshComplete') {
          console.log('Connection refresh complete');
          
          // 2. Switch audio playback to new connection
          this.switchToNewConnection(newWs);
          
          // 3. Close old connection gracefully
          this.ws.close(1000, 'Connection refresh');
          
          // 4. Update reference to new connection
          this.ws = newWs;
          this.connectionStartTime = Date.now();
          this.isRefreshing = false;
          
          this.emit('connectionRefreshed', { sessionId: this.config.sessionId });
        }
      };

      newWs.onerror = (error) => {
        console.error('Refresh connection error:', error);
        this.isRefreshing = false;
        
        // Retry after 30 seconds
        setTimeout(() => {
          this.handleConnectionRefresh(message);
        }, 30000);
      };

    } catch (error) {
      console.error('Connection refresh failed:', error);
      this.isRefreshing = false;
    }
  }

  /**
   * Switch audio playback to new connection
   */
  switchToNewConnection(newWs) {
    // Buffer audio from old connection during transition
    const oldOnMessage = this.ws.onmessage;
    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'audioData') {
        this.audioBuffer.push(msg.audioData);
      }
    };

    // Setup new connection for audio playback
    newWs.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      
      // Flush buffered audio first
      if (this.audioBuffer.length > 0) {
        console.log(`Flushing ${this.audioBuffer.length} buffered audio chunks`);
        while (this.audioBuffer.length > 0) {
          const audioData = this.audioBuffer.shift();
          this.playAudio(audioData);
        }
      }
      
      // Then handle new messages
      this.handleMessage(event);
    };

    newWs.onerror = this.ws.onerror;
    newWs.onclose = this.ws.onclose;
  }

  /**
   * Handle received audio data
   */
  handleAudioData(audioData) {
    // audioData is base64 encoded audio
    this.playAudio(audioData);
    this.emit('audioReceived', { audioData });
  }

  /**
   * Play audio using Web Audio API
   */
  async playAudio(base64Audio) {
    try {
      if (!this.audioContext) {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      }

      // Decode base64 to ArrayBuffer
      const binaryString = atob(base64Audio);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      // Decode audio data
      const audioBuffer = await this.audioContext.decodeAudioData(bytes.buffer);

      // Create buffer source
      const source = this.audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(this.audioContext.destination);

      // Play audio
      source.start(0);
      
    } catch (error) {
      console.error('Error playing audio:', error);
    }
  }

  /**
   * Start heartbeat to keep connection alive
   */
  startHeartbeat() {
    this.heartbeatInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ action: 'heartbeat' }));
      }
    }, 30000); // Every 30 seconds
  }

  /**
   * Stop heartbeat
   */
  stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  /**
   * Attempt to reconnect after unexpected disconnect
   */
  async attemptReconnect(retryCount = 0, maxRetries = 5) {
    if (retryCount >= maxRetries) {
      console.error('Max reconnection attempts reached');
      this.emit('reconnectFailed');
      return;
    }

    const backoffDelay = Math.min(30000 * Math.pow(2, retryCount), 300000); // Max 5 minutes
    console.log(`Attempting to reconnect in ${backoffDelay}ms (attempt ${retryCount + 1}/${maxRetries})`);

    setTimeout(async () => {
      try {
        await this.connect();
        console.log('Reconnected successfully');
        this.emit('reconnected');
      } catch (error) {
        console.error('Reconnection failed:', error);
        this.attemptReconnect(retryCount + 1, maxRetries);
      }
    }, backoffDelay);
  }

  /**
   * Change target language
   */
  changeLanguage(newLanguage) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'changeLanguage',
        sessionId: this.config.sessionId,
        targetLanguage: newLanguage
      }));
      this.config.targetLanguage = newLanguage;
      this.emit('languageChanged', { language: newLanguage });
    }
  }

  /**
   * Disconnect from session
   */
  disconnect() {
    this.stopHeartbeat();
    
    if (this.ws) {
      this.ws.close(1000, 'Listener disconnected');
      this.ws = null;
    }
    
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
    
    this.connectionStartTime = null;
    this.emit('disconnected');
  }

  /**
   * Event emitter
   */
  on(event, handler) {
    if (!this.eventHandlers[event]) {
      this.eventHandlers[event] = [];
    }
    this.eventHandlers[event].push(handler);
  }

  emit(event, data) {
    if (this.eventHandlers[event]) {
      this.eventHandlers[event].forEach(handler => handler(data));
    }
  }
}

// Usage Example
async function main() {
  const client = new ListenerClient({
    apiEndpoint: 'wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod',
    sessionId: 'golden-eagle-427', // Session ID from speaker
    targetLanguage: 'es' // Spanish
  });

  // Setup event handlers
  client.on('sessionJoined', (data) => {
    console.log('Successfully joined session:', data.sessionId);
    console.log('Listening in:', data.targetLanguage);
  });

  client.on('audioReceived', (data) => {
    console.log('Received audio chunk');
  });

  client.on('sessionEnded', () => {
    console.log('Session has ended');
  });

  client.on('sessionPaused', () => {
    console.log('Session paused by speaker');
  });

  client.on('sessionResumed', () => {
    console.log('Session resumed by speaker');
  });

  client.on('connectionWarning', (data) => {
    console.warn(`Connection will expire in ${data.remainingMinutes} minutes`);
  });

  client.on('connectionRefreshed', () => {
    console.log('Connection refreshed successfully');
  });

  client.on('disconnect', (data) => {
    console.warn('Disconnected unexpectedly:', data.reason);
  });

  client.on('reconnected', () => {
    console.log('Reconnected successfully');
  });

  client.on('error', (error) => {
    console.error('Client error:', error);
  });

  try {
    // Connect and join session
    await client.connect();
    
    // Audio will be played automatically as it's received
    
    // Optional: Change language during session
    // setTimeout(() => {
    //   client.changeLanguage('fr'); // Switch to French
    // }, 60000);
    
  } catch (error) {
    console.error('Failed to join session:', error);
  }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ListenerClient;
}
