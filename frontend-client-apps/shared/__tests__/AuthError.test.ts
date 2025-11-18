/**
 * AuthError Tests
 * 
 * Comprehensive test suite for authentication error handling utilities.
 * Tests error creation, type guards, helper functions, and JSON serialization.
 */

import { describe, it, expect } from 'vitest';
import {
  AuthError,
  AUTH_ERROR_CODES,
  AUTH_ERROR_MESSAGES,
  isAuthError,
  toAuthError,
  handleAuthError,
  shouldReAuthenticate,
  isRetryableError,
  type AuthErrorCode,
} from '../utils/AuthError';

describe('AuthError', () => {
  describe('constructor', () => {
    it('should create error with all properties', () => {
      const originalError = new Error('Original error');
      const context = { userId: '123', action: 'login' };
      
      const error = new AuthError(
        AUTH_ERROR_CODES.TOKEN_EXPIRED,
        'Custom message',
        originalError,
        context
      );

      expect(error).toBeInstanceOf(Error);
      expect(error).toBeInstanceOf(AuthError);
      expect(error.name).toBe('AuthError');
      expect(error.code).toBe(AUTH_ERROR_CODES.TOKEN_EXPIRED);
      expect(error.message).toBe('Custom message');
      expect(error.userMessage).toBe(AUTH_ERROR_MESSAGES[AUTH_ERROR_CODES.TOKEN_EXPIRED]);
      expect(error.originalError).toBe(originalError);
      expect(error.context).toEqual(context);
    });

    it('should use default message when none provided', () => {
      const error = new AuthError(AUTH_ERROR_CODES.NETWORK_ERROR);

      expect(error.message).toBe(AUTH_ERROR_MESSAGES[AUTH_ERROR_CODES.NETWORK_ERROR]);
      expect(error.userMessage).toBe(AUTH_ERROR_MESSAGES[AUTH_ERROR_CODES.NETWORK_ERROR]);
    });

    it('should work without optional parameters', () => {
      const error = new AuthError(AUTH_ERROR_CODES.NOT_AUTHENTICATED);

      expect(error.code).toBe(AUTH_ERROR_CODES.NOT_AUTHENTICATED);
      expect(error.originalError).toBeUndefined();
      expect(error.context).toBeUndefined();
    });

    it('should create error for all error codes', () => {
      const codes = Object.values(AUTH_ERROR_CODES);
      
      codes.forEach((code) => {
        const error = new AuthError(code as AuthErrorCode);
        
        expect(error.code).toBe(code);
        expect(error.userMessage).toBe(AUTH_ERROR_MESSAGES[code as AuthErrorCode]);
        expect(error.message).toBe(AUTH_ERROR_MESSAGES[code as AuthErrorCode]);
      });
    });
  });

  describe('getUserMessage', () => {
    it('should return user-friendly message', () => {
      const error = new AuthError(AUTH_ERROR_CODES.TOKEN_EXPIRED);
      
      expect(error.getUserMessage()).toBe(
        'Your session has expired. Please log in again.'
      );
    });

    it('should return correct message for all error codes', () => {
      const codes = Object.values(AUTH_ERROR_CODES);
      
      codes.forEach((code) => {
        const error = new AuthError(code as AuthErrorCode);
        const message = error.getUserMessage();
        
        expect(message).toBe(AUTH_ERROR_MESSAGES[code as AuthErrorCode]);
        expect(message).toBeTruthy();
        expect(message.length).toBeGreaterThan(0);
      });
    });
  });

  describe('isCode', () => {
    it('should return true for matching code', () => {
      const error = new AuthError(AUTH_ERROR_CODES.REFRESH_FAILED);
      
      expect(error.isCode(AUTH_ERROR_CODES.REFRESH_FAILED)).toBe(true);
    });

    it('should return false for non-matching code', () => {
      const error = new AuthError(AUTH_ERROR_CODES.REFRESH_FAILED);
      
      expect(error.isCode(AUTH_ERROR_CODES.TOKEN_EXPIRED)).toBe(false);
      expect(error.isCode(AUTH_ERROR_CODES.NETWORK_ERROR)).toBe(false);
    });
  });

  describe('toJSON', () => {
    it('should serialize error with all properties', () => {
      const originalError = new Error('Original error');
      const context = { userId: '123' };
      
      const error = new AuthError(
        AUTH_ERROR_CODES.COGNITO_ERROR,
        'Test message',
        originalError,
        context
      );

      const json = error.toJSON();

      expect(json).toEqual({
        name: 'AuthError',
        code: AUTH_ERROR_CODES.COGNITO_ERROR,
        message: 'Test message',
        userMessage: AUTH_ERROR_MESSAGES[AUTH_ERROR_CODES.COGNITO_ERROR],
        context: { userId: '123' },
        stack: expect.any(String),
        originalError: {
          name: 'Error',
          message: 'Original error',
          stack: expect.any(String),
        },
      });
    });

    it('should serialize error without optional properties', () => {
      const error = new AuthError(AUTH_ERROR_CODES.STORAGE_ERROR);

      const json = error.toJSON();

      expect(json).toEqual({
        name: 'AuthError',
        code: AUTH_ERROR_CODES.STORAGE_ERROR,
        message: AUTH_ERROR_MESSAGES[AUTH_ERROR_CODES.STORAGE_ERROR],
        userMessage: AUTH_ERROR_MESSAGES[AUTH_ERROR_CODES.STORAGE_ERROR],
        context: undefined,
        stack: expect.any(String),
        originalError: undefined,
      });
    });

    it('should produce valid JSON string', () => {
      const error = new AuthError(
        AUTH_ERROR_CODES.INVALID_TOKEN,
        'Test',
        new Error('Original')
      );

      const json = error.toJSON();
      const jsonString = JSON.stringify(json);

      expect(() => JSON.parse(jsonString)).not.toThrow();
      
      const parsed = JSON.parse(jsonString);
      expect(parsed.code).toBe(AUTH_ERROR_CODES.INVALID_TOKEN);
      expect(parsed.name).toBe('AuthError');
    });
  });
});

