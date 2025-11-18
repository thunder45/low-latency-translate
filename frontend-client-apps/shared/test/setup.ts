import { expect, afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

// Cleanup after each test
afterEach(() => {
  cleanup();
});

// Mock Web Audio API
global.AudioContext = vi.fn().mockImplementation(() => ({
  createGain: vi.fn().mockReturnValue({
    connect: vi.fn(),
    disconnect: vi.fn(),
    gain: { value: 1 },
  }),
  createScriptProcessor: vi.fn().mockReturnValue({
    connect: vi.fn(),
    disconnect: vi.fn(),
    onaudioprocess: null,
  }),
  createMediaStreamSource: vi.fn().mockReturnValue({
    connect: vi.fn(),
    disconnect: vi.fn(),
  }),
  createBufferSource: vi.fn().mockReturnValue({
    connect: vi.fn(),
    disconnect: vi.fn(),
    start: vi.fn(),
    stop: vi.fn(),
    buffer: null,
  }),
  createBuffer: vi.fn(),
  decodeAudioData: vi.fn(),
  destination: {},
  sampleRate: 16000,
  currentTime: 0,
  state: 'running',
  close: vi.fn(),
  resume: vi.fn(),
  suspend: vi.fn(),
})) as any;

// Mock WebSocket
global.WebSocket = vi.fn().mockImplementation(() => ({
  send: vi.fn(),
  close: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  readyState: 1,
  CONNECTING: 0,
  OPEN: 1,
  CLOSING: 2,
  CLOSED: 3,
})) as any;

// Mock localStorage with actual storage
const createLocalStorageMock = () => {
  let store: Record<string, string> = {};
  
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
    get length() {
      return Object.keys(store).length;
    },
    key: (index: number) => {
      const keys = Object.keys(store);
      return keys[index] || null;
    },
  };
};

global.localStorage = createLocalStorageMock() as any;

// Mock crypto (use Object.defineProperty to avoid read-only error)
Object.defineProperty(global, 'crypto', {
  value: {
    getRandomValues: vi.fn((arr) => {
      for (let i = 0; i < arr.length; i++) {
        arr[i] = Math.floor(Math.random() * 256);
      }
      return arr;
    }),
    subtle: {
      importKey: vi.fn().mockResolvedValue({ type: 'secret' }),
      deriveKey: vi.fn().mockResolvedValue({ type: 'secret', algorithm: { name: 'AES-GCM' } }),
      encrypt: vi.fn().mockImplementation(async (algorithm, key, data) => {
        // Simple mock encryption - just return the data with some transformation
        return new Uint8Array(data).buffer;
      }),
      decrypt: vi.fn().mockImplementation(async (algorithm, key, data) => {
        // Simple mock decryption - just return the data
        return new Uint8Array(data).buffer;
      }),
    } as any,
  },
  writable: true,
  configurable: true,
});
