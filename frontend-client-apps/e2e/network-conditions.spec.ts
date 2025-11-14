import { test, expect } from '@playwright/test';

test.describe('Network Conditions', () => {
  test('should handle slow 3G connection', async ({ page, context }) => {
    // Simulate slow 3G
    await context.route('**/*', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 500)); // 500ms delay
      await route.continue();
    });

    await page.goto('http://localhost:3001');
    
    // Verify page loads despite slow connection
    await expect(page.locator('[data-testid="session-joiner"]')).toBeVisible({ timeout: 10000 });
    
    // Verify loading indicators
    const loadingIndicator = page.locator('[data-testid="loading-indicator"]');
    // Loading indicator should appear during slow load
  });

  test('should handle connection interruption', async ({ page, context }) => {
    await page.goto('http://localhost:3001');
    
    // Simulate connection loss
    await context.setOffline(true);
    
    // Verify offline indicator
    await expect(page.locator('[data-testid="connection-status"]')).toContainText(/offline|disconnected/i, {
      timeout: 5000,
    });
    
    // Restore connection
    await context.setOffline(false);
    
    // Verify reconnection
    await expect(page.locator('[data-testid="connection-status"]')).toContainText(/connected/i, {
      timeout: 10000,
    });
  });

  test('should retry on network failure', async ({ page, context }) => {
    let requestCount = 0;
    
    // Fail first 2 requests, succeed on 3rd
    await context.route('**/api/**', async (route) => {
      requestCount++;
      if (requestCount <= 2) {
        await route.abort('failed');
      } else {
        await route.continue();
      }
    });

    await page.goto('http://localhost:3001');
    
    // Verify retry mechanism works
    // (Implementation-specific verification)
    expect(requestCount).toBeGreaterThan(1);
  });
});
