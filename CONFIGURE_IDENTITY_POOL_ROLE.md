# Configure Identity Pool Role - AWS Console Method

**Identity Pool ID**: `us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4`  
**New Role ARN**: `arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN`

## Step-by-Step Instructions

### 1. Open AWS Console

Go to: https://console.aws.amazon.com/cognito/

### 2. Navigate to Identity Pools

1. Click on **"Identity Pools"** in the left sidebar (NOT User Pools)
2. Find and click on **"IdentityPool_LowLatencyTranslate"**
   - Identity Pool ID: `us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4`

### 3. Edit Identity Pool Settings

1. Click **"Edit identity pool"** button (top right)
2. Scroll down to **"Authentication providers"** section
3. You should see your Cognito User Pool already configured

### 4. Update Authenticated Role

1. Scroll to **"IAM role configuration"** section
2. Find **"Authenticated role"**
3. Click the dropdown or "Choose role from IAM" option
4. Search for and select: **`KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN`**
5. Click **"Save changes"**

### Alternative: Direct Role Assignment

If you can't find the role in the dropdown:

1. Copy the role ARN: `arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN`
2. In the Identity Pool settings, look for "Use default role" toggle
3. Toggle it OFF if needed
4. Paste the ARN directly into the authenticated role field
5. Save changes

## Verification

After saving, verify the configuration:

1. In the Identity Pool details page, check:
   - **Authenticated role** shows: `KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN`
2. Click on the role name to open it in IAM
3. Verify permissions include:
   - `kinesisvideo:GetSignalingChannelEndpoint`
   - `kinesisvideo:ConnectAsMaster`
   - `kinesisvideo:ConnectAsViewer`
   - `kinesisvideo:GetIceServerConfig`

## What This Does

When users authenticate via the User Pool and get AWS credentials:
- **Old behavior**: Got `ServiceTranslateStack-AuthenticatedRole` (no KVS permissions)
- **New behavior**: Get `KVSWebRTC-dev-KVSClientRole` (has KVS permissions)

This allows the frontend to:
- Connect to KVS signaling channels
- Get ICE server configuration
- Establish WebRTC connections
- Stream audio via WebRTC UDP

## Test After Configuration

### Clear Browser Cache

```bash
# Important: Clear browser cache/cookies to get new credentials
```

### Test Speaker App

```bash
cd frontend-client-apps/speaker-app
npm run dev
```

1. Login with your credentials
2. Create a new session
3. Grant microphone access
4. Check browser console for:
   - `[KVS] Connecting as Master (Speaker)...`
   - `[KVS] ICE servers obtained`
   - `[KVS] Connected as Master, ready for viewers`
   - `[KVS] ICE connection established successfully`

**Success**: No `AccessDeniedException` errors!

### Test Listener App

```bash
cd frontend-client-apps/listener-app
npm run dev
```

1. Enter the session code
2. Check browser console for:
   - `[KVS] Connecting as Viewer (Listener)...`
   - `[KVS] ICE servers obtained`
   - `[KVS] Connected as Viewer, waiting for media from Master`
   - `[KVS] Received media track from Master`

**Success**: Audio streaming from speaker to listener!

## Expected Console Logs

### Speaker (Success)

```
[KVS] Connecting as Master (Speaker)...
[KVS] ICE servers obtained: 2 servers
[KVS] Microphone access granted
[KVS] Added audio track to peer connection
[KVS] Opening signaling channel...
[KVS] Signaling channel opened as Master
[KVS] ICE connection state: connected
[KVS] Connected as Master, ready for viewers
```

### Listener (Success)

```
[KVS] Connecting as Viewer (Listener)...
[KVS] ICE servers obtained: 2 servers
[KVS] Opening signaling channel...
[KVS] Signaling channel opened as Viewer, creating offer...
[KVS] Created and set local SDP offer
[KVS] Sent SDP offer to Master
[KVS] Received SDP answer from: <master-id>
[KVS] ICE connection state: connected
[KVS] Received media track from Master
```

## Troubleshooting

### If Role Not Found in Dropdown

- Wait a few seconds - IAM can take time to propagate
- Refresh the page
- Try searching for "KVSWebRTC" in the role search
- Use the direct ARN entry method instead

### If Still Getting AccessDeniedException

1. Verify role was assigned correctly in Identity Pool settings
2. Clear ALL browser data (cache, cookies, local storage)
3. Close browser completely and reopen
4. Try in an incognito/private window
5. Check role trust policy includes your Identity Pool ID

### If WebRTC Connection Fails

1. Check browser console for specific errors
2. Verify Identity Pool ID in .env files matches: `us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4`
3. Check KVS channel was created in Lambda logs
4. Verify network allows UDP traffic (for WebRTC)

## Summary

**Current Status:**
- ✅ New Identity Pool created
- ✅ KVSWebRTC stack deployed
- ✅ KVSClientRole created with KVS permissions
- ⚠️ Need to link role to Identity Pool (AWS Console)
- ⏳ Ready to test after role assignment

**Next Action**: Assign role via AWS Console, then test!
