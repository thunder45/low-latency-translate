# Design Document

## Overview

This design addresses the frontend build failures, configuration issues, and WebSocket message format mismatches that prevent the frontend applications from working with the deployed staging backend. The solution involves fixing TypeScript syntax errors, creating proper environment configuration, correcting WebSocket message types, and updating documentation to reflect the actual state of the system.

## Architecture

### Current State

```
frontend-client-apps/
├── shared/                          # ❌ Has TypeScript syntax errors
│   ├── components/
│   │   ├── ListenerControls.tsx    # ❌ Syntax error: }));
│   │   └── SpeakerControls.tsx     # ❌ Syntax error: }));
│   └── package.json                # ✅ Dependencies defined correctly
├── speaker-app/                     # ⚠️ Missing .env.example
│   └── src/
│       └── services/
│           └── SpeakerService.ts   # ❌ Wrong message type: 'audio_quality_warning'
├── listener-app/                    # ⚠️ Missing .env.example
│   └── src/
│       └── services/
│           └── ListenerService.ts  # ❌ Wrong action: 'switchLanguage'
│                                   # ❌ Wrong message types: 'speakerPaused', etc.
└── README.md                        # ⚠️ Inaccurate documentation
```

### Target State

```
frontend-client-apps/
├── shared/
│   ├── components/
│   │   ├── ListenerControls.tsx    # ✅ Fixed syntax
│   │   └── SpeakerControls.tsx     # ✅ Fixed syntax
│   └── package.json
├── speaker-app/
│   ├── .env.example                # ✅ New file with staging values
│   └── src/
│       └── services/
│           └── SpeakerService.ts   # ✅ Fixed: 'audioQualityWarning'
├── listener-app/
│   ├── .env.example                # ✅ New file with staging values
│   └── src/
│       └── services/
│           └── ListenerService.ts  # ✅ Fixed: 'changeLanguage'
│                                   # ✅ Fixed: 'broadcastPaused', etc.
└── README.md                        # ✅ Accurate documentation
```

## Components and Interfaces

### 1. TypeScript Syntax Fixes

#### Problem Analysis

Both `ListenerControls.tsx` and `SpeakerControls.tsx` use incorrect closing syntax for `React.memo()`:

```typescript
// CURRENT (WRONG) - Line 246 in ListenerControls.tsx, Line 222 in SpeakerControls.tsx
export const Component = React.memo(({
  // props
}) => {
  return <div>...</div>;
}));  // ❌ THREE closing parentheses
```

The TypeScript compiler expects:
- One `)` to close the arrow function
- One `)` to close the `React.memo()` call
- One `;` to end the statement

But the code has an extra `)` which causes: `error TS1005: ',' expected`

#### Solution

```typescript
// FIXED
export const Component = React.memo(({
  // props
}) => {
  return <div>...</div>;
});  // ✅ TWO closing parentheses + semicolon
```

**Files to modify:**
- `frontend-client-apps/shared/components/ListenerControls.tsx` (line 246)
- `frontend-client-apps/shared/components/SpeakerControls.tsx` (line 222)

**Change:** Replace `}));` with `});`

### 2. WebSocket Message Type Corrections

#### Problem Analysis

The frontend uses inconsistent message type naming that doesn't match the backend API:

| Frontend (WRONG) | Backend (CORRECT) | Location |
|------------------|-------------------|----------|
| `switchLanguage` | `changeLanguage` | ListenerService.ts:234 |
| `audio_quality_warning` | `audioQualityWarning` | SpeakerService.ts:115 |
| `speakerPaused` | `broadcastPaused` | ListenerService.ts:195 |
| `speakerResumed` | `broadcastResumed` | ListenerService.ts:200 |
| `speakerMuted` | `broadcastMuted` | ListenerService.ts:205 |
| `speakerUnmuted` | `broadcastUnmuted` | ListenerService.ts:210 |

#### Solution: Message Type Mapping

**Backend API Contract (from session-management CDK stack):**

