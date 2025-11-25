/**
 * AWS Credentials Provider for KVS WebRTC
 * 
 * Exchanges Cognito JWT tokens for temporary AWS credentials
 * to access Kinesis Video Streams
 */
import { AWSCredentials } from './KVSWebRTCService';

/**
 * Configuration for credentials provider
 */
export interface CredentialsProviderConfig {
  region: string;
  identityPoolId: string;
  userPoolId: string;
}

/**
 * KVS Credentials Provider
 * 
 * Uses AWS Cognito Identity Pool to exchange JWT token
 * for temporary AWS credentials with KVS permissions
 */
export class KVSCredentialsProvider {
  private config: CredentialsProviderConfig;
  private cachedCredentials: AWSCredentials | null = null;
  private credentialsExpiration: number = 0;

  constructor(config: CredentialsProviderConfig) {
    this.config = config;
  }

  /**
   * Get AWS credentials for KVS access
   * Caches credentials and refreshes when expired
   * 
   * Supports both authenticated (with JWT) and unauthenticated access
   */
  async getCredentials(idToken: string): Promise<AWSCredentials> {
    // Check if cached credentials are still valid
    if (this.cachedCredentials && Date.now() < this.credentialsExpiration) {
      console.log('[KVS Credentials] Using cached credentials');
      return this.cachedCredentials;
    }

    const isAuthenticated = idToken && idToken.trim().length > 0;
    console.log(`[KVS Credentials] Fetching ${isAuthenticated ? 'authenticated' : 'unauthenticated'} credentials from Cognito Identity Pool...`);

    try {
      // Import AWS SDK for Cognito Identity
      const { CognitoIdentityClient, GetIdCommand, GetCredentialsForIdentityCommand } = 
        await import('@aws-sdk/client-cognito-identity');

      const cognitoIdentity = new CognitoIdentityClient({
        region: this.config.region,
      });

      // 1. Get Identity ID from Cognito Identity Pool
      const getIdParams: any = {
        IdentityPoolId: this.config.identityPoolId,
      };

      // Only add Logins if we have a valid JWT token (authenticated flow)
      if (isAuthenticated) {
        const providerName = `cognito-idp.${this.config.region}.amazonaws.com/${this.config.userPoolId}`;
        getIdParams.Logins = {
          [providerName]: idToken,
        };
      }

      const getIdResponse = await cognitoIdentity.send(new GetIdCommand(getIdParams));

      const identityId = getIdResponse.IdentityId;
      if (!identityId) {
        throw new Error('Failed to get Identity ID from Cognito');
      }

      console.log('[KVS Credentials] Got Identity ID:', identityId);

      // 2. Get temporary AWS credentials
      const getCredentialsParams: any = {
        IdentityId: identityId,
      };

      // Only add Logins if authenticated
      if (isAuthenticated) {
        const providerName = `cognito-idp.${this.config.region}.amazonaws.com/${this.config.userPoolId}`;
        getCredentialsParams.Logins = {
          [providerName]: idToken,
        };
      }

      const getCredentialsResponse = await cognitoIdentity.send(
        new GetCredentialsForIdentityCommand(getCredentialsParams)
      );

      const credentials = getCredentialsResponse.Credentials;
      if (!credentials || !credentials.AccessKeyId || !credentials.SecretKey) {
        throw new Error('Failed to get AWS credentials from Cognito');
      }

      // 3. Cache credentials
      this.cachedCredentials = {
        accessKeyId: credentials.AccessKeyId,
        secretAccessKey: credentials.SecretKey,
        sessionToken: credentials.SessionToken,
      };

      // Set expiration (credentials typically valid for 1 hour, refresh 5 min early)
      if (credentials.Expiration) {
        this.credentialsExpiration = credentials.Expiration.getTime() - 5 * 60 * 1000;
      } else {
        // Default: 55 minutes from now
        this.credentialsExpiration = Date.now() + 55 * 60 * 1000;
      }

      console.log('[KVS Credentials] Credentials obtained, valid until:', new Date(this.credentialsExpiration));

      return this.cachedCredentials;
    } catch (error) {
      console.error('[KVS Credentials] Failed to get credentials:', error);
      throw error;
    }
  }

  /**
   * Clear cached credentials (force refresh on next call)
   */
  clearCache(): void {
    this.cachedCredentials = null;
    this.credentialsExpiration = 0;
    console.log('[KVS Credentials] Cache cleared');
  }

  /**
   * Check if credentials are expired or about to expire
   */
  needsRefresh(): boolean {
    return Date.now() >= this.credentialsExpiration;
  }
}

/**
 * Singleton instance for convenience
 */
let providerInstance: KVSCredentialsProvider | null = null;

/**
 * Get or create singleton credentials provider
 */
export function getKVSCredentialsProvider(config: CredentialsProviderConfig): KVSCredentialsProvider {
  if (!providerInstance) {
    providerInstance = new KVSCredentialsProvider(config);
  }
  return providerInstance;
}

/**
 * Clear singleton instance (for testing or reconfiguration)
 */
export function clearKVSCredentialsProvider(): void {
  providerInstance?.clearCache();
  providerInstance = null;
}
