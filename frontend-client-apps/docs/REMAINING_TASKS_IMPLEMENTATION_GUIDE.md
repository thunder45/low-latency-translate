# Implementation Guide for Remaining Speaker-Listener Controls Tasks

## Overview

This document provides detailed guidance for implementing the remaining tasks (4-7, 12-18) for the speaker-listener controls feature. Tasks 1-3, 8-11 have been completed.

## Completed Tasks Summary

✅ Task 1: Core data models and types (`shared/types/controls.ts`)
✅ Task 2: CircularAudioBuffer class (`shared/audio/CircularAudioBuffer.ts`)
✅ Task 3: PreferenceStore service (`shared/services/PreferenceStore.ts`)
✅ Task 8: LanguageSelector service (`shared/services/LanguageSelector.ts`)
✅ Task 9: SpeakerControls UI component (`shared/components/SpeakerControls.tsx`)
✅ Task 10: ListenerControls UI component (`shared/components/ListenerControls.tsx`)
✅ Task 11: KeyboardShortcutManager (`shared/services/KeyboardShortcutManager.ts`)

## Remaining Tasks

### Task 4: Implement AudioManager for speakers

**Approach**: Extend existing `SpeakerService` class rather than creating a new AudioManager.

**File to modify**: `speaker-app/src/services/SpeakerService.ts`

**Implementation**:

```typescript
// Add to SpeakerService class:

private isPaused: boolean = false;
private isMuted: boolean = false;
private inputVolume: number = 75;

/**
 * Pause audio transmission
 */
async pause(): Promise<void> {
  if (this.isPaused) return;
  
  this.isPaused = true;
  this.audioCapture.pause(); // Add pause method to AudioCapture
  useSpeakerStore.getState().setPaused(true);
  
  // Notify listeners via WebSocket
  this.wsClient.send({
    action: 'speakerStateChange',
    state: { isPaused: true }
  });
}

/**
 * Resume audio transmission
 */
async resume(): Promise<void> {
  if (!this.isPaused) return;
  
  this.isPaused = false;
  this.audioCapture.resume(); // Add resume method to AudioCapture
  useSpeakerStore.getState().setPaused(false);
  
  // Notify listeners via WebSocket
  this.wsClient.send({
    action: 'speakerStateChange',
    state: { isPaused: false }
  });
}

/**
 * Mute microphone
 */
async mute(): Promise<void> {
  if (this.isMuted) return;
  
  this.isMuted = true;
  this.audioCapture.mute(); // Add mute method to AudioCapture
  useSpeakerStore.getState().setMuted(true);
  
  // Notify listeners via WebSocket
  this.wsClient.send({
    action: 'speakerStateChange',
    state: { isMuted: true }
  });
}

/**
 * Unmute microphone
 */
async unmute(): Promise<void> {
  if (!this.isMuted) return;
  
  this.isMuted = false;
  this.audioCapture.unmute(); // Add unmute method to AudioCapture
  useSpeakerStore.getState().setMuted(false);
  
  // Notify listeners via WebSocket
  this.wsClient.send({
    action: 'speakerStateChange',
    state: { isMuted: false }
  });
}

/**
 * Set input volume
 */
async setVolume(volume: number): Promise<void> {
  const clampedVolume = Math.max(0, Math.min(100, volume));
  this.inputVolume = clampedVolume;
  this.audioCapture.setVolume(clampedVolume / 100); // Normalize to 0-1
  useSpeakerStore.getState().setInputVolume(clampedVolume);
  
  // Save preference
  if (this.userId) {
    await preferenceStore.saveVolume(this.userId, clampedVolume);
  }
}
```

**Also modify**: `shared/audio/AudioCapture.ts` to add pause/resume/mute/setVolume methods.

---

### Task 5: Implement AudioManager for listeners

**Approach**: Extend existing `ListenerService` class and integrate CircularAudioBuffer.

**File to modify**: `listener-app/src/services/ListenerService.ts`

**Implementation**:

```typescript
import { CircularAudioBuffer } from '../../../shared/audio/CircularAudioBuffer';

// Add to ListenerService class:

private isPaused: boolean = false;
private isMuted: boolean = false;
private playbackVolume: number = 75;
private audioBuffer: CircularAudioBuffer;

constructor(config: ListenerServiceConfig) {
  // ... existing code ...
  
  // Initialize circular buffer (24kHz sample rate, 30 seconds)
  this.audioBuffer = new CircularAudioBuffer(24000, 30000);
}

/**
 * Pause audio playback
 */
async pause(): Promise<void> {
  if (this.isPaused) return;
  
  this.isPaused = true;
  this.audioPlayback.pause(); // Add pause method to AudioPlayback
  useListenerStore.getState().setPaused(true);
  
  // Start buffering incoming audio
  this.startBuffering();
}

/**
 * Resume audio playback
 */
async resume(): Promise<void> {
  if (!this.isPaused) return;
  
  this.isPaused = false;
  
  // Play buffered audio first
  await this.playBufferedAudio();
  
  this.audioPlayback.resume(); // Add resume method to AudioPlayback
  useListenerStore.getState().setPaused(false);
  
  // Stop buffering
  this.stopBuffering();
}

/**
 * Start buffering incoming audio
 */
private startBuffering(): void {
  // Intercept audio chunks and write to buffer
  this.onAudioChunk = (chunk: Float32Array) => {
    const isNearCapacity = this.audioBuffer.write(chunk);
    
    if (isNearCapacity) {
      console.warn('Audio buffer near capacity');
      // Optionally notify user
    }
  };
}

/**
 * Stop buffering
 */
private stopBuffering(): void {
  this.onAudioChunk = null;
  this.audioBuffer.clear();
}

/**
 * Play buffered audio
 */
private async playBufferedAudio(): Promise<void> {
  const bufferedDuration = this.audioBuffer.getBufferedDuration();
  
  if (bufferedDuration > 0) {
    const audioData = this.audioBuffer.read(bufferedDuration);
    await this.audioPlayback.playBuffer(audioData);
  }
}

/**
 * Mute audio playback
 */
async mute(): Promise<void> {
  if (this.isMuted) return;
  
  this.isMuted = true;
  this.audioPlayback.setVolume(0);
  useListenerStore.getState().setMuted(true);
}

/**
 * Unmute audio playback
 */
async unmute(): Promise<void> {
  if (!this.isMuted) return;
  
  this.isMuted = false;
  this.audioPlayback.setVolume(this.playbackVolume / 100);
  useListenerStore.getState().setMuted(false);
}

/**
 * Set playback volume
 */
async setVolume(volume: number): Promise<void> {
  const clampedVolume = Math.max(0, Math.min(100, volume));
  this.playbackVolume = clampedVolume;
  
  if (!this.isMuted) {
    this.audioPlayback.setVolume(clampedVolume / 100);
  }
  
  useListenerStore.getState().setVolume(clampedVolume);
  
  // Save preference
  if (this.userId) {
    await preferenceStore.saveVolume(this.userId, clampedVolume);
  }
}
```

**Also modify**: `shared/audio/AudioPlayback.ts` to add pause/resume/playBuffer methods.

---

### Task 6: Implement ControlStateManager service

**Approach**: Create new service that manages control state synchronization.

**File to create**: `shared/services/ControlStateManager.ts`

**Implementation**:

```typescript
import type { AudioState, SessionState } from '../types/controls';

export class ControlStateManager {
  private wsClient: WebSocketClient;
  private sessionStates: Map<string, SessionState> = new Map();
  private stateChangeCallbacks: Map<string, Function[]> = new Map();
  
  constructor(wsClient: WebSocketClient) {
    this.wsClient = wsClient;
    this.setupMessageHandlers();
  }
  
  /**
   * Update speaker state
   */
  async updateSpeakerState(
    sessionId: string,
    userId: string,
    state: Partial<AudioState>
  ): Promise<void> {
    // Send state update via WebSocket
    this.wsClient.send({
      action: 'updateSpeakerState',
      sessionId,
      userId,
      state
    });
    
    // Update local cache
    this.updateLocalState(sessionId, 'speaker', state);
  }
  
  /**
   * Update listener state
   */
  async updateListenerState(
    sessionId: string,
    userId: string,
    state: Partial<AudioState>
  ): Promise<void> {
    // Send state update via WebSocket
    this.wsClient.send({
      action: 'updateListenerState',
      sessionId,
      userId,
      state
    });
    
    // Update local cache
    this.updateLocalState(sessionId, userId, state);
  }
  
  /**
   * Get session state
   */
  async getSessionState(sessionId: string): Promise<SessionState> {
    return this.sessionStates.get(sessionId) || {
      sessionId,
      speakerState: { isPaused: false, isMuted: false, volume: 75, timestamp: Date.now() },
      listenerStates: new Map(),
      activeListenerCount: 0
    };
  }
  
  /**
   * Subscribe to speaker state changes
   */
  subscribeToSpeakerState(
    sessionId: string,
    callback: (state: AudioState) => void
  ): () => void {
    const key = `speaker_${sessionId}`;
    const callbacks = this.stateChangeCallbacks.get(key) || [];
    callbacks.push(callback);
    this.stateChangeCallbacks.set(key, callbacks);
    
    // Return unsubscribe function
    return () => {
      const cbs = this.stateChangeCallbacks.get(key) || [];
      const index = cbs.indexOf(callback);
      if (index > -1) {
        cbs.splice(index, 1);
      }
    };
  }
  
  // ... similar methods for listener state subscription ...
  
  private setupMessageHandlers(): void {
    this.wsClient.on('speakerStateChange', (data) => {
      this.handleSpeakerStateChange(data);
    });
    
    this.wsClient.on('listenerStateChange', (data) => {
      this.handleListenerStateChange(data);
    });
  }
  
  private handleSpeakerStateChange(data: any): void {
    // Update local state and notify subscribers
    const { sessionId, state } = data;
    this.updateLocalState(sessionId, 'speaker', state);
    this.notifySubscribers(`speaker_${sessionId}`, state);
  }
  
  // ... similar handlers for listener state ...
}
```

---

### Task 7: Implement NotificationService

**Approach**: This is largely handled by WebSocket message routing. Create a thin wrapper.

**File to create**: `shared/services/NotificationService.ts`

**Implementation**:

```typescript
import type { Notification } from '../types/controls';

export class NotificationService {
  private wsClient: WebSocketClient;
  private subscriptions: Map<string, Function[]> = new Map();
  
  constructor(wsClient: WebSocketClient) {
    this.wsClient = wsClient;
    this.setupHandlers();
  }
  
  /**
   * Notify speaker state change
   */
  async notifySpeakerStateChange(sessionId: string, state: AudioState): Promise<void> {
    this.wsClient.send({
      action: 'notifySpeakerState',
      sessionId,
      state
    });
  }
  
  /**
   * Subscribe to session notifications
   */
  subscribeToSession(
    sessionId: string,
    callback: (notification: Notification) => void
  ): () => void {
    const callbacks = this.subscriptions.get(sessionId) || [];
    callbacks.push(callback);
    this.subscriptions.set(sessionId, callbacks);
    
    return () => {
      const cbs = this.subscriptions.get(sessionId) || [];
      const index = cbs.indexOf(callback);
      if (index > -1) {
        cbs.splice(index, 1);
      }
    };
  }
  
  private setupHandlers(): void {
    this.wsClient.on('notification', (data) => {
      const notification: Notification = {
        type: data.type,
        sessionId: data.sessionId,
        userId: data.userId,
        data: data.data,
        timestamp: Date.now()
      };
      
      this.notifySubscribers(data.sessionId, notification);
    });
  }
  
  private notifySubscribers(sessionId: string, notification: Notification): void {
    const callbacks = this.subscriptions.get(sessionId) || [];
    callbacks.forEach(cb => {
      try {
        cb(notification);
      } catch (error) {
        console.error('Error in notification callback:', error);
      }
    });
  }
}
```

---

### Task 12: Implement error handling and recovery

**Approach**: Create error handling utilities and integrate throughout.

**File to create**: `shared/utils/ControlErrorHandler.ts`

**Implementation**:

```typescript
import type { ControlError, ControlErrorType } from '../types/controls';

export class ControlErrorHandler {
  /**
   * Retry with exponential backoff
   */
  static async retryWithBackoff(
    operation: () => Promise<void>,
    maxAttempts: number = 3
  ): Promise<void> {
    let attempt = 0;
    let delay = 1000;
    
    while (attempt < maxAttempts) {
      try {
        await operation();
        return;
      } catch (error) {
        attempt++;
        if (attempt >= maxAttempts) {
          throw error;
        }
        await new Promise(resolve => setTimeout(resolve, delay));
        delay *= 2;
      }
    }
  }
  
  /**
   * Handle control error
   */
  static handleError(error: ControlError): void {
    console.error(`Control error [${error.type}]:`, error.message);
    
    // Display user-friendly error message
    if (error.recoverable) {
      this.showRecoverableError(error);
    } else {
      this.showFatalError(error);
    }
  }
  
  private static showRecoverableError(error: ControlError): void {
    // Show toast notification or inline error
    // Implementation depends on UI framework
  }
  
  private static showFatalError(error: ControlError): void {
    // Show modal or redirect to error page
    // Implementation depends on UI framework
  }
}
```