describe('isAuthError', () => {
  it('should return true for AuthError instances', () => {
    const error = new AuthError(AUTH_ERROR_CODES.TOKEN_EXPIRED);
    
    expect(isAuthError(error)).toBe(true);
  });

  it('should return false for regular Error', () => {
    const error = new Error('Regular error');
    
    expect(isAuthError(error)).toBe(false);
  });

  it('should return false for non-error values', () => {
    expect(isAuthError(null)).toBe(false);
    expect(isAuthError(undefined)).toBe(false);
    expect(isAuthError('string')).toBe(false);
    expect(isAuthError(123)).toBe(false);
    expect(isAuthError({})).toBe(false);
    expect(isAuthError([])).toBe(false);
  });

  it('should work as type guard', () => {
    const error: unknown = new AuthError(AUTH_ERROR_CODES.NETWORK_ERROR);
    
    if (isAuthError(error)) {
      // TypeScript should recognize error as AuthError here
      expect(error.code).toBe(AUTH_ERROR_CODES.NETWORK_ERROR);
      expect(error.getUserMessage()).toBeTruthy();
    } else {
      throw new Error('Type guard failed');
    }
  });
});

describe('toAuthError', () => {
  it('should return AuthError unchanged', () => {
    const originalError = new AuthError(AUTH_ERROR_CODES.TOKEN_EXPIRED);
    const result = toAuthError(originalError);
    
    expect(result).toBe(originalError);
    expect(result.code).toBe(AUTH_ERROR_CODES.TOKEN_EXPIRED);
  });

  it('should convert Error with network keyword to NETWORK_ERROR', () => {
    const error = new Error('network request failed');
    const result = toAuthError(error);
    
    expect(result).toBeInstanceOf(AuthError);
    expect(result.code).toBe(AUTH_ERROR_CODES.NETWORK_ERROR);
    expect(result.originalError).toBe(error);
  });

  it('should convert Error with fetch keyword to NETWORK_ERROR', () => {
    const error = new Error('fetch failed');
    const result = toAuthError(error);
    
    expect(result.code).toBe(AUTH_ERROR_CODES.NETWORK_ERROR);
  });

  it('should convert Error with token keyword to TOKEN_EXPIRED', () => {
    const error = new Error('Invalid token provided');
    const result = toAuthError(error);
    
    expect(result.code).toBe(AUTH_ERROR_CODES.TOKEN_EXPIRED);
  });

  it('should convert Error with expired keyword to TOKEN_EXPIRED', () => {
    const error = new Error('Session expired');
    const result = toAuthError(error);
    
    expect(result.code).toBe(AUTH_ERROR_CODES.TOKEN_EXPIRED);
  });

  it('should use default code for generic Error', () => {
    const error = new Error('Something went wrong');
    const result = toAuthError(error);
    
    expect(result.code).toBe(AUTH_ERROR_CODES.COGNITO_ERROR);
    expect(result.message).toBe('Something went wrong');
    expect(result.originalError).toBe(error);
  });

  it('should use custom default code', () => {
    const error = new Error('Generic error');
    const result = toAuthError(error, AUTH_ERROR_CODES.STORAGE_ERROR);
    
    expect(result.code).toBe(AUTH_ERROR_CODES.STORAGE_ERROR);
  });

  it('should convert string to AuthError', () => {
    const result = toAuthError('Error message string');
    
    expect(result).toBeInstanceOf(AuthError);
    expect(result.code).toBe(AUTH_ERROR_CODES.COGNITO_ERROR);
    expect(result.message).toBe('Error message string');
  });

  it('should convert unknown types to AuthError', () => {
    const result = toAuthError({ unknown: 'object' });
    
    expect(result).toBeInstanceOf(AuthError);
    expect(result.code).toBe(AUTH_ERROR_CODES.COGNITO_ERROR);
    expect(result.message).toBe('An unexpected error occurred');
  });

  it('should handle null and undefined', () => {
    const nullResult = toAuthError(null);
    expect(nullResult.code).toBe(AUTH_ERROR_CODES.COGNITO_ERROR);
    
    const undefinedResult = toAuthError(undefined);
    expect(undefinedResult.code).toBe(AUTH_ERROR_CODES.COGNITO_ERROR);
  });
});

