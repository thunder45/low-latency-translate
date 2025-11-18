# AWS Cognito OAuth2 Setup Guide

## Overview

This guide walks you through configuring AWS Cognito User Pool for OAuth2 authentication with the speaker app.

## Prerequisites

- AWS Console access
- User Pool ID: `us-east-1_WoaXmyQLQ`
- App Client ID: `38t8057tbi0o6873qt441kuo3n`
- Region: `us-east-1`

## Step 1: Create Cognito Domain

1. **Open AWS Console**
   - Navigate to: https://console.aws.amazon.com/cognito/
   - Select region: `us-east-1` (top right)

2. **Select Your User Pool**
   - Click on User Pool: `us-east-1_WoaXmyQLQ`

3. **Configure Domain**
   - In the left sidebar, click **App integration**
   - Scroll down to **Domain** section
   - Click **Actions** → **Create Cognito domain**

4. **Choose Domain Name**
   - Enter a domain prefix (must be unique across all AWS):
     - Suggested: `low-latency-translate-[your-initials]` (e.g., `low-latency-translate-jd`)
     - Or: `llt-speaker-[random-number]` (e.g., `llt-speaker-42`)
   - Click **Check availability** to verify it's available
   - Once available, click **Create Cognito domain**

5. **Note Your Domain**
   - Your full domain will be: `https://[your-prefix].auth.us-east-1.amazoncognito.com`
   - Example: `https://low-latency-translate-jd.auth.us-east-1.amazoncognito.com`
   - **Save this URL** - you'll need it for the .env file

## Step 2: Configure App Client for OAuth2

1. **Navigate to App Clients**
   - Still in your User Pool
   - Click **App integration** in left sidebar
   - Scroll to **App clients and analytics**
   - Click on your app client: `38t8057tbi0o6873qt441kuo3n`

2. **Edit Hosted UI Settings**
   - Click **Edit** in the **Hosted UI** section

3. **Configure Allowed Callback URLs**
   - Add these URLs (one per line):
     ```
     http://localhost:3000/callback
     http://localhost:5173/callback
     https://your-production-domain.com/callback
     ```
   - Note: Port 3000 is for production build, 5173 is for Vite dev server

4. **Configure Allowed Sign-out URLs**
   - Add these URLs (one per line):
     ```
     http://localhost:3000/
     http://localhost:5173/
     https://your-production-domain.com/
     ```

5. **Configure OAuth 2.0 Grant Types**
   - Ensure these are checked:
     - ✅ **Authorization code grant**
     - ✅ **Implicit grant** (optional, for testing)

6. **Configure OAuth Scopes**
   - Ensure these are checked:
     - ✅ **openid**
     - ✅ **email**
     - ✅ **profile**

7. **Advanced Settings (Optional)**
   - **Authentication flows**: Ensure these are enabled:
     - ✅ ALLOW_USER_PASSWORD_AUTH (for future direct auth if needed)
     - ✅ ALLOW_REFRESH_TOKEN_AUTH
     - ✅ ALLOW_USER_SRP_AUTH

8. **Save Changes**
   - Click **Save changes** at the bottom

## Step 3: Verify App Client Configuration

1. **Check App Client Settings**
   - In the app client details page, verify:
     - **Client ID**: `38t8057tbi0o6873qt441kuo3n`
     - **Client secret**: Should be "No secret" or blank (public client)
     - **Hosted UI**: Should show your callback URLs

2. **Test the Hosted UI (Optional)**
   - Copy this URL (replace `[YOUR-DOMAIN]` with your actual domain):
     ```
     https://[YOUR-DOMAIN].auth.us-east-1.amazoncognito.com/login?client_id=38t8057tbi0o6873qt441kuo3n&response_type=code&scope=openid+email+profile&redirect_uri=http://localhost:3000/callback
     ```
   - Open it in a browser
   - You should see the Cognito hosted login page
   - Don't log in yet - just verify the page loads

## Step 4: Create Test User (If Needed)

1. **Navigate to Users**
   - Click **Users** in left sidebar
   - Click **Create user**

2. **User Details**
   - **Username**: Choose a username (e.g., `testuser`)
   - **Email**: Enter a valid email address
   - **Temporary password**: Create a temporary password
   - **Mark email as verified**: ✅ Check this box
   - Click **Create user**

3. **Note Credentials**
   - Username: `[your-username]`
   - Temporary password: `[your-temp-password]`
   - You'll be prompted to change this on first login

## Step 5: Update Your .env File

Update `frontend-client-apps/speaker-app/.env`:

```env
# WebSocket API Endpoint (from staging deployment)
VITE_WEBSOCKET_URL=wss://vphqnkfxtf.execute-api.us-east-1.amazonaws.com/prod

# AWS Cognito Configuration
VITE_COGNITO_USER_POOL_ID=us-east-1_WoaXmyQLQ
VITE_COGNITO_CLIENT_ID=38t8057tbi0o6873qt441kuo3n
VITE_AWS_REGION=us-east-1

# OAuth Redirect URIs
VITE_COGNITO_REDIRECT_URI=http://localhost:3000/callback
VITE_COGNITO_LOGOUT_URI=http://localhost:3000/

# Cognito Domain (REPLACE WITH YOUR ACTUAL DOMAIN)
VITE_COGNITO_DOMAIN=https://[YOUR-DOMAIN-PREFIX].auth.us-east-1.amazoncognito.com

# Security
VITE_ENCRYPTION_KEY=dev-encryption-key-for-local-testing-only-32chars
```

**Important**: Replace `[YOUR-DOMAIN-PREFIX]` with the domain you created in Step 1.

## Step 6: Verify Configuration

Run this command to verify your configuration:

```bash
cd frontend-client-apps/speaker-app
npm run dev
```

Then:
1. Open http://localhost:5173 in your browser
2. Click "Create Session" or any action requiring auth
3. You should be redirected to the Cognito hosted UI
4. After login, you should be redirected back to your app

## Troubleshooting

### Issue: "Invalid redirect_uri"
- **Cause**: Callback URL not registered in Cognito
- **Fix**: Go back to Step 2 and add your callback URL

### Issue: Domain not available
- **Cause**: Domain prefix already taken
- **Fix**: Try a different prefix with your initials or random numbers

### Issue: "Client authentication failed"
- **Cause**: App client has a secret (should be public)
- **Fix**: Create a new app client without a secret

### Issue: Hosted UI shows error
- **Cause**: OAuth scopes or grant types not configured
- **Fix**: Go back to Step 2 and verify all settings

## Next Steps

Once you've completed this setup:
1. ✅ Verify the domain is created
2. ✅ Verify callback URLs are registered
3. ✅ Update your .env file with the domain
4. ✅ Test the login flow

Then let me know, and I'll update the code to fix the authentication issues!

## Quick Reference

**Your Configuration:**
- User Pool ID: `us-east-1_WoaXmyQLQ`
- App Client ID: `38t8057tbi0o6873qt441kuo3n`
- Region: `us-east-1`
- Domain: `https://[YOUR-PREFIX].auth.us-east-1.amazoncognito.com`
- Callback URL: `http://localhost:3000/callback`
- Scopes: `openid email profile`
