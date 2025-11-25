# Listener Permissions Still Failing - Troubleshooting

## Current Status

✅ **Cognito Identity Pool configured correctly:**
```json
{
  "authenticated": "arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN",
  "unauthenticated": "arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt"
}
```

✅ **Guest Role has correct permissions:**
```json
{
  "Action": [
    "kinesisvideo:ConnectAsViewer",
    "kinesisvideo:DescribeSignalingChannel",
    "kinesisvideo:GetIceServerConfig",
    "kinesisvideo:GetSignalingChannelEndpoint"
  ],
  "Resource": "arn:aws:kinesisvideo:us-east-1:193020606184:channel/session-*/*"
}
```

❌ **But listener still gets AccessDeniedException**

## Root Cause: Browser Credential Caching

The browser cached Cognito Identity credentials **before** the role had permissions. These cached credentials are still being used even though the role now has the correct permissions.

## Solution: Clear Browser Credentials Cache

### Method 1: Hard Refresh (Try This First)

1. **Close the listener app tab completely**
2. **Open browser DevTools Console** (F12)
3. **Run these commands to clear cached credentials:**
```javascript
// Clear localStorage
localStorage.clear();

// Clear sessionStorage  
sessionStorage.clear();

// Clear IndexedDB (where AWS SDK caches credentials)
indexedDB.databases().then(dbs => {
  dbs.forEach(db => indexedDB.deleteDatabase(db.name));
});
```
4. **Close DevTools**
5. **Hard refresh:** Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
6. **Try joining session again**

### Method 2: Incognito/Private Window

1. **Open new Incognito/Private window** (Cmd+Shift+N)
2. **Navigate to:** http://localhost:5174
3. **Join session** - fresh credentials will be fetched

### Method 3: Wait for Credential Expiration

AWS Cognito credentials expire after 1 hour. If nothing else works:
- Wait 1 hour
- The browser will automatically fetch new credentials with proper permissions

### Method 4: Clear Browser Data (Nuclear Option)

1. **Chrome/Edge:** Settings → Privacy → Clear browsing data
2. **Select:** Cookies and site data, Cached images and files
3. **Time range:** Last hour
4. **Clear data**
5. **Restart browser**

## Verify It's Working

After clearing cache, you should see in browser console:

```
✅ [KVS Credentials] Credentials obtained, valid until: ...
✅ [KVS] Connecting as Viewer (Listener)...
✅ [KVS] Getting ICE servers...
✅ [KVS] Connected as Viewer
```

**Not:**
```
❌ Failed to get ICE servers: AccessDeniedException
```

## If Still Failing After Cache Clear

### Check 1: Verify IAM Policy Propagation (Can Take 5 Minutes)

```bash
# Wait 5 minutes after deployment, then check
aws iam get-role-policy \
  --role-name KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt \
  --policy-name KVSGuestRoleDefaultPolicyE9CC46BC
```

### Check 2: Test Credentials Manually

```bash
# Get identity and credentials as if you're the browser
IDENTITY_ID=$(aws cognito-identity get-id \
  --identity-pool-id us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4 \
  --query 'IdentityId' \
  --output text)

echo "Identity ID: $IDENTITY_ID"

# Get credentials
aws cognito-identity get-credentials-for-identity \
  --identity-id "$IDENTITY_ID"

# Test if credentials can call KVS
# Note: You'll need to export the credentials from above and test
```

### Check 3: Verify Session Exists

The logs also show `SESSION_NOT_FOUND` error. Make sure:
1. **Speaker app created the session** (check speaker console)
2. **Session ID matches exactly** (copy from speaker, paste in listener)
3. **Session is still active** (not expired or ended)

## Quick Test Script

```javascript
// Run this in browser console on listener app
(async () => {
  console.log('Testing credential refresh...');
  
  // Clear all storage
  localStorage.clear();
  sessionStorage.clear();
  
  // Clear IndexedDB
  const dbs = await indexedDB.databases();
  for (const db of dbs) {
    console.log('Deleting database:', db.name);
    indexedDB.deleteDatabase(db.name);
  }
  
  console.log('✅ Cache cleared. Reload page now (Cmd+Shift+R)');
})();
```

## Timeline

| Time | Action | Status |
|------|--------|--------|
| T+0 | CDK deploys guest role | ✅ Role created |
| T+30s | Cognito pool configured | ✅ Pool updated |
| T+30s | Browser fetches credentials | ❌ Role not ready yet |
| T+5min | IAM policy propagated | ✅ Permissions active |
| T+5min | Browser still has old credentials | ❌ Cached! |
| T+5min+ | Clear cache & refresh | ✅ New credentials work |

## Expected Behavior After Fix

1. **Browser fetches new identity** from Cognito Identity Pool
2. **New identity assumes** KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt
3. **Role has permissions** for GetSignalingChannelEndpoint
4. **Connection succeeds** ✅

## Summary

**The infrastructure is correct.** The issue is browser credential caching.

**Quick fix:**
1. Open browser DevTools console (F12)
2. Run: `localStorage.clear(); sessionStorage.clear();`
3. Hard refresh: Cmd+Shift+R
4. Try joining session again

If this doesn't work, use Incognito mode for guaranteed fresh credentials.
