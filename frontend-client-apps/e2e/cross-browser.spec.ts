import { test, expect } from '@playwright/test';

test.describe('Cross-Browser Compatibility', () => {
  test('should work in all browsers', async ({ page, browserName }) => {
    // Navigate to speaker app
    await page.goto('http://localhost:3000');
    
    // Verify page loads
    await expect(page).toHaveTitle(/Speaker/i);
    
    // Check for required features
    const hasWebSocket = await page.evaluate(() => 'WebSocket' in window);
    const hasAudioContext = await page.evaluate(() => 'AudioContext' in window || 'webkitAudioContext' in window);
    const hasMediaDevices = await page.evaluate(() => 'mediaDevices' in navigator);
    const hasLocalStorage = await page.evaluate(() => {
      try {
        localStorage.setItem('test', 'test');
        localStorage.removeItem('test');
        return true;
      } catch {
        return false;
      }
    });
    
    // Verify all required features are supported
    expect(hasWebSocket).toBe(true);
    expect(hasAudioContext).toBe(true);
    expect(hasMediaDevices).toBe(true);
    expect(hasLocalStorage).toBe(true);
    
    // Log browser info
    console.log(`Browser: ${browserName}`);
    console.log(`WebSocket: ${hasWebSocket}`);
    console.log(`AudioContext: ${hasAudioContext}`);
    console.log(`MediaDevices: ${hasMediaDevices}`);
    console.log(`LocalStorage: ${hasLocalStorage}`);
  });

  test('should render UI correctly', async ({ page }) => {
    await page.goto('http://localhost:3000');
    
    // Check for key UI elements
    await expect(page.locator('[data-testid="login-form"]')).toBeVisible();
    await expect(page.locator('[data-testid="email-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="password-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="login-button"]')).toBeVisible();
    
    // Verify accessibility
    const emailInput = page.locator('[data-testid="email-input"]');
    await expect(emailInput).toHaveAttribute('aria-label');
    
    const loginButton = page.locator('[data-testid="login-button"]');
    await expect(loginButton).toHaveAttribute('aria-label');
  });
});