```python
# WebSocket Routes
routes = {
    '$connect': connection_handler,
    '$disconnect': disconnect_handler,
    'heartbeat': heartbeat_handler,
    'refreshConnection': refresh_handler,
    'changeLanguage': change_language_handler,  # ✅ Correct action name
    'getStatus': status_handler,
}

# Message Types Sent by Backend
message_types = {
    'audioQualityWarning',    # ✅ camelCase
    'broadcastPaused',        # ✅ camelCase
    'broadcastResumed',       # ✅ camelCase
    'broadcastMuted',         # ✅ camelCase
    'broadcastUnmuted',       # ✅ camelCase
    'sessionEnded',           # ✅ camelCase
    'translatedAudio',        # ✅ camelCase
}
```

**Frontend Changes Required:**

1. **ListenerService.ts - Language Switch Action**
```typescript
// BEFORE (line 234)
this.wsClient.send({
  action: 'switchLanguage',  // ❌ WRONG
  targetLanguage: newLanguage,
});

// AFTER
this.wsClient.send({
  action: 'changeLanguage',  // ✅ CORRECT
  targetLanguage: newLanguage,
});
```

2. **SpeakerService.ts - Audio Quality Warning Handler**
```typescript
// BEFORE (line 115)
this.wsClient.on('audio_quality_warning', (message: any) => {  // ❌ WRONG

// AFTER
this.wsClient.on('audioQualityWarning', (message: any) => {  // ✅ CORRECT
```

3. **ListenerService.ts - Speaker State Handlers**
```typescript
// BEFORE (lines 195-215)
this.wsClient.on('speakerPaused', () => {     // ❌ WRONG
this.wsClient.on('speakerResumed', () => {    // ❌ WRONG
this.wsClient.on('speakerMuted', () => {      // ❌ WRONG
this.wsClient.on('speakerUnmuted', () => {    // ❌ WRONG

// AFTER
this.wsClient.on('broadcastPaused', () => {     // ✅ CORRECT
this.wsClient.on('broadcastResumed', () => {    // ✅ CORRECT
this.wsClient.on('broadcastMuted', () => {      // ✅ CORRECT
this.wsClient.on('broadcastUnmuted', () => {    // ✅ CORRECT
```

### 3. Environment Configuration Files

#### Design: .env.example Files

Create two `.env.example` files with actual staging values from `session-management/infrastructure/config/staging.json`:

**speaker-app/.env.example:**
```bash
# WebSocket API Endpoint
VITE_WEBSOCKET_URL=wss://vphqnkfxtf.execute-api.us-east-1.amazonaws.com/prod

# AWS Cognito Configuration
VITE_COGNITO_USER_POOL_ID=us-east-1_WoaXmyQLQ
VITE_COGNITO_CLIENT_ID=38t8057tbi0o6873qt441kuo3n
VITE_AWS_REGION=us-east-1

# Security (generate your own encryption key)
VITE_ENCRYPTION_KEY=your-32-character-encryption-key-here

# AWS CloudWatch RUM (Real User Monitoring) - Optional
# VITE_RUM_GUEST_ROLE_ARN=arn:aws:iam::193020606184:role/RUM-Monitor-us-east-1-193020606184-xxxx-Unauth
# VITE_RUM_IDENTITY_POOL_ID=us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# VITE_RUM_ENDPOINT=https://dataplane.rum.us-east-1.amazonaws.com
```

**listener-app/.env.example:**
```bash
# WebSocket API Endpoint
VITE_WEBSOCKET_URL=wss://vphqnkfxtf.execute-api.us-east-1.amazonaws.com/prod

# AWS Region
VITE_AWS_REGION=us-east-1

# Security (generate your own encryption key)
VITE_ENCRYPTION_KEY=your-32-character-encryption-key-here

# AWS CloudWatch RUM (Real User Monitoring) - Optional
# VITE_RUM_GUEST_ROLE_ARN=arn:aws:iam::193020606184:role/RUM-Monitor-us-east-1-193020606184-xxxx-Unauth
# VITE_RUM_IDENTITY_POOL_ID=us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# VITE_RUM_ENDPOINT=https://dataplane.rum.us-east-1.amazonaws.com
```

