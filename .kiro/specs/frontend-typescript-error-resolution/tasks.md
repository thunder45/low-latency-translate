# Implementation Plan

- [x] 1. Fix shared library AccessibleButton component
  - Add `ariaPressed` prop to AccessibleButtonProps interface
  - Add `className` prop to AccessibleButtonProps interface
  - Update component implementation to handle `ariaPressed` prop (use it if provided, otherwise fall back to `pressed`)
  - Update component implementation to apply `className` prop to button element
  - Verify shared library builds successfully: `npm run build:shared`
  - _Requirements: 2.1_

- [x] 2. Fix ErrorHandler usage in SpeakerService
  - Update all `ErrorHandler.handleError()` calls to `ErrorHandler.handle()` in SpeakerService.ts
  - Update ErrorHandler calls to pass context object instead of ErrorType enum as second parameter
  - Fix ErrorType enum references: change `ErrorType.AUDIO_ERROR` to `ErrorType.AUDIO_PROCESSING_ERROR` (line 155)
  - Verify speaker-app TypeScript errors decrease
  - _Requirements: 3.1, 3.4_

- [x] 3. Fix ErrorHandler usage in ListenerService
  - Update all `ErrorHandler.handleError()` calls to `ErrorHandler.handle()` in ListenerService.ts
  - Update ErrorHandler calls to pass context object instead of ErrorType enum as second parameter
  - Verify listener-app TypeScript errors decrease
  - _Requirements: 3.1_

- [x] 4. Fix PreferenceStore usage in SpeakerService
  - Import `preferenceStore` singleton from '@frontend/shared/services/PreferenceStore'
  - Replace `PreferenceStore.getInstance()` calls with direct `preferenceStore` usage (lines 100, 331)
  - Verify speaker-app TypeScript errors decrease
  - _Requirements: 3.2_

- [x] 5. Fix PreferenceStore usage in ListenerService
  - Import `preferenceStore` singleton from '@frontend/shared/services/PreferenceStore'
  - Replace `PreferenceStore.getInstance()` calls with direct `preferenceStore` usage (lines 86, 227, 301)
  - Verify listener-app TypeScript errors decrease
  - _Requirements: 3.2_

- [x] 6. Fix AuthService null safety issue
  - Add null check or non-null assertion at line 156 in shared/services/AuthService.ts
  - Verify shared library builds successfully
  - _Requirements: 3.3_

- [x] 7. Fix LoginForm authentication error handling
  - Change `ErrorType.AUTHENTICATION_ERROR` to `ErrorType.AUTH_FAILED` in speaker-app/src/components/LoginForm.tsx (line 42)
  - Update SignInResult type handling to extract idToken, accessToken, refreshToken properties correctly (line 38)
  - _Requirements: 3.4_

- [x] 8. Fix JSX style prop errors in listener-app components
  - Remove `jsx={true}` prop from style element in BufferIndicator.tsx (line 78)
  - Remove `jsx={true}` prop from style element in LanguageSelector.tsx (line 124)
  - Remove `jsx={true}` prop from style element in PlaybackControls.tsx (line 145)
  - Remove `jsx={true}` prop from style element in SessionJoiner.tsx (line 106)
  - Remove `jsx={true}` prop from style element in SpeakerStatus.tsx (line 106)
  - Verify listener-app TypeScript errors decrease
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 9. Fix notification type enum comparisons in BroadcastControlsContainer
  - Update notification type comparison from string literals to NotificationType enum values in speaker-app/src/components/BroadcastControlsContainer.tsx (line 42)
  - Change `'listenerJoined'` to `NotificationType.LISTENER_JOINED`
  - Change `'listenerLeft'` to `NotificationType.LISTENER_LEFT`
  - Import NotificationType enum if not already imported
  - _Requirements: 5.1, 5.3_

