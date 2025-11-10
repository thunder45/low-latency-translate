# Design Document

## Overview

The Frontend Client Applications consist of two separate single-page web applications built with React and TypeScript: the Speaker Application for authenticated broadcasters and the Listener Application for anonymous audience members. Both applications share common architectural patterns including WebSocket client management, Web Audio API integration, state management with Zustand, and reusable UI components. The applications are designed for deployment as static sites on AWS S3 + CloudFront with sub-3-second load times and responsive performance across modern browsers.

### Technology Stack

**Core Framework**: React 18+ with TypeScript, Vite build tool  
**State Management**: Zustand (lightweight, performant)  
**WebSocket**: Native WebSocket API with custom wrapper  
**Audio Processing**: Web Audio API (native browser APIs)  
**UI Components**: Custom components with Material-UI base  
**Authentication**: AWS Cognito with amazon-cognito-identity-js  
**Testing**: Jest, React Testing Library, Playwright  
**Deployment**: AWS S3 + CloudFront (static hosting)

### Design Principles

1. **Separation of Concerns**: Distinct layers for UI, business logic, WebSocket communication, and audio processing
2. **Shared Code**: Common utilities and components extracted to shared library
3. **Performance First**: Code splitting, lazy loading, optimized bundle sizes
4. **Accessibility**: WCAG 2.1 Level AA compliance throughout
5. **Error Resilience**: Graceful degradation with automatic recovery
6. **Testability**: Pure functions, dependency injection, comprehensive test coverage

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser Environment                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │ Speaker App      │         │ Listener App     │          │
│  │                  │         │                  │          │
│  │ ┌──────────────┐ │         │ ┌──────────────┐ │          │
│  │ │ UI Layer     │ │         │ │ UI Layer     │ │          │
│  │ └──────┬───────┘ │         │ └──────┬───────┘ │          │
│  │        │         │         │        │         │          │
│  │ ┌──────▼───────┐ │         │ ┌──────▼───────┐ │          │
│  │ │ State Layer  │ │         │ │ State Layer  │ │          │
│  │ └──────┬───────┘ │         │ └──────┬───────┘ │          │
│  │        │         │         │        │         │          │
│  │ ┌──────▼───────┐ │         │ ┌──────▼───────┐ │          │
│  │ │ Service Layer│ │         │ │ Service Layer│ │          │
│  │ └──────┬───────┘ │         │ └──────┬───────┘ │          │
│  └────────┼─────────┘         └────────┼─────────┘          │
│           │                            │                     │
│  ┌────────▼────────────────────────────▼─────────┐          │
│  │         Shared Library                        │          │
│  │  - WebSocket Client                           │          │
│  │  - Audio Utilities                            │          │
│  │  - Common Components                          │          │
│  └────────┬──────────────────────────┬───────────┘          │
│           │                          │                       │
└───────────┼──────────────────────────┼───────────────────────┘
            │                          │
            ▼                          ▼
    ┌───────────────┐          ┌──────────────┐
    │ WebSocket API │          │ Web Audio API│
    │ (Backend)     │          │ (Browser)    │
    └───────────────┘          └──────────────┘
```

### Application Structure

```
frontend-client-apps/
├── shared/                      # Shared library
│   ├── websocket/
│   │   ├── WebSocketClient.ts
│   │   ├── MessageHandler.ts
│   │   └── types.ts
│   ├── audio/
│   │   ├── AudioCapture.ts
│   │   ├── AudioPlayback.ts
│   │   ├── AudioProcessor.ts
│   │   └── types.ts
│   ├── components/
│   │   ├── ConnectionStatus.tsx
│   │   ├── ErrorDisplay.tsx
│   │   └── AudioControls.tsx
│   └── utils/
│       ├── storage.ts
│       ├── retry.ts
│       └── validation.ts
├── speaker-app/
│   ├── src/
│   │   ├── components/
│   │   ├── services/
│   │   ├── store/
│   │   ├── hooks/
│   │   └── App.tsx
│   └── package.json
└── listener-app/
    ├── src/
    │   ├── components/
    │   ├── services/
    │   ├── store/
    │   ├── hooks/
    │   └── App.tsx
    └── package.json
```


## Components and Interfaces

### Shared WebSocket Client

The WebSocket client provides a unified interface for both applications with automatic reconnection, heartbeat management, and message routing.

```typescript
// shared/websocket/types.ts
export interface WebSocketConfig {
  url: string;
  token?: string;  // For speaker authentication
  reconnect: boolean;
  maxReconnectAttempts: number;
  reconnectDelay: number;  // Initial delay in ms
  heartbeatInterval: number;  // Default 30000ms
}

export interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

export interface ConnectionState {
  status: 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'failed';
  connectionId: string | null;
  lastHeartbeat: number | null;
  reconnectAttempts: number;
}

// shared/websocket/WebSocketClient.ts
export class WebSocketClient {
  private ws: WebSocket | null = null;
  private config: WebSocketConfig;
  private state: ConnectionState;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private messageHandlers: Map<string, (message: WebSocketMessage) => void>;
  private reconnectTimer: NodeJS.Timeout | null = null;

  constructor(config: WebSocketConfig) {
    this.config = config;
    this.state = {
      status: 'disconnected',
      connectionId: null,
      lastHeartbeat: null,
      reconnectAttempts: 0
    };
    this.messageHandlers = new Map();
  }

  async connect(queryParams: Record<string, string>): Promise<void> {
    const url = this.buildUrl(queryParams);
    this.state.status = 'connecting';
    
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(url);
      
      this.ws.onopen = () => {
        this.state.status = 'connected';
        this.state.reconnectAttempts = 0;
        this.startHeartbeat();
        resolve();
      };
      
      this.ws.onmessage = (event) => {
        this.handleMessage(JSON.parse(event.data));
      };
      
      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };
      
      this.ws.onclose = () => {
        this.handleDisconnect();
      };
    });
  }

  send(message: WebSocketMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      throw new Error('WebSocket not connected');
    }
  }

  on(messageType: string, handler: (message: WebSocketMessage) => void): void {
    this.messageHandlers.set(messageType, handler);
  }

  disconnect(): void {
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }
    this.ws?.close();
    this.state.status = 'disconnected';
  }

  getState(): ConnectionState {
    return { ...this.state };
  }

  private buildUrl(queryParams: Record<string, string>): string {
    const params = new URLSearchParams(queryParams);
    return `${this.config.url}?${params.toString()}`;
  }

  private handleMessage(message: WebSocketMessage): void {
    // Handle heartbeat ack
    if (message.type === 'heartbeatAck') {
      this.state.lastHeartbeat = Date.now();
      return;
    }

    // Route to registered handler
    const handler = this.messageHandlers.get(message.type);
    if (handler) {
      handler(message);
    }
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      this.send({
        action: 'heartbeat',
        timestamp: Date.now()
      });

      // Check if heartbeat ack received within 5 seconds
      setTimeout(() => {
        const timeSinceLastHeartbeat = Date.now() - (this.state.lastHeartbeat || 0);
        if (timeSinceLastHeartbeat > 5000) {
          console.warn('Heartbeat timeout, reconnecting...');
          this.handleDisconnect();
        }
      }, 5000);
    }, this.config.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private handleDisconnect(): void {
    this.stopHeartbeat();
    this.state.status = 'disconnected';

    if (this.config.reconnect && this.state.reconnectAttempts < this.config.maxReconnectAttempts) {
      this.attemptReconnect();
    } else {
      this.state.status = 'failed';
    }
  }

  private attemptReconnect(): void {
    this.state.status = 'reconnecting';
    this.state.reconnectAttempts++;

    const delay = Math.min(
      this.config.reconnectDelay * Math.pow(2, this.state.reconnectAttempts - 1),
      30000  // Max 30 seconds
    );

    this.reconnectTimer = setTimeout(() => {
      // Reconnect logic handled by application layer
      // Emit reconnect event for application to handle
    }, delay);
  }
}
```

### Audio Capture Service (Speaker)

```typescript
// shared/audio/types.ts
export interface AudioCaptureConfig {
  sampleRate: number;  // 16000
  channelCount: number;  // 1 (mono)
  chunkDuration: number;  // 1-3 seconds
  echoCancellation: boolean;
  noiseSuppression: boolean;
  autoGainControl: boolean;
}

