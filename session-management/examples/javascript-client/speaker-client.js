/**
 * Speaker Client Example
 * 
 * This example demonstrates how to implement a speaker client that:
 * - Authenticates with Cognito
 * - Creates a WebSocket session
 * - Handles connection refresh for unlimited session duration
 * - Manages audio streaming
 * - Handles errors and reconnection
 */

class SpeakerClient {
  constructor(config) {
    this.config = {
      apiEndpoint: config.apiEndpoint, // wss://abc123.execute-api.us-east-1.amazonaws.com/prod
      cognitoUserPoolId: config.cognitoUserPoolId,
      cognitoClientId: config.cognitoClientId,
      sourceLanguage: config.sourceLanguage || 'en',
      qualityTier: config.qualityTier || 'standard',
      ...config
    };
    
    this.ws = null;
    this.sessionId = null;
    this.connectionStartTime = null;
    this.refreshThreshold = 100 * 60 * 1000; // 100 minutes in milliseconds
    this.isRefreshing = false;
    this.audioQueue = [];
    this.eventHandlers = {};
  }

  /**
   * Authenticate with Cognito and get JWT token
   */
  async authenticate(username, password) {
    try {
      // Using AWS SDK for JavaScript v3
      const { CognitoIdentityProviderClient, InitiateAuthCommand } = require('@aws-sdk/client-cognito-identity-provider');
      
      const client = new CognitoIdentityProviderClient({ region: this.config.region || 'us-east-1' });
      
      const command = new InitiateAuthCommand({
        AuthFlow: 'USER_PASSWORD_AUTH',
        ClientId: this.config.cognitoClientId,
        AuthParameters: {
          USERNAME: username,
          PASSWORD: password
        }
      });
      
      const response = await client.send(command);
      this.jwtToken = response.AuthenticationResult.IdToken;
      
      console.log('Authentication successful');
      return this.jwtToken;
    } catch (error) {
      console.error('Authentication failed:', error);
      throw error;
    }
  }

  /**
   * Connect to WebSocket and create session
   */
  async connect() {
    if (!this.jwtToken) {
      throw new Error('Must authenticate before connecting');
    }

    return new Promise((resolve, reject) => {
      const wsUrl = `${this.config.apiEndpoint}?action=createSession&sourceLanguage=${this.config.sourceLanguage}&qualityTier=${this.config.qualityTier}&token=${this.jwtToken}`;
      
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
        case 'sessionCreated':
          this.sessionId = message.sessionId;
          console.log('Session created:', this.sessionId);
          this.emit('sessionCreated', message);
          resolve(message);
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
      // 1. Establish new connection while keeping old one active
      const newWsUrl = `${this.config.apiEndpoint}?action=refreshConnection&sessionId=${this.sessionId}&role=speaker&token=${this.jwtToken}`;
      const newWs = new WebSocket(newWsUrl);

      newWs.onopen = () => {
        console.log('New connection established');
      };

      newWs.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        
        if (msg.type === 'connectionRefreshComplete') {
          console.log('Connection refresh complete');
          
          // 2. Switch audio streaming to new connection
          this.switchToNewConnection(newWs);
          
          // 3. Close old connection gracefully
          this.ws.close(1000, 'Connection refresh');
          
          // 4. Update reference to new connection
          this.ws = newWs;
          this.connectionStartTime = Date.now();
          this.isRefreshing = false;
          
          this.emit('connectionRefreshed', { sessionId: this.sessionId });
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
   * Switch audio streaming to new connection
   */
  switchToNewConnection(newWs) {
    // Flush any queued audio to old connection
    while (this.audioQueue.length > 0) {
      const audioData = this.audioQueue.shift();
      if (this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(audioData);
      }
    }

    // Setup new connection for audio streaming
    newWs.onmessage = this.ws.onmessage;
    newWs.onerror = this.ws.onerror;
    newWs.onclose = this.ws.onclose;
  }

  /**
   * Send audio data to server
   */
  sendAudio(audioData) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message = JSON.stringify({
        action: 'sendAudio',
        sessionId: this.sessionId,
        audioData: audioData // Base64 encoded audio
      });
      
      this.ws.send(message);
    } else {
      console.warn('WebSocket not ready, queueing audio');
      this.audioQueue.push(audioData);
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
   * Pause audio streaming
   */
  pause() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'controlSession',
        sessionId: this.sessionId,
        command: 'pause'
      }));
      this.emit('paused');
    }
  }

  /**
   * Resume audio streaming
   */
  resume() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'controlSession',
        sessionId: this.sessionId,
        command: 'resume'
      }));
      this.emit('resumed');
    }
  }

  /**
   * End session and disconnect
   */
  disconnect() {
    this.stopHeartbeat();
    
    if (this.ws) {
      this.ws.close(1000, 'Session ended by speaker');
      this.ws = null;
    }
    
    this.sessionId = null;
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
  const client = new SpeakerClient({
    apiEndpoint: 'wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod',
    cognitoUserPoolId: 'us-east-1_ABC123XYZ',
    cognitoClientId: '1a2b3c4d5e6f7g8h9i0j',
    sourceLanguage: 'en',
    qualityTier: 'standard'
  });

  // Setup event handlers
  client.on('sessionCreated', (data) => {
    console.log('Session ID:', data.sessionId);
    console.log('Share this ID with listeners:', data.sessionId);
  });

  client.on('connectionWarning', (data) => {
    console.warn(`Connection will expire in ${data.remainingMinutes} minutes`);
  });

  client.on('connectionRefreshed', (data) => {
    console.log('Connection refreshed successfully');
  });

  client.on('error', (error) => {
    console.error('Client error:', error);
  });

  try {
    // Authenticate
    await client.authenticate('username', 'password');
    
    // Connect and create session
    await client.connect();
    
    // Start streaming audio (example with Web Audio API)
    const audioContext = new AudioContext();
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const source = audioContext.createMediaStreamSource(stream);
    
    // Process and send audio chunks
    // (Implementation depends on your audio processing pipeline)
    
  } catch (error) {
    console.error('Failed to start session:', error);
  }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = SpeakerClient;
}