**Usage Instructions:**
```bash
# Copy example to actual .env file
cp speaker-app/.env.example speaker-app/.env
cp listener-app/.env.example listener-app/.env

# Edit .env files to customize if needed
```

### 4. Documentation Updates

#### README.md Improvements

**Add to "Getting Started" section:**

```markdown
### Prerequisites

- Node.js 18+ and npm 9+
- Modern browser (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)

### Installation

**IMPORTANT: You must install dependencies before building or running the applications.**

```bash
# Install all dependencies (root + all workspaces)
npm run install:all

# Or install individually
npm install                      # Root dependencies
npm install --workspace=shared   # Shared library
npm install --workspace=speaker-app
npm install --workspace=listener-app
```

### Configuration

Before running the applications, you need to configure environment variables:

1. **Copy the example environment files:**
   ```bash
   cp speaker-app/.env.example speaker-app/.env
   cp listener-app/.env.example listener-app/.env
   ```

2. **Review the .env files** - The example files contain staging environment values. For production, update the WebSocket URL and Cognito credentials.

3. **Generate an encryption key** (optional but recommended):
   ```bash
   # Generate a random 32-character key
   openssl rand -base64 32
   ```
   Replace `VITE_ENCRYPTION_KEY` in both .env files with the generated key.
```

**Add "Troubleshooting" section:**

```markdown
## Troubleshooting

### Build Fails with "tsc: command not found"

**Problem:** TypeScript compiler is not installed.

**Solution:** Run `npm run install:all` to install all dependencies.

### Build Fails with TypeScript Errors

**Problem:** There may be syntax errors in the code.

**Solution:** 
1. Check the error message for the file and line number
2. Ensure you're using the latest code from the repository
3. Try cleaning and rebuilding:
   ```bash
   rm -rf node_modules shared/node_modules speaker-app/node_modules listener-app/node_modules
   npm run install:all
   npm run build:all
   ```

### WebSocket Connection Fails

**Problem:** Frontend cannot connect to the backend.

**Solution:**
1. Verify the WebSocket URL in your .env file matches the deployed API Gateway endpoint
2. Check that the backend is deployed and healthy (see STAGING_STATUS.md)
3. Verify Cognito credentials are correct (speaker-app only)
4. Check browser console for detailed error messages

### "Module not found" Errors

**Problem:** Dependencies are not installed or workspace links are broken.

**Solution:**
```bash
npm run install:all
```

### Development Server Won't Start

**Problem:** Port may be in use or dependencies missing.

**Solution:**
1. Check if another process is using the port:
   ```bash
   lsof -i :3000  # For speaker-app
   lsof -i :3001  # For listener-app
   ```
2. Kill the process or use a different port
3. Ensure dependencies are installed: `npm run install:all`
```

## Data Models

### Environment Variables Schema

```typescript
// speaker-app environment variables
interface SpeakerAppEnv {
  VITE_WEBSOCKET_URL: string;           // Required: WebSocket API endpoint
  VITE_COGNITO_USER_POOL_ID: string;    // Required: Cognito User Pool ID
  VITE_COGNITO_CLIENT_ID: string;       // Required: Cognito Client ID
  VITE_AWS_REGION: string;              // Required: AWS region
  VITE_ENCRYPTION_KEY?: string;         // Optional: Token encryption key
  VITE_RUM_GUEST_ROLE_ARN?: string;     // Optional: CloudWatch RUM role
  VITE_RUM_IDENTITY_POOL_ID?: string;   // Optional: Cognito Identity Pool
  VITE_RUM_ENDPOINT?: string;           // Optional: RUM endpoint
}

// listener-app environment variables
interface ListenerAppEnv {
  VITE_WEBSOCKET_URL: string;           // Required: WebSocket API endpoint
  VITE_AWS_REGION: string;              // Required: AWS region
  VITE_ENCRYPTION_KEY?: string;         // Optional: Token encryption key
  VITE_RUM_GUEST_ROLE_ARN?: string;     // Optional: CloudWatch RUM role
  VITE_RUM_IDENTITY_POOL_ID?: string;   // Optional: Cognito Identity Pool
  VITE_RUM_ENDPOINT?: string;           // Optional: RUM endpoint
}
```

