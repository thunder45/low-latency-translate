/**
 * AuthError - Authentication error handling utilities
 * 
 * Provides structured error handling for authentication operations
 * with user-friendly error messages and error codes.
 */

/**
 * Authentication error codes
 */
export const AUTH_ERROR_CODES = {
  NOT_AUTHENTICATED: 'NOT_AUTHENTICATED',
  TOKEN_EXPIRED: 'TOKEN_EXPIRED',
  REFRESH_FAILED: 'REFRESH_FAILED',
  INVALID_TOKEN: 'INVALID_TOKEN',
  NETWORK_ERROR: 'NETWORK_ERROR',
  COGNITO_ERROR: 'COGNITO_ERROR',
  STORAGE_ERROR: 'STORAGE_ERROR',
  INITIALIZATION_ERROR: 'INITIALIZATION_ERROR',
  CALLBACK_ERROR: 'CALLBACK_ERROR',
  LOGOUT_ERROR: 'LOGOUT_ERROR',
} as const;

/**
 * Type for error codes
 */
export type AuthErrorCode = typeof AUTH_ERROR_CODES[keyof typeof AUTH_ERROR_CODES];

/**
 * User-friendly error messages mapped to error codes
 */
export const AUTH_ERROR_MESSAGES: Record<AuthErrorCode, string> = {
  [AUTH_ERROR_CODES.NOT_AUTHENTICATED]: 'Please log in to create a session',
  [AUTH_ERROR_CODES.TOKEN_EXPIRED]: 'Your session has expired. Please log in again.',
  [AUTH_ERROR_CODES.REFRESH_FAILED]: 'Failed to refresh authentication. Please log in again.',
  [AUTH_ERROR_CODES.INVALID_TOKEN]: 'Invalid authentication token. Please log in again.',
  [AUTH_ERROR_CODES.NETWORK_ERROR]: 'Network error. Please check your connection and try again.',
  [AUTH_ERROR_CODES.COGNITO_ERROR]: 'Authentication service error. Please try again later.',
  [AUTH_ERROR_CODES.STORAGE_ERROR]: 'Failed to store authentication data. Please try again.',
  [AUTH_ERROR_CODES.INITIALIZATION_ERROR]: 'Failed to initialize authentication. Please refresh the page.',
  [AUTH_ERROR_CODES.CALLBACK_ERROR]: 'Failed to complete login. Please try again.',
  [AUTH_ERROR_CODES.LOGOUT_ERROR]: 'Failed to log out. Please try again.',
};

/**
 * Authentication error class
 */
export class AuthError extends Error {
  /**
   * Error code for programmatic handling
   */
  public readonly code: AuthErrorCode;

  /**
   * User-friendly error message
   */
  public readonly userMessage: string;

  /**
   * Original error if available
   */
  public readonly originalError?: Error;

  /**
   * Additional context data
   */
  public readonly context?: Record<string, any>;

  constructor(
    code: AuthErrorCode,
    message?: string,
    originalError?: Error,
    context?: Record<string, any>
  ) {
    // Use provided message or default user-friendly message
    const errorMessage = message || AUTH_ERROR_MESSAGES[code];
    super(errorMessage);

    this.name = 'AuthError';
    this.code = code;
    this.userMessage = AUTH_ERROR_MESSAGES[code];
    this.originalError = originalError;
    this.context = context;

    // Maintains proper stack trace for where error was thrown (V8 only)
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, AuthError);
    }
  }

  /**
   * Get user-friendly error message
   */
  getUserMessage(): string {
    return this.userMessage;
  }

  /**
   * Check if error is of specific code
   */
  isCode(code: AuthErrorCode): boolean {
    return this.code === code;
  }

  /**
   * Convert to JSON for logging
   */
  toJSON(): Record<string, any> {
    return {
      name: this.name,
      code: this.code,
      message: this.message,
      userMessage: this.userMessage,
      context: this.context,
      stack: this.stack,
      originalError: this.originalError ? {
        name: this.originalError.name,
        message: this.originalError.message,
        stack: this.originalError.stack,
      } : undefined,
    };
  }
}

/**
 * Type guard to check if error is AuthError
 */
export function isAuthError(error: unknown): error is AuthError {
  return error instanceof AuthError;
}

/**
 * Helper to create AuthError from unknown error
 */
export function toAuthError(
  error: unknown,
  defaultCode: AuthErrorCode = AUTH_ERROR_CODES.COGNITO_ERROR
): AuthError {
  if (isAuthError(error)) {
    return error;
  }

  if (error instanceof Error) {
    // Map common error types to auth error codes
    if (error.message.includes('network') || error.message.includes('fetch')) {
      return new AuthError(AUTH_ERROR_CODES.NETWORK_ERROR, undefined, error);
    }
    if (error.message.includes('token') || error.message.includes('expired')) {
      return new AuthError(AUTH_ERROR_CODES.TOKEN_EXPIRED, undefined, error);
    }
    return new AuthError(defaultCode, error.message, error);
  }

  // Unknown error type
  return new AuthError(
    defaultCode,
    typeof error === 'string' ? error : 'An unexpected error occurred'
  );
}

/**
 * Helper to handle auth errors with logging
 */
export function handleAuthError(
  error: unknown,
  context?: Record<string, any>
): AuthError {
  const authError = toAuthError(error);

  // Log error (without sensitive data)
  console.error('Authentication error:', {
    code: authError.code,
    message: authError.message,
    context: context || authError.context,
    // Don't log tokens or sensitive data
  });

  return authError;
}

/**
 * Helper to check if error should trigger re-authentication
 */
export function shouldReAuthenticate(error: unknown): boolean {
  if (!isAuthError(error)) {
    return false;
  }

  const reAuthCodes: AuthErrorCode[] = [
    AUTH_ERROR_CODES.NOT_AUTHENTICATED,
    AUTH_ERROR_CODES.TOKEN_EXPIRED,
    AUTH_ERROR_CODES.REFRESH_FAILED,
    AUTH_ERROR_CODES.INVALID_TOKEN,
  ];

  return reAuthCodes.includes(error.code);
}

/**
 * Helper to check if error is retryable
 */
export function isRetryableError(error: unknown): boolean {
  if (!isAuthError(error)) {
    return false;
  }

  const retryableCodes: AuthErrorCode[] = [
    AUTH_ERROR_CODES.NETWORK_ERROR,
    AUTH_ERROR_CODES.COGNITO_ERROR,
  ];

  return retryableCodes.includes(error.code);
}
