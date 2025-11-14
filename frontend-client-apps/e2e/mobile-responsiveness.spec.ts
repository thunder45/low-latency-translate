import { test, expect, devices } from '@playwright/test';

test.describe('Mobile Responsiveness', () => {
  test('should be responsive on mobile devices', async ({ browser }) => {
    const context = await browser.newContext({
      ...devices['iPhone 12'],
    });
    const page = await context.newPage();

    try {
      // Navigate to listener app (simpler for mobile)
      await page.goto('http://localhost:3001');
      
      // Verify viewport
      const viewport = page.viewportSize();
      expect(viewport?.width).toBeLessThan(500);
      
      // Check for mobile-optimized layout
      await expect(page.locator('[data-testid="session-joiner"]')).toBeVisible();
      
      // Verify touch-friendly button sizes
      const joinButton = page.locator('[data-testid="join-button"]');
      const buttonBox = await joinButton.boundingBox();
      expect(buttonBox?.height).toBeGreaterThanOrEqual(44); // iOS minimum touch target
      
      // Test mobile navigation
      await page.fill('[data-testid="session-id-input"]', 'test-session-123');
      await page.selectOption('[data-testid="target-language"]', 'es');
      
      // Verify inputs are accessible on mobile
      const sessionInput = page.locator('[data-testid="session-id-input"]');
      await expect(sessionInput).toBeVisible();
      await expect(sessionInput).toBeEnabled();
      
    } finally {
      await context.close();
    }
  });

  test('should handle orientation changes', async ({ browser }) => {
    const context = await browser.newContext({
      ...devices['iPhone 12'],
    });
    const page = await context.newPage();

    try {
      await page.goto('http://localhost:3001');
      
      // Portrait mode
      await page.setViewportSize({ width: 390, height: 844 });
      await expect(page.locator('[data-testid="session-joiner"]')).toBeVisible();
      
      // Landscape mode
      await page.setViewportSize({ width: 844, height: 390 });
      await expect(page.locator('[data-testid="session-joiner"]')).toBeVisible();
      
    } finally {
      await context.close();
    }
  });
});
