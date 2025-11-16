# Implementation Plan

- [x] 1. Fix TypeScript syntax errors in shared components
  - Fix closing parenthesis syntax in ListenerControls.tsx (line 246)
  - Fix closing parenthesis syntax in SpeakerControls.tsx (line 222)
  - Verify TypeScript compilation succeeds with `npm run build:shared`
  - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3_

- [x] 2. Fix WebSocket message type mismatches in listener service
  - Change 'switchLanguage' action to 'changeLanguage' in ListenerService.ts (line 234)
  - Change 'speakerPaused' handler to 'broadcastPaused' in ListenerService.ts (line 195)
  - Change 'speakerResumed' handler to 'broadcastResumed' in ListenerService.ts (line 200)
  - Change 'speakerMuted' handler to 'broadcastMuted' in ListenerService.ts (line 205)
  - Change 'speakerUnmuted' handler to 'broadcastUnmuted' in ListenerService.ts (line 210)
  - _Requirements: 7.1, 7.3, 7.4, 7.5, 7.6, 7.7_

- [x] 3. Fix WebSocket message type mismatch in speaker service
  - Change 'audio_quality_warning' handler to 'audioQualityWarning' in SpeakerService.ts (line 115)
  - _Requirements: 7.2, 7.7_

- [x] 4. Create environment configuration files
  - Create speaker-app/.env.example with staging WebSocket URL and Cognito credentials
  - Create listener-app/.env.example with staging WebSocket URL
  - Add comments explaining each environment variable
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 5. Update README documentation
  - Add emphasis to installation section that dependencies must be installed before building
  - Add configuration section with instructions for copying .env.example files
  - Add troubleshooting section with common build and runtime issues
  - Update environment variables section with actual staging values as examples
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 6. Verify build process works end-to-end
  - Run clean install: `rm -rf node_modules */node_modules && npm run install:all`
  - Run full build: `npm run build:all`
  - Verify all three workspaces build successfully
  - Verify dist/ directories contain compiled output
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 7. Verify development workflow
  - Test speaker-app development server: `npm run dev:speaker`
  - Test listener-app development server: `npm run dev:listener`
  - Verify hot-reload works when making code changes
  - Verify applications load in browser without console errors
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 8. Verify code quality standards
  - Run linter: `npm run lint`
  - Verify zero linting errors
  - Check that React.memo() syntax is correct in all components
  - _Requirements: 6.1, 6.2, 6.3_

- [ ] 9. Test WebSocket connectivity with staging backend
  - Copy .env.example to .env in both apps
  - Start speaker-app and verify WebSocket connection to staging
  - Start listener-app and verify WebSocket connection to staging
  - Test language switch action sends correct 'changeLanguage' message
  - Test that broadcast state messages are received correctly
  - _Requirements: 5.5, 7.1, 7.3, 7.4, 7.5, 7.6_
