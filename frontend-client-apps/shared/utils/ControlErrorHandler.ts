import type { ControlError, ControlErrorType } from '../types/controls';

/**
 * Error handler for control operations
 * Provides retry logic and user-friendly error messages
 */
export class ControlErrorHandler {
  /**
   * Retry operation with exponential backoff
   */
  static async retryWithBackoff<T>(
    operation: () => Promise<T>,
    maxAttempts: number = 3
  ): Promise<T> {
    let attempt = 0;
    let delay = 1000;
    
    while (attempt < maxAttempts) {
      try {
        return await operation();
      } catch (error) {
        attempt++;
        if (attempt >= maxAttempts) {
          throw error;
        }
        await new Promise(resolve => setTimeout(resolve, delay));
        delay *= 2;
      }
    }
    
    throw new Error('Max retry attempts exceeded');
  }
  
  /**
   * Handle control error and provide user feedback
   */
  static handleError(error: ControlError): void {
    console.error(`Control error [${error.type}]:`, error.message);
    
    // Display user-friendly error message
    if (error.recoverable) {
      this.showRecoverableError(error);
    } else {
      this.showFatalError(error);
    }
    
    // Log to monitoring service
    this.logError(error);
  }
  
  /**
   * Create control error from generic error
   */
  static createControlError(
    error: Error,
    type: ControlErrorType,
    recoverable: boolean = true
  ): ControlError {
    return {
      type,
      message: error.message,
      recoverable,
      timestamp: Date.now(),
    };
  }
  
  /**
   * Show recoverable error notification
   */
  private static showRecoverableError(error: ControlError): void {
    // In a real implementation, this would show a toast notification
    console.warn('Recoverable error:', error.message);
  }
  
  /**
   * Show fatal error notification
   */
  private static showFatalError(error: ControlError): void {
    // In a real implementation, this would show a modal or redirect
    console.error('Fatal error:', error.message);
  }
  
  /**
   * Log error to monitoring service
   */
  private static logError(error: ControlError): void {
    // In a real implementation, this would send to monitoring service
    if (typeof window !== 'undefined' && (window as any).monitoring) {
      (window as any).monitoring.logError({
        type: error.type,
        message: error.message,
        timestamp: error.timestamp,
        recoverable: error.recoverable,
      });
    }
  }
}
