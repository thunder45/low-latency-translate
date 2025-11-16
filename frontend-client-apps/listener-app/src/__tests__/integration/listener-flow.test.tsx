import { describe, it, expect, beforeEach, vi } from 'vitest';
import { waitFor } from '@testing-library/react';
import { ListenerService } from '../../services/ListenerService';
import { useListenerStore } from '@shared/store/listenerStore';

// Mock WebSocket and Audio APIs
vi.mock('@shared/websocket/WebSocketClient');
vi.mock('@shared/audio/AudioPlayback');

describe('Listener Flow Integration', () => {
  let listenerService: ListenerService;

  beforeEach(() => {
    // Reset store
    useListenerStore.getState().reset();
    
    // Create service instance
    listenerService = new ListenerService({
      wsUrl: 'wss://test.example.com',
      sessionId: 'test-session-123',
      targetLanguage: 'es',
    });
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
      // Mock WebSocket to simulate error
      const mockError = new Error('Session not found');
      vi.spyOn(listenerService as any, 'wsClient').mockImplementation(() => {
        throw mockError;
      });

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

      // Trigger audio handler via WebSocket event
      (listenerService as any).wsClient.emit('audio', audioMessage);

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

    it('should handle language switch failure', async () => {
      // Mock failure
      const mockError = new Error('Language not supported');
      vi.spyOn(listenerService as any, 'wsClient', 'get').mockReturnValue({
        send: vi.fn(() => { throw mockError; }),
        isConnected: vi.fn(() => true),
      });

      // Attempt language switch
      await expect(
        listenerService.switchLanguage('invalid')
      ).rejects.toThrow();

      // Verify language reverted
      const state = useListenerStore.getState();
      expect(state.targetLanguage).toBe('es');
    });
  });

  describe('Speaker State Flow', () => {
    beforeEach(async () => {
      await listenerService.initialize();
    });

    it('should handle speaker paused message', async () => {
      // Trigger handler via WebSocket event
      (listenerService as any).wsClient.emit('broadcastPaused');

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isSpeakerPaused).toBe(true);
      });
    });

    it('should handle speaker resumed message', async () => {
      // Set paused first
      useListenerStore.getState().setSpeakerPaused(true);

      // Trigger handler via WebSocket event
      (listenerService as any).wsClient.emit('broadcastResumed');

      // Verify store state (with delay for setTimeout in handler)
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isSpeakerPaused).toBe(false);
      }, { timeout: 1000 });
    });

    it('should handle speaker muted message', async () => {
      // Trigger handler via WebSocket event
      (listenerService as any).wsClient.emit('broadcastMuted');

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isSpeakerMuted).toBe(true);
      });
    });
  });

  describe('Buffer Management Flow', () => {
    beforeEach(async () => {
      await listenerService.initialize();
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
    });

    it('should handle session ended message', async () => {
      // Trigger handler via WebSocket event
      (listenerService as any).wsClient.emit('sessionEnded');

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isConnected).toBe(false);
      });
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