---

### Task 13: Integrate components with state management

**Approach**: Wire up UI components in speaker and listener apps.

**File to modify**: `speaker-app/src/App.tsx` (or main component)

**Implementation**:

```typescript
import { SpeakerControls } from '../../shared/components/SpeakerControls';
import { useSpeakerStore } from '../../shared/store/speakerStore';
import { keyboardShortcutManager } from '../../shared/services/KeyboardShortcutManager';

function SpeakerApp() {
  const speakerService = useSpeakerService(); // Get from context or hook
  const {
    isPaused,
    isMuted,
    inputVolume,
    listenerCount,
    sessionId
  } = useSpeakerStore();
  
  useEffect(() => {
    // Initialize keyboard shortcuts
    keyboardShortcutManager.initialize(userId);
    keyboardShortcutManager.registerHandler('pause', () => speakerService.togglePause());
    keyboardShortcutManager.registerHandler('mute', () => speakerService.toggleMute());
    
    return () => {
      keyboardShortcutManager.destroy();
    };
  }, []);
  
  return (
    <div>
      {/* ... other components ... */}
      
      <SpeakerControls
        sessionId={sessionId}
        onPauseToggle={() => speakerService.togglePause()}
        onMuteToggle={() => speakerService.toggleMute()}
        onVolumeChange={(vol) => speakerService.setVolume(vol)}
        isPaused={isPaused}
        isMuted={isMuted}
        volume={inputVolume}
        listenerCount={listenerCount}
      />
    </div>
  );
}
```

Similar integration for `listener-app/src/App.tsx` with ListenerControls component.

---

### Task 14: Implement preference persistence flow

**Approach**: Load preferences on mount, save on changes.

**Implementation** (in SpeakerService/ListenerService):

```typescript
async initialize(): Promise<void> {
  // ... existing initialization ...
  
  // Load saved preferences
  const savedVolume = await preferenceStore.getVolume(this.userId);
  if (savedVolume !== null) {
    await this.setVolume(savedVolume);
  }
  
  const savedLanguage = await preferenceStore.getLanguage(this.userId);
  if (savedLanguage !== null && this.languageSelector) {
    await this.languageSelector.switchLanguage(this.sessionId, savedLanguage);
  }
}
```

---

### Task 15: Add performance optimizations

**Already implemented**:
- Volume slider debouncing (50ms) in UI components
- React.memo can be added to components if needed

**Additional optimizations**:

```typescript
// In UI components, add React.memo:
export const SpeakerControls = React.memo<SpeakerControlsProps>(({ ... }) => {
  // ... component code ...
});

// Throttle listener state updates in ControlStateManager:
private throttleStateUpdate = throttle((sessionId: string, state: AudioState) => {
  this.updateListenerState(sessionId, this.userId, state);
}, 1000);
```

---

### Task 16: Add monitoring and logging

**Approach**: Add metrics collection throughout control operations.

**Implementation**:

```typescript
// In SpeakerService/ListenerService:

private logControlLatency(operation: string, startTime: number): void {
  const latency = Date.now() - startTime;
  console.log(`Control latency [${operation}]: ${latency}ms`);
  
  // Send to monitoring service
  if (latency > 100) {
    console.warn(`Control latency exceeded target: ${latency}ms`);
  }
}

async pause(): Promise<void> {
  const startTime = Date.now();
  // ... pause logic ...
  this.logControlLatency('pause', startTime);
}
```

---

### Task 17: Create integration tests

**File to create**: `shared/__tests__/integration/controls.test.ts`

**Implementation**:

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { SpeakerService } from '../../../speaker-app/src/services/SpeakerService';
import { ListenerService } from '../../../listener-app/src/services/ListenerService';

