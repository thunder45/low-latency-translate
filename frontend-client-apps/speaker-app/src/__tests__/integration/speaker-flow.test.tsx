import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { SpeakerService } from '../../services/SpeakerService';
import { useSpeakerStore } from '@shared/store/speakerStore';

// Mock WebSocket and Audio APIs
vi.mock('@shared/websocket/WebSocketClient');
vi.mock('@shared/audio/AudioCapture');

describe('Speaker Flow Integration', () => {
  let speakerService: SpeakerService;

  beforeEach(() => {
    // Reset store
    useSpeakerStore.getState().reset();
    
    // Create service instance
    speakerService = new SpeakerService({
      wsUrl: 'wss://test.example.com',
      authToken: 'test-token',
    });
  });

  describe('Session Creation Flow', () => {
    it('should create session and update store', async () => {
      // Simulate session creation
      const mockSessionData = {
        sessionId: 'golden-eagle-427',
        sourceLanguage: 'en',
        qualityTier: 'standard',
      };

      // Trigger session creation
      await speakerService.createSession(mockSessionData);

      // Wait for store update
      await waitFor(() => {
        const state = useSpeakerStore.getState();
        expect(state.session).toBeDefined();
        expect(state.session?.sessionId).toBe('golden-eagle-427');
        expect(state.isConnected).toBe(true);
      });
    });

    it('should handle session creation failure', async () => {
      // Mock WebSocket to simulate error
      const mockError = new Error('Session creation failed');
      vi.spyOn(speakerService as any, 'sendMessage').mockRejectedValue(mockError);

      // Attempt session creation
      await expect(
        speakerService.createSession({
          sessionId: 'test-session',
          sourceLanguage: 'en',
          qualityTier: 'standard',
        })
      ).rejects.toThrow('Session creation failed');

      // Verify store state
      const state = useSpeakerStore.getState();
      expect(state.session).toBeNull();
      expect(state.isConnected).toBe(false);
    });
  });

  describe('Audio Transmission Flow', () => {
    beforeEach(async () => {
      // Set up session first
      await speakerService.createSession({
        sessionId: 'test-session',
        sourceLanguage: 'en',
        qualityTier: 'standard',
      });
    });

    it('should start audio transmission', async () => {
      // Start audio capture
      await speakerService.startAudioTransmission();

      // Verify store state
      await waitFor(() => {
        const state = useSpeakerStore.getState();
        expect(state.isTransmitting).toBe(true);
      });
    });

    it('should pause audio transmission', async () => {
      // Start transmission
      await speakerService.startAudioTransmission();

      // Pause
      await speakerService.pauseBroadcast();

      // Verify store state
      await waitFor(() => {
        const state = useSpeakerStore.getState();
        expect(state.isPaused).toBe(true);
        expect(state.isTransmitting).toBe(false);
      });
    });

    it('should resume audio transmission', async () => {
      // Start, pause, then resume
      await speakerService.startAudioTransmission();
      await speakerService.pauseBroadcast();
      await speakerService.resumeBroadcast();

      // Verify store state
      await waitFor(() => {
        const state = useSpeakerStore.getState();
        expect(state.isPaused).toBe(false);
        expect(state.isTransmitting).toBe(true);
      });
    });
  });

  describe('Quality Warning Flow', () => {
    beforeEach(async () => {
      await speakerService.createSession({
        sessionId: 'test-session',
        sourceLanguage: 'en',
        qualityTier: 'standard',
      });
    });

    it('should handle quality warnings', async () => {
      // Simulate quality warning message
      const warningMessage = {
        type: 'audio_quality_warning',
        issue: 'snr_low',
        message: 'Background noise detected',
        timestamp: Date.now(),
      };

      // Trigger warning handler
      (speakerService as any).handleQualityWarning(warningMessage);

      // Verify store state
      await waitFor(() => {
        const state = useSpeakerStore.getState();
        expect(state.qualityWarnings).toHaveLength(1);
        expect(state.qualityWarnings[0].issue).toBe('snr_low');
      });
    });

    it('should clear quality warnings', async () => {
      // Add warning
      const warningMessage = {
        type: 'audio_quality_warning',
        issue: 'snr_low',
        message: 'Background noise detected',
        timestamp: Date.now(),
      };
      (speakerService as any).handleQualityWarning(warningMessage);

      // Clear warnings
      useSpeakerStore.getState().clearQualityWarnings();

      // Verify store state
      const state = useSpeakerStore.getState();
      expect(state.qualityWarnings).toHaveLength(0);
    });
  });

  describe('Session End Flow', () => {
    beforeEach(async () => {
      await speakerService.createSession({
        sessionId: 'test-session',
        sourceLanguage: 'en',
        qualityTier: 'standard',
      });
      await speakerService.startAudioTransmission();
    });

    it('should end session and cleanup', async () => {
      // End session
      await speakerService.endSession();

      // Verify store state
      await waitFor(() => {
        const state = useSpeakerStore.getState();
        expect(state.session).toBeNull();
        expect(state.isConnected).toBe(false);
        expect(state.isTransmitting).toBe(false);
      });
    });

    it('should retry session end on failure', async () => {
      // Mock first attempt to fail
      const sendSpy = vi.spyOn(speakerService as any, 'sendMessage')
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce(undefined);

      // End session
      await speakerService.endSession();

      // Verify retry occurred
      expect(sendSpy).toHaveBeenCalledTimes(2);
    });
  });

  describe('Listener Stats Flow', () => {
    beforeEach(async () => {
      await speakerService.createSession({
        sessionId: 'test-session',
        sourceLanguage: 'en',
        qualityTier: 'standard',
      });
    });

    it('should update listener stats', async () => {
      // Simulate session status message
      const statusMessage = {
        type: 'sessionStatus',
        listenerCount: 5,
        languageDistribution: {
          es: 3,
          fr: 2,
        },
      };

      // Trigger status handler
      (speakerService as any).handleSessionStatus(statusMessage);

      // Verify store state
      await waitFor(() => {
        const state = useSpeakerStore.getState();
        expect(state.listenerCount).toBe(5);
        expect(state.languageDistribution).toEqual({ es: 3, fr: 2 });
      });
    });
  });
});
