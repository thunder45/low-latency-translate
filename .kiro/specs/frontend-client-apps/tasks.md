# Implementation Plan

- [x] 1. Set up project structure and shared library
  - Create monorepo structure with shared, speaker-app, and listener-app directories
  - Initialize React + TypeScript + Vite projects for both applications
  - Configure shared library with WebSocket, audio, and component modules
  - Set up package.json with dependencies (React 18, Zustand, amazon-cognito-identity-js, crypto-js)
  - Configure TypeScript with strict mode and path aliases
  - _Requirements: 20.5_

- [x] 2. Implement shared WebSocket client
  - [x] 2.1 Create WebSocket client class with connection management
    - Write WebSocketClient class with connect, send, disconnect methods
    - Implement connection state tracking (disconnected, connecting, connected, reconnecting, failed)
    - Add message handler registration with on() method
    - _Requirements: 13.1, 13.2, 13.3, 13.4_
  
  - [x] 2.2 Implement heartbeat mechanism
    - Add automatic heartbeat sending every 30 seconds
    - Implement heartbeat acknowledgment tracking with 5-second timeout
    - Trigger reconnection on heartbeat timeout
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [x] 2.3 Add automatic reconnection with exponential backoff
    - Implement reconnection logic with exponential backoff (1s, 2s, 4s, 8s, max 30s)
    - Track reconnection attempts and enforce maximum attempts limit
    - Emit reconnection events for application layer handling
    - _Requirements: 13.5, 15.1, 15.2, 15.3_
  
  - [x] 2.4 Create TypeScript interfaces for all message types
    - Define interfaces for speaker messages (sendAudio, pauseBroadcast, endSession, getSessionStatus)
    - Define interfaces for listener messages (switchLanguage)
    - Define interfaces for server messages (sessionCreated, sessionJoined, audio, qualityWarning, sessionStatus, speakerState, connectionRefresh, sessionEnded, error)
    - _Requirements: 2.1, 8.1, 11.1_

- [x] 3. Implement audio capture service for speaker
  - [x] 3.1 Create AudioCapture class with microphone access
    - Request microphone permission with getUserMedia
    - Configure audio constraints (16kHz, mono, echo cancellation, noise suppression, auto gain)
    - Handle permission denial with user-friendly error
    - _Requirements: 3.1, 3.5_
  
  - [x] 3.2 Implement audio processing pipeline
    - Create AudioContext with 16kHz sample rate
    - Set up ScriptProcessorNode for audio chunk processing
    - Process audio in 1-3 second chunks
    - _Requirements: 3.2_
  
  - [x] 3.3 Add PCM conversion and base64 encoding
    - Convert Float32 audio samples to PCM 16-bit format
    - Encode PCM data as base64 string
    - Generate chunk metadata (timestamp, chunkId, duration)
    - _Requirements: 3.3_
  
  - [x] 3.4 Implement input level monitoring
    - Calculate real-time audio input level (0-100)
    - Provide getInputLevel() method for visualization
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5_

- [x] 4. Implement audio playback service for listener
  - [x] 4.1 Create AudioPlayback class with buffer queue
    - Initialize AudioContext and GainNode
    - Implement audio buffer queue for incoming chunks
    - Track playback state (playing, paused, muted)
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  
  - [x] 4.2 Implement audio decoding and playback
    - Decode base64 audio data to PCM samples
    - Convert PCM to Float32 and create AudioBuffer
    - Schedule playback with automatic queue processing
    - Handle buffer underruns with buffering indicator
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [x] 4.3 Add playback controls (pause, mute, volume)
    - Implement pause() and resume() methods
    - Implement setMuted() with gain node control
    - Implement setVolume() with range 0-1
    - _Requirements: 10.1, 10.2, 10.3, 10.4_
  
  - [x] 4.4 Implement buffer management with 30-second limit
    - Track buffered duration with getBufferDuration()
    - Discard oldest chunks when buffer exceeds 30 seconds
    - Emit buffer overflow warning
    - _Requirements: 10.5_