describe('Speaker Controls Integration', () => {
  let speakerService: SpeakerService;
  
  beforeEach(() => {
    speakerService = new SpeakerService(mockConfig);
  });
  
  it('should pause and notify listeners', async () => {
    await speakerService.pause();
    
    expect(speakerService.isPaused).toBe(true);
    // Verify WebSocket message sent
    // Verify store updated
  });
  
  it('should mute within 50ms', async () => {
    const startTime = Date.now();
    await speakerService.mute();
    const elapsed = Date.now() - startTime;
    
    expect(elapsed).toBeLessThan(50);
    expect(speakerService.isMuted).toBe(true);
  });
});

describe('Listener Controls Integration', () => {
  let listenerService: ListenerService;
  
  beforeEach(() => {
    listenerService = new ListenerService(mockConfig);
  });
  
  it('should pause and start buffering', async () => {
    await listenerService.pause();
    
    expect(listenerService.isPaused).toBe(true);
    // Verify buffer is receiving data
  });
  
  it('should switch language within 500ms', async () => {
    const startTime = Date.now();
    await listenerService.switchLanguage('es');
    const elapsed = Date.now() - startTime;
    
    expect(elapsed).toBeLessThan(500);
  });
});
```

---

### Task 18: Create end-to-end tests

**File to create**: `e2e/speaker-listener-controls.spec.ts`

**Implementation**:

```typescript
import { test, expect } from '@playwright/test';

test.describe('Speaker Controls E2E', () => {
  test('complete speaker session flow', async ({ page }) => {
    // Navigate to speaker app
    await page.goto('/speaker');
    
    // Create session
    await page.click('[data-testid="create-session"]');
    
    // Pause broadcast
    await page.click('[data-testid="pause-button"]');
    await expect(page.locator('[data-testid="pause-button"]')).toHaveAttribute('aria-pressed', 'true');
    
    // Mute microphone
    await page.click('[data-testid="mute-button"]');
    await expect(page.locator('[data-testid="mute-button"]')).toHaveAttribute('aria-pressed', 'true');
    
    // Adjust volume
    await page.locator('[data-testid="volume-slider"]').fill('50');
    await expect(page.locator('[data-testid="volume-display"]')).toHaveText('50%');
    
    // Verify listener count updates
    await expect(page.locator('[data-testid="listener-count"]')).toContainText('0');
  });
  
  test('keyboard shortcuts work', async ({ page }) => {
    await page.goto('/speaker');
    await page.click('[data-testid="create-session"]');
    
    // Press M to mute
    await page.keyboard.press('KeyM');
    await expect(page.locator('[data-testid="mute-button"]')).toHaveAttribute('aria-pressed', 'true');
    
    // Press P to pause
    await page.keyboard.press('KeyP');
    await expect(page.locator('[data-testid="pause-button"]')).toHaveAttribute('aria-pressed', 'true');
  });
});

test.describe('Listener Controls E2E', () => {
  test('complete listener session flow', async ({ page }) => {
    // Navigate to listener app
    await page.goto('/listener');
    
    // Join session
    await page.fill('[data-testid="session-id-input"]', 'test-session-123');
    await page.click('[data-testid="join-button"]');
    
    // Switch language
    await page.selectOption('[data-testid="language-select"]', 'es');
    await expect(page.locator('[data-testid="language-select"]')).toHaveValue('es');
    
    // Pause playback
    await page.click('[data-testid="pause-button"]');
    await expect(page.locator('[data-testid="buffer-status"]')).toBeVisible();
    
    // Resume playback
    await page.click('[data-testid="pause-button"]');
    await expect(page.locator('[data-testid="buffer-status"]')).not.toBeVisible();
  });
});
```

---

## Testing Strategy

1. **Unit Tests**: Test individual services and utilities
2. **Integration Tests**: Test service interactions and state management
3. **E2E Tests**: Test complete user flows in browser

## Deployment Checklist

- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] All E2E tests passing
- [ ] Performance metrics validated (latency <100ms for controls, <500ms for language switch)
- [ ] Accessibility audit passed
- [ ] Cross-browser testing completed
- [ ] Mobile responsiveness verified

## Notes

- Tasks 4-7 extend existing services rather than creating new classes
- Error handling should be added throughout all control operations
- Preference loading should happen on session initialization
- WebSocket message handlers need to be added for state synchronization
- CSS styling needs to be added for UI components
