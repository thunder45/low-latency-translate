/**
 * Language Selector Service
 * 
 * Manages language switching for listeners via stream reconnection.
 * Coordinates with audio playback to ensure smooth transitions.
 */

import type { Language, SwitchContext } from '../types/controls';

/**
 * Language availability data
 */
const AVAILABLE_LANGUAGES: Language[] = [
  { code: 'en', name: 'English', isAvailable: true },
  { code: 'es', name: 'Spanish', isAvailable: true },
  { code: 'fr', name: 'French', isAvailable: true },
  { code: 'de', name: 'German', isAvailable: true },
  { code: 'it', name: 'Italian', isAvailable: true },
  { code: 'pt', name: 'Portuguese', isAvailable: true },
  { code: 'ja', name: 'Japanese', isAvailable: true },
  { code: 'ko', name: 'Korean', isAvailable: true },
  { code: 'zh', name: 'Chinese', isAvailable: true },
  { code: 'ar', name: 'Arabic', isAvailable: true },
  { code: 'hi', name: 'Hindi', isAvailable: true },
  { code: 'ru', name: 'Russian', isAvailable: true },
];

/**
 * Language change callback type
 */
type LanguageChangeCallback = (languageCode: string) => void;

/**
 * Language availability callback type
 */
type LanguageAvailabilityCallback = (languages: Language[]) => void;

/**
 * Language Selector for managing language switching
 */
export class LanguageSelector {
  private currentLanguage: string = 'en';
  private sessionId: string | null = null;
  private wsBaseUrl: string;
  private languageChangeCallbacks: LanguageChangeCallback[] = [];
  private availabilityCallbacks: LanguageAvailabilityCallback[] = [];
  
  constructor(wsBaseUrl: string) {
    this.wsBaseUrl = wsBaseUrl;
  }
  
  /**
   * Set current session
   * 
   * @param sessionId - Session identifier
   * @param initialLanguage - Initial language code
   */
  setSession(sessionId: string, initialLanguage: string = 'en'): void {
    this.sessionId = sessionId;
    this.currentLanguage = initialLanguage;
  }
  
  /**
   * Get available languages for a session
   * 
   * @param sessionId - Session identifier
   * @returns List of available languages
   */
  async getAvailableLanguages(sessionId: string): Promise<Language[]> {
    // In a real implementation, this would query the backend
    // For now, return the static list
    return Promise.resolve([...AVAILABLE_LANGUAGES]);
  }
  
  /**
   * Switch to a different language
   * 
   * This initiates a language switch by preparing the context
   * and coordinating with the audio playback system.
   * 
   * @param sessionId - Session identifier
   * @param languageCode - Target language code
   */
  async switchLanguage(sessionId: string, languageCode: string): Promise<void> {
    if (languageCode === this.currentLanguage) {
      return; // Already on this language
    }
    
    // Validate language is available
    const languages = await this.getAvailableLanguages(sessionId);
    const targetLanguage = languages.find(l => l.code === languageCode);
    
    if (!targetLanguage || !targetLanguage.isAvailable) {
      throw new Error(`Language ${languageCode} is not available`);
    }
    
    // Prepare switch context
    const context = await this.prepareLanguageSwitch(
      sessionId,
      this.currentLanguage,
      languageCode
    );
    
    // Update current language
    const previousLanguage = this.currentLanguage;
    this.currentLanguage = languageCode;
    
    try {
      // Complete the switch (this would coordinate with audio playback)
      await this.completeLanguageSwitch(sessionId, context);
      
      // Notify listeners of language change
      this.notifyLanguageChange(languageCode);
    } catch (error) {
      // Rollback on failure
      this.currentLanguage = previousLanguage;
      throw error;
    }
  }
  
  /**
   * Get current language
   * 
   * @param sessionId - Session identifier
   * @returns Current language code
   */
  async getCurrentLanguage(sessionId: string): Promise<string> {
    return Promise.resolve(this.currentLanguage);
  }
  
  /**
   * Get WebSocket URL for a specific language stream
   * 
   * @param sessionId - Session identifier
   * @param languageCode - Language code
   * @returns WebSocket URL for the language stream
   */
  async getLanguageStreamUrl(sessionId: string, languageCode: string): Promise<string> {
    // Construct WebSocket URL with language parameter
    const url = new URL(this.wsBaseUrl);
    url.searchParams.set('sessionId', sessionId);
    url.searchParams.set('language', languageCode);
    url.searchParams.set('role', 'listener');
    
    return url.toString();
  }
  
  /**
   * Prepare language switch context
   * 
   * @param sessionId - Session identifier
   * @param fromLanguage - Current language code
   * @param toLanguage - Target language code
   * @returns Switch context for coordination
   */
  async prepareLanguageSwitch(
    sessionId: string,
    fromLanguage: string,
    toLanguage: string
  ): Promise<SwitchContext> {
    const newStreamUrl = await this.getLanguageStreamUrl(sessionId, toLanguage);
    
    return {
      fromLanguage,
      toLanguage,
      newStreamUrl,
      syncTimestamp: Date.now(),
      estimatedLatency: 500 // Target: <500ms
    };
  }
  
  /**
   * Complete language switch
   * 
   * This would coordinate with the audio playback system to:
   * 1. Pause current stream
   * 2. Disconnect from current language stream
   * 3. Connect to new language stream
   * 4. Resume playback
   * 
   * @param sessionId - Session identifier
   * @param context - Switch context
   */
  async completeLanguageSwitch(sessionId: string, context: SwitchContext): Promise<void> {
    // In a real implementation, this would coordinate with AudioPlayback
    // For now, just simulate the switch delay
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Verify switch completed within target time
    const elapsed = Date.now() - context.syncTimestamp;
    if (elapsed > context.estimatedLatency) {
      console.warn(`Language switch took ${elapsed}ms, target was ${context.estimatedLatency}ms`);
    }
  }
  
  /**
   * Register callback for language changes
   * 
   * @param callback - Function to call when language changes
   */
  onLanguageChange(callback: LanguageChangeCallback): void {
    this.languageChangeCallbacks.push(callback);
  }
  
  /**
   * Register callback for language availability updates
   * 
   * @param callback - Function to call when availability changes
   */
  onLanguageAvailability(callback: LanguageAvailabilityCallback): void {
    this.availabilityCallbacks.push(callback);
  }
  
  /**
   * Notify all listeners of language change
   * 
   * @param languageCode - New language code
   */
  private notifyLanguageChange(languageCode: string): void {
    this.languageChangeCallbacks.forEach(callback => {
      try {
        callback(languageCode);
      } catch (error) {
        console.error('Error in language change callback:', error);
      }
    });
  }
  
  /**
   * Notify all listeners of availability changes
   * 
   * @param languages - Updated language list
   */
  private notifyAvailabilityChange(languages: Language[]): void {
    this.availabilityCallbacks.forEach(callback => {
      try {
        callback(languages);
      } catch (error) {
        console.error('Error in availability callback:', error);
      }
    });
  }
}