### WebSocket Message Types

```typescript
// Actions sent FROM frontend TO backend
type ClientActions = 
  | 'heartbeat'
  | 'refreshConnection'
  | 'changeLanguage'      // ✅ CORRECT (not 'switchLanguage')
  | 'getStatus';

// Message types sent FROM backend TO frontend
type ServerMessageTypes =
  | 'audioQualityWarning'   // ✅ CORRECT (not 'audio_quality_warning')
  | 'broadcastPaused'       // ✅ CORRECT (not 'speakerPaused')
  | 'broadcastResumed'      // ✅ CORRECT (not 'speakerResumed')
  | 'broadcastMuted'        // ✅ CORRECT (not 'speakerMuted')
  | 'broadcastUnmuted'      // ✅ CORRECT (not 'speakerUnmuted')
  | 'sessionEnded'
  | 'translatedAudio'
  | 'error';
```

## Error Handling

### Build-Time Errors

1. **TypeScript Compilation Errors**
   - **Detection:** `tsc` command fails with error code
   - **Handling:** Display clear error message with file and line number
   - **Recovery:** Fix syntax errors and rebuild

2. **Missing Dependencies**
   - **Detection:** `tsc: command not found` or similar
   - **Handling:** Display error message instructing to run `npm run install:all`
   - **Recovery:** Install dependencies and retry

3. **Workspace Link Errors**
   - **Detection:** "Cannot find module '@frontend/shared'"
   - **Handling:** Display error message about workspace configuration
   - **Recovery:** Run `npm run install:all` to rebuild workspace links

### Runtime Errors

1. **Missing Environment Variables**
   - **Detection:** `import.meta.env.VITE_WEBSOCKET_URL` is undefined
   - **Handling:** Display error message in UI listing missing variables
   - **Recovery:** Create .env file with required variables

2. **WebSocket Connection Failures**
   - **Detection:** WebSocket connection rejected or times out
   - **Handling:** Display user-friendly error message with troubleshooting steps
   - **Recovery:** Verify backend is running, check credentials, retry connection

3. **Message Type Mismatches**
   - **Detection:** Backend sends message type that frontend doesn't handle
   - **Handling:** Log warning to console, ignore unknown message types
   - **Recovery:** Update frontend to handle new message types

## Testing Strategy

### Build Verification

```bash
# Test 1: Clean build from scratch
rm -rf node_modules */node_modules */*/node_modules
npm run install:all
npm run build:all

# Expected: All builds succeed with exit code 0

# Test 2: Verify output files exist
ls -la shared/dist/
ls -la speaker-app/dist/
ls -la listener-app/dist/

# Expected: dist/ directories contain compiled JavaScript files
```

### Syntax Fix Verification

```bash
# Test 3: Verify TypeScript compilation succeeds
cd shared
npm run build

# Expected: No TypeScript errors, dist/ directory created

# Test 4: Check specific files were fixed
grep -n "}));" components/ListenerControls.tsx
grep -n "}));" components/SpeakerControls.tsx

# Expected: No matches (syntax fixed)
```

### WebSocket Message Type Verification

```bash
# Test 5: Verify correct action names in listener service
grep -n "switchLanguage" listener-app/src/services/ListenerService.ts

# Expected: No matches (changed to 'changeLanguage')

# Test 6: Verify correct message types in speaker service
grep -n "audio_quality_warning" speaker-app/src/services/SpeakerService.ts

# Expected: No matches (changed to 'audioQualityWarning')

# Test 7: Verify correct broadcast message types
grep -n "speakerPaused\|speakerResumed\|speakerMuted\|speakerUnmuted" listener-app/src/services/ListenerService.ts

# Expected: No matches (changed to 'broadcast*' variants)
```

### Environment Configuration Verification