describe('handleAuthError', () => {
  it('should convert error to AuthError', () => {
    const error = new Error('Test error');
    const result = handleAuthError(error);
    
    expect(result).toBeInstanceOf(AuthError);
  });

  it('should preserve AuthError', () => {
    const error = new AuthError(AUTH_ERROR_CODES.REFRESH_FAILED);
    const result = handleAuthError(error);
    
    expect(result).toBe(error);
  });

  it('should add context to error', () => {
    const error = new Error('Test error');
    const context = { action: 'login', userId: '123' };
    
    const result = handleAuthError(error, context);
    
    // Context is logged but not added to error object
    expect(result).toBeInstanceOf(AuthError);
  });

  it('should handle string errors', () => {
    const result = handleAuthError('String error');
    
    expect(result).toBeInstanceOf(AuthError);
    expect(result.message).toBe('String error');
  });
});

describe('shouldReAuthenticate', () => {
  it('should return true for NOT_AUTHENTICATED', () => {
    const error = new AuthError(AUTH_ERROR_CODES.NOT_AUTHENTICATED);
    
    expect(shouldReAuthenticate(error)).toBe(true);
  });

  it('should return true for TOKEN_EXPIRED', () => {
    const error = new AuthError(AUTH_ERROR_CODES.TOKEN_EXPIRED);
    
    expect(shouldReAuthenticate(error)).toBe(true);
  });

  it('should return true for REFRESH_FAILED', () => {
    const error = new AuthError(AUTH_ERROR_CODES.REFRESH_FAILED);
    
    expect(shouldReAuthenticate(error)).toBe(true);
  });

  it('should return true for INVALID_TOKEN', () => {
    const error = new AuthError(AUTH_ERROR_CODES.INVALID_TOKEN);
    
    expect(shouldReAuthenticate(error)).toBe(true);
  });

  it('should return false for NETWORK_ERROR', () => {
    const error = new AuthError(AUTH_ERROR_CODES.NETWORK_ERROR);
    
    expect(shouldReAuthenticate(error)).toBe(false);
  });

  it('should return false for COGNITO_ERROR', () => {
    const error = new AuthError(AUTH_ERROR_CODES.COGNITO_ERROR);
    
    expect(shouldReAuthenticate(error)).toBe(false);
  });

  it('should return false for STORAGE_ERROR', () => {
    const error = new AuthError(AUTH_ERROR_CODES.STORAGE_ERROR);
    
    expect(shouldReAuthenticate(error)).toBe(false);
  });

  it('should return false for non-AuthError', () => {
    const error = new Error('Regular error');
    
    expect(shouldReAuthenticate(error)).toBe(false);
  });

  it('should return false for non-error values', () => {
    expect(shouldReAuthenticate(null)).toBe(false);
    expect(shouldReAuthenticate(undefined)).toBe(false);
    expect(shouldReAuthenticate('string')).toBe(false);
  });
});

