# Frontend Configuration Guide

This guide explains how to configure the frontend applications to connect to your deployed backend infrastructure.

## Quick Start

### 1. Environment Files

Both speaker and listener apps require `.env` files with configuration. Example files are provided:

```bash
# Copy example files to create your .env files
cp speaker-app/.env.example speaker-app/.env
cp listener-app/.env.example listener-app/.env
```

### 2. Required Configuration

Edit the `.env` files with your actual values:

**Speaker App** (`speaker-app/.env`):
```bash
# WebSocket API Endpoint - Get from your AWS deployment
VITE_WEBSOCKET_URL=wss://your-api-id.execute-api.region.amazonaws.com/stage

# AWS Cognito Configuration - Get from your Cognito User Pool
VITE_COGNITO_USER_POOL_ID=region_PoolId
VITE_COGNITO_CLIENT_ID=your-client-id
VITE_AWS_REGION=us-east-1

# Security - Generate a secure 32+ character key
VITE_ENCRYPTION_KEY=your-secure-32-character-key-here
```

**Listener App** (`listener-app/.env`):
```bash
# WebSocket API Endpoint - Same as speaker app
VITE_WEBSOCKET_URL=wss://your-api-id.execute-api.region.amazonaws.com/stage

# AWS Region
VITE_AWS_REGION=us-east-1

# Security - Same key as speaker app
VITE_ENCRYPTION_KEY=your-secure-32-character-key-here
```

### 3. Get Your Configuration Values

#### WebSocket URL

From your deployed infrastructure:

```bash
# Option 1: Check CloudFormation outputs
aws cloudformation describe-stacks \
  --stack-name SessionManagement-staging \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`WebSocketApiUrl`].OutputValue' \
  --output text

# Option 2: Check API Gateway
aws apigatewayv2 get-apis \
  --region us-east-1 \
  --query 'Items[?Name==`SessionManagementWebSocketApi`].ApiEndpoint' \
  --output text

# Option 3: Check STAGING_STATUS.md in project root
cat ../STAGING_STATUS.md | grep "Endpoint:"
```

**Current Staging URL**: `wss://vphqnkfxtf.execute-api.us-east-1.amazonaws.com/prod`

#### Cognito Configuration

From your staging configuration:

```bash
# Check staging config
cat ../session-management/infrastructure/config/staging.json
```

**Current Staging Values**:
- User Pool ID: `us-east-1_WoaXmyQLQ`
- Client ID: `38t8057tbi0o6873qt441kuo3n`
- Region: `us-east-1`

#### Encryption Key

Generate a secure encryption key:

```bash
# Generate a secure 32-character base64 key
openssl rand -base64 32

# Or use a UUID-based key
uuidgen | tr -d '-'
```

**⚠️ IMPORTANT**: 
- Never commit your encryption key to git
- Use different keys for dev/staging/production
- Store production keys in a secure secrets manager

## Configuration Validation

The apps include built-in configuration validation. If configuration is missing or invalid, you'll see helpful error messages.

### Test Configuration

```bash
# Build the apps to test configuration
npm run build:all

# Or run in development mode
npm run dev:speaker  # Terminal 1
npm run dev:listener # Terminal 2
```

### Configuration Errors

Common errors and solutions:

**"VITE_WEBSOCKET_URL is required"**
- Solution: Add `VITE_WEBSOCKET_URL` to your `.env` file

**"WebSocket URL must use ws:// or wss:// protocol"**
- Solution: Ensure URL starts with `wss://` (secure) or `ws://` (local dev)

**"Encryption key must be at least 32 characters long"**
- Solution: Generate a longer key using `openssl rand -base64 32`

**"Please generate a secure encryption key"**
- Solution: Replace the example key with a real one

## Environment-Specific Configuration

### Development

For local development, you can use the staging infrastructure:

```bash
# speaker-app/.env.development
VITE_WEBSOCKET_URL=wss://vphqnkfxtf.execute-api.us-east-1.amazonaws.com/prod
VITE_COGNITO_USER_POOL_ID=us-east-1_WoaXmyQLQ
VITE_COGNITO_CLIENT_ID=38t8057tbi0o6873qt441kuo3n
VITE_AWS_REGION=us-east-1
VITE_ENCRYPTION_KEY=dev-key-for-local-testing-only-32chars
```

### Staging

```bash
# speaker-app/.env.staging
VITE_WEBSOCKET_URL=wss://staging-api-id.execute-api.us-east-1.amazonaws.com/staging
VITE_COGNITO_USER_POOL_ID=us-east-1_StagingPoolId
VITE_COGNITO_CLIENT_ID=staging-client-id
VITE_AWS_REGION=us-east-1
VITE_ENCRYPTION_KEY=<secure-staging-key>
```

### Production

```bash
# speaker-app/.env.production
VITE_WEBSOCKET_URL=wss://prod-api-id.execute-api.us-east-1.amazonaws.com/prod
VITE_COGNITO_USER_POOL_ID=us-east-1_ProdPoolId
VITE_COGNITO_CLIENT_ID=prod-client-id
VITE_AWS_REGION=us-east-1
VITE_ENCRYPTION_KEY=<secure-production-key>
```