```bash
# Test 8: Verify .env.example files exist
ls -la speaker-app/.env.example
ls -la listener-app/.env.example

# Expected: Both files exist

# Test 9: Verify .env.example contains staging values
grep "wss://vphqnkfxtf" speaker-app/.env.example
grep "us-east-1_WoaXmyQLQ" speaker-app/.env.example

# Expected: Staging values present
```

### Development Server Verification

```bash
# Test 10: Start speaker app in development mode
npm run dev:speaker &
sleep 5
curl -I http://localhost:3000

# Expected: HTTP 200 OK

# Test 11: Start listener app in development mode
npm run dev:listener &
sleep 5
curl -I http://localhost:3001

# Expected: HTTP 200 OK
```

### Integration Testing

```bash
# Test 12: Manual WebSocket connection test
# 1. Start speaker-app: npm run dev:speaker
# 2. Open browser to http://localhost:3000
# 3. Open browser console
# 4. Verify WebSocket connection established
# 5. Check for any console errors

# Expected: 
# - WebSocket connection successful
# - No console errors
# - UI loads correctly
```

## Implementation Notes

### Order of Operations

1. **Fix TypeScript syntax errors first** - This unblocks the build process
2. **Fix WebSocket message types** - This ensures frontend/backend compatibility
3. **Create .env.example files** - This enables developers to configure the apps
4. **Update README documentation** - This guides developers through the process
5. **Verify build and development workflow** - This confirms everything works

### Files to Modify

1. `frontend-client-apps/shared/components/ListenerControls.tsx` (line 246)
2. `frontend-client-apps/shared/components/SpeakerControls.tsx` (line 222)
3. `frontend-client-apps/listener-app/src/services/ListenerService.ts` (lines 195-215, 234)
4. `frontend-client-apps/speaker-app/src/services/SpeakerService.ts` (line 115)
5. `frontend-client-apps/speaker-app/.env.example` (new file)
6. `frontend-client-apps/listener-app/.env.example` (new file)
7. `frontend-client-apps/README.md` (multiple sections)

### Validation Checklist

- [ ] TypeScript compilation succeeds with zero errors
- [ ] All three workspaces build successfully
- [ ] .env.example files contain correct staging values
- [ ] WebSocket message types match backend API
- [ ] README accurately describes setup process
- [ ] Development servers start without errors
- [ ] Manual testing confirms WebSocket connectivity

## Design Decisions

### Decision 1: Fix Syntax vs Refactor Components

**Options:**
- A) Minimal fix: Just remove extra parenthesis
- B) Refactor: Rewrite components without React.memo()

**Choice:** Option A (Minimal fix)

**Rationale:** 
- React.memo() is appropriate for these components (they receive props that change frequently)
- Minimal change reduces risk of introducing new bugs
- Syntax fix is straightforward and well-understood

### Decision 2: Environment File Strategy

**Options:**
- A) Single .env.example at root with all variables
- B) Separate .env.example per app
- C) No .env.example, document in README only

**Choice:** Option B (Separate files per app)

**Rationale:**
- Each app has different required variables
- Easier for developers to copy and customize
- Follows standard practice for monorepo projects
- Reduces confusion about which variables apply to which app

### Decision 3: WebSocket Message Type Naming

**Options:**
- A) Change backend to match frontend (snake_case)
- B) Change frontend to match backend (camelCase)
- C) Add translation layer to convert between formats

**Choice:** Option B (Change frontend to match backend)

**Rationale:**
- Backend is already deployed to staging
- camelCase is JavaScript/TypeScript convention
- Frontend changes are easier than backend changes
- No translation layer needed (simpler architecture)

### Decision 4: Documentation Approach

**Options:**
- A) Minimal updates to fix inaccuracies
- B) Comprehensive rewrite of README
- C) Create separate troubleshooting guide

**Choice:** Option A + partial C (Fix inaccuracies + add troubleshooting section)

**Rationale:**
- README structure is good, just needs accuracy fixes
- Troubleshooting section addresses common issues
- Keeps documentation maintainable
- Provides immediate value to developers