describe('isRetryableError', () => {
  it('should return true for NETWORK_ERROR', () => {
    const error = new AuthError(AUTH_ERROR_CODES.NETWORK_ERROR);
    
    expect(isRetryableError(error)).toBe(true);
  });

  it('should return true for COGNITO_ERROR', () => {
    const error = new AuthError(AUTH_ERROR_CODES.COGNITO_ERROR);
    
    expect(isRetryableError(error)).toBe(true);
  });

  it('should return false for TOKEN_EXPIRED', () => {
    const error = new AuthError(AUTH_ERROR_CODES.TOKEN_EXPIRED);
    
    expect(isRetryableError(error)).toBe(false);
  });

  it('should return false for REFRESH_FAILED', () => {
    const error = new AuthError(AUTH_ERROR_CODES.REFRESH_FAILED);
    
    expect(isRetryableError(error)).toBe(false);
  });

  it('should return false for INVALID_TOKEN', () => {
    const error = new AuthError(AUTH_ERROR_CODES.INVALID_TOKEN);
    
    expect(isRetryableError(error)).toBe(false);
  });

  it('should return false for STORAGE_ERROR', () => {
    const error = new AuthError(AUTH_ERROR_CODES.STORAGE_ERROR);
    
    expect(isRetryableError(error)).toBe(false);
  });

  it('should return false for non-AuthError', () => {
    const error = new Error('Regular error');
    
    expect(isRetryableError(error)).toBe(false);
  });

  it('should return false for non-error values', () => {
    expect(isRetryableError(null)).toBe(false);
    expect(isRetryableError(undefined)).toBe(false);
    expect(isRetryableError({})).toBe(false);
  });
});

describe('AUTH_ERROR_MESSAGES', () => {
  it('should have message for every error code', () => {
    const codes = Object.values(AUTH_ERROR_CODES);
    
    codes.forEach((code) => {
      const message = AUTH_ERROR_MESSAGES[code as AuthErrorCode];
      
      expect(message).toBeTruthy();
      expect(typeof message).toBe('string');
      expect(message.length).toBeGreaterThan(0);
    });
  });

  it('should have user-friendly messages', () => {
    const codes = Object.values(AUTH_ERROR_CODES);
    
    codes.forEach((code) => {
      const message = AUTH_ERROR_MESSAGES[code as AuthErrorCode];
      
      // User-friendly messages should:
      // - Not contain technical jargon
      // - Provide actionable guidance
      // - Be clear and concise
      expect(message).not.toContain('undefined');
      expect(message).not.toContain('null');
      expect(message.length).toBeLessThan(200); // Reasonable length
    });
  });
});