export interface AudioChunk {
  data: string;  // Base64-encoded PCM
  timestamp: number;
  chunkId: string;
  duration: number;
}

// shared/audio/AudioCapture.ts
export class AudioCapture {
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private config: AudioCaptureConfig;
  private chunkCounter: number = 0;
  private onChunkCallback: ((chunk: AudioChunk) => void) | null = null;

  constructor(config: AudioCaptureConfig) {
    this.config = config;
  }

  async start(): Promise<void> {
    // Request microphone permission
    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: this.config.echoCancellation,
        noiseSuppression: this.config.noiseSuppression,
        autoGainControl: this.config.autoGainControl,
        sampleRate: this.config.sampleRate,
        channelCount: this.config.channelCount
      }
    });

    // Create audio context
    this.audioContext = new AudioContext({ sampleRate: this.config.sampleRate });
    this.source = this.audioContext.createMediaStreamSource(this.mediaStream);

    // Calculate buffer size for chunk duration
    const bufferSize = this.config.sampleRate * this.config.chunkDuration;
    this.processor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);

    this.processor.onaudioprocess = (e) => {
      const audioData = e.inputBuffer.getChannelData(0);
      const chunk = this.processAudioChunk(audioData);
      
      if (this.onChunkCallback) {
        this.onChunkCallback(chunk);
      }
    };

    this.source.connect(this.processor);
    this.processor.connect(this.audioContext.destination);
  }

  stop(): void {
    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }
    if (this.source) {
      this.source.disconnect();
      this.source = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop());
      this.mediaStream = null;
    }
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
  }

  onChunk(callback: (chunk: AudioChunk) => void): void {
    this.onChunkCallback = callback;
  }

  getInputLevel(): number {
    // Return current input level (0-100)
    // Implementation would analyze current audio buffer
    return 0;
  }

  private processAudioChunk(audioData: Float32Array): AudioChunk {
    // Convert Float32 to PCM 16-bit
    const pcm16 = new Int16Array(audioData.length);
    for (let i = 0; i < audioData.length; i++) {
      const s = Math.max(-1, Math.min(1, audioData[i]));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }

    // Convert to base64
    const bytes = new Uint8Array(pcm16.buffer);
    const base64 = btoa(String.fromCharCode(...bytes));

    return {
      data: base64,
      timestamp: Date.now(),
      chunkId: `chunk-${++this.chunkCounter}`,
      duration: this.config.chunkDuration
    };
  }
}
```


### Audio Playback Service (Listener)

```typescript
// shared/audio/AudioPlayback.ts
export class AudioPlayback {
  private audioContext: AudioContext | null = null;
  private audioQueue: AudioBuffer[] = [];
  private isPlaying: boolean = false;
  private isPaused: boolean = false;
  private isMuted: boolean = false;
  private volume: number = 1.0;  // 0.0 to 1.0
  private gainNode: GainNode | null = null;
  private currentSource: AudioBufferSourceNode | null = null;

  async initialize(): Promise<void> {
    this.audioContext = new AudioContext();
    this.gainNode = this.audioContext.createGain();
    this.gainNode.connect(this.audioContext.destination);
    this.gainNode.gain.value = this.volume;
  }

  async playAudio(audioMessage: {
    audioData: string;
    sampleRate: number;
    channels: number;
  }): Promise<void> {
    if (!this.audioContext || !this.gainNode) {
      throw new Error('AudioPlayback not initialized');
    }

    // Decode base64 to audio samples
    const audioBytes = atob(audioMessage.audioData);
    const audioData = new Int16Array(audioBytes.length / 2);
    
    for (let i = 0; i < audioData.length; i++) {
      const byte1 = audioBytes.charCodeAt(i * 2);
      const byte2 = audioBytes.charCodeAt(i * 2 + 1);
      audioData[i] = (byte2 << 8) | byte1;  // Little-endian
    }

    // Create AudioBuffer
    const audioBuffer = this.audioContext.createBuffer(
      audioMessage.channels,
      audioData.length,
      audioMessage.sampleRate
    );

    // Convert PCM to Float32 and copy to buffer
    const channelData = audioBuffer.getChannelData(0);
    for (let i = 0; i < audioData.length; i++) {
      channelData[i] = audioData[i] / 32768.0;  // Normalize to -1.0 to 1.0
    }

    // Queue for playback
    this.audioQueue.push(audioBuffer);
    
    if (!this.isPaused) {
      this.schedulePlayback();
    }
  }

  pause(): void {
    this.isPaused = true;
    if (this.currentSource) {
      this.currentSource.stop();
      this.currentSource = null;
    }
    this.isPlaying = false;
  }

  resume(): void {
    this.isPaused = false;
    this.schedulePlayback();
  }

  setMuted(muted: boolean): void {
    this.isMuted = muted;
    if (this.gainNode) {
      this.gainNode.gain.value = muted ? 0 : this.volume;
    }
  }

  setVolume(volume: number): void {
    this.volume = Math.max(0, Math.min(1, volume));
    if (this.gainNode && !this.isMuted) {
      this.gainNode.gain.value = this.volume;
    }
  }

  clearBuffer(): void {
    this.audioQueue = [];
  }

  getBufferDuration(): number {
    return this.audioQueue.reduce((total, buffer) => total + buffer.duration, 0);
  }

  getQueueLength(): number {
    return this.audioQueue.length;
  }

  private schedulePlayback(): void {
    if (this.isPaused || this.isPlaying || this.audioQueue.length === 0) {
      return;
    }

    const buffer = this.audioQueue.shift()!;
    this.currentSource = this.audioContext!.createBufferSource();
    this.currentSource.buffer = buffer;
    this.currentSource.connect(this.gainNode!);
    
    this.currentSource.onended = () => {
      this.isPlaying = false;
      this.currentSource = null;
      this.schedulePlayback();
    };

    this.currentSource.start();
    this.isPlaying = true;
  }