- [x] 10. Fix notification type enum comparisons in PlaybackControlsContainer
  - Update notification type comparisons from string literals to NotificationType enum values in listener-app/src/components/PlaybackControlsContainer.tsx (lines 41-47)
  - Change `'speakerPaused'` to `NotificationType.BROADCAST_PAUSED`
  - Change `'speakerResumed'` to `NotificationType.BROADCAST_RESUMED`
  - Change `'speakerMuted'` to `NotificationType.BROADCAST_MUTED`
  - Change `'speakerUnmuted'` to `NotificationType.BROADCAST_UNMUTED`
  - Import NotificationType enum if not already imported
  - _Requirements: 5.2, 5.3, 5.4_

- [x] 11. Fix SessionDisplay component props in SpeakerApp
  - Add `listenerCount` prop to SessionDisplay component usage in speaker-app/src/components/SpeakerApp.tsx (line 105)
  - Add `languageDistribution` prop to SessionDisplay component usage
  - Ensure props are passed from SpeakerApp state or provide default values
  - _Requirements: 2.2_

- [x] 12. Fix AudioVisualizer component props in SpeakerApp
  - Change `getInputLevel` prop to `inputLevel` in speaker-app/src/components/SpeakerApp.tsx (line 117)
  - Pass number value instead of function: `inputLevel={audioProcessor.getInputLevel()}`
  - _Requirements: 2.3_

- [x] 13. Fix SessionJoiner component props interface
  - Add `onSessionJoined` prop to SessionJoinerProps interface in listener-app/src/components/SessionJoiner.tsx
  - Add `onSendMessage` prop to SessionJoinerProps interface
  - Verify component usage in ListenerApp matches updated interface
  - _Requirements: 2.4_

- [x] 14. Fix SpeakerStatus component props interface
  - Add `isPaused` prop to SpeakerStatusProps interface in listener-app/src/components/SpeakerStatus.tsx
  - Add `isMuted` prop to SpeakerStatusProps interface
  - Verify component usage in ListenerApp matches updated interface (line 108)
  - _Requirements: 2.5_

- [x] 15. Fix BufferIndicator component props in ListenerApp
  - Add `bufferOverflow` prop to BufferIndicator component usage in listener-app/src/components/ListenerApp.tsx (line 112)
  - Ensure prop value is provided from ListenerApp state or provide default value
  - _Requirements: 2.6_

- [x] 16. Fix language data type consistency in ListenerApp
  - Update language data handling in listener-app/src/components/ListenerApp.tsx (lines 129-138)
  - Extract language codes from language objects before passing to LanguageSelector
  - Change from passing `{ code: string, name: string }` objects to passing string codes
  - _Requirements: 7.1, 7.2_

- [x] 17. Fix null safety in ListenerService language handling
  - Add null check before passing languageCode to methods in listener-app/src/services/ListenerService.ts (line 311)
  - Use null coalescing or conditional check to ensure non-null string is passed
  - _Requirements: 3.5_

- [x] 18. Fix null safety in useListenerControls hook
  - Add null check for string parameter in listener-app/src/hooks/useListenerControls.ts (line 110)
  - Ensure non-null string is passed to methods requiring string parameters
  - _Requirements: 3.5_

- [x] 19. Remove unused imports and variables in speaker-app
  - Remove unused `render`, `screen`, `fireEvent` imports from speaker-flow.test.tsx (line 2)
  - Remove unused `useEffect` import from KeyboardShortcutsHandler.tsx (line 1)
  - Remove unused `useEffect` import from useSpeakerControls.ts (line 1)
  - Remove unused `inputVolume` variable from SpeakerService.ts (line 28)
  - Remove unused `newSessionId` variable from SpeakerApp.tsx (line 28)
  - Remove unused `handleSessionCreationResponse` variable from SessionCreator.tsx (line 69)
  - Remove unused `appError` variable from SpeakerService.ts (line 463)
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 20. Remove unused imports and variables in listener-app
  - Remove unused `render`, `screen` imports from listener-flow.test.tsx (line 2)
  - Remove unused `useEffect` import from useListenerControls.ts (line 1)
  - Remove unused `playbackVolume` variable from ListenerService.ts (line 25)
  - Remove unused `onAudioChunk` variable from ListenerService.ts (line 26)
  - Remove unused `isConnected` variable from ListenerApp.tsx (line 25)
  - Remove unused `state` variable from ListenerService.ts (line 386)
  - Remove unused `message` variable from ListenerService.ts (line 437)
  - Remove unused `appError` variable from ListenerService.ts (line 460)
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 21. Remove unused variable in shared CircularAudioBuffer
  - Remove unused `maxDuration` variable from shared/audio/CircularAudioBuffer.ts (line 15)
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 22. Update speaker-app integration test service configuration
  - Remove `authToken` property from SpeakerServiceConfig in speaker-flow.test.tsx (line 20)
  - Update service configuration to match current SpeakerServiceConfig interface
  - _Requirements: 1.4_