- [x] 5. Implement state management with Zustand
  - [x] 5.1 Create speaker store with session and audio state
    - Define SpeakerState interface with all state properties
    - Implement actions for session management (setSession, setConnected, reset)
    - Implement actions for audio controls (setPaused, setMuted, setInputVolume, setTransmitting)
    - Implement actions for quality warnings (addQualityWarning, clearQualityWarnings)
    - Implement actions for listener stats (updateListenerStats)
    - _Requirements: 2.3, 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [x] 5.2 Create listener store with session and playback state
    - Define ListenerState interface with all state properties
    - Implement actions for session management (setSession, setConnected, reset)
    - Implement actions for playback controls (setPaused, setMuted, setPlaybackVolume)
    - Implement actions for language switching (setTargetLanguage)
    - Implement actions for buffer tracking (setBufferedDuration, setBuffering, setBufferOverflow)
    - Implement actions for speaker state (setSpeakerPaused, setSpeakerMuted)
    - _Requirements: 8.3, 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 11.2, 12.1, 12.2, 12.3, 12.4, 12.5_

- [x] 6. Implement authentication service for speaker
  - [x] 6.1 Create AuthService with Cognito integration
    - Initialize CognitoUserPool with userPoolId and clientId
    - Implement signIn() method with email and password
    - Return JWT tokens (idToken, accessToken, refreshToken) on success
    - _Requirements: 1.1, 1.3_
  
  - [x] 6.2 Add token refresh mechanism
    - Implement refreshSession() method using refresh token
    - Check token expiration and refresh automatically when within 5 minutes
    - _Requirements: 1.4_
  
  - [x] 6.3 Implement sign out functionality
    - Create signOut() method to clear Cognito session
    - Clear stored tokens from secure storage
    - _Requirements: 1.5_

- [x] 7. Implement secure storage utilities
  - [x] 7.1 Create SecureStorage class with encryption
    - Implement set() method with AES encryption
    - Implement get() method with AES decryption
    - Implement remove() and clear() methods
    - Handle decryption errors gracefully
    - _Requirements: 1.2, 16.1, 16.2, 16.3_
  
  - [x] 7.2 Define storage keys and preference interfaces
    - Create STORAGE_KEYS constants for all storage keys
    - Define SpeakerPreferences interface (inputVolume, keyboardShortcuts)
    - Define ListenerPreferences interface (playbackVolume, languagePreference, keyboardShortcuts)
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

- [x] 8. Implement error handling utilities
  - [x] 8.1 Create error types and ErrorHandler class
    - Define ErrorType enum with all error types
    - Define AppError interface with type, message, userMessage, recoverable, retryable
    - Implement ErrorHandler.handle() method with user-friendly messages and recovery actions
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_
  
  - [x] 8.2 Create RetryHandler with exponential backoff
    - Implement RetryHandler class with configurable retry parameters
    - Implement execute() method with retry logic and backoff calculation
    - Track retry attempts and enforce maximum attempts
    - Provide onRetry callback for progress updates
    - _Requirements: 13.5, 14.5, 15.1, 15.2_

- [x] 9. Implement validation utilities
  - [x] 9.1 Create Validator class with input validation methods
    - Implement isValidSessionId() for session ID format validation
    - Implement isValidLanguageCode() for ISO 639-1 validation
    - Implement isValidEmail() for email format validation
    - Implement sanitizeInput() to remove dangerous characters
    - _Requirements: 2.1, 8.1, 11.1_

- [x] 10. Create shared UI components
  - [x] 10.1 Build ConnectionStatus component
    - Display connection status with color-coded indicator (green, yellow, orange, red)
    - Show reconnection attempts with countdown
    - Provide "Retry Now" button for failed connections
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 15.1, 15.2_
  
  - [x] 10.2 Build ErrorDisplay component
    - Display error messages with appropriate styling
    - Show recovery action buttons based on error type
    - Support dismissible and persistent error modes
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_
  
  - [x] 10.3 Build AccessibleButton component
    - Implement button with ARIA labels and pressed state
    - Support keyboard navigation with focus indicators
    - Ensure 4.5:1 color contrast ratio
    - _Requirements: 17.1, 17.2, 18.1, 18.2, 18.3, 18.4, 18.5_

