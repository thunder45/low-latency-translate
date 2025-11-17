import { describe, it, expect, vi, beforeEach } from 'vitest';
import { RetryHandler } from '../RetryHandler';

describe('RetryHandler', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('execute', () => {
    it('should succeed on first attempt', async () => {
      const operation = vi.fn().mockResolvedValue('success');
      const handler = new RetryHandler();
      
      const promise = handler.execute(operation);
      await vi.runAllTimersAsync();
      const result = await promise;
      
      expect(result).toBe('success');
      expect(operation).toHaveBeenCalledTimes(1);
    });

    it('should retry on failure and eventually succeed', async () => {
      const operation = vi.fn()
        .mockRejectedValueOnce(new Error('fail 1'))
        .mockRejectedValueOnce(new Error('fail 2'))
        .mockResolvedValue('success');
      
      const handler = new RetryHandler({ maxAttempts: 3 });
      
      const promise = handler.execute(operation);
      await vi.runAllTimersAsync();
      const result = await promise;
      
      expect(result).toBe('success');
      expect(operation).toHaveBeenCalledTimes(3);
    });

    it('should fail after max attempts', async () => {
      const operation = vi.fn().mockRejectedValue(new Error('persistent failure'));
      const handler = new RetryHandler({ maxAttempts: 3 });
      
      const promise = handler.execute(operation);
      await vi.runAllTimersAsync();
      
      await expect(promise).rejects.toThrow('persistent failure');
      expect(operation).toHaveBeenCalledTimes(3);
    });

    it('should use exponential backoff', async () => {
      const operation = vi.fn()
        .mockRejectedValueOnce(new Error('fail 1'))
        .mockRejectedValueOnce(new Error('fail 2'))
        .mockResolvedValue('success');
      
      const handler = new RetryHandler({
        maxAttempts: 3,
        initialDelay: 1000,
        maxDelay: 10000,
      });
      
      const promise = handler.execute(operation);
      
      // First attempt fails immediately
      await vi.advanceTimersByTimeAsync(0);
      expect(operation).toHaveBeenCalledTimes(1);
      
      // Wait for first retry (1000ms)
      await vi.advanceTimersByTimeAsync(1000);
      expect(operation).toHaveBeenCalledTimes(2);
      
      // Wait for second retry (2000ms)
      await vi.advanceTimersByTimeAsync(2000);
      expect(operation).toHaveBeenCalledTimes(3);
      
      const result = await promise;
      expect(result).toBe('success');
    });

    it('should respect max delay', async () => {
      const operation = vi.fn()
        .mockRejectedValueOnce(new Error('fail 1'))
        .mockRejectedValueOnce(new Error('fail 2'))
        .mockResolvedValue('success');
      
      const handler = new RetryHandler({
        maxAttempts: 3,
        initialDelay: 1000,
        maxDelay: 1500,
      });
      
      const promise = handler.execute(operation);
      
      await vi.advanceTimersByTimeAsync(0);
      expect(operation).toHaveBeenCalledTimes(1);
      
      // First retry at 1000ms
      await vi.advanceTimersByTimeAsync(1000);
      expect(operation).toHaveBeenCalledTimes(2);
      
      // Second retry should be capped at 1500ms (not 2000ms)
      await vi.advanceTimersByTimeAsync(1500);
      expect(operation).toHaveBeenCalledTimes(3);
      
      const result = await promise;
      expect(result).toBe('success');
    });

    it('should call onRetry callback', async () => {
      const operation = vi.fn()
        .mockRejectedValueOnce(new Error('fail 1'))
        .mockResolvedValue('success');
      
      const onRetry = vi.fn();
      const handler = new RetryHandler({ maxAttempts: 2, onRetry });
      
      const promise = handler.execute(operation);
      await vi.runAllTimersAsync();
      await promise;
      
      expect(onRetry).toHaveBeenCalledWith(1, expect.any(Number), expect.any(Error));
    });

    it('should not retry if maxAttempts is 1', async () => {
      const operation = vi.fn().mockRejectedValue(new Error('fail'));
      const handler = new RetryHandler({ maxAttempts: 1 });
      
      const promise = handler.execute(operation);
      await vi.runAllTimersAsync();
      
      await expect(promise).rejects.toThrow('fail');
      expect(operation).toHaveBeenCalledTimes(1);
    });
  });
});