  destroy(): void {
    this.pause();
    this.clearBuffer();
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
  }
}
```

### State Management (Zustand)

```typescript
// speaker-app/src/store/speakerStore.ts
import create from 'zustand';

export interface ListenerInfo {
  connectionId: string;
  targetLanguage: string;
  isPaused: boolean;
  isMuted: boolean;
}

export interface QualityWarning {
  issue: 'snr_low' | 'clipping' | 'echo' | 'silence';
  message: string;
  details: Record<string, any>;
  timestamp: number;
}

interface SpeakerState {
  // Session
  sessionId: string | null;
  connectionId: string | null;
  sourceLanguage: string | null;
  qualityTier: 'standard' | 'premium';
  isConnected: boolean;
  
  // Audio
  isPaused: boolean;
  isMuted: boolean;
  inputVolume: number;
  isTransmitting: boolean;
  inputLevel: number;
  
  // Quality
  qualityWarnings: QualityWarning[];
  
  // Listeners
  listenerCount: number;
  languageDistribution: Record<string, number>;
  
  // Connection
  connectionDuration: number;
  needsRefresh: boolean;
  refreshing: boolean;
  
  // Actions
  setSession: (sessionId: string, connectionId: string, sourceLanguage: string) => void;
  setConnected: (connected: boolean) => void;
  setPaused: (paused: boolean) => void;
  setMuted: (muted: boolean) => void;
  setInputVolume: (volume: number) => void;
  setTransmitting: (transmitting: boolean) => void;
  setInputLevel: (level: number) => void;
  addQualityWarning: (warning: QualityWarning) => void;
  clearQualityWarnings: () => void;
  updateListenerStats: (count: number, distribution: Record<string, number>) => void;
  setNeedsRefresh: (needs: boolean) => void;
  setRefreshing: (refreshing: boolean) => void;
  reset: () => void;
}

export const useSpeakerStore = create<SpeakerState>((set) => ({
  // Initial state
  sessionId: null,
  connectionId: null,
  sourceLanguage: null,
  qualityTier: 'standard',
  isConnected: false,
  isPaused: false,
  isMuted: false,
  inputVolume: 80,
  isTransmitting: false,
  inputLevel: 0,
  qualityWarnings: [],
  listenerCount: 0,
  languageDistribution: {},
  connectionDuration: 0,
  needsRefresh: false,
  refreshing: false,
  
  // Actions
  setSession: (sessionId, connectionId, sourceLanguage) =>
    set({ sessionId, connectionId, sourceLanguage }),
  
  setConnected: (connected) =>
    set({ isConnected: connected }),
  
  setPaused: (paused) =>
    set({ isPaused: paused }),
  
  setMuted: (muted) =>
    set({ isMuted: muted }),
  
  setInputVolume: (volume) =>
    set({ inputVolume: Math.max(0, Math.min(100, volume)) }),
  
  setTransmitting: (transmitting) =>
    set({ isTransmitting: transmitting }),
  
  setInputLevel: (level) =>
    set({ inputLevel: level }),
  
  addQualityWarning: (warning) =>
    set((state) => ({
      qualityWarnings: [...state.qualityWarnings, warning]
    })),
  
  clearQualityWarnings: () =>
    set({ qualityWarnings: [] }),
  
  updateListenerStats: (count, distribution) =>
    set({ listenerCount: count, languageDistribution: distribution }),
  
  setNeedsRefresh: (needs) =>
    set({ needsRefresh: needs }),
  
  setRefreshing: (refreshing) =>
    set({ refreshing: refreshing }),
  
  reset: () =>
    set({
      sessionId: null,
      connectionId: null,
      sourceLanguage: null,
      isConnected: false,
      isPaused: false,
      isMuted: false,
      isTransmitting: false,
      inputLevel: 0,
      qualityWarnings: [],
      listenerCount: 0,
      languageDistribution: {},
      connectionDuration: 0,
      needsRefresh: false,
      refreshing: false
    })
}));
```

```typescript
// listener-app/src/store/listenerStore.ts
import create from 'zustand';

interface ListenerState {
  // Session
  sessionId: string | null;
  connectionId: string | null;
  sourceLanguage: string | null;
  targetLanguage: string | null;
  isConnected: boolean;
  
  // Audio
  isPaused: boolean;
  isMuted: boolean;
  playbackVolume: number;
  
  // Buffer
  bufferedDuration: number;
  isBuffering: boolean;
  bufferOverflow: boolean;
  
  // Speaker state
  speakerPaused: boolean;
  speakerMuted: boolean;
  
  // Connection
  connectionDuration: number;
  needsRefresh: boolean;
  refreshing: boolean;
  
  // Actions
  setSession: (sessionId: string, connectionId: string, sourceLanguage: string, targetLanguage: string) => void;
  setConnected: (connected: boolean) => void;
  setPaused: (paused: boolean) => void;
  setMuted: (muted: boolean) => void;
  setPlaybackVolume: (volume: number) => void;
  setTargetLanguage: (language: string) => void;
  setBufferedDuration: (duration: number) => void;
  setBuffering: (buffering: boolean) => void;
  setBufferOverflow: (overflow: boolean) => void;
  setSpeakerPaused: (paused: boolean) => void;
  setSpeakerMuted: (muted: boolean) => void;
  setNeedsRefresh: (needs: boolean) => void;
  setRefreshing: (refreshing: boolean) => void;
  reset: () => void;
}

export const useListenerStore = create<ListenerState>((set) => ({
  // Initial state
  sessionId: null,
  connectionId: null,
  sourceLanguage: null,
  targetLanguage: null,
  isConnected: false,
  isPaused: false,
  isMuted: false,
  playbackVolume: 80,
  bufferedDuration: 0,
  isBuffering: false,
  bufferOverflow: false,
  speakerPaused: false,
  speakerMuted: false,
  connectionDuration: 0,
  needsRefresh: false,
  refreshing: false,
  
  // Actions
  setSession: (sessionId, connectionId, sourceLanguage, targetLanguage) =>
    set({ sessionId, connectionId, sourceLanguage, targetLanguage }),
  
  setConnected: (connected) =>
    set({ isConnected: connected }),
  
  setPaused: (paused) =>
    set({ isPaused: paused }),
  
  setMuted: (muted) =>
    set({ isMuted: muted }),
  
  setPlaybackVolume: (volume) =>
    set({ playbackVolume: Math.max(0, Math.min(100, volume)) }),
  
  setTargetLanguage: (language) =>
    set({ targetLanguage: language }),
  
  setBufferedDuration: (duration) =>
    set({ bufferedDuration: duration }),
  
  setBuffering: (buffering) =>
    set({ isBuffering: buffering }),
  
  setBufferOverflow: (overflow) =>
    set({ bufferOverflow: overflow }),
  
  setSpeakerPaused: (paused) =>
    set({ speakerPaused: paused }),
  
  setSpeakerMuted: (muted) =>
    set({ speakerMuted: muted }),
  
  setNeedsRefresh: (needs) =>
    set({ needsRefresh: needs }),
  
  setRefreshing: (refreshing) =>
    set({ refreshing: refreshing }),
  
  reset: () =>
    set({
      sessionId: null,
      connectionId: null,
      sourceLanguage: null,
      targetLanguage: null,
      isConnected: false,
      isPaused: false,
      isMuted: false,
      bufferedDuration: 0,
      isBuffering: false,
      bufferOverflow: false,
      speakerPaused: false,
      speakerMuted: false,
      connectionDuration: 0,
      needsRefresh: false,
      refreshing: false
    })
}));
```


### Authentication Service (Speaker)

```typescript
// speaker-app/src/services/AuthService.ts
import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserSession
} from 'amazon-cognito-identity-js';