- [x] 11. Implement speaker application components
  - [x] 11.1 Create LoginForm component
    - Build form with email and password inputs
    - Integrate with AuthService for authentication
    - Display authentication errors with user-friendly messages
    - Redirect to session creation on successful login
    - _Requirements: 1.1, 1.3, 1.5_
  
  - [x] 11.2 Create SessionCreator component
    - Build form with source language and quality tier selection
    - Send session creation request via WebSocket with JWT token
    - Handle session creation success and errors (401, 429)
    - _Requirements: 2.1, 2.2, 2.4, 2.5_
  
  - [x] 11.3 Create SessionDisplay component
    - Display session ID in large, copyable text (minimum 24-point font)
    - Show active listener count with minimum 18-point font
    - Display language distribution as list with language codes and counts
    - Implement copy-to-clipboard functionality with visual feedback
    - _Requirements: 2.2, 5.2, 5.3, 5.4, 5.5_
  
  - [x] 11.4 Create BroadcastControls component
    - Build pause button with toggle state and Ctrl+P shortcut
    - Build mute button with toggle state and Ctrl+M shortcut
    - Build volume slider with debounced updates (50ms)
    - Build end session button with confirmation dialog
    - Update button states within 50ms of user interaction
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3, 7.4, 7.5, 17.1, 17.2_
  
  - [x] 11.5 Create AudioVisualizer component
    - Display real-time waveform or level meter at 30+ FPS
    - Show visual warning for input level >80% (yellow) and >95% (red)
    - Display "Low audio level detected" for <5% level lasting >3 seconds
    - Calculate and display average level over 1-second rolling window
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5_
  
  - [x] 11.6 Create QualityIndicator component
    - Display quality warnings for SNR low, clipping, echo, silence
    - Show warning messages with issue-specific styling
    - Clear warnings automatically when quality returns to normal (within 2 seconds)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 12. Implement listener application components
  - [x] 12.1 Create SessionJoiner component
    - Build form with session ID input and target language selection
    - Validate session ID format before submission
    - Send joinSession request via WebSocket
    - Handle join errors (404, 503) with user-friendly messages
    - _Requirements: 8.1, 8.2, 8.4, 8.5_
  
  - [x] 12.2 Create PlaybackControls component
    - Build pause button with toggle state and Ctrl+P shortcut
    - Build mute button with toggle state and Ctrl+M shortcut
    - Build volume slider with debounced updates (50ms)
    - Update button states within 50ms of user interaction
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 17.3, 17.4_
  
  - [x] 12.3 Create LanguageSelector component
    - Build dropdown with available target languages
    - Send switchLanguage action on selection change
    - Display "Switching to {languageName}..." indicator during switch
    - Handle language switch failure with revert to previous language
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [x] 12.4 Create BufferIndicator component
    - Display buffered audio duration (0-30 seconds)
    - Show "Buffering..." indicator when buffer is empty
    - Show "Buffer full - audio being skipped" warning when buffer overflows
    - _Requirements: 9.5, 10.5_
  
  - [x] 12.5 Create SpeakerStatus component
    - Display "Speaker paused" indicator when speaker pauses
    - Display "Speaker muted" indicator when speaker mutes
    - Clear indicators within 500ms when speaker resumes/unmutes
    - Use distinct visual styling for each state
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [x] 13. Implement speaker application integration
  - [x] 13.1 Create SpeakerService to orchestrate WebSocket and audio
    - Initialize WebSocket client with speaker configuration
    - Initialize AudioCapture service
    - Connect WebSocket with JWT token and session parameters
    - Handle sessionCreated message and update store
    - _Requirements: 2.1, 2.3, 3.1_
  
  - [x] 13.2 Implement audio transmission flow
    - Start audio capture on session creation
    - Send audio chunks via WebSocket with sendAudio action
    - Handle pause/mute by stopping audio transmission
    - Handle resume/unmute by restarting audio transmission
    - _Requirements: 3.2, 3.3, 6.1, 6.2, 6.4_
  
  - [x] 13.3 Implement session status polling
    - Request session status every 5 seconds while session is active
    - Update listener count and language distribution in store
    - Update display within 1 second when listener count changes >10%
    - _Requirements: 5.1, 5.4, 5.5_
  
  - [x] 13.4 Handle quality warnings from server
    - Register handler for audio_quality_warning messages
    - Add warnings to store with addQualityWarning action
    - Clear warnings when quality returns to normal
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  
  - [x] 13.5 Implement session end flow
    - Send endSession action on user request
    - Stop audio capture and close WebSocket within 1 second
    - Clear session state and redirect to session creation
    - Retry endSession with exponential backoff on failure (up to 3 attempts)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 14. Implement listener application integration
  - [x] 14.1 Create ListenerService to orchestrate WebSocket and audio
    - Initialize WebSocket client with listener configuration
    - Initialize AudioPlayback service
    - Connect WebSocket with session ID and target language
    - Handle sessionJoined message and update store
    - _Requirements: 8.1, 8.2, 8.3_
  
  - [x] 14.2 Implement audio reception and playback flow
    - Register handler for audio messages
    - Decode and queue audio for playback
    - Handle pause by buffering audio (up to 30 seconds)
    - Handle resume by playing buffered audio
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.4_
  
  - [x] 14.3 Implement language switching flow
    - Send switchLanguage action on user request
    - Clear audio buffer and reset playback state
    - Display switching indicator during transition
    - Handle switch failure with revert to previous language
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [x] 14.4 Handle speaker state messages
    - Register handlers for speakerPaused, speakerMuted, speakerResumed, speakerUnmuted
    - Update store with speaker state changes
    - Display appropriate indicators in UI
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_
  
  - [x] 14.5 Handle session ended message
    - Display "Session ended by speaker" message
    - Provide "Join Another Session" button
    - Clear session state and stop audio playback
    - _Requirements: 15.5_

