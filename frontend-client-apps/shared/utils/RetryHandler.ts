/**
 * Retry configuration options
 */
export interface RetryOptions {
  maxAttempts: number;
  initialDelay: number; // milliseconds
  maxDelay: number; // milliseconds
  backoffMultiplier: number;
  onRetry?: (attempt: number, delay: number, error: Error) => void;
}

/**
 * Default retry options
 */
const DEFAULT_RETRY_OPTIONS: RetryOptions = {
  maxAttempts: 3,
  initialDelay: 1000,
  maxDelay: 30000,
  backoffMultiplier: 2,
};

/**
 * Retry handler with exponential backoff
 */
export class RetryHandler {
  private options: RetryOptions;
  private currentAttempt: number = 0;

  /**
   * Create retry handler with options
   * @param options - Retry configuration options
   */
  constructor(options: Partial<RetryOptions> = {}) {
    this.options = { ...DEFAULT_RETRY_OPTIONS, ...options };
  }

  /**
   * Execute function with retry logic
   * @param fn - Function to execute
   * @returns Promise that resolves with function result
   */
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    this.currentAttempt = 0;

    while (true) {
      try {
        this.currentAttempt++;
        return await fn();
      } catch (error) {
        // If we've reached max attempts, throw the error
        if (this.currentAttempt >= this.options.maxAttempts) {
          throw error;
        }

        // Calculate delay with exponential backoff
        const delay = this.calculateDelay();

        // Call onRetry callback if provided
        if (this.options.onRetry && error instanceof Error) {
          this.options.onRetry(this.currentAttempt, delay, error);
        }

        // Wait before retrying
        await this.sleep(delay);
      }
    }
  }

  /**
   * Calculate delay for next retry with exponential backoff
   * @returns Delay in milliseconds
   */
  private calculateDelay(): number {
    const exponentialDelay =
      this.options.initialDelay * Math.pow(this.options.backoffMultiplier, this.currentAttempt - 1);

    // Cap at max delay
    return Math.min(exponentialDelay, this.options.maxDelay);
  }

  /**
   * Sleep for specified duration
   * @param ms - Duration in milliseconds
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Get current attempt number
   * @returns Current attempt number (1-indexed)
   */
  getCurrentAttempt(): number {
    return this.currentAttempt;
  }

  /**
   * Get remaining attempts
   * @returns Number of remaining attempts
   */
  getRemainingAttempts(): number {
    return Math.max(0, this.options.maxAttempts - this.currentAttempt);
  }

  /**
   * Reset attempt counter
   */
  reset(): void {
    this.currentAttempt = 0;
  }
}

/**
 * Create a retry handler with custom options
 * @param options - Retry configuration options
 * @returns RetryHandler instance
 */
export function createRetryHandler(options: Partial<RetryOptions> = {}): RetryHandler {
  return new RetryHandler(options);
}

/**
 * Execute function with retry logic (convenience function)
 * @param fn - Function to execute
 * @param options - Retry configuration options
 * @returns Promise that resolves with function result
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  options: Partial<RetryOptions> = {}
): Promise<T> {
  const handler = new RetryHandler(options);
  return handler.execute(fn);
}
