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

```bash
# Install all dependencies
npm run install:all

# Or install individually
npm install
npm install --workspace=shared
npm install --workspace=speaker-app
npm install --workspace=listener-app
```

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

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and linting
4. Submit a pull request

## License

Proprietary - All rights reserved
