/**
 * ISO 639-1 language codes supported by the platform
 * This is a subset of all ISO 639-1 codes, limited to languages
 * supported by both AWS Translate and AWS Polly
 */
const SUPPORTED_LANGUAGE_CODES = new Set([
  'ar', 'zh', 'cs', 'da', 'nl', 'en', 'fi', 'fr', 'de', 'el',
  'he', 'hi', 'id', 'it', 'ja', 'ko', 'ms', 'no', 'pl', 'pt',
  'ro', 'ru', 'es', 'sv', 'th', 'tr', 'uk', 'vi',
  // Add more as needed based on AWS service intersection
]);

/**
 * Validation utility class for input validation
 */
export class Validator {
  /**
   * Validate session ID format
   * Format: {adjective}-{noun}-{number} (e.g., "golden-eagle-427")
   * @param sessionId - Session ID to validate
   * @returns True if valid format
   */
  static isValidSessionId(sessionId: string): boolean {
    if (!sessionId || typeof sessionId !== 'string') {
      return false;
    }

    // Pattern: lowercase letters, hyphens, and 3-digit number at end
    const pattern = /^[a-z]+-[a-z]+-\d{3}$/;
    return pattern.test(sessionId);
  }

  /**
   * Validate language code (ISO 639-1)
   * @param languageCode - Language code to validate
   * @returns True if valid and supported
   */
  static isValidLanguageCode(languageCode: string): boolean {
    if (!languageCode || typeof languageCode !== 'string') {
      return false;
    }

    // Check if it's a 2-letter code and in our supported set
    return languageCode.length === 2 && SUPPORTED_LANGUAGE_CODES.has(languageCode.toLowerCase());
  }

  /**
   * Validate email format
   * @param email - Email address to validate
   * @returns True if valid format
   */
  static isValidEmail(email: string): boolean {
    if (!email || typeof email !== 'string') {
      return false;
    }

    // Basic email validation pattern
    const pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return pattern.test(email);
  }

  /**
   * Sanitize input by removing potentially dangerous characters
   * Removes: <, >, &, ", ', /, \, script tags
   * @param input - Input string to sanitize
   * @returns Sanitized string
   */
  static sanitizeInput(input: string): string {
    if (!input || typeof input !== 'string') {
      return '';
    }

    return input
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#x27;')
      .replace(/\//g, '&#x2F;')
      .replace(/\\/g, '&#x5C;')
      // Remove any script tags
      .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
  }

  /**
   * Validate volume level (0-100)
   * @param volume - Volume level to validate
   * @returns True if valid range
   */
  static isValidVolume(volume: number): boolean {
    return typeof volume === 'number' && volume >= 0 && volume <= 100 && !isNaN(volume);
  }

  /**
   * Validate quality tier
   * @param tier - Quality tier to validate
   * @returns True if valid tier
   */
  static isValidQualityTier(tier: string): boolean {
    return tier === 'standard' || tier === 'premium';
  }

  /**
   * Get list of supported language codes
   * @returns Array of supported language codes
   */
  static getSupportedLanguages(): string[] {
    return Array.from(SUPPORTED_LANGUAGE_CODES).sort();
  }

  /**
   * Validate JWT token format (basic check)
   * @param token - JWT token to validate
   * @returns True if valid format (3 parts separated by dots)
   */
  static isValidJWT(token: string): boolean {
    if (!token || typeof token !== 'string') {
      return false;
    }

    const parts = token.split('.');
    return parts.length === 3 && parts.every(part => part.length > 0);
  }
}
