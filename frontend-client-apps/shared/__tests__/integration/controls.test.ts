/**
 * Integration tests for speaker-listener controls
 * 
 * Tests the integration between services, state management, and UI components
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { controlsMonitoring } from '../../utils/ControlsMonitoring';
import { PreferenceStore } from '../../services/PreferenceStore';
import { KeyboardShortcutManager } from '../../services/KeyboardShortcutManager';
import { CircularAudioBuffer } from '../../audio/CircularAudioBuffer';

// Mock localStorage
const mockStorage: Record<string, string> = {};
const localStorageMock = {
  getItem: vi.fn((key: string) => mockStorage[key] || null),
  setItem: vi.fn((key: string, value: string) => {
    mockStorage[key] = value;
  }),
  removeItem: vi.fn((key: string) => {
    delete mockStorage[key];
  }),
  clear: vi.fn(() => {
    Object.keys(mockStorage).forEach(key => delete mockStorage[key]);
  }),
  length: 0,
  key: vi.fn(),
};

Object.defineProperty(global, 'localStorage', {
  value: localStorageMock,
  writable: true,
});

describe('Speaker Controls Integration', () => {
  beforeEach(() => {
    // Clear mock storage
    Object.keys(mockStorage).forEach(key => delete mockStorage[key]);
    
    // Clear monitoring data
    controlsMonitoring.clear();
    
    // Reset preference store
    PreferenceStore.getInstance().resetPreferences('test-speaker');
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Control Operations', () => {
    it('should track pause operation latency', async () => {
      const startTime = Date.now();
      
      // Simulate pause operation
      controlsMonitoring.logControlLatency('pause', startTime, {
        userType: 'speaker',
        sessionId: 'test-session',
      });
      
      const summary = controlsMonitoring.getMetricsSummary();
      expect(summary.totalMetrics).toBeGreaterThan(0);
      expect(summary.averageLatencies['control.pause.latency']).toBeDefined();
    });

    it('should track mute operation within 50ms target', async () => {
      const startTime = Date.now();
      
      // Simulate fast mute operation
      await new Promise(resolve => setTimeout(resolve, 20));
      
      controlsMonitoring.logControlLatency('mute', startTime);
      
      const summary = controlsMonitoring.getMetricsSummary();
      const muteLatency = summary.averageLatencies['control.mute.latency'];
      
      expect(muteLatency).toBeLessThan(50);
    });
  });

  describe('Preference Persistence', () => {
    it('should save and load volume preference', async () => {
      const preferenceStore = PreferenceStore.getInstance();
      const userId = 'test-speaker';
      const volume = 85;
      
      // Save preference
      await preferenceStore.saveVolume(userId, volume);
      
      // Load preference
      const loadedVolume = await preferenceStore.getVolume(userId);
      
      expect(loadedVolume).toBe(volume);
    });

    it('should save and load language preference', async () => {
      const preferenceStore = PreferenceStore.getInstance();
      const userId = 'test-listener';
      const language = 'es';
      
      // Save preference
      await preferenceStore.saveLanguage(userId, language);
      
      // Load preference
      const loadedLanguage = await preferenceStore.getLanguage(userId);
      
      expect(loadedLanguage).toBe(language);
    });

    it('should load preferences within 1 second', async () => {
      const preferenceStore = PreferenceStore.getInstance();
      const userId = 'test-user';
      
      // Save some preferences
      await preferenceStore.saveVolume(userId, 75);
      await preferenceStore.saveLanguage(userId, 'en');
      
      // Measure load time
      const startTime = Date.now();
      await preferenceStore.getVolume(userId);
      await preferenceStore.getLanguage(userId);
      const duration = Date.now() - startTime;
      
      expect(duration).toBeLessThan(1000);
    });
  });

  describe('Keyboard Shortcuts', () => {
    it('should register and manage keyboard shortcuts', async () => {
      const manager = KeyboardShortcutManager.getInstance();
      await manager.initialize('test-user');
      
      // Verify shortcuts are loaded with defaults
      const shortcuts = manager.getShortcuts();
      expect(shortcuts.pause).toBe('KeyP');
      expect(shortcuts.mute).toBe('KeyM');
      
      // Verify handler registration works
      const pauseHandler = vi.fn();
      manager.registerHandler('pause', pauseHandler);
      
      // Verify handler can be unregistered
      manager.unregisterHandler('pause');
      
      // Verify shortcuts can be updated
      const result = await manager.updateShortcut('pause', 'KeySpace');
      expect(result).toBe(true);
      
      const updatedShortcuts = manager.getShortcuts();
      expect(updatedShortcuts.pause).toBe('KeySpace');
      
      manager.destroy();
    });

    it('should prevent conflicts with reserved shortcuts', async () => {
      const manager = KeyboardShortcutManager.getInstance();
      await manager.initialize('test-user');
      
      // Try to register a reserved shortcut (KeyR is reserved for refresh)
      const result = await manager.updateShortcut('pause', 'KeyR');
      
      expect(result).toBe(false);
      
      manager.destroy();
    });
  });
});

describe('Listener Controls Integration', () => {
  beforeEach(() => {
    controlsMonitoring.clear();
  });

  describe('Audio Buffer', () => {
    it('should buffer audio during pause', () => {
      const buffer = new CircularAudioBuffer(16000, 30000);
      
      // Write some audio data
      const audioChunk = new Float32Array(1600); // 100ms at 16kHz
      audioChunk.fill(0.5);
      
      const isNearCapacity = buffer.write(audioChunk);
      
      expect(isNearCapacity).toBe(false);
      expect(buffer.getBufferedDuration()).toBeGreaterThan(0);
    });

    it('should warn when buffer approaches capacity', () => {
      const buffer = new CircularAudioBuffer(16000, 1000); // 1 second max
      
      // Fill buffer to near capacity
      const audioChunk = new Float32Array(14400); // 900ms at 16kHz
      audioChunk.fill(0.5);
      
      const isNearCapacity = buffer.write(audioChunk);
      
      expect(isNearCapacity).toBe(true);
    });

    it('should read buffered audio correctly', () => {
      const buffer = new CircularAudioBuffer(16000, 30000);
      
      // Write audio data
      const audioChunk = new Float32Array(1600);
      audioChunk.fill(0.5);
      buffer.write(audioChunk);
      
      // Read audio data
      const bufferedDuration = buffer.getBufferedDuration();
      const readData = buffer.read(bufferedDuration);
      
      expect(readData.length).toBeGreaterThan(0);
      expect(readData[0]).toBe(0.5);
    });
  });

  describe('Monitoring Integration', () => {
    it('should track control success rates', () => {
      // Log some successful operations
      controlsMonitoring.logControlAction('pause', true);
      controlsMonitoring.logControlAction('pause', true);
      controlsMonitoring.logControlAction('pause', false);
      
      const summary = controlsMonitoring.getMetricsSummary();
      const pauseSuccessRate = summary.successRates['pause'];
      
      expect(pauseSuccessRate).toBeCloseTo(66.67, 1);
    });

    it('should track buffer overflow events', () => {
      controlsMonitoring.logBufferOverflow(31000, 30000, {
        sessionId: 'test-session',
      });
      
      const summary = controlsMonitoring.getMetricsSummary();
      expect(summary.totalEvents).toBeGreaterThan(0);
      
      const overflowEvents = summary.recentEvents.filter(
        e => e.operation === 'buffer_overflow'
      );
      expect(overflowEvents.length).toBe(1);
    });
  });
});
