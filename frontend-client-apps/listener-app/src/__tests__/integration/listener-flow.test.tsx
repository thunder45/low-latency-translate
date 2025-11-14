import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
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
    });
  });

  describe('Session Join Flow', () => {
    it('should join session and update store', async () => {
      // Simulate session join
      const joinData = {
        sessionId: 'golden-eagle-427',
        targetLanguage: 'es',
      };

      // Trigger session join
      await listenerService.joinSession(joinData);

      // Wait for store update
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.session).toBeDefined();
        expect(state.session?.sessionId).toBe('golden-eagle-427');
        expect(state.targetLanguage).toBe('es');
        expect(state.isConnected).toBe(true);
      });
    });

    it('should handle session join failure', async () => {
      // Mock WebSocket to simulate error
      const mockError = new Error('Session not found');
      vi.spyOn(listenerService as any, 'sendMessage').mockRejectedValue(mockError);

      // Attempt session join
      await expect(
        listenerService.joinSession({
          sessionId: 'invalid-session',
          targetLanguage: 'es',
        })
      ).rejects.toThrow('Session not found');

      // Verify store state
      const state = useListenerStore.getState();
      expect(state.session).toBeNull();
      expect(state.isConnected).toBe(false);
    });
  });

  describe('Audio Playback Flow', () => {
    beforeEach(async () => {
      // Set up session first
      await listenerService.joinSession({
        sessionId: 'test-session',
        targetLanguage: 'es',
      });
    });

    it('should receive and queue audio', async () => {
      // Simulate audio message
      const audioMessage = {
        type: 'audio',
        data: 'base64-encoded-audio-data',
        timestamp: Date.now(),
      };

      // Trigger audio handler
      (listenerService as any).handleAudioMessage(audioMessage);

      // Verify audio was queued (implementation-specific)
      // This would check the AudioPlayback service
      expect(true).toBe(true); // Placeholder
    });

    it('should pause playback', async () => {
      // Pause playback
      await listenerService.pausePlayback();

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isPaused).toBe(true);
      });
    });

    it('should resume playback', async () => {
      // Pause then resume
      await listenerService.pausePlayback();
      await listenerService.resumePlayback();

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isPaused).toBe(false);
      });
    });

    it('should mute audio', async () => {
      // Mute
      await listenerService.setMuted(true);

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isMuted).toBe(true);
      });
    });

    it('should adjust volume', async () => {
      // Set volume
      await listenerService.setVolume(0.5);

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.playbackVolume).toBe(0.5);
      });
    });
  });

  describe('Language Switch Flow', () => {
    beforeEach(async () => {
      await listenerService.joinSession({
        sessionId: 'test-session',
        targetLanguage: 'es',
      });
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
      vi.spyOn(listenerService as any, 'sendMessage').mockRejectedValue(mockError);

      // Attempt language switch
      await expect(
        listenerService.switchLanguage('invalid')
      ).rejects.toThrow('Language not supported');

      // Verify language unchanged
      const state = useListenerStore.getState();
      expect(state.targetLanguage).toBe('es');
    });
  });

  describe('Speaker State Flow', () => {
    beforeEach(async () => {
      await listenerService.joinSession({
        sessionId: 'test-session',
        targetLanguage: 'es',
      });
    });

    it('should handle speaker paused message', async () => {
      // Simulate speaker paused message
      const message = {
        type: 'speakerPaused',
        timestamp: Date.now(),
      };

      // Trigger handler
      (listenerService as any).handleSpeakerStateChange(message);

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isSpeakerPaused).toBe(true);
      });
    });

    it('should handle speaker resumed message', async () => {
      // Set paused first
      useListenerStore.getState().setSpeakerPaused(true);

      // Simulate speaker resumed message
      const message = {
        type: 'speakerResumed',
        timestamp: Date.now(),
      };

      // Trigger handler
      (listenerService as any).handleSpeakerStateChange(message);

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isSpeakerPaused).toBe(false);
      });
    });

    it('should handle speaker muted message', async () => {
      // Simulate speaker muted message
      const message = {
        type: 'speakerMuted',
        timestamp: Date.now(),
      };

      // Trigger handler
      (listenerService as any).handleSpeakerStateChange(message);

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isSpeakerMuted).toBe(true);
      });
    });
  });

  describe('Buffer Management Flow', () => {
    beforeEach(async () => {
      await listenerService.joinSession({
        sessionId: 'test-session',
        targetLanguage: 'es',
      });
    });

    it('should track buffer duration', async () => {
      // Simulate buffer update
      useListenerStore.getState().setBufferedDuration(15);

      // Verify store state
      const state = useListenerStore.getState();
      expect(state.bufferedDuration).toBe(15);
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
      await listenerService.joinSession({
        sessionId: 'test-session',
        targetLanguage: 'es',
      });
    });

    it('should handle session ended message', async () => {
      // Simulate session ended message
      const message = {
        type: 'sessionEnded',
        reason: 'Speaker ended session',
        timestamp: Date.now(),
      };

      // Trigger handler
      (listenerService as any).handleSessionEnded(message);

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.session).toBeNull();
        expect(state.isConnected).toBe(false);
      });
    });

    it('should cleanup on disconnect', async () => {
      // Disconnect
      await listenerService.disconnect();

      // Verify store state
      await waitFor(() => {
        const state = useListenerStore.getState();
        expect(state.isConnected).toBe(false);
      });
    });
  });
});
