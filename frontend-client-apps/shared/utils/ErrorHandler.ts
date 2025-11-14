/**
 * Error types for application errors
 */
export enum ErrorType {
  // Network errors
  NETWORK_ERROR = 'NETWORK_ERROR',
  WEBSOCKET_ERROR = 'WEBSOCKET_ERROR',
  CONNECTION_TIMEOUT = 'CONNECTION_TIMEOUT',
  
  // Authentication errors
  AUTH_FAILED = 'AUTH_FAILED',
  AUTH_EXPIRED = 'AUTH_EXPIRED',
  AUTH_INVALID = 'AUTH_INVALID',
  
  // Session errors
  SESSION_NOT_FOUND = 'SESSION_NOT_FOUND',
  SESSION_FULL = 'SESSION_FULL',
  SESSION_ENDED = 'SESSION_ENDED',
  SESSION_CREATE_FAILED = 'SESSION_CREATE_FAILED',
  
  // Audio errors
  MICROPHONE_ACCESS_DENIED = 'MICROPHONE_ACCESS_DENIED',
  MICROPHONE_NOT_FOUND = 'MICROPHONE_NOT_FOUND',
  AUDIO_PROCESSING_ERROR = 'AUDIO_PROCESSING_ERROR',
  AUDIO_PLAYBACK_ERROR = 'AUDIO_PLAYBACK_ERROR',
  
  // Validation errors
  INVALID_INPUT = 'INVALID_INPUT',
  INVALID_SESSION_ID = 'INVALID_SESSION_ID',
  INVALID_LANGUAGE = 'INVALID_LANGUAGE',
  
  // Rate limiting
  RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED',
  
  // Server errors
  SERVER_ERROR = 'SERVER_ERROR',
  SERVICE_UNAVAILABLE = 'SERVICE_UNAVAILABLE',
  
  // Browser compatibility
  BROWSER_NOT_SUPPORTED = 'BROWSER_NOT_SUPPORTED',
  FEATURE_NOT_SUPPORTED = 'FEATURE_NOT_SUPPORTED',
  
  // Unknown
  UNKNOWN_ERROR = 'UNKNOWN_ERROR',
}

/**
 * Application error interface
 */
export interface AppError {
  type: ErrorType;
  message: string;
  userMessage: string;
  recoverable: boolean;
  retryable: boolean;
  details?: Record<string, unknown>;
}

/**
 * Recovery action for errors
 */
export interface RecoveryAction {
  label: string;
  action: () => void | Promise<void>;
}

/**
 * Error handler utility class
 */
export class ErrorHandler {
  /**
   * Handle error and return user-friendly error object
   * @param error - Error to handle
   * @param context - Additional context about the error
   * @returns AppError object with user-friendly message
   */
  static handle(error: unknown, context?: Record<string, unknown>): AppError {
    // If it's already an AppError, return it
    if (this.isAppError(error)) {
      return error;
    }

    // Handle different error types
    if (error instanceof Error) {
      return this.handleStandardError(error, context);
    }

    // Handle string errors
    if (typeof error === 'string') {
      return this.createError(ErrorType.UNKNOWN_ERROR, error, error);
    }

    // Handle unknown errors
    return this.createError(
      ErrorType.UNKNOWN_ERROR,
      'An unexpected error occurred',
      'An unexpected error occurred. Please try again.'
    );
  }

