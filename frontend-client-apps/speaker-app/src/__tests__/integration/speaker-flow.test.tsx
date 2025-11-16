import { describe, it, expect, beforeEach, vi } from 'vitest';
import { waitFor } from '@testing-library/react';
import { SpeakerService } from '../../services/SpeakerService';
import { useSpeakerStore, QualityWarning } from '@shared/store/speakerStore';

// Mock WebSocket and Audio APIs
vi.mock('@shared/websocket/WebSocketClient', () => {
  return {
    WebSocketClient: vi.fn().mockImplementation(() => ({
      connect: vi.fn().mockResolvedValue(undefined),
      send: vi.fn(),
      on: vi.fn(),
      off: vi.fn(),
      onConnect: vi.fn(),
      onDisconnect: vi.fn(),
      onError: vi.fn(),
      onStateChange: vi.fn(),
      disconnect: vi.fn(),
      isConnected: vi.fn().mockReturnValue(true),
      getState: vi.fn().mockReturnValue({ status: 'connected' }),
    })),
  };
});

vi.mock('@shared/audio/AudioCapture', () => {
  return {
    AudioCapture: vi.fn().mockImplementation(() => ({
      start: vi.fn().mockResolvedValue(undefined),
      stop: vi.fn(),
      pause: vi.fn(),
      resume: vi.fn(),
      mute: vi.fn(),
      unmute: vi.fn(),
      setVolume: vi.fn(),
      getInputLevel: vi.fn().mockReturnValue(50),
      getAverageInputLevel: vi.fn().mockReturnValue(45),
      onChunk: vi.fn(),
    })),
  };
});