export interface AuthConfig {
  userPoolId: string;
  clientId: string;
}

export interface AuthTokens {
  idToken: string;
  accessToken: string;
  refreshToken: string;
}

export class AuthService {
  private userPool: CognitoUserPool;
  private currentUser: CognitoUser | null = null;

  constructor(config: AuthConfig) {
    this.userPool = new CognitoUserPool({
      UserPoolId: config.userPoolId,
      ClientId: config.clientId
    });
  }

  async signIn(email: string, password: string): Promise<AuthTokens> {
    const authDetails = new AuthenticationDetails({
      Username: email,
      Password: password
    });

    const cognitoUser = new CognitoUser({
      Username: email,
      Pool: this.userPool
    });

    return new Promise((resolve, reject) => {
      cognitoUser.authenticateUser(authDetails, {
        onSuccess: (result: CognitoUserSession) => {
          this.currentUser = cognitoUser;
          resolve({
            idToken: result.getIdToken().getJwtToken(),
            accessToken: result.getAccessToken().getJwtToken(),
            refreshToken: result.getRefreshToken().getToken()
          });
        },
        onFailure: (err) => {
          reject(err);
        }
      });
    });
  }

  async refreshSession(): Promise<AuthTokens> {
    if (!this.currentUser) {
      throw new Error('No user session to refresh');
    }

    return new Promise((resolve, reject) => {
      this.currentUser!.getSession((err: Error | null, session: CognitoUserSession | null) => {
        if (err || !session) {
          reject(err || new Error('Failed to get session'));
          return;
        }

        if (session.isValid()) {
          resolve({
            idToken: session.getIdToken().getJwtToken(),
            accessToken: session.getAccessToken().getJwtToken(),
            refreshToken: session.getRefreshToken().getToken()
          });
        } else {
          reject(new Error('Session is not valid'));
        }
      });
    });
  }

  signOut(): void {
    if (this.currentUser) {
      this.currentUser.signOut();
      this.currentUser = null;
    }
  }

  getCurrentUser(): CognitoUser | null {
    return this.userPool.getCurrentUser();
  }
}
```

### UI Components

```typescript
// shared/components/ConnectionStatus.tsx
import React from 'react';

interface ConnectionStatusProps {
  status: 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'failed';
  reconnectAttempts?: number;
  maxAttempts?: number;
  onRetry?: () => void;
}

export const ConnectionStatus: React.FC<ConnectionStatusProps> = ({
  status,
  reconnectAttempts = 0,
  maxAttempts = 5,
  onRetry
}) => {
  const getStatusColor = () => {
    switch (status) {
      case 'connected': return 'green';
      case 'connecting': return 'yellow';
      case 'reconnecting': return 'orange';
      case 'disconnected':
      case 'failed': return 'red';
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'connected': return 'Connected';
      case 'connecting': return 'Connecting...';
      case 'reconnecting': return `Reconnecting... (${reconnectAttempts}/${maxAttempts})`;
      case 'disconnected': return 'Disconnected';
      case 'failed': return 'Connection Failed';
    }
  };

  return (
    <div className="connection-status" style={{ color: getStatusColor() }}>
      <span className="status-indicator" />
      <span className="status-text">{getStatusText()}</span>
      {(status === 'failed' || status === 'disconnected') && onRetry && (
        <button onClick={onRetry} className="retry-button">
          Retry Now
        </button>
      )}
    </div>
  );
};
```

```typescript
// speaker-app/src/components/SessionDisplay.tsx
import React, { useState } from 'react';

interface SessionDisplayProps {
  sessionId: string;
  listenerCount: number;
  languageDistribution: Record<string, number>;
}

