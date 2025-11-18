/**
 * Authentication constants
 */
export const AUTH_CONSTANTS = {
  /** Time before expiry when tokens should be refreshed (5 minutes) */
  TOKEN_REFRESH_THRESHOLD_MS: 5 * 60 * 1000,
  
  /** Connection timeout for WebSocket (5 seconds) */
  CONNECTION_TIMEOUT_MS: 5000,
  
  /** Maximum number of authentication retry attempts */
  MAX_AUTH_RETRY_ATTEMPTS: 1,
  
  /** Minimum encryption key length (256-bit = 32 bytes) */
  ENCRYPTION_KEY_MIN_LENGTH: 32,
  
  /** PBKDF2 iterations for key derivation */
  PBKDF2_ITERATIONS: 100000,
  
  /** Encryption initialization vector length */
  ENCRYPTION_IV_LENGTH: 12,
  
  /** Application salt for PBKDF2 (can be public) */
  APPLICATION_SALT: 'low-latency-translate-v1',
} as const;

/**
 * WebSocket close codes
 * @see https://developer.mozilla.org/en-US/docs/Web/API/CloseEvent/code
 */
export enum WebSocketCloseCode {
  /** Normal closure; the connection successfully completed */
  NORMAL_CLOSURE = 1000,
  
  /** Abnormal closure; connection dropped without close frame */
  ABNORMAL_CLOSURE = 1006,
  
  /** Policy violation; used for authentication failures */
  POLICY_VIOLATION = 1008,
  
  /** Internal server error */
  SERVER_ERROR = 1011,
}

/**
 * Required environment variables (for documentation)
 */
export const REQUIRED_ENV_VARS = {
  BACKEND: ['USER_POOL_ID', 'CLIENT_ID', 'REGION'],
  FRONTEND: ['VITE_COGNITO_USER_POOL_ID', 'VITE_COGNITO_CLIENT_ID', 'VITE_AWS_REGION', 'VITE_ENCRYPTION_KEY'],
} as const;