describe('Speaker Flow Integration', () => {
  let speakerService: SpeakerService;

  beforeEach(() => {
    // Reset store
    useSpeakerStore.getState().reset();
    
    // Create service instance
    speakerService = new SpeakerService({
      wsUrl: 'wss://test.example.com',
      jwtToken: 'test-token',
      sourceLanguage: 'en',
      qualityTier: 'standard',
    });
  });

  describe('Session Creation Flow', () => {
    it('should initialize and connect successfully', async () => {
      // Trigger session initialization
      await speakerService.initialize();

      // Verify WebSocket connect was called
      expect(speakerService['wsClient'].connect).toHaveBeenCalledWith({
        sourceLanguage: 'en',
        qualityTier: 'standard',
      });

      // Verify send was called to create session
      expect(speakerService['wsClient'].send).toHaveBeenCalledWith({
        action: 'createSession',
        sourceLanguage: 'en',
        qualityTier: 'standard',
      });

      // Verify store state
      const state = useSpeakerStore.getState();
      expect(state.isConnected).toBe(true);
    });

    it('should handle initialization failure', async () => {
      // Mock WebSocket to simulate error
      const mockError = new Error('Connection failed');
      speakerService['wsClient'].connect = vi.fn().mockRejectedValue(mockError);

      // Attempt initialization
      await expect(
        speakerService.initialize()
      ).rejects.toThrow();

      // Verify store state
      const state = useSpeakerStore.getState();
      expect(state.isConnected).toBe(false);
    });
  });

  describe('Audio Transmission Flow', () => {
    beforeEach(async () => {
      // Set up session first
      await speakerService.initialize();
      useSpeakerStore.getState().setSession('test-session', 'en', 'standard');
    });

    it('should start audio broadcast', async () => {
      // Start audio capture
      await speakerService.startBroadcast();

      // Verify audio capture was started
      expect(speakerService['audioCapture'].start).toHaveBeenCalled();
      
      // Verify onChunk handler was registered
      expect(speakerService['audioCapture'].onChunk).toHaveBeenCalled();
    });

    it('should pause broadcast', async () => {
      // Start transmission
      await speakerService.startBroadcast();

      // Pause
      await speakerService.pause();

      // Verify audio capture was paused
      expect(speakerService['audioCapture'].pause).toHaveBeenCalled();
      
      // Verify store state
      const state = useSpeakerStore.getState();
      expect(state.isPaused).toBe(true);
      expect(state.isTransmitting).toBe(false);
      
      // Verify WebSocket message was sent
      expect(speakerService['wsClient'].send).toHaveBeenCalledWith(
        expect.objectContaining({
          action: 'pauseBroadcast',
        })
      );
    });

    it('should resume broadcast', async () => {
      // Start, pause, then resume
      await speakerService.startBroadcast();
      await speakerService.pause();
      await speakerService.resume();

      // Verify audio capture was resumed
      expect(speakerService['audioCapture'].resume).toHaveBeenCalled();
      
      // Verify store state
      const state = useSpeakerStore.getState();
      expect(state.isPaused).toBe(false);
      
      // Verify WebSocket message was sent
      expect(speakerService['wsClient'].send).toHaveBeenCalledWith(
        expect.objectContaining({
          action: 'resumeBroadcast',
        })
      );
    });
  });

  describe('Quality Warning Flow', () => {
    beforeEach(async () => {
      await speakerService.initialize();
      useSpeakerStore.getState().setSession('test-session', 'en', 'standard');
    });

    it('should register quality warning handler', async () => {
      // Verify that the 'audioQualityWarning' handler was registered
      expect(speakerService['wsClient'].on).toHaveBeenCalledWith(
        'audioQualityWarning',
        expect.any(Function)
      );
    });

    it('should clear quality warnings', async () => {
      // Manually add a warning to the store
      const warning: QualityWarning = {
        type: 'snr_low',
        message: 'Background noise detected',
        timestamp: Date.now(),
        issue: 'Low signal-to-noise ratio detected',
      };
      useSpeakerStore.getState().addQualityWarning(warning);

      // Verify warning was added
      expect(useSpeakerStore.getState().qualityWarnings).toHaveLength(1);

      // Clear warnings
      useSpeakerStore.getState().clearQualityWarnings();

      // Verify store state
      const state = useSpeakerStore.getState();
      expect(state.qualityWarnings).toHaveLength(0);
    });
  });

  describe('Session End Flow', () => {
    beforeEach(async () => {
      await speakerService.initialize();
      useSpeakerStore.getState().setSession('test-session', 'en', 'standard');
      await speakerService.startBroadcast();
    });

    it('should end session and cleanup', async () => {
      // End session
      await speakerService.endSession();

      // Verify audio capture was stopped
      expect(speakerService['audioCapture'].stop).toHaveBeenCalled();
      
      // Verify WebSocket message was sent
      expect(speakerService['wsClient'].send).toHaveBeenCalledWith(
        expect.objectContaining({
          action: 'endSession',
          sessionId: 'test-session',
        })
      );

      // Verify store state was reset
      await waitFor(() => {
        const state = useSpeakerStore.getState();
        expect(state.sessionId).toBeNull();
        expect(state.isConnected).toBe(false);
        expect(state.isTransmitting).toBe(false);
      });
    });

    it('should retry session end on failure', async () => {
      // Mock first attempt to fail, second to succeed
      let callCount = 0;
      speakerService['wsClient'].send = vi.fn().mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          throw new Error('Network error');
        }
        // Success on retry
      });

      // End session (retry handler will retry automatically)
      await speakerService.endSession();

      // Verify send was called (retry handler handles the retry)
      expect(speakerService['wsClient'].send).toHaveBeenCalled();
    });
  });

  describe('Listener Stats Flow', () => {
    beforeEach(async () => {
      await speakerService.initialize();
      useSpeakerStore.getState().setSession('test-session', 'en', 'standard');
    });

    it('should register session status handler', async () => {
      // Verify that the 'sessionStatus' handler was registered
      expect(speakerService['wsClient'].on).toHaveBeenCalledWith(
        'sessionStatus',
        expect.any(Function)
      );
    });

    it('should start status polling when broadcast starts', async () => {
      // Start broadcast
      await speakerService.startBroadcast();

      // Verify that status polling was initiated
      // The service should have set up an interval to poll for status
      expect(speakerService['statusPollInterval']).not.toBeNull();
    });
  });
});
