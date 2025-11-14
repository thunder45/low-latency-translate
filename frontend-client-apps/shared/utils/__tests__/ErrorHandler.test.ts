import { describe, it, expect } from 'vitest';
import { ErrorHandler, ErrorType } from '../ErrorHandler';

describe('ErrorHandler', () => {
  describe('handle', () => {
    it('should handle network errors', () => {
      const error = ErrorHandler.handle(ErrorType.NETWORK_ERROR, 'Connection failed');
      
      expect(error.type).toBe(ErrorType.NETWORK_ERROR);
      expect(error.message).toBe('Connection failed');
      expect(error.userMessage).toContain('network');
      expect(error.recoverable).toBe(true);
      expect(error.retryable).toBe(true);
    });

    it('should handle authentication errors', () => {
      const error = ErrorHandler.handle(ErrorType.AUTH_ERROR, 'Invalid credentials');
      
      expect(error.type).toBe(ErrorType.AUTH_ERROR);
      expect(error.userMessage).toContain('authentication');
      expect(error.recoverable).toBe(true);
      expect(error.retryable).toBe(false);
    });

    it('should handle validation errors', () => {
      const error = ErrorHandler.handle(ErrorType.VALIDATION_ERROR, 'Invalid input');
      
      expect(error.type).toBe(ErrorType.VALIDATION_ERROR);
      expect(error.userMessage).toContain('input');
      expect(error.recoverable).toBe(true);
      expect(error.retryable).toBe(false);
    });

    it('should handle session errors', () => {
      const error = ErrorHandler.handle(ErrorType.SESSION_ERROR, 'Session not found');
      
      expect(error.type).toBe(ErrorType.SESSION_ERROR);
      expect(error.userMessage).toContain('session');
      expect(error.recoverable).toBe(false);
      expect(error.retryable).toBe(false);
    });

    it('should handle audio errors', () => {
      const error = ErrorHandler.handle(ErrorType.AUDIO_ERROR, 'Microphone access denied');
      
      expect(error.type).toBe(ErrorType.AUDIO_ERROR);
      expect(error.userMessage).toContain('audio');
      expect(error.recoverable).toBe(true);
      expect(error.retryable).toBe(false);
    });

    it('should handle WebSocket errors', () => {
      const error = ErrorHandler.handle(ErrorType.WEBSOCKET_ERROR, 'Connection closed');
      
      expect(error.type).toBe(ErrorType.WEBSOCKET_ERROR);
      expect(error.userMessage).toContain('connection');
      expect(error.recoverable).toBe(true);
      expect(error.retryable).toBe(true);
    });

    it('should handle rate limit errors', () => {
      const error = ErrorHandler.handle(ErrorType.RATE_LIMIT_ERROR, 'Too many requests');
      
      expect(error.type).toBe(ErrorType.RATE_LIMIT_ERROR);
      expect(error.userMessage).toContain('limit');
      expect(error.recoverable).toBe(true);
      expect(error.retryable).toBe(true);
    });

    it('should handle unknown errors', () => {
      const error = ErrorHandler.handle(ErrorType.UNKNOWN_ERROR, 'Something went wrong');
      
      expect(error.type).toBe(ErrorType.UNKNOWN_ERROR);
      expect(error.userMessage).toContain('unexpected');
      expect(error.recoverable).toBe(false);
      expect(error.retryable).toBe(false);
    });

    it('should include original message in error object', () => {
      const originalMessage = 'Specific error details';
      const error = ErrorHandler.handle(ErrorType.NETWORK_ERROR, originalMessage);
      
      expect(error.message).toBe(originalMessage);
    });
  });
});
