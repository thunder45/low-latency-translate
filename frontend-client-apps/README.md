# Frontend Client Applications

This directory contains the frontend applications for the Real-Time Emotion-Aware Speech Translation Platform.

## Structure

```
frontend-client-apps/
├── shared/              # Shared library for common code
│   ├── websocket/      # WebSocket client implementation
│   ├── audio/          # Audio capture and playback services
│   ├── components/     # Reusable UI components
│   ├── utils/          # Utility functions
│   └── hooks/          # Custom React hooks
├── speaker-app/        # Speaker application (authenticated users)
│   └── src/
│       ├── components/ # Speaker-specific components
│       ├── services/   # Speaker services
│       ├── store/      # Zustand state management
│       └── hooks/      # Speaker-specific hooks
└── listener-app/       # Listener application (anonymous users)
    └── src/
        ├── components/ # Listener-specific components
        ├── services/   # Listener services
        ├── store/      # Zustand state management
        └── hooks/      # Listener-specific hooks
```

## Technology Stack

- **Framework**: React 18+ with TypeScript
- **Build Tool**: Vite
- **State Management**: Zustand
- **WebSocket**: Native WebSocket API
- **Audio**: Web Audio API
- **Authentication**: AWS Cognito (speaker-app only)
- **Testing**: Jest, React Testing Library, Playwright

## Getting Started

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

### Development

```bash
# Run speaker app in development mode
npm run dev:speaker

# Run listener app in development mode
npm run dev:listener
```

The speaker app will be available at http://localhost:3000  
The listener app will be available at http://localhost:3001

### Building

```bash
# Build all applications
npm run build:all

# Or build individually
npm run build:shared
npm run build:speaker
npm run build:listener
```

### Testing

```bash
# Run all tests
npm test

# Run tests for specific workspace
npm test --workspace=speaker-app
npm test --workspace=listener-app
```

### Linting and Formatting

```bash
# Lint all code
npm run lint

# Format all code
npm run format
```

## Environment Variables

### Speaker App

Create a `.env` file in `speaker-app/`:

```
VITE_WEBSOCKET_URL=wss://your-api-gateway-url
VITE_COGNITO_USER_POOL_ID=your-user-pool-id
VITE_COGNITO_CLIENT_ID=your-client-id
VITE_AWS_REGION=us-east-1
VITE_ENCRYPTION_KEY=your-encryption-key
VITE_RUM_GUEST_ROLE_ARN=your-rum-role-arn
VITE_RUM_IDENTITY_POOL_ID=your-identity-pool-id
VITE_RUM_ENDPOINT=your-rum-endpoint
```

### Listener App

Create a `.env` file in `listener-app/`:

```
VITE_WEBSOCKET_URL=wss://your-api-gateway-url
VITE_AWS_REGION=us-east-1
VITE_ENCRYPTION_KEY=your-encryption-key
VITE_RUM_GUEST_ROLE_ARN=your-rum-role-arn
VITE_RUM_IDENTITY_POOL_ID=your-identity-pool-id
VITE_RUM_ENDPOINT=your-rum-endpoint
```

## Deployment

### Build for Production

```bash
npm run build:all
```

### Deploy to AWS S3 + CloudFront

```bash
# Deploy speaker app
./deploy.sh speaker prod

# Deploy listener app
./deploy.sh listener prod
```

## Architecture

### Speaker Application

The speaker application allows authenticated users to:
- Create broadcast sessions with human-readable session IDs
- Capture and transmit audio from their microphone
- Monitor audio quality in real-time
- View active listeners and language distribution
- Control broadcast (pause, mute, volume)
- End sessions cleanly

### Listener Application

The listener application allows anonymous users to:
- Join sessions using session ID
- Receive translated audio in their preferred language
- Control playback (pause, mute, volume)
- Switch target language during session
- View speaker state (paused, muted)

### Shared Library

The shared library provides:
- WebSocket client with automatic reconnection
- Audio capture and playback services
- Common UI components
- Utility functions (validation, storage, error handling)
- Custom React hooks

## Performance Targets

- Time to Interactive: < 3 seconds
- Bundle Size: < 500KB (gzipped)
- First Contentful Paint: < 1.5 seconds
- Largest Contentful Paint: < 2.5 seconds
- Cumulative Layout Shift: < 0.1
- First Input Delay: < 100ms

## Browser Compatibility

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Accessibility

All applications comply with WCAG 2.1 Level AA:
- Keyboard navigation support
- Screen reader compatibility
- Color contrast ratios (4.5:1 for text, 3:1 for UI components)
- ARIA labels and roles
- Focus management

## Security

- Content Security Policy (CSP) headers
- Encrypted token storage
- Input validation and sanitization
- HTTPS-only connections
- No persistent audio/transcript storage

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

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and linting
4. Submit a pull request

## License

Proprietary - All rights reserved