- [x] 23. Update speaker-app integration test API calls
  - Update integration tests to use current SpeakerService API methods in speaker-flow.test.tsx
  - Replace references to non-existent methods: `createSession()`, `startAudioTransmission()`, `pauseBroadcast()`, `resumeBroadcast()`
  - Update to use actual methods available in SpeakerService implementation
  - _Requirements: 1.1_

- [x] 24. Update speaker-app integration test state property access
  - Change `state.session.sessionId` to `state.sessionId` in speaker-flow.test.tsx (lines 39, 40, 61, 182)
  - Update all references to use correct state property names from SpeakerState interface
  - _Requirements: 1.3_

- [x] 25. Update speaker-app integration test QualityWarning usage
  - Add `issue` property to QualityWarning object references in speaker-flow.test.tsx (line 142)
  - Ensure QualityWarning objects match the QualityWarning interface definition
  - _Requirements: 8.1, 8.2_

- [x] 26. Update listener-app integration test service configuration
  - Add required `sessionId` property to ListenerServiceConfig in listener-flow.test.tsx (line 18)
  - Add required `targetLanguage` property to ListenerServiceConfig
  - Update service configuration to match current ListenerServiceConfig interface
  - _Requirements: 1.4_

- [x] 27. Update listener-app integration test API calls
  - Update integration tests to use current ListenerService API methods in listener-flow.test.tsx
  - Replace references to non-existent methods: `joinSession()`, `pausePlayback()`, `resumePlayback()`, `setMuted()`, `disconnect()`
  - Update to use actual methods available in ListenerService implementation
  - _Requirements: 1.2_

- [x] 28. Update listener-app integration test state property access
  - Change `state.session.sessionId` to `state.sessionId` in listener-flow.test.tsx (lines 37, 38, 59, 291)
  - Update all references to use correct state property names from ListenerState interface
  - _Requirements: 1.3_

- [x] 29. Fix ListenerService method signature error
  - Fix method call with incorrect number of arguments in ListenerService.ts (line 380)
  - Update to pass correct number of arguments (expected 2, currently passing 3)
  - _Requirements: 3.1_

- [x] 30. Fix ListenerApp startPlayback method call
  - Update `startPlayback()` method call in ListenerApp.tsx (line 72)
  - Verify method exists in ListenerService or update to use correct method name
  - _Requirements: 1.2_

- [x] 31. Fix KeyboardShortcutsHandler import error
  - Fix import path for speakerStore in speaker-app/src/components/KeyboardShortcutsHandler.tsx (line 3)
  - Update import to use correct path or module name
  - _Requirements: 1.1_

- [x] 32. Verify speaker-app builds successfully
  - Run `npm run build:speaker` and verify zero TypeScript errors
  - Verify dist/ directory contains compiled output
  - Check that all 44 speaker-app errors are resolved
  - _Requirements: 9.1, 9.3, 9.4, 9.5_

- [x] 33. Verify listener-app builds successfully
  - Run `npm run build:listener` and verify zero TypeScript errors
  - Verify dist/ directory contains compiled output
  - Check that all 62 listener-app errors are resolved
  - _Requirements: 9.2, 9.3, 9.4, 9.5_

- [x] 34. Verify full workspace builds successfully
  - Run `npm run build:all` and verify all three workspaces build with zero errors
  - Verify dist/ directories exist for shared, speaker-app, and listener-app
  - Confirm total error count is zero (was 106)
  - _Requirements: 9.3, 9.4, 9.5_