export const SessionDisplay: React.FC<SessionDisplayProps> = ({
  sessionId,
  listenerCount,
  languageDistribution
}) => {
  const [copied, setCopied] = useState(false);

  const copySessionId = () => {
    navigator.clipboard.writeText(sessionId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="session-display">
      <div className="session-id-container">
        <h2>Session ID</h2>
        <div className="session-id" onClick={copySessionId}>
          {sessionId}
          {copied && <span className="copied-indicator">Copied!</span>}
        </div>
      </div>
      
      <div className="listener-stats">
        <div className="listener-count">
          <span className="count">{listenerCount}</span>
          <span className="label">Active Listeners</span>
        </div>
        
        <div className="language-distribution">
          <h3>Languages</h3>
          <ul>
            {Object.entries(languageDistribution).map(([lang, count]) => (
              <li key={lang}>
                <span className="language">{lang.toUpperCase()}</span>
                <span className="count">{count}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};
```

```typescript
// speaker-app/src/components/AudioVisualizer.tsx
import React, { useEffect, useRef } from 'react';

interface AudioVisualizerProps {
  inputLevel: number;  // 0-100
  qualityWarnings: Array<{
    issue: string;
    message: string;
  }>;
}

export const AudioVisualizer: React.FC<AudioVisualizerProps> = ({
  inputLevel,
  qualityWarnings
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw level meter
    const barWidth = (canvas.width * inputLevel) / 100;
    const color = inputLevel > 95 ? 'red' : inputLevel > 80 ? 'yellow' : 'green';
    
    ctx.fillStyle = color;
    ctx.fillRect(0, 0, barWidth, canvas.height);
  }, [inputLevel]);

  return (
    <div className="audio-visualizer">
      <canvas ref={canvasRef} width={300} height={50} />
      <div className="level-indicator">{inputLevel}%</div>
      
      {qualityWarnings.length > 0 && (
        <div className="quality-warnings">
          {qualityWarnings.map((warning, idx) => (
            <div key={idx} className={`warning warning-${warning.issue}`}>
              {warning.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
```

```typescript
// listener-app/src/components/SessionJoiner.tsx
import React, { useState } from 'react';

interface SessionJoinerProps {
  onJoin: (sessionId: string, targetLanguage: string) => void;
  availableLanguages: string[];
}

export const SessionJoiner: React.FC<SessionJoinerProps> = ({
  onJoin,
  availableLanguages
}) => {
  const [sessionId, setSessionId] = useState('');
  const [targetLanguage, setTargetLanguage] = useState('es');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (sessionId.trim()) {
      onJoin(sessionId.trim(), targetLanguage);
    }
  };

  return (
    <form className="session-joiner" onSubmit={handleSubmit}>
      <h2>Join Session</h2>
      
      <div className="form-group">
        <label htmlFor="sessionId">Session ID</label>
        <input
          id="sessionId"
          type="text"
          value={sessionId}
          onChange={(e) => setSessionId(e.target.value)}
          placeholder="e.g., golden-eagle-427"
          required
          aria-label="Session ID"
        />
      </div>
      
      <div className="form-group">
        <label htmlFor="targetLanguage">Your Language</label>
        <select
          id="targetLanguage"
          value={targetLanguage}
          onChange={(e) => setTargetLanguage(e.target.value)}
          aria-label="Target language"
        >
          {availableLanguages.map(lang => (
            <option key={lang} value={lang}>
              {lang.toUpperCase()}
            </option>
          ))}
        </select>
      </div>
      
      <button type="submit" className="join-button">
        Join Session
      </button>
    </form>
  );
};
```


## Data Models

### WebSocket Message Types

```typescript
// Shared message types
export interface BaseMessage {
  type: string;
  timestamp: number;
}

// Speaker → Server
export interface SendAudioMessage {
  action: 'sendAudio';
  audioData: string;  // Base64-encoded PCM
  timestamp: number;
  chunkId: string;
}

export interface PauseBroadcastMessage {
  action: 'pauseBroadcast';
  sessionId: string;
}

export interface EndSessionMessage {
  action: 'endSession';
  sessionId: string;
  reason: string;
}

export interface GetSessionStatusMessage {
  action: 'getSessionStatus';
  sessionId: string;
}

// Server → Speaker
export interface SessionCreatedMessage extends BaseMessage {
  type: 'sessionCreated';
  sessionId: string;
  sourceLanguage: string;
  qualityTier: string;
  connectionId: string;
  expiresAt: number;
}

export interface AudioQualityWarningMessage extends BaseMessage {
  type: 'audio_quality_warning';
  issue: 'snr_low' | 'clipping' | 'echo' | 'silence';
  message: string;
  details: Record<string, any>;
}

export interface SessionStatusMessage extends BaseMessage {
  type: 'sessionStatus';
  sessionId: string;
  isActive: boolean;
  listenerCount: number;
  languageDistribution: Record<string, number>;
  sessionDuration: number;
  createdAt: number;
  expiresAt: number;
}

// Listener → Server
export interface SwitchLanguageMessage {
  action: 'switchLanguage';
  targetLanguage: string;
}

// Server → Listener
export interface SessionJoinedMessage extends BaseMessage {
  type: 'sessionJoined';
  sessionId: string;
  targetLanguage: string;
  sourceLanguage: string;
  connectionId: string;
  listenerCount: number;
  qualityTier: string;
}

export interface AudioMessage extends BaseMessage {
  type: 'audio';
  audioData: string;  // Base64-encoded PCM
  format: 'pcm';
  sampleRate: number;
  channels: number;
  sequenceNumber: number;
}

export interface SpeakerStateMessage extends BaseMessage {
  type: 'speakerPaused' | 'speakerMuted' | 'speakerResumed' | 'speakerUnmuted';
}

// Common messages
export interface ConnectionRefreshRequiredMessage extends BaseMessage {
  type: 'connectionRefreshRequired';
  refreshBy: number;
}

export interface SessionEndedMessage extends BaseMessage {
  type: 'sessionEnded';
  sessionId: string;
  reason: string;
}

export interface ErrorMessage extends BaseMessage {
  type: 'error';
  code: number;
  message: string;
  retryAfter?: number;
}
```

### Local Storage Schema

```typescript
// Speaker preferences
export interface SpeakerPreferences {
  inputVolume: number;  // 0-100
  keyboardShortcuts: {
    mute: string;  // e.g., "Ctrl+M"
    pause: string;  // e.g., "Ctrl+P"
  };
}

// Listener preferences
export interface ListenerPreferences {
  playbackVolume: number;  // 0-100
  languagePreference: string;  // ISO 639-1
  keyboardShortcuts: {
    mute: string;
    pause: string;
    volumeUp: string;
    volumeDown: string;
  };
}

// Storage keys
export const STORAGE_KEYS = {
  SPEAKER_AUTH_TOKEN: 'speaker_auth_token',
  SPEAKER_REFRESH_TOKEN: 'speaker_refresh_token',
  SPEAKER_PREFERENCES: 'speaker_preferences',
  LISTENER_PREFERENCES: 'listener_preferences'
};
```

## Error Handling

### Error Types and Recovery Strategies

```typescript
// shared/utils/errors.ts
export enum ErrorType {
  AUTHENTICATION_FAILED = 'AUTHENTICATION_FAILED',
  SESSION_NOT_FOUND = 'SESSION_NOT_FOUND',
  SESSION_FULL = 'SESSION_FULL',
  RATE_LIMITED = 'RATE_LIMITED',
  NETWORK_ERROR = 'NETWORK_ERROR',
  MICROPHONE_PERMISSION_DENIED = 'MICROPHONE_PERMISSION_DENIED',
  AUDIO_FORMAT_NOT_SUPPORTED = 'AUDIO_FORMAT_NOT_SUPPORTED',
  HEARTBEAT_TIMEOUT = 'HEARTBEAT_TIMEOUT',
  CONNECTION_REFRESH_FAILED = 'CONNECTION_REFRESH_FAILED'
}

export interface AppError {
  type: ErrorType;
  message: string;
  userMessage: string;
  recoverable: boolean;
  retryable: boolean;
  retryAfter?: number;
}

export class ErrorHandler {
  static handle(error: AppError): {
    displayMessage: string;
    actions: Array<{ label: string; handler: () => void }>;
  } {
    switch (error.type) {
      case ErrorType.AUTHENTICATION_FAILED:
        return {
          displayMessage: 'Authentication failed. Please log in again.',
          actions: [{ label: 'Go to Login', handler: () => window.location.href = '/login' }]
        };
      
      case ErrorType.SESSION_NOT_FOUND:
        return {
          displayMessage: 'Session not found. Please check the session ID.',
          actions: [{ label: 'Try Again', handler: () => window.location.reload() }]
        };
      
      case ErrorType.SESSION_FULL:
        return {
          displayMessage: 'Session is full (500 listeners). Try again later.',
          actions: [
            { label: 'Retry', handler: () => window.location.reload() },
            { label: 'Join Another Session', handler: () => window.location.href = '/' }
          ]
        };
      
      case ErrorType.RATE_LIMITED:
        return {
          displayMessage: `Too many attempts. Please wait ${error.retryAfter || 60} seconds.`,
          actions: []
        };
      
      case ErrorType.NETWORK_ERROR:
        return {
          displayMessage: 'Connection lost. Reconnecting...',
          actions: [{ label: 'Retry Now', handler: () => window.location.reload() }]
        };
      
      case ErrorType.MICROPHONE_PERMISSION_DENIED:
        return {
          displayMessage: 'Microphone access required. Please enable in browser settings.',
          actions: [{ label: 'Learn How', handler: () => window.open('/help/microphone') }]
        };
      
      case ErrorType.HEARTBEAT_TIMEOUT:
        return {
          displayMessage: 'Connection timeout. Attempting to reconnect...',
          actions: []
        };
      
      default:
        return {
          displayMessage: 'An unexpected error occurred. Please try again.',
          actions: [{ label: 'Reload', handler: () => window.location.reload() }]
        };
    }
  }
}
```

### Retry Logic

```typescript
// shared/utils/retry.ts
export interface RetryConfig {
  maxAttempts: number;
  initialDelay: number;  // milliseconds
  maxDelay: number;  // milliseconds
  backoffMultiplier: number;
}

export class RetryHandler {
  private attempts: number = 0;
  private config: RetryConfig;

  constructor(config: RetryConfig) {
    this.config = config;
  }

  async execute<T>(
    operation: () => Promise<T>,
    onRetry?: (attempt: number, delay: number) => void
  ): Promise<T> {
    while (this.attempts < this.config.maxAttempts) {
      try {
        const result = await operation();
        this.attempts = 0;  // Reset on success
        return result;
      } catch (error) {
        this.attempts++;
        
        if (this.attempts >= this.config.maxAttempts) {
          throw error;
        }
        
        const delay = Math.min(
          this.config.initialDelay * Math.pow(this.config.backoffMultiplier, this.attempts - 1),
          this.config.maxDelay
        );
        
        if (onRetry) {
          onRetry(this.attempts, delay);
        }
        
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
    
    throw new Error('Max retry attempts exceeded');
  }

  reset(): void {
    this.attempts = 0;
  }

  getAttempts(): number {
    return this.attempts;
  }
}
```

## Testing Strategy

### Unit Tests

**Test Coverage Areas**:
1. WebSocket client message handling
2. Audio processing utilities (PCM conversion, base64 encoding/decoding)
3. State management actions and selectors
4. Error handling and retry logic
5. Storage utilities (encryption, persistence)
6. Component rendering and user interactions

**Example Test**:
```typescript
// shared/audio/__tests__/AudioCapture.test.ts
import { AudioCapture } from '../AudioCapture';

describe('AudioCapture', () => {
  let audioCapture: AudioCapture;

  beforeEach(() => {
    audioCapture = new AudioCapture({
      sampleRate: 16000,
      channelCount: 1,
      chunkDuration: 2,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true
    });
  });

  afterEach(() => {
    audioCapture.stop();
  });

  it('should convert Float32 audio to PCM 16-bit correctly', () => {
    const float32Data = new Float32Array([0.5, -0.5, 1.0, -1.0]);
    const chunk = audioCapture['processAudioChunk'](float32Data);
    
    expect(chunk.data).toBeDefined();
    expect(chunk.timestamp).toBeGreaterThan(0);
    expect(chunk.chunkId).toMatch(/^chunk-\d+$/);
  });

  it('should handle microphone permission denial', async () => {
    // Mock getUserMedia to reject
    global.navigator.mediaDevices.getUserMedia = jest.fn()
      .mockRejectedValue(new Error('Permission denied'));
    
    await expect(audioCapture.start()).rejects.toThrow('Permission denied');
  });
});
```

### Integration Tests

**Test Scenarios**:
1. Complete speaker flow: login → create session → broadcast → end
2. Complete listener flow: join → listen → controls → leave
3. Connection refresh flow
4. Error recovery scenarios
5. Multi-tab testing (multiple listeners)

**Example Test**:
```typescript
// speaker-app/src/__tests__/integration/SpeakerFlow.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../../App';

describe('Speaker Flow Integration', () => {
  it('should complete full speaker workflow', async () => {
    const user = userEvent.setup();
    render(<App />);
    
    // Login
    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.type(screen.getByLabelText(/password/i), 'password123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    
    // Wait for session creation page
    await waitFor(() => {
      expect(screen.getByText(/create session/i)).toBeInTheDocument();
    });
    
    // Create session
    await user.click(screen.getByRole('button', { name: /create session/i }));
    
    // Verify session ID displayed
    await waitFor(() => {
      expect(screen.getByText(/session id/i)).toBeInTheDocument();
    });
    
    // Test pause control
    const pauseButton = screen.getByRole('button', { name: /pause/i });
    await user.click(pauseButton);
    expect(pauseButton).toHaveAttribute('aria-pressed', 'true');
    
    // End session
    await user.click(screen.getByRole('button', { name: /end session/i }));
    
    await waitFor(() => {
      expect(screen.getByText(/session ended/i)).toBeInTheDocument();
    });
  });
});
```

### End-to-End Tests

**Test Tools**: Playwright or Cypress

**Test Scenarios**:
1. Cross-browser compatibility (Chrome, Firefox, Safari, Edge)
2. Mobile responsiveness
3. Network condition simulation (slow 3G, packet loss)
4. Concurrent user testing
5. Performance benchmarks

**Example Test**:
```typescript
// e2e/speaker-listener.spec.ts
import { test, expect } from '@playwright/test';

test('speaker and listener can communicate', async ({ browser }) => {
  // Create two browser contexts (speaker and listener)
  const speakerContext = await browser.newContext();
  const listenerContext = await browser.newContext();
  
  const speakerPage = await speakerContext.newPage();
  const listenerPage = await listenerContext.newPage();
  
  // Speaker: Login and create session
  await speakerPage.goto('http://localhost:3000/speaker');
  await speakerPage.fill('[name="email"]', 'test@example.com');
  await speakerPage.fill('[name="password"]', 'password123');
  await speakerPage.click('button:has-text("Sign In")');
  
  await speakerPage.waitForSelector('button:has-text("Create Session")');
  await speakerPage.click('button:has-text("Create Session")');
  
  // Get session ID
  const sessionId = await speakerPage.textContent('.session-id');
  expect(sessionId).toBeTruthy();
  
  // Listener: Join session
  await listenerPage.goto('http://localhost:3000/listener');
  await listenerPage.fill('[name="sessionId"]', sessionId!);
  await listenerPage.selectOption('[name="targetLanguage"]', 'es');
  await listenerPage.click('button:has-text("Join Session")');
  
  // Verify listener joined
  await listenerPage.waitForSelector('text=Connected');
  
  // Verify speaker sees listener count
  await expect(speakerPage.locator('.listener-count')).toContainText('1');
  
  // Cleanup
  await speakerContext.close();
  await listenerContext.close();
});
```


### Performance Tests

**Metrics to Track**:
- Time to Interactive (TTI) < 3 seconds
- First Contentful Paint (FCP) < 1.5 seconds
- Largest Contentful Paint (LCP) < 2.5 seconds
- Cumulative Layout Shift (CLS) < 0.1
- First Input Delay (FID) < 100ms
- Bundle size < 500KB (gzipped)

**Tools**: Lighthouse, WebPageTest, Chrome DevTools

## Deployment Architecture

### Build Configuration

```typescript
// vite.config.ts (shared configuration)
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { visualizer } from 'rollup-plugin-visualizer';

export default defineConfig({
  plugins: [
    react(),
    visualizer({
      filename: './dist/stats.html',
      open: false,
      gzipSize: true
    })
  ],
  build: {
    target: 'es2020',
    minify: 'terser',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          'audio-vendor': ['amazon-cognito-identity-js'],
          'state-vendor': ['zustand']
        }
      }
    },
    chunkSizeWarningLimit: 500
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'zustand']
  }
});
```

### AWS S3 + CloudFront Deployment

**Infrastructure**:
```yaml
# CloudFormation template (simplified)
Resources:
  SpeakerAppBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: speaker-app-frontend
      WebsiteConfiguration:
        IndexDocument: index.html
        ErrorDocument: index.html
      PublicAccessBlockConfiguration:
        BlockPublicAcls: false
        BlockPublicPolicy: false
        IgnorePublicAcls: false
        RestrictPublicBuckets: false

  SpeakerAppBucketPolicy:
    Type: AWS::S3::BucketPolicy
    Properties:
      Bucket: !Ref SpeakerAppBucket
      PolicyDocument:
        Statement:
          - Effect: Allow
            Principal: '*'
            Action: 's3:GetObject'
            Resource: !Sub '${SpeakerAppBucket.Arn}/*'

  SpeakerAppDistribution:
    Type: AWS::CloudFront::Distribution
    Properties:
      DistributionConfig:
        Enabled: true
        DefaultRootObject: index.html
        Origins:
          - Id: S3Origin
            DomainName: !GetAtt SpeakerAppBucket.DomainName
            S3OriginConfig:
              OriginAccessIdentity: ''
        DefaultCacheBehavior:
          TargetOriginId: S3Origin
          ViewerProtocolPolicy: redirect-to-https
          AllowedMethods: [GET, HEAD, OPTIONS]
          CachedMethods: [GET, HEAD]
          ForwardedValues:
            QueryString: false
            Cookies:
              Forward: none
          Compress: true
          MinTTL: 0
          DefaultTTL: 86400
          MaxTTL: 31536000
        CustomErrorResponses:
          - ErrorCode: 404
            ResponseCode: 200
            ResponsePagePath: /index.html
          - ErrorCode: 403
            ResponseCode: 200
            ResponsePagePath: /index.html
        PriceClass: PriceClass_100
        ViewerCertificate:
          CloudFrontDefaultCertificate: true

  # Similar resources for ListenerAppBucket and ListenerAppDistribution
```

### Deployment Script

```bash
#!/bin/bash
# deploy.sh

APP_NAME=$1  # "speaker" or "listener"
ENVIRONMENT=$2  # "dev", "staging", "prod"

if [ -z "$APP_NAME" ] || [ -z "$ENVIRONMENT" ]; then
  echo "Usage: ./deploy.sh <speaker|listener> <dev|staging|prod>"
  exit 1
fi

# Build application
cd ${APP_NAME}-app
npm run build

# Upload to S3
aws s3 sync dist/ s3://${APP_NAME}-app-${ENVIRONMENT}/ --delete

# Invalidate CloudFront cache
DISTRIBUTION_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Origins.Items[0].DomainName=='${APP_NAME}-app-${ENVIRONMENT}.s3.amazonaws.com'].Id" \
  --output text)

aws cloudfront create-invalidation \
  --distribution-id $DISTRIBUTION_ID \
  --paths "/*"

echo "Deployment complete for ${APP_NAME}-app to ${ENVIRONMENT}"
```

## Security Considerations

### Content Security Policy

```html
<!-- index.html -->
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  connect-src 'self' wss://*.execute-api.*.amazonaws.com https://cognito-idp.*.amazonaws.com;
  script-src 'self' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data:;
  font-src 'self';
  media-src 'self';
">
```

### Token Storage

```typescript
// shared/utils/storage.ts
import CryptoJS from 'crypto-js';

const ENCRYPTION_KEY = process.env.VITE_ENCRYPTION_KEY || 'default-key';

export class SecureStorage {
  static set(key: string, value: string): void {
    const encrypted = CryptoJS.AES.encrypt(value, ENCRYPTION_KEY).toString();
    localStorage.setItem(key, encrypted);
  }

  static get(key: string): string | null {
    const encrypted = localStorage.getItem(key);
    if (!encrypted) return null;

    try {
      const decrypted = CryptoJS.AES.decrypt(encrypted, ENCRYPTION_KEY);
      return decrypted.toString(CryptoJS.enc.Utf8);
    } catch (error) {
      console.error('Failed to decrypt storage value:', error);
      return null;
    }
  }

  static remove(key: string): void {
    localStorage.removeItem(key);
  }

  static clear(): void {
    localStorage.clear();
  }
}
```

### Input Validation

```typescript
// shared/utils/validation.ts
export class Validator {
  static isValidSessionId(sessionId: string): boolean {
    // Format: word-word-number (e.g., "golden-eagle-427")
    return /^[a-z]+-[a-z]+-\d+$/.test(sessionId);
  }

  static isValidLanguageCode(code: string): boolean {
    // ISO 639-1 format (2 lowercase letters)
    return /^[a-z]{2}$/.test(code);
  }

  static isValidEmail(email: string): boolean {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }

  static sanitizeInput(input: string): string {
    // Remove potentially dangerous characters
    return input.replace(/[<>'"]/g, '');
  }
}
```

## Accessibility Implementation

### Keyboard Navigation

```typescript
// shared/hooks/useKeyboardShortcuts.ts
import { useEffect } from 'react';

export interface KeyboardShortcut {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  handler: () => void;
  description: string;
}

export const useKeyboardShortcuts = (shortcuts: KeyboardShortcut[]) => {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      for (const shortcut of shortcuts) {
        const ctrlMatch = shortcut.ctrlKey === undefined || shortcut.ctrlKey === event.ctrlKey;
        const metaMatch = shortcut.metaKey === undefined || shortcut.metaKey === event.metaKey;
        
        if (event.key === shortcut.key && ctrlMatch && metaMatch) {
          event.preventDefault();
          shortcut.handler();
          break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [shortcuts]);
};

// Usage in Speaker App
const shortcuts: KeyboardShortcut[] = [
  {
    key: 'm',
    ctrlKey: true,
    handler: () => toggleMute(),
    description: 'Toggle mute'
  },
  {
    key: 'p',
    ctrlKey: true,
    handler: () => togglePause(),
    description: 'Toggle pause'
  }
];

useKeyboardShortcuts(shortcuts);
```

### ARIA Labels and Screen Reader Support

```typescript
// Example: Accessible button component
interface AccessibleButtonProps {
  onClick: () => void;
  ariaLabel: string;
  ariaPressed?: boolean;
  children: React.ReactNode;
}

export const AccessibleButton: React.FC<AccessibleButtonProps> = ({
  onClick,
  ariaLabel,
  ariaPressed,
  children
}) => {
  return (
    <button
      onClick={onClick}
      aria-label={ariaLabel}
      aria-pressed={ariaPressed}
      className="accessible-button"
    >
      {children}
    </button>
  );
};
```

### Focus Management

```typescript
// shared/hooks/useFocusTrap.ts
import { useEffect, useRef } from 'react';

export const useFocusTrap = (isActive: boolean) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isActive || !containerRef.current) return;

    const container = containerRef.current;
    const focusableElements = container.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );

    const firstElement = focusableElements[0] as HTMLElement;
    const lastElement = focusableElements[focusableElements.length - 1] as HTMLElement;

    const handleTabKey = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          lastElement.focus();
          e.preventDefault();
        }
      } else {
        if (document.activeElement === lastElement) {
          firstElement.focus();
          e.preventDefault();
        }
      }
    };

    container.addEventListener('keydown', handleTabKey);
    firstElement?.focus();

    return () => container.removeEventListener('keydown', handleTabKey);
  }, [isActive]);

  return containerRef;
};
```

## Monitoring and Analytics

### CloudWatch RUM Integration

```typescript
// shared/monitoring/rum.ts
import { AwsRum, AwsRumConfig } from 'aws-rum-web';

export const initializeRUM = (appName: string) => {
  try {
    const config: AwsRumConfig = {
      sessionSampleRate: 1.0,
      guestRoleArn: process.env.VITE_RUM_GUEST_ROLE_ARN!,
      identityPoolId: process.env.VITE_RUM_IDENTITY_POOL_ID!,
      endpoint: process.env.VITE_RUM_ENDPOINT!,
      telemetries: ['performance', 'errors', 'http'],
      allowCookies: true,
      enableXRay: true
    };

    const awsRum = new AwsRum(
      appName,
      '1.0.0',
      process.env.VITE_AWS_REGION!,
      config
    );

    return awsRum;
  } catch (error) {
    console.error('Failed to initialize RUM:', error);
    return null;
  }
};

// Custom metrics
export const recordCustomMetric = (
  rum: AwsRum | null,
  metricName: string,
  value: number
) => {
  if (!rum) return;
  
  rum.recordEvent(metricName, {
    value,
    timestamp: Date.now()
  });
};
```

### Performance Monitoring

```typescript
// shared/monitoring/performance.ts
export class PerformanceMonitor {
  static recordPageLoad(): void {
    if (!window.performance) return;

    const perfData = window.performance.timing;
    const pageLoadTime = perfData.loadEventEnd - perfData.navigationStart;
    const connectTime = perfData.responseEnd - perfData.requestStart;
    const renderTime = perfData.domComplete - perfData.domLoading;

    console.log('Performance Metrics:', {
      pageLoadTime,
      connectTime,
      renderTime
    });

    // Send to monitoring service
    this.sendMetrics({
      pageLoadTime,
      connectTime,
      renderTime
    });
  }

  static recordAudioLatency(sendTime: number, receiveTime: number): void {
    const latency = receiveTime - sendTime;
    console.log('Audio Latency:', latency, 'ms');
    
    this.sendMetrics({ audioLatency: latency });
  }

  private static sendMetrics(metrics: Record<string, number>): void {
    // Implementation would send to CloudWatch or other monitoring service
  }
}
```

## Browser Compatibility Strategy

### Feature Detection

```typescript
// shared/utils/browserSupport.ts
export class BrowserSupport {
  static checkWebSocketSupport(): boolean {
    return 'WebSocket' in window;
  }

  static checkWebAudioSupport(): boolean {
    return 'AudioContext' in window || 'webkitAudioContext' in window;
  }

  static checkMediaDevicesSupport(): boolean {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  }

  static checkLocalStorageSupport(): boolean {
    try {
      const test = '__storage_test__';
      localStorage.setItem(test, test);
      localStorage.removeItem(test);
      return true;
    } catch (e) {
      return false;
    }
  }

  static checkAllRequirements(): {
    supported: boolean;
    missing: string[];
  } {
    const missing: string[] = [];

    if (!this.checkWebSocketSupport()) missing.push('WebSocket');
    if (!this.checkWebAudioSupport()) missing.push('Web Audio API');
    if (!this.checkMediaDevicesSupport()) missing.push('MediaDevices API');
    if (!this.checkLocalStorageSupport()) missing.push('LocalStorage');

    return {
      supported: missing.length === 0,
      missing
    };
  }
}

// Usage in App.tsx
const { supported, missing } = BrowserSupport.checkAllRequirements();

if (!supported) {
  return (
    <div className="unsupported-browser">
      <h1>Browser Not Supported</h1>
      <p>Your browser is missing the following required features:</p>
      <ul>
        {missing.map(feature => <li key={feature}>{feature}</li>)}
      </ul>
      <p>Please use a modern browser (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)</p>
    </div>
  );
}
```

## Design Decisions and Rationales

### 1. React + TypeScript
**Decision**: Use React 18 with TypeScript  
**Rationale**: React provides excellent performance with hooks and concurrent features. TypeScript adds type safety, reducing runtime errors and improving developer experience. Large ecosystem and community support.

### 2. Zustand for State Management
**Decision**: Use Zustand instead of Redux or Context API  
**Rationale**: Zustand is lightweight (1KB), has minimal boilerplate, excellent TypeScript support, and sufficient for our state complexity. Avoids Redux overhead while being more performant than Context API for frequent updates.

### 3. Native WebSocket API
**Decision**: Use native WebSocket API instead of Socket.io or similar libraries  
**Rationale**: Backend uses API Gateway WebSocket which doesn't support Socket.io protocol. Native API is sufficient for our needs, reduces bundle size, and provides full control over connection management.

### 4. Web Audio API (Native)
**Decision**: Use native Web Audio API instead of libraries like Howler.js  
**Rationale**: We need low-level control over audio processing (PCM conversion, real-time streaming). Native API provides best performance and smallest bundle size. Libraries add unnecessary overhead for our use case.

### 5. Vite Build Tool
**Decision**: Use Vite instead of Create React App or Webpack  
**Rationale**: Vite provides faster development server (HMR), faster builds, better tree-shaking, and modern defaults. Simpler configuration than Webpack while being more performant than CRA.

### 6. Separate Applications
**Decision**: Build separate Speaker and Listener apps instead of single app with routing  
**Rationale**: Different user types (authenticated vs anonymous), different feature sets, allows independent deployment and optimization. Reduces bundle size for each user type.

### 7. S3 + CloudFront Deployment
**Decision**: Use S3 + CloudFront instead of Amplify Hosting or EC2  
**Rationale**: Most cost-effective for static sites, excellent global performance with CDN, simple deployment, automatic HTTPS, and scales infinitely. Amplify adds unnecessary cost for our needs.

### 8. Component-Based Architecture
**Decision**: Use component-based architecture with shared library  
**Rationale**: Promotes code reuse between Speaker and Listener apps, easier testing, better maintainability, and allows independent development of features.

## Future Enhancements

### Phase 2 Features
1. **Mobile Applications**: React Native apps for iOS and Android
2. **Closed Captions**: Real-time text display of translations
3. **Recording**: Save sessions for later playback
4. **Analytics Dashboard**: Detailed session analytics for speakers
5. **Custom Branding**: White-label options for enterprise customers
6. **Advanced Audio Controls**: Equalizer, noise gate, compressor
7. **Multi-Speaker Support**: Panel discussions with multiple speakers
8. **Chat Integration**: Text chat alongside audio translation

### Technical Improvements
1. **AudioWorklet**: Replace ScriptProcessorNode for better performance
2. **WebRTC**: Explore WebRTC for lower latency audio streaming
3. **Progressive Web App**: Add PWA support for offline capabilities
4. **Service Worker**: Implement caching strategies for faster loads
5. **WebAssembly**: Use WASM for audio processing performance
6. **GraphQL**: Consider GraphQL for more efficient data fetching
