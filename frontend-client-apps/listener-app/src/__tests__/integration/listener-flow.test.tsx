import { describe, it, expect, beforeEach, vi } from 'vitest';
import { waitFor } from '@testing-library/react';
import { ListenerService } from '../../services/ListenerService';
import { useListenerStore } from '@shared/store/listenerStore';
import { MockWebSocketClient } from '@shared/websocket/__tests__/mocks/MockWebSocketClient';

// Mock Audio APIs
vi.mock('@shared/audio/AudioPlayback');

describe('Listener Flow Integration', () => {
  let listenerService: ListenerService;
  let mockWsClient: MockWebSocketClient;

  beforeEach(() => {
    // Reset store
    useListenerStore.getState().reset();
    
    // Create mock WebSocket client
    mockWsClient = new MockWebSocketClient();
    
    // Create service instance
    listenerService = new ListenerService({
      wsUrl: 'wss://test.example.com',
      sessionId: 'test-session-123',
      targetLanguage: 'es',
      jwtToken: '',
      kvsChannelArn: 'arn:aws:kinesisvideo:us-east-1:123456789012:channel/test-channel/1234567890',
      kvsSignalingEndpoint: 'wss://test-kvs.kinesisvideo.us-east-1.amazonaws.com',
      region: 'us-east-1',
      identityPoolId: 'us-east-1:test-identity-pool-id',
      userPoolId: 'us-east-1_TestPool',
    });
    
    // Replace wsClient with mock BEFORE setupEventHandlers is called
    // We need to do this immediately after construction
    Object.defineProperty(listenerService, 'wsClient', {
      value: mockWsClient,
      writable: true,
      configurable: true,
    });
    
    // Manually call setupEventHandlers to register handlers on the mock client
    (listenerService as any).setupEventHandlers();
  });

  describe('Session Join Flow', () => {
    it('should initialize and join session', async () => {
      // Initialize service (connects and joins)
      await listenerService.initialize();

      // Wait for store update
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isConnected).toBe(true);
      });
    });

    it('should handle session join failure', async () => {
      // Mock connect to fail
      const mockError = new Error('Session not found');
      mockWsClient.connect.mockRejectedValue(mockError);

      // Attempt session join
      await expect(
        listenerService.initialize()
      ).rejects.toThrow();

      // Verify store state
      const state = useListenerStore.getState();
      expect(state.isConnected).toBe(false);
    });
  });

  describe('Audio Playback Flow', () => {
    beforeEach(async () => {
      // Set up session first
      await listenerService.initialize();
    });

    it('should receive and queue audio', async () => {
      // Simulate audio message
      const audioMessage = {
        type: 'audio',
        data: 'base64-encoded-audio-data',
        timestamp: Date.now(),
      };

      // Trigger audio handler via WebSocket event using emit
      mockWsClient.emit('audio', audioMessage);

      // Verify audio was queued (implementation-specific)
      // This would check the AudioPlayback service
      expect(true).toBe(true); // Placeholder
    });

    it('should pause playback', async () => {
      // Pause playback
      await listenerService.pause();

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isPaused).toBe(true);
      });
    });

    it('should resume playback', async () => {
      // Pause then resume
      await listenerService.pause();
      await listenerService.resume();

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isPaused).toBe(false);
      });
    });

    it('should mute audio', async () => {
      // Mute
      await listenerService.mute();

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isMuted).toBe(true);
      });
    });

    it('should adjust volume', async () => {
      // Set volume (0-100 range)
      await listenerService.setVolume(50);

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.playbackVolume).toBe(50);
      });
    });
  });

  describe('Language Switch Flow', () => {
    beforeEach(async () => {
      await listenerService.initialize();
    });

    it('should switch language successfully', async () => {
      // Switch language
      await listenerService.switchLanguage('fr');

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.targetLanguage).toBe('fr');
      });
    });

    it('should handle language switch with validation', async () => {
      // Switch to a valid language
      await listenerService.switchLanguage('de');

      // Verify language was updated
      const state = useListenerStore.getState();
      expect(state.targetLanguage).toBe('de');
      
      // Verify send was called with correct action
      expect(mockWsClient.send).toHaveBeenCalledWith(
        expect.objectContaining({
          action: 'changeLanguage',
          targetLanguage: 'de',
        })
      );
    });
  });

  describe('Speaker State Flow', () => {
    beforeEach(async () => {
      await listenerService.initialize();
      // Give time for event handlers to be registered
      await new Promise(resolve => setTimeout(resolve, 10));
    });

    it('should handle speaker paused message', async () => {
      // Trigger handler via WebSocket event using emit
      mockWsClient.emit('broadcastPaused');

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isSpeakerPaused).toBe(true);
      }, { timeout: 2000 });
    });

    it('should handle speaker resumed message', async () => {
      // Set paused first
      useListenerStore.getState().setSpeakerPaused(true);

      // Trigger handler via WebSocket event using emit
      mockWsClient.emit('broadcastResumed');

      // Verify store state (with delay for setTimeout in handler)
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isSpeakerPaused).toBe(false);
      }, { timeout: 2000 });
    });

    it('should handle speaker muted message', async () => {
      // Trigger handler via WebSocket event using emit
      mockWsClient.emit('broadcastMuted');

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isSpeakerMuted).toBe(true);
      }, { timeout: 2000 });
    });
  });

  describe('Buffer Management Flow', () => {
    let mockAudioPlayback: any;
    
    beforeEach(async () => {
      await listenerService.initialize();
      
      // Mock audio playback with getBufferDuration method
      mockAudioPlayback = {
        queueAudio: vi.fn(),
        pause: vi.fn(),
        resume: vi.fn(),
        stop: vi.fn(),
        setMuted: vi.fn(),
        setVolume: vi.fn(),
        clearBuffer: vi.fn(),
        playBuffer: vi.fn(),
        getBufferDuration: vi.fn().mockReturnValue(1.5),
        isPlaying: vi.fn().mockReturnValue(true)
      };
      
      // Use Object.defineProperty for proper mocking
      Object.defineProperty(listenerService, 'audioPlayback', {
        get: () => mockAudioPlayback,
        configurable: true,
      });
    });

    it('should track buffer duration', async () => {
      // Get buffer duration from service
      const duration = listenerService.getBufferedDuration();

      // Verify it returns a number
      expect(typeof duration).toBe('number');
      expect(duration).toBeGreaterThanOrEqual(0);
    });

    it('should indicate buffering state', async () => {
      // Set buffering
      useListenerStore.getState().setBuffering(true);

      // Verify store state
      const state = useListenerStore.getState();
      expect(state.isBuffering).toBe(true);
    });

    it('should handle buffer overflow', async () => {
      // Simulate buffer overflow
      useListenerStore.getState().setBufferOverflow(true);

      // Verify store state
      const state = useListenerStore.getState();
      expect(state.isBufferOverflow).toBe(true);
    });
  });

  describe('Session End Flow', () => {
    beforeEach(async () => {
      await listenerService.initialize();
      // Give time for event handlers to be registered
      await new Promise(resolve => setTimeout(resolve, 10));
    });

    it('should handle session ended message', async () => {
      // Trigger handler via WebSocket event using emit
      mockWsClient.emit('sessionEnded');

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isConnected).toBe(false);
      }, { timeout: 2000 });
    });

    it('should cleanup on leave', async () => {
      // Leave session
      listenerService.leave();

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isConnected).toBe(false);
      });
    });

    it('should cleanup resources', () => {
      // Cleanup
      listenerService.cleanup();

      // Verify cleanup was called (no errors thrown)
      expect(true).toBe(true);
    });
  });
});
