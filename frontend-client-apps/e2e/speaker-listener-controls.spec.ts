/**
 * End-to-end tests for speaker-listener controls
 * 
 * Tests complete user flows for speaker and listener control operations
 */

import { test, expect } from '@playwright/test';

test.describe('Speaker Controls E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to speaker app
    await page.goto('/speaker');
    
    // Wait for app to load
    await page.waitForLoadState('networkidle');
  });

  test('complete speaker session flow with controls', async ({ page }) => {
    // Login (if required)
    // await page.fill('[data-testid="username"]', 'test-speaker');
    // await page.fill('[data-testid="password"]', 'test-password');
    // await page.click('[data-testid="login-button"]');
    
    // Create session
    await page.click('[data-testid="create-session"]');
    await page.waitForSelector('[data-testid="session-id"]');
    
    // Verify session created
    const sessionId = await page.textContent('[data-testid="session-id"]');
    expect(sessionId).toBeTruthy();
    
    // Start broadcast
    await page.click('[data-testid="start-broadcast"]');
    await page.waitForSelector('[data-testid="broadcasting-indicator"]');
    
    // Pause broadcast
    await page.click('[data-testid="pause-button"]');
    await expect(page.locator('[data-testid="pause-button"]')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('[data-testid="status-badge-paused"]')).toBeVisible();
    
    // Resume broadcast
    await page.click('[data-testid="pause-button"]');
    await expect(page.locator('[data-testid="pause-button"]')).toHaveAttribute('aria-pressed', 'false');
    await expect(page.locator('[data-testid="status-badge-paused"]')).not.toBeVisible();
    
    // Mute microphone
    await page.click('[data-testid="mute-button"]');
    await expect(page.locator('[data-testid="mute-button"]')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('[data-testid="status-badge-muted"]')).toBeVisible();
    
    // Unmute microphone
    await page.click('[data-testid="mute-button"]');
    await expect(page.locator('[data-testid="mute-button"]')).toHaveAttribute('aria-pressed', 'false');
    await expect(page.locator('[data-testid="status-badge-muted"]')).not.toBeVisible();
  });

  test('volume control adjusts correctly', async ({ page }) => {
    // Create and start session
    await page.click('[data-testid="create-session"]');
    await page.click('[data-testid="start-broadcast"]');
    
    // Adjust volume to 50%
    await page.locator('[data-testid="volume-slider"]').fill('50');
    
    // Verify volume display updates
    await expect(page.locator('[data-testid="volume-display"]')).toHaveText('50%');
    
    // Adjust volume to 100%
    await page.locator('[data-testid="volume-slider"]').fill('100');
    await expect(page.locator('[data-testid="volume-display"]')).toHaveText('100%');
    
    // Adjust volume to 0%
    await page.locator('[data-testid="volume-slider"]').fill('0');
    await expect(page.locator('[data-testid="volume-display"]')).toHaveText('0%');
  });

  test('keyboard shortcuts work correctly', async ({ page }) => {
    // Create and start session
    await page.click('[data-testid="create-session"]');
    await page.click('[data-testid="start-broadcast"]');
    
    // Press Ctrl+M to mute
    await page.keyboard.press('Control+KeyM');
    await expect(page.locator('[data-testid="mute-button"]')).toHaveAttribute('aria-pressed', 'true');
    
    // Press Ctrl+M again to unmute
    await page.keyboard.press('Control+KeyM');
    await expect(page.locator('[data-testid="mute-button"]')).toHaveAttribute('aria-pressed', 'false');
    
    // Press Ctrl+P to pause
    await page.keyboard.press('Control+KeyP');
    await expect(page.locator('[data-testid="pause-button"]')).toHaveAttribute('aria-pressed', 'true');
    
    // Press Ctrl+P again to resume
    await page.keyboard.press('Control+KeyP');
    await expect(page.locator('[data-testid="pause-button"]')).toHaveAttribute('aria-pressed', 'false');
  });

  test('listener count updates in real-time', async ({ page }) => {
    // Create and start session
    await page.click('[data-testid="create-session"]');
    await page.click('[data-testid="start-broadcast"]');
    
    // Initial listener count should be 0
    await expect(page.locator('[data-testid="listener-count"]')).toContainText('0');
    
    // Note: In a real test, you would simulate listeners joining
    // For now, we just verify the element exists and displays correctly
  });
});

