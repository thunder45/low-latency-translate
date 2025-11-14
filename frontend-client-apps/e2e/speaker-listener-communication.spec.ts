import { test, expect } from '@playwright/test';

test.describe('Speaker-Listener Communication', () => {
  test('should allow speaker to create session and listener to join', async ({ browser }) => {
    // Create two contexts (speaker and listener)
    const speakerContext = await browser.newContext();
    const listenerContext = await browser.newContext();
    
    const speakerPage = await speakerContext.newPage();
    const listenerPage = await listenerContext.newPage();

    try {
      // Speaker: Navigate to speaker app
      await speakerPage.goto('http://localhost:3000');
      
      // Speaker: Login (mock or use test credentials)
      await speakerPage.fill('[data-testid="email-input"]', 'test@example.com');
      await speakerPage.fill('[data-testid="password-input"]', 'testpassword');
      await speakerPage.click('[data-testid="login-button"]');
      
      // Speaker: Wait for login success
      await speakerPage.waitForSelector('[data-testid="session-creator"]', { timeout: 5000 });
      
      // Speaker: Create session
      await speakerPage.selectOption('[data-testid="source-language"]', 'en');
      await speakerPage.click('[data-testid="create-session-button"]');
      
      // Speaker: Wait for session creation
      await speakerPage.waitForSelector('[data-testid="session-display"]', { timeout: 5000 });
      
      // Speaker: Get session ID
      const sessionId = await speakerPage.textContent('[data-testid="session-id"]');
      expect(sessionId).toBeTruthy();
      expect(sessionId).toMatch(/^[a-z]+-[a-z]+-\d{3}$/);
      
      // Listener: Navigate to listener app
      await listenerPage.goto('http://localhost:3001');
      
      // Listener: Join session
      await listenerPage.fill('[data-testid="session-id-input"]', sessionId!);
      await listenerPage.selectOption('[data-testid="target-language"]', 'es');
      await listenerPage.click('[data-testid="join-button"]');
      
      // Listener: Wait for join success
      await listenerPage.waitForSelector('[data-testid="playback-controls"]', { timeout: 5000 });
      
      // Verify listener joined
      const connectionStatus = await listenerPage.textContent('[data-testid="connection-status"]');
      expect(connectionStatus).toContain('Connected');
      
      // Speaker: Verify listener count updated
      await speakerPage.waitForTimeout(1000); // Wait for stats update
      const listenerCount = await speakerPage.textContent('[data-testid="listener-count"]');
      expect(listenerCount).toContain('1');
      
      // Speaker: Start broadcasting
      await speakerPage.click('[data-testid="start-broadcast-button"]');
      
      // Verify speaker is transmitting
      const transmittingStatus = await speakerPage.getAttribute(
        '[data-testid="broadcast-indicator"]',
        'data-transmitting'
      );
      expect(transmittingStatus).toBe('true');
      
      // Listener: Verify receiving audio (check buffer indicator)
      await listenerPage.waitForSelector('[data-testid="buffer-indicator"]', { timeout: 3000 });
      
      // Test playback controls
      await listenerPage.click('[data-testid="pause-button"]');
      const pausedState = await listenerPage.getAttribute(
        '[data-testid="pause-button"]',
        'aria-pressed'
      );
      expect(pausedState).toBe('true');
      
      // Test mute control
      await listenerPage.click('[data-testid="mute-button"]');
      const mutedState = await listenerPage.getAttribute(
        '[data-testid="mute-button"]',
        'aria-pressed'
      );
      expect(mutedState).toBe('true');
      
      // Speaker: End session
      await speakerPage.click('[data-testid="end-session-button"]');
      await speakerPage.click('[data-testid="confirm-end-button"]');
      
      // Listener: Verify session ended
      await listenerPage.waitForSelector('[data-testid="session-ended-message"]', { timeout: 3000 });
      const endedMessage = await listenerPage.textContent('[data-testid="session-ended-message"]');
      expect(endedMessage).toContain('ended');
      
    } finally {
      await speakerContext.close();
      await listenerContext.close();
    }
  });

  test('should handle language switching', async ({ browser }) => {
    const speakerContext = await browser.newContext();
    const listenerContext = await browser.newContext();
    
    const speakerPage = await speakerContext.newPage();
    const listenerPage = await listenerContext.newPage();

    try {
      // Setup: Create session and join
      await speakerPage.goto('http://localhost:3000');
      // ... (abbreviated setup steps)
      
      await listenerPage.goto('http://localhost:3001');
      // ... (abbreviated join steps)
      
      // Listener: Switch language
      await listenerPage.selectOption('[data-testid="language-selector"]', 'fr');
      
      // Verify switching indicator
      await listenerPage.waitForSelector('[data-testid="switching-indicator"]', { timeout: 2000 });
      
      // Verify language switched
      await listenerPage.waitForSelector('[data-testid="switching-indicator"]', { 
        state: 'hidden',
        timeout: 5000 
      });
      
      const currentLanguage = await listenerPage.inputValue('[data-testid="language-selector"]');
      expect(currentLanguage).toBe('fr');
      
    } finally {
      await speakerContext.close();
      await listenerContext.close();
    }
  });
});
