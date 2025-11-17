import { describe, it, expect } from 'vitest';
import { Validator } from '../Validator';

describe('Validator', () => {
  describe('isValidSessionId', () => {
    it('should validate correct session ID format', () => {
      expect(Validator.isValidSessionId('golden-eagle-427')).toBe(true);
      expect(Validator.isValidSessionId('faithful-shepherd-001')).toBe(true);
      expect(Validator.isValidSessionId('blessed-temple-999')).toBe(true);
    });

    it('should reject invalid session ID formats', () => {
      expect(Validator.isValidSessionId('invalid')).toBe(false);
      expect(Validator.isValidSessionId('golden-eagle')).toBe(false);
      expect(Validator.isValidSessionId('golden-eagle-')).toBe(false);
      expect(Validator.isValidSessionId('Golden-Eagle-427')).toBe(false);
      expect(Validator.isValidSessionId('golden_eagle_427')).toBe(false);
      expect(Validator.isValidSessionId('')).toBe(false);
    });

    it('should reject session IDs with invalid number format', () => {
      expect(Validator.isValidSessionId('golden-eagle-1')).toBe(false);
      expect(Validator.isValidSessionId('golden-eagle-12')).toBe(false);
      expect(Validator.isValidSessionId('golden-eagle-1234')).toBe(false);
    });
  });

  describe('isValidLanguageCode', () => {
    it('should validate correct ISO 639-1 language codes', () => {
      expect(Validator.isValidLanguageCode('en')).toBe(true);
      expect(Validator.isValidLanguageCode('es')).toBe(true);
      expect(Validator.isValidLanguageCode('fr')).toBe(true);
      expect(Validator.isValidLanguageCode('de')).toBe(true);
      expect(Validator.isValidLanguageCode('zh')).toBe(true);
    });

    it('should reject invalid language codes', () => {
      expect(Validator.isValidLanguageCode('eng')).toBe(false);
      expect(Validator.isValidLanguageCode('e')).toBe(false);
      expect(Validator.isValidLanguageCode('EN')).toBe(false);
      expect(Validator.isValidLanguageCode('123')).toBe(false);
      expect(Validator.isValidLanguageCode('')).toBe(false);
    });
  });

  describe('isValidEmail', () => {
    it('should validate correct email formats', () => {
      expect(Validator.isValidEmail('user@example.com')).toBe(true);
      expect(Validator.isValidEmail('test.user@example.co.uk')).toBe(true);
      expect(Validator.isValidEmail('user+tag@example.com')).toBe(true);
    });

    it('should reject invalid email formats', () => {
      expect(Validator.isValidEmail('invalid')).toBe(false);
      expect(Validator.isValidEmail('user@')).toBe(false);
      expect(Validator.isValidEmail('@example.com')).toBe(false);
      expect(Validator.isValidEmail('user@example')).toBe(false);
      expect(Validator.isValidEmail('')).toBe(false);
    });
  });

  describe('sanitizeInput', () => {
    it('should remove dangerous characters', () => {
      expect(Validator.sanitizeInput('Hello<script>alert("xss")</script>'))
        .toBe('Hello alert("xss") ');
      expect(Validator.sanitizeInput('Test & <b>bold</b>'))
        .toBe('Test    bold ');
    });

    it('should preserve safe characters', () => {
      expect(Validator.sanitizeInput('Hello World 123')).toBe('Hello World 123');
      expect(Validator.sanitizeInput('user@example.com')).toBe('user@example.com');
    });

    it('should handle empty strings', () => {
      expect(Validator.sanitizeInput('')).toBe('');
    });
  });
});
