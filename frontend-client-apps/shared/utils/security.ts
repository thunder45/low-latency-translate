/**
 * Security utilities for Content Security Policy and input sanitization
 */

/**
 * Content Security Policy configuration
 */
export const CSP_CONFIG = {
  'default-src': ["'self'"],
  'script-src': ["'self'", "'unsafe-inline'"],  // unsafe-inline needed for React
  'style-src': ["'self'", "'unsafe-inline'"],   // unsafe-inline needed for styled components
  'img-src': ["'self'", 'data:', 'https:'],
  'font-src': ["'self'", 'data:'],
  'connect-src': [
    "'self'",
    'wss://*.execute-api.*.amazonaws.com',  // WebSocket API Gateway
    'https://*.execute-api.*.amazonaws.com', // REST API Gateway
    'https://cognito-idp.*.amazonaws.com',   // Cognito
    'https://*.amazoncognito.com'            // Cognito
  ],
  'media-src': ["'self'", 'blob:'],
  'object-src': ["'none'"],
  'base-uri': ["'self'"],
  'form-action': ["'self'"],
  'frame-ancestors': ["'none'"],
  'upgrade-insecure-requests': []
};

/**
 * Generate CSP meta tag content
 */
export function generateCSPContent(): string {
  return Object.entries(CSP_CONFIG)
    .map(([directive, sources]) => {
      if (sources.length === 0) {
        return directive;
      }
      return `${directive} ${sources.join(' ')}`;
    })
    .join('; ');
}

/**
 * Sanitize user input to prevent XSS attacks
 */
export function sanitizeInput(input: string): string {
  if (!input) return '';

  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .replace(/\//g, '&#x2F;');
}

/**
 * Sanitize HTML content
 */
export function sanitizeHTML(html: string): string {
  const div = document.createElement('div');
  div.textContent = html;
  return div.innerHTML;
}

/**
 * Validate and sanitize URL
 */
export function sanitizeURL(url: string): string {
  try {
    const parsed = new URL(url);
    
    // Only allow https and wss protocols
    if (!['https:', 'wss:'].includes(parsed.protocol)) {
      throw new Error('Invalid protocol');
    }
    
    return parsed.toString();
  } catch (error) {
    console.error('Invalid URL:', error);
    return '';
  }
}

/**
 * Validate session ID format
 */
export function isValidSessionId(sessionId: string): boolean {
  // Format: {adjective}-{noun}-{number}
  const pattern = /^[a-z]+-[a-z]+-\d{3}$/;
  return pattern.test(sessionId);
}

/**
 * Validate language code (ISO 639-1)
 */
export function isValidLanguageCode(code: string): boolean {
  // ISO 639-1 codes are 2 lowercase letters
  const pattern = /^[a-z]{2}$/;
  return pattern.test(code);
}

/**
 * Validate email format
 */
export function isValidEmail(email: string): boolean {
  const pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return pattern.test(email);
}

/**
 * Remove dangerous characters from input
 */
export function removeDangerousChars(input: string): string {
  // Remove control characters and other potentially dangerous characters
  return input.replace(/[\x00-\x1F\x7F-\x9F]/g, '');
}

/**
 * Validate and sanitize JSON input
 */
export function sanitizeJSON(input: string): any {
  try {
    const parsed = JSON.parse(input);
    
    // Recursively sanitize string values
    const sanitize = (obj: any): any => {
      if (typeof obj === 'string') {
        return sanitizeInput(obj);
      } else if (Array.isArray(obj)) {
        return obj.map(sanitize);
      } else if (typeof obj === 'object' && obj !== null) {
        const sanitized: any = {};
        for (const [key, value] of Object.entries(obj)) {
          sanitized[sanitizeInput(key)] = sanitize(value);
        }
        return sanitized;
      }
      return obj;
    };
    
    return sanitize(parsed);
  } catch (error) {
    console.error('Invalid JSON:', error);
    return null;
  }
}

/**
 * Generate secure random string
 */
export function generateSecureRandom(length: number = 32): string {
  const array = new Uint8Array(length);
  crypto.getRandomValues(array);
  return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
}

/**
 * Check if running in secure context (HTTPS)
 */
export function isSecureContext(): boolean {
  return window.isSecureContext;
}

/**
 * Validate WebSocket URL
 */
export function isValidWebSocketURL(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'wss:';
  } catch {
    return false;
  }
}