- [x] 15. Implement connection refresh mechanism
  - [x] 15.1 Handle connectionRefreshRequired message in speaker app
    - Display "Connection refresh required in 20 minutes" warning at 100 minutes
    - Initiate refresh at 115 minutes by establishing new WebSocket connection
    - Send refreshConnection action with JWT token and session ID
    - Close old connection after receiving connectionRefreshComplete
    - _Requirements: 14.1, 14.2, 14.3, 14.4_
  
  - [x] 15.2 Handle connectionRefreshRequired message in listener app
    - Display "Connection refresh required in 20 minutes" warning at 100 minutes
    - Initiate refresh at 115 minutes by establishing new WebSocket connection
    - Send refreshConnection action with session ID and target language
    - Close old connection after receiving connectionRefreshComplete
    - _Requirements: 14.1, 14.2, 14.3, 14.4_
  
  - [x] 15.3 Implement refresh retry logic
    - Retry refresh with exponential backoff on failure (1s, 2s, 4s)
    - Allow up to 5 retry attempts
    - Display "Session will expire soon. Please create new session" after max retries
    - _Requirements: 14.5_

- [x] 16. Implement keyboard shortcuts
  - [x] 16.1 Create useKeyboardShortcuts hook
    - Accept array of KeyboardShortcut objects with key, modifiers, handler, description
    - Register keydown event listener
    - Match key combinations and call handlers
    - Prevent default browser behavior for registered shortcuts
    - _Requirements: 17.1, 17.2, 17.3, 17.4_
  
  - [x] 16.2 Integrate shortcuts in speaker app
    - Register Ctrl+M/Cmd+M for mute toggle
    - Register Ctrl+P/Cmd+P for pause toggle
    - Display temporary tooltip showing action name for 2 seconds
    - Provide visual feedback within 50ms
    - _Requirements: 17.1, 17.2, 17.5_
  
  - [x] 16.3 Integrate shortcuts in listener app
    - Register Ctrl+M/Cmd+M for mute toggle
    - Register Ctrl+P/Cmd+P for pause toggle
    - Register Ctrl+Up/Cmd+Up for volume increase (10%)
    - Register Ctrl+Down/Cmd+Down for volume decrease (10%)
    - _Requirements: 17.3, 17.4_

- [x] 17. Implement accessibility features
  - [x] 17.1 Add ARIA labels to all interactive elements
    - Add aria-label to all buttons with descriptive text
    - Add aria-pressed to toggle buttons (pause, mute)
    - Add aria-label to form inputs
    - Ensure screen readers announce all state changes
    - _Requirements: 18.3, 18.4_
  
  - [x] 17.2 Implement keyboard navigation
    - Ensure all interactive elements are keyboard accessible
    - Add visible focus indicators with 3:1 contrast ratio
    - Implement logical tab order through all components
    - _Requirements: 18.1, 18.2_
  
  - [x] 17.3 Create useFocusTrap hook for modal dialogs
    - Trap focus within modal when active
    - Handle Tab and Shift+Tab for forward/backward navigation
    - Return focus to trigger element on close
    - _Requirements: 18.1, 18.2_
  
  - [x] 17.4 Ensure color contrast compliance
    - Verify 4.5:1 contrast ratio for all text
    - Verify 3:1 contrast ratio for UI components
    - Test with color contrast analyzer tools
    - _Requirements: 18.5_

- [x] 18. Implement preference persistence
  - [x] 18.1 Create preference loading on app initialization
    - Load speaker preferences (inputVolume, keyboardShortcuts) from SecureStorage
    - Load listener preferences (playbackVolume, languagePreference, keyboardShortcuts) from SecureStorage
    - Apply preferences to store within 500ms
    - _Requirements: 16.4, 16.5_
  
  - [x] 18.2 Implement preference saving on changes
    - Save speaker input volume to storage on change
    - Save listener playback volume to storage on change
    - Save listener language preference to storage on change
    - Debounce storage writes to avoid excessive writes
    - _Requirements: 16.1, 16.2, 16.3_