## Optional Configuration

### AWS CloudWatch RUM (Real User Monitoring)

To enable frontend monitoring:

1. Create a CloudWatch RUM app monitor in AWS Console
2. Get the configuration values
3. Add to your `.env` file:

```bash
VITE_RUM_GUEST_ROLE_ARN=arn:aws:iam::account:role/RUM-Monitor-role
VITE_RUM_IDENTITY_POOL_ID=region:pool-id
VITE_RUM_ENDPOINT=https://dataplane.rum.region.amazonaws.com
```

## Configuration in Code

### Using Configuration

The apps use a centralized configuration utility:

```typescript
import { getConfig } from '@/shared/utils/config';

// Get validated configuration
const config = getConfig();

// Access values
const wsUrl = config.websocketUrl;
const region = config.awsRegion;
const cognito = config.cognito; // Optional, may be undefined
```

### Configuration Validation

```typescript
import { isConfigValid } from '@/shared/utils/config';

// Check if config is valid
const { valid, errors } = isConfigValid();

if (!valid) {
  console.error('Configuration errors:', errors);
}
```

### Development Fallback

For local development only:

```typescript
import { getConfigWithFallback } from '@/shared/utils/config';

// Gets config with development fallbacks if validation fails
const config = getConfigWithFallback();
```

**⚠️ WARNING**: Never use `getConfigWithFallback()` in production builds!

## Build-Time vs Runtime Configuration

### Vite Environment Variables

Vite embeds environment variables at **build time**:

- Variables are replaced during the build process
- Different builds needed for different environments
- Variables are visible in the client-side bundle

### Security Considerations

**Safe to include**:
- ✅ API endpoints (WebSocket URLs)
- ✅ AWS region
- ✅ Cognito User Pool ID
- ✅ Cognito Client ID (public client)

**Never include**:
- ❌ AWS access keys
- ❌ AWS secret keys
- ❌ Private API keys
- ❌ Database credentials

**Encryption key**: Used for client-side token storage. Should be unique per environment but can be in the bundle.

## Troubleshooting

### Configuration Not Loading

**Problem**: Environment variables are undefined

**Solutions**:
1. Ensure `.env` file exists in the app directory
2. Restart the dev server after changing `.env`
3. Check variable names start with `VITE_`
4. Verify no syntax errors in `.env` file

### WebSocket Connection Fails

**Problem**: Can't connect to WebSocket API

**Solutions**:
1. Verify WebSocket URL is correct
2. Check API Gateway is deployed and active
3. Ensure URL uses `wss://` protocol
4. Test connection with `wscat`:
   ```bash
   npm install -g wscat
   wscat -c wss://your-api-url
   ```

### Cognito Authentication Fails

**Problem**: Speaker can't authenticate

**Solutions**:
1. Verify Cognito User Pool ID is correct
2. Check Cognito Client ID matches
3. Ensure user exists in the pool
4. Verify JWT token is valid

### Build Fails with Config Errors

**Problem**: Build fails due to missing configuration

**Solutions**:
1. Create `.env` file from `.env.example`
2. Fill in all required values
3. Run `npm run build:all` to test

## Configuration Checklist

Before deploying:

- [ ] `.env` files created for both apps
- [ ] WebSocket URL configured correctly
- [ ] Cognito credentials configured (speaker app)
- [ ] Encryption key generated (32+ characters)
- [ ] Encryption key is unique per environment
- [ ] `.env` files are in `.gitignore`
- [ ] Configuration validated with `npm run build:all`
- [ ] WebSocket connection tested
- [ ] Authentication tested (speaker app)

## Next Steps

After configuration:

1. **Test locally**: `npm run dev:speaker` and `npm run dev:listener`
2. **Build for production**: `npm run build:all`
3. **Deploy**: Upload `dist/` directories to your hosting service
4. **Monitor**: Check CloudWatch RUM if enabled

## Support

For configuration issues:

1. Check this guide
2. Review `.env.example` files
3. Check `STAGING_STATUS.md` for current infrastructure
4. Review CloudWatch logs for backend errors
5. Check browser console for frontend errors

## Security Best Practices

1. **Never commit `.env` files** - They're in `.gitignore` for a reason
2. **Use different keys per environment** - Dev, staging, and production should have unique encryption keys
3. **Rotate keys regularly** - Change encryption keys periodically
4. **Use HTTPS/WSS only** - Never use unencrypted connections in production
5. **Monitor access** - Use CloudWatch RUM to track usage
6. **Limit CORS** - Configure API Gateway CORS to allow only your domains

## Additional Resources

- [Vite Environment Variables](https://vitejs.dev/guide/env-and-mode.html)
- [AWS Cognito Documentation](https://docs.aws.amazon.com/cognito/)
- [WebSocket API Documentation](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-websocket-api.html)
- [CloudWatch RUM](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-RUM.html)
