# Cognito OAuth2 Troubleshooting

## Error: "Login pages unavailable - Please contact an administrator"

This error occurs when the Hosted UI is not properly enabled for your app client.

### Solution: Enable Hosted UI

1. **Go to AWS Cognito Console**
   - Navigate to: https://console.aws.amazon.com/cognito/
   - Region: `us-east-1`
   - Select User Pool: `us-east-1_WoaXmyQLQ`

2. **Navigate to App Integration**
   - Click **App integration** in the left sidebar
   - Scroll to **App clients and analytics**
   - Click on your app client: `38t8057tbi0o6873qt441kuo3n`

3. **Check Hosted UI Configuration**
   - Look for the **Hosted UI** section
   - If it says "Not configured" or is empty, you need to enable it

4. **Edit Hosted UI Settings**
   - Click **Edit** button in the Hosted UI section
   - Configure the following:

### Required Settings:

**Allowed callback URLs** (add all of these):
```
http://localhost:3000/callback
```

**Allowed sign-out URLs** (add all of these):
```
http://localhost:3000/
```

**Identity providers**:
- ✅ Check **Cognito user pool**

**OAuth 2.0 grant types**:
- ✅ Check **Authorization code grant**
- ✅ Check **Implicit grant** (optional)

**OpenID Connect scopes**:
- ✅ Check **openid**
- ✅ Check **email**
- ✅ Check **profile**

5. **Save Changes**
   - Click **Save changes** at the bottom
   - Wait 30 seconds for changes to propagate

6. **Test Again**
   - Try the URL again: https://advm.auth.us-east-1.amazoncognito.com/login?client_id=38t8057tbi0o6873qt441kuo3n&response_type=code&scope=openid+email+profile&redirect_uri=http://localhost:3000/callback
   - You should now see the Cognito login page

## Alternative: Check if App Client Has Secret

If the above doesn't work, your app client might have a client secret (which shouldn't be used for web apps).

### Check for Client Secret:

1. In the app client details page, look for **Client secret**
2. If it shows a secret value (not "No secret"), you need to create a new app client

### Create New Public App Client:

1. **Go to App Integration**
   - Click **App integration** → **App clients and analytics**
   - Click **Create app client**

2. **Configure App Client**
   - **App type**: Public client
   - **App client name**: `speaker-app-public`
   - **Authentication flows**:
     - ✅ ALLOW_USER_SRP_AUTH
     - ✅ ALLOW_REFRESH_TOKEN_AUTH
   - Click **Create app client**

3. **Note the New Client ID**
   - Copy the new client ID
   - Update your `.env` file with the new client ID

4. **Configure Hosted UI for New Client**
   - Follow steps 1-6 above for the new app client

## Verification Checklist

After making changes, verify:

- [ ] Domain is created: `https://advm.auth.us-east-1.amazoncognito.com`
- [ ] App client type is **Public** (no client secret)
- [ ] Hosted UI section shows callback URLs
- [ ] OAuth grant types include "Authorization code grant"
- [ ] OpenID scopes include openid, email, profile
- [ ] Identity provider "Cognito user pool" is selected
- [ ] Test URL loads the login page (not error page)

## Still Not Working?

If you still see the error after following these steps:

1. **Wait 1-2 minutes** - Changes can take time to propagate
2. **Clear browser cache** - Old cached responses might cause issues
3. **Try incognito/private window** - Eliminates cache issues
4. **Check CloudWatch Logs** - Look for errors in Cognito logs

## Quick Test Command

Once configured, test with this curl command:

```bash
curl -I "https://advm.auth.us-east-1.amazoncognito.com/login?client_id=38t8057tbi0o6873qt441kuo3n&response_type=code&scope=openid+email+profile&redirect_uri=http://localhost:3000/callback"
```

You should see `HTTP/2 200` (not 400 or 500).
