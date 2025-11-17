import { describe, it, expect } from 'vitest';
import { ErrorHandler, ErrorType } from '../ErrorHandler';

describe('ErrorHandler', () => {
  describe('handle', () => {
    it('should handle network errors', () => {
      const error = ErrorHandler.handle(ErrorType.NETWORK_ERROR, 'Connection failed');
      
      expect(error.type).toBe(ErrorType.NETWORK_ERROR);
      expect(error.message).toBe('Connection failed');
      expect(error.userMessage).toContain('Network');
      expect(error.recoverable).toBe(true);
      expect(error.retryable).toBe(true);
    });

    it('should handle authentication errors', () => {
      const error = ErrorHandler.handle(ErrorType.AUTH_FAILED, 'Invalid credentials');
      
      expect(error.type).toBe(ErrorType.AUTH_FAILED);
      expect(error.userMessage).toContain('Authentication');
      expect(error.recoverable).toBe(true);
      expect(error.retryable).toBe(false);
    });

    it('should handle validation errors', () => {
      const error = ErrorHandler.handle(ErrorType.INVALID_INPUT, 'Invalid input');
      
      expect(error.type).toBe(ErrorType.INVALID_INPUT);
      expect(error.userMessage).toContain('input');
      expect(error.recoverable).toBe(true);
      expect(error.retryable).toBe(false);
    });

    it('should handle session errors', () => {
      const error = ErrorHandler.handle(ErrorType.SESSION_NOT_FOUND, 'Session not found');
      
      expect(error.type).toBe(ErrorType.SESSION_NOT_FOUND);
      expect(error.userMessage).toContain('Session');
      expect(error.recoverable).toBe(true);
      expect(error.retryable).toBe(false);
    });

    it('should handle audio errors', () => {
      const error = ErrorHandler.handle(ErrorType.MICROPHONE_ACCESS_DENIED, 'Microphone access denied');
      
      expect(error.type).toBe(ErrorType.MICROPHONE_ACCESS_DENIED);
      expect(error.userMessage).toContain('Microphone');
      expect(error.recoverable).toBe(true);
      expect(error.retryable).toBe(false);
    });

    it('should handle WebSocket errors', () => {
      const error = ErrorHandler.handle(ErrorType.WEBSOCKET_ERROR, 'Connection closed');
      
      expect(error.type).toBe(ErrorType.WEBSOCKET_ERROR);
      expect(error.userMessage).toContain('Connection');
      expect(error.recoverable).toBe(true);
      expect(error.retryable).toBe(true);
    });

    it('should handle rate limit errors', () => {
      const error = ErrorHandler.handle(ErrorType.RATE_LIMIT_EXCEEDED, 'Too many requests');
      
      expect(error.type).toBe(ErrorType.RATE_LIMIT_EXCEEDED);
      expect(error.userMessage).toContain('requests');
      expect(error.recoverable).toBe(true);
      expect(error.retryable).toBe(true);
    });

    it('should handle unknown errors', () => {
      const error = ErrorHandler.handle(ErrorType.UNKNOWN_ERROR, 'Something went wrong');
      
      expect(error.type).toBe(ErrorType.UNKNOWN_ERROR);
      expect(error.userMessage).toContain('unexpected');
      expect(error.recoverable).toBe(true);
      expect(error.retryable).toBe(true);
    });

    it('should include original message in error object', () => {
      const originalMessage = 'Specific error details';
      const error = ErrorHandler.handle(ErrorType.NETWORK_ERROR, originalMessage);
      
      expect(error.message).toBe(originalMessage);
    });
  });
});
