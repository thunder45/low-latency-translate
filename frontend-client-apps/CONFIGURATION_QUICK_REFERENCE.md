# Configuration Quick Reference

## Current Configuration (Staging)

### WebSocket API
```
wss://vphqnkfxtf.execute-api.us-east-1.amazonaws.com/prod
```

### Cognito (Speaker App)
```
User Pool ID: us-east-1_WoaXmyQLQ
Client ID:    38t8057tbi0o6873qt441kuo3n
Region:       us-east-1
```

## Quick Commands

```bash
# Validate configuration
npm run validate-config

# Build all apps
npm run build:all

# Run locally
npm run dev:speaker   # Terminal 1
npm run dev:listener  # Terminal 2

# Generate encryption key
openssl rand -base64 32
```

## File Locations

```
speaker-app/.env          # Speaker configuration
listener-app/.env         # Listener configuration
shared/utils/config.ts    # Configuration utility
scripts/validate-config.js # Validation script
CONFIGURATION_GUIDE.md    # Full documentation
```

## Required Environment Variables

### Speaker App
```bash
VITE_WEBSOCKET_URL=wss://...
VITE_COGNITO_USER_POOL_ID=...
VITE_COGNITO_CLIENT_ID=...
VITE_AWS_REGION=us-east-1
VITE_ENCRYPTION_KEY=...
```

### Listener App
```bash
VITE_WEBSOCKET_URL=wss://...
VITE_AWS_REGION=us-east-1
VITE_ENCRYPTION_KEY=...
```

## Common Issues

| Issue | Solution |
|-------|----------|
| Config not loading | Restart dev server after changing `.env` |
| Build fails | Verify `"types": ["vite/client"]` in tsconfig.json |
| Validation fails | Check error messages, see CONFIGURATION_GUIDE.md |
| WebSocket fails | Verify URL is correct and API Gateway is deployed |

## Security Checklist

- [ ] `.env` files not committed to git
- [ ] Different encryption keys per environment
- [ ] Secure keys generated (not example values)
- [ ] Production keys stored in secrets manager
- [ ] No AWS credentials in frontend code

## Next Steps

1. ✅ Configuration validated
2. ✅ Build successful
3. ⏭️ Test WebSocket connection
4. ⏭️ Test authentication
5. ⏭️ Deploy to hosting service

For detailed information, see **CONFIGURATION_GUIDE.md**