test.describe('Listener Controls E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to listener app
    await page.goto('/listener');
    
    // Wait for app to load
    await page.waitForLoadState('networkidle');
  });

  test('complete listener session flow with controls', async ({ page }) => {
    // Join session
    await page.fill('[data-testid="session-id-input"]', 'test-session-123');
    await page.selectOption('[data-testid="language-select"]', 'en');
    await page.click('[data-testid="join-button"]');
    
    // Wait for connection
    await page.waitForSelector('[data-testid="connected-indicator"]');
    
    // Pause playback
    await page.click('[data-testid="pause-button"]');
    await expect(page.locator('[data-testid="pause-button"]')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('[data-testid="buffer-status"]')).toBeVisible();
    
    // Resume playback
    await page.click('[data-testid="pause-button"]');
    await expect(page.locator('[data-testid="pause-button"]')).toHaveAttribute('aria-pressed', 'false');
    await expect(page.locator('[data-testid="buffer-status"]')).not.toBeVisible();
    
    // Mute audio
    await page.click('[data-testid="mute-button"]');
    await expect(page.locator('[data-testid="mute-button"]')).toHaveAttribute('aria-pressed', 'true');
    
    // Unmute audio
    await page.click('[data-testid="mute-button"]');
    await expect(page.locator('[data-testid="mute-button"]')).toHaveAttribute('aria-pressed', 'false');
  });

  test('language switching works correctly', async ({ page }) => {
    // Join session
    await page.fill('[data-testid="session-id-input"]', 'test-session-123');
    await page.selectOption('[data-testid="language-select"]', 'en');
    await page.click('[data-testid="join-button"]');
    
    // Wait for connection
    await page.waitForSelector('[data-testid="connected-indicator"]');
    
    // Switch to Spanish
    await page.selectOption('[data-testid="language-select"]', 'es');
    
    // Verify language changed
    await expect(page.locator('[data-testid="language-select"]')).toHaveValue('es');
    
    // Verify reconnection indicator (language switch requires reconnection)
    // await expect(page.locator('[data-testid="reconnecting-indicator"]')).toBeVisible();
    // await expect(page.locator('[data-testid="reconnecting-indicator"]')).not.toBeVisible({ timeout: 1000 });
  });

  test('volume control works correctly', async ({ page }) => {
    // Join session
    await page.fill('[data-testid="session-id-input"]', 'test-session-123');
    await page.click('[data-testid="join-button"]');
    
    // Adjust volume
    await page.locator('[data-testid="volume-slider"]').fill('75');
    await expect(page.locator('[data-testid="volume-display"]')).toHaveText('75%');
  });

  test('speaker status displays correctly', async ({ page }) => {
    // Join session
    await page.fill('[data-testid="session-id-input"]', 'test-session-123');
    await page.click('[data-testid="join-button"]');
    
    // Wait for connection
    await page.waitForSelector('[data-testid="connected-indicator"]');
    
    // Verify speaker status element exists
    await expect(page.locator('[data-testid="speaker-status"]')).toBeVisible();
    
    // Note: In a real test, you would verify speaker pause/mute states
    // are reflected in the listener UI
  });

  test('buffer status shows during pause', async ({ page }) => {
    // Join session
    await page.fill('[data-testid="session-id-input"]', 'test-session-123');
    await page.click('[data-testid="join-button"]');
    
    // Pause playback
    await page.click('[data-testid="pause-button"]');
    
    // Verify buffer status is visible
    await expect(page.locator('[data-testid="buffer-status"]')).toBeVisible();
    
    // Verify buffer duration is displayed
    await expect(page.locator('[data-testid="buffer-duration"]')).toBeVisible();
  });
});

test.describe('Preference Persistence E2E', () => {
  test('volume preference persists across sessions', async ({ page }) => {
    // Speaker: Set volume and create session
    await page.goto('/speaker');
    await page.click('[data-testid="create-session"]');
    await page.locator('[data-testid="volume-slider"]').fill('85');
    
    // Reload page
    await page.reload();
    
    // Verify volume is restored
    await expect(page.locator('[data-testid="volume-slider"]')).toHaveValue('85');
  });

  test('language preference persists for listener', async ({ page }) => {
    // Listener: Join session with Spanish
    await page.goto('/listener');
    await page.fill('[data-testid="session-id-input"]', 'test-session-123');
    await page.selectOption('[data-testid="language-select"]', 'es');
    await page.click('[data-testid="join-button"]');
    
    // Reload page
    await page.reload();
    
    // Verify language is restored
    await expect(page.locator('[data-testid="language-select"]')).toHaveValue('es');
  });
});