- [x] 19. Implement browser compatibility checks
  - [x] 19.1 Create BrowserSupport utility class
    - Implement checkWebSocketSupport() method
    - Implement checkWebAudioSupport() method
    - Implement checkMediaDevicesSupport() method
    - Implement checkLocalStorageSupport() method
    - Implement checkAllRequirements() method returning supported status and missing features
    - _Requirements: 20.1, 20.2, 20.3, 20.4_
  
  - [x] 19.2 Add browser compatibility check on app load
    - Check all requirements before rendering main app
    - Display unsupported browser message with missing features list
    - Provide browser upgrade recommendations (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)
    - _Requirements: 20.1, 20.2, 20.3, 20.4_

- [x] 20. Implement monitoring and analytics
  - [x] 20.1 Create RUM integration utility
    - Initialize AWS CloudWatch RUM with app configuration
    - Implement recordCustomMetric() for custom events
    - Configure telemetries for performance, errors, and HTTP
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5_
  
  - [x] 20.2 Create PerformanceMonitor utility
    - Implement recordPageLoad() to track load metrics
    - Implement recordAudioLatency() to track end-to-end latency
    - Send metrics to CloudWatch or monitoring service
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5_
  
  - [x] 20.3 Add performance tracking to key operations
    - Track session creation time
    - Track listener join time
    - Track audio end-to-end latency
    - Track control response time
    - Track language switch duration
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5_

- [x] 21. Configure build and deployment
  - [x] 21.1 Create Vite configuration for both apps
    - Configure React plugin and TypeScript
    - Set up code splitting with manual chunks (react-vendor, audio-vendor, state-vendor)
    - Configure minification with terser
    - Set chunk size warning limit to 500KB
    - Add bundle analyzer plugin
    - _Requirements: 20.5_
  
  - [x] 21.2 Create deployment scripts
    - Write deploy.sh script for S3 upload
    - Add CloudFront invalidation after deployment
    - Support multiple environments (dev, staging, prod)
    - _Requirements: 20.1, 20.2_
  
  - [x] 21.3 Create CloudFormation templates for infrastructure
    - Define S3 buckets for speaker and listener apps
    - Define CloudFront distributions with caching configuration
    - Configure custom error responses for SPA routing
    - Set up HTTPS with CloudFront default certificate
    - _Requirements: 20.1, 20.2_

- [x] 22. Implement security measures
  - [x] 22.1 Add Content Security Policy
    - Configure CSP meta tag in index.html
    - Allow WebSocket connections to API Gateway
    - Allow HTTPS connections to Cognito
    - Restrict script and style sources
    - _Requirements: 1.1, 2.1, 8.1_
  
  - [x] 22.2 Implement input sanitization
    - Sanitize all user inputs before display
    - Validate session IDs, language codes, and email formats
    - Prevent XSS attacks with proper escaping
    - _Requirements: 2.1, 8.1, 11.1_

- [x]* 23. Write unit tests for core functionality
  - Write tests for WebSocket client message handling
  - Write tests for audio processing utilities (PCM conversion, base64 encoding/decoding)
  - Write tests for state management actions and selectors
  - Write tests for error handling and retry logic
  - Write tests for storage utilities (encryption, persistence)
  - Write tests for component rendering and user interactions
  - _Requirements: All requirements_

- [x]* 24. Write integration tests for user flows
  - Write test for complete speaker flow (login → create → broadcast → end)
  - Write test for complete listener flow (join → listen → controls → leave)
  - Write test for connection refresh flow
  - Write test for error recovery scenarios
  - Write test for multi-tab testing (multiple listeners)
  - _Requirements: All requirements_

- [x]* 25. Write end-to-end tests with Playwright
  - Write test for speaker and listener communication
  - Write test for cross-browser compatibility (Chrome, Firefox, Safari, Edge)
  - Write test for mobile responsiveness
  - Write test for network condition simulation (slow 3G, packet loss)
  - Write test for concurrent user testing
  - _Requirements: All requirements_

- [x] 26. Perform performance optimization
  - Run Lighthouse audits and achieve target scores (Performance, Accessibility, Best Practices, SEO)
  - Verify Core Web Vitals (LCP < 2.5s, FID < 100ms, CLS < 0.1)
  - Verify bundle size < 500KB (gzipped)
  - Verify Time to Interactive < 3 seconds
  - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5_