  /**
   * Handle standard JavaScript Error objects
   */
  private static handleStandardError(error: Error, context?: Record<string, unknown>): AppError {
    const message = error.message.toLowerCase();

    // Network errors
    if (message.includes('network') || message.includes('fetch')) {
      return this.createError(
        ErrorType.NETWORK_ERROR,
        error.message,
        'Network connection failed. Please check your internet connection and try again.',
        true,
        true
      );
    }

    // WebSocket errors
    if (message.includes('websocket')) {
      return this.createError(
        ErrorType.WEBSOCKET_ERROR,
        error.message,
        'Connection to server failed. Attempting to reconnect...',
        true,
        true
      );
    }

    // Microphone errors
    if (message.includes('microphone') || message.includes('getusermedia')) {
      return this.createError(
        ErrorType.MICROPHONE_ACCESS_DENIED,
        error.message,
        'Microphone access denied. Please allow microphone access in your browser settings.',
        true,
        false
      );
    }

    // Default error
    return this.createError(
      ErrorType.UNKNOWN_ERROR,
      error.message,
      'An error occurred. Please try again.',
      true,
      true,
      context
    );
  }

  /**
   * Create AppError object
   */
  private static createError(
    type: ErrorType,
    message: string,
    userMessage: string,
    recoverable: boolean = true,
    retryable: boolean = false,
    details?: Record<string, unknown>
  ): AppError {
    return {
      type,
      message,
      userMessage,
      recoverable,
      retryable,
      details,
    };
  }

  /**
   * Check if error is an AppError
   */
  private static isAppError(error: unknown): error is AppError {
    return (
      typeof error === 'object' &&
      error !== null &&
      'type' in error &&
      'message' in error &&
      'userMessage' in error &&
      'recoverable' in error &&
      'retryable' in error
    );
  }

  /**
   * Get recovery actions for error
   * @param error - Error to get recovery actions for
   * @param callbacks - Callback functions for recovery actions
   * @returns Array of recovery actions
   */
  static getRecoveryActions(
    error: AppError,
    callbacks: {
      retry?: () => void | Promise<void>;
      reconnect?: () => void | Promise<void>;
      refresh?: () => void | Promise<void>;
      goBack?: () => void | Promise<void>;
    }
  ): RecoveryAction[] {
    const actions: RecoveryAction[] = [];

    // Add retry action for retryable errors
    if (error.retryable && callbacks.retry) {
      actions.push({
        label: 'Retry',
        action: callbacks.retry,
      });
    }

    // Add reconnect action for connection errors
    if (
      (error.type === ErrorType.WEBSOCKET_ERROR || error.type === ErrorType.CONNECTION_TIMEOUT) &&
      callbacks.reconnect
    ) {
      actions.push({
        label: 'Reconnect',
        action: callbacks.reconnect,
      });
    }

    // Add refresh action for session errors
    if (error.type === ErrorType.SESSION_NOT_FOUND && callbacks.refresh) {
      actions.push({
        label: 'Refresh',
        action: callbacks.refresh,
      });
    }

    // Add go back action for non-recoverable errors
    if (!error.recoverable && callbacks.goBack) {
      actions.push({
        label: 'Go Back',
        action: callbacks.goBack,
      });
    }

    return actions;
  }

  /**
   * Create error from HTTP status code
   * @param statusCode - HTTP status code
   * @param message - Error message
   * @returns AppError object
   */
  static fromHttpStatus(statusCode: number, message?: string): AppError {
    switch (statusCode) {
      case 401:
        return this.createError(
          ErrorType.AUTH_INVALID,
          message || 'Unauthorized',
          'Authentication failed. Please sign in again.',
          true,
          false
        );
      case 404:
        return this.createError(
          ErrorType.SESSION_NOT_FOUND,
          message || 'Not found',
          'Session not found. Please check the session ID and try again.',
          true,
          false
        );
      case 429:
        return this.createError(
          ErrorType.RATE_LIMIT_EXCEEDED,
          message || 'Too many requests',
          'Too many requests. Please wait a moment and try again.',
          true,
          true
        );
      case 503:
        return this.createError(
          ErrorType.SERVICE_UNAVAILABLE,
          message || 'Service unavailable',
          'Service is temporarily unavailable. Please try again later.',
          true,
          true
        );
      default:
        return this.createError(
          ErrorType.SERVER_ERROR,
          message || 'Server error',
          'A server error occurred. Please try again.',
          true,
          true
        );
    }
  }
}
