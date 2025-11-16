/**
 * Application configuration utility
 * Validates and provides type-safe access to environment variables
 */

export interface AppConfig {
  websocketUrl: string;
  awsRegion: string;
  encryptionKey: string;
  cognito?: {
    userPoolId: string;
    clientId: string;
  };
  rum?: {
    guestRoleArn: string;
    identityPoolId: string;
    endpoint: string;
  };
}

/**
 * Validate required environment variables
 */
function validateConfig(): void {
  const errors: string[] = [];

  if (!import.meta.env.VITE_WEBSOCKET_URL) {
    errors.push('VITE_WEBSOCKET_URL is required');
  }

  if (!import.meta.env.VITE_AWS_REGION) {
    errors.push('VITE_AWS_REGION is required');
  }

  if (!import.meta.env.VITE_ENCRYPTION_KEY) {
    errors.push('VITE_ENCRYPTION_KEY is required');
  }

  if (errors.length > 0) {
    throw new Error(
      `Configuration validation failed:\n${errors.join('\n')}\n\n` +
      'Please ensure all required environment variables are set in your .env file.\n' +
      'See .env.example for reference.'
    );
  }
}

/**
 * Validate WebSocket URL format
 */
function validateWebSocketUrl(url: string): void {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'wss:' && parsed.protocol !== 'ws:') {
      throw new Error('WebSocket URL must use ws:// or wss:// protocol');
    }
  } catch (error) {
    throw new Error(`Invalid WebSocket URL: ${url}`);
  }
}

/**
 * Validate encryption key format
 */
function validateEncryptionKey(key: string): void {
  if (key.length < 32) {
    throw new Error('Encryption key must be at least 32 characters long');
  }
  if (key === 'your-32-character-encryption-key-here') {
    throw new Error(
      'Please generate a secure encryption key. Do not use the example value.'
    );
  }
}

/**
 * Get application configuration
 * Validates all required environment variables and returns typed config
 */
export function getConfig(): AppConfig {
  // Validate required variables exist
  validateConfig();

  const websocketUrl = import.meta.env.VITE_WEBSOCKET_URL;
  const encryptionKey = import.meta.env.VITE_ENCRYPTION_KEY;

  // Validate formats
  validateWebSocketUrl(websocketUrl);
  validateEncryptionKey(encryptionKey);

  const config: AppConfig = {
    websocketUrl,
    awsRegion: import.meta.env.VITE_AWS_REGION,
    encryptionKey,
  };

  // Optional Cognito config (required for speaker app)
  if (import.meta.env.VITE_COGNITO_USER_POOL_ID && import.meta.env.VITE_COGNITO_CLIENT_ID) {
    config.cognito = {
      userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID,
      clientId: import.meta.env.VITE_COGNITO_CLIENT_ID,
    };
  }

  // Optional RUM config
  if (
    import.meta.env.VITE_RUM_GUEST_ROLE_ARN &&
    import.meta.env.VITE_RUM_IDENTITY_POOL_ID &&
    import.meta.env.VITE_RUM_ENDPOINT
  ) {
    config.rum = {
      guestRoleArn: import.meta.env.VITE_RUM_GUEST_ROLE_ARN,
      identityPoolId: import.meta.env.VITE_RUM_IDENTITY_POOL_ID,
      endpoint: import.meta.env.VITE_RUM_ENDPOINT,
    };
  }

  return config;
}

/**
 * Check if configuration is valid without throwing
 * Useful for displaying helpful error messages in UI
 */
export function isConfigValid(): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  try {
    validateConfig();
    validateWebSocketUrl(import.meta.env.VITE_WEBSOCKET_URL);
    validateEncryptionKey(import.meta.env.VITE_ENCRYPTION_KEY);
    return { valid: true, errors: [] };
  } catch (error) {
    if (error instanceof Error) {
      errors.push(error.message);
    }
    return { valid: false, errors };
  }
}

/**
 * Get configuration with fallback for development
 * Only use this for local development/testing
 */
export function getConfigWithFallback(): AppConfig {
  try {
    return getConfig();
  } catch (error) {
    console.warn('Configuration validation failed, using development fallbacks:', error);
    return {
      websocketUrl: 'wss://vphqnkfxtf.execute-api.us-east-1.amazonaws.com/prod',
      awsRegion: 'us-east-1',
      encryptionKey: 'dev-encryption-key-32-chars-min',
      cognito: {
        userPoolId: 'us-east-1_WoaXmyQLQ',
        clientId: '38t8057tbi0o6873qt441kuo3n',
      },
    };
  }
}
