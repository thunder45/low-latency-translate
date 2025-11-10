# Requirements Document

## Introduction

This specification defines the requirements for two web-based client applications that enable real-time emotion-aware speech translation: a Speaker Application for authenticated users to broadcast audio, and a Listener Application for anonymous users to receive translated audio. Both applications integrate with the backend WebSocket API, handle audio processing using the Web Audio API, and provide responsive user interfaces with accessibility compliance. The system targets sub-4-second end-to-end latency with support for up to 500 concurrent listeners per session.

## Glossary

- **Speaker Application**: Web application used by authenticated users to create sessions and broadcast audio
- **Listener Application**: Web application used by anonymous users to join sessions and receive translated audio
- **WebSocket Client**: Browser-based client that maintains persistent connection to backend API Gateway
- **Audio Context**: Web Audio API object that manages audio processing graph
- **PCM Audio**: Pulse Code Modulation format (16-bit signed integers, 16kHz, mono)
- **Session ID**: Human-readable identifier (e.g., "golden-eagle-427") for broadcast sessions
- **JWT Token**: JSON Web Token from AWS Cognito for speaker authentication
- **Audio Buffer**: Client-side queue storing received audio chunks for playback
- **Heartbeat**: Periodic ping message sent every 30 seconds to maintain connection
- **Connection Refresh**: Process of establishing new WebSocket connection before 2-hour timeout
- **Quality Warning**: Server-generated alert about audio issues (SNR, clipping, echo, silence)
- **Control State**: User-controlled audio parameters (pause, mute, volume)
- **Target Language**: ISO 639-1 language code for translation output (e.g., "es", "fr", "de")
- **Source Language**: ISO 639-1 language code for speaker's input audio

## Requirements

### Requirement 1

**User Story:** As a speaker, I want to authenticate with my credentials, so that I can create secure broadcast sessions

#### Acceptance Criteria

1. WHEN the speaker enters valid email and password, THE Speaker Application SHALL authenticate with AWS Cognito and obtain JWT tokens
2. WHEN authentication succeeds, THE Speaker Application SHALL store the JWT token securely in encrypted browser storage
3. IF authentication fails with invalid credentials, THEN THE Speaker Application SHALL display "Authentication failed. Please check your credentials and try again"
4. WHEN the JWT token expires within 5 minutes, THE Speaker Application SHALL automatically refresh the token using the refresh token
5. WHEN the speaker clicks logout, THE Speaker Application SHALL clear all stored tokens and redirect to the login page

### Requirement 2

**User Story:** As a speaker, I want to create a broadcast session with my preferred language and quality settings, so that listeners can join and hear my translated speech

#### Acceptance Criteria

1. WHEN the speaker selects source language and quality tier, THE Speaker Application SHALL send session creation request with JWT token via WebSocket connection
2. WHEN session creation succeeds, THE Speaker Application SHALL display the session ID in large, copyable text format with minimum 24-point font size
3. WHEN session creation succeeds, THE Speaker Application SHALL store session metadata including sessionId, connectionId, and expiresAt timestamp
4. IF session creation fails with 401 error, THEN THE Speaker Application SHALL display "Authentication failed. Please log in again" and redirect to login
5. IF session creation fails with 429 error, THEN THE Speaker Application SHALL display "Too many sessions created. Please wait {retryAfter} seconds" with countdown timer

### Requirement 3

**User Story:** As a speaker, I want to broadcast my voice through my microphone, so that listeners receive my speech in their selected languages

#### Acceptance Criteria

1. WHEN the speaker grants microphone permission, THE Speaker Application SHALL create Audio Context with 16kHz sample rate and mono channel configuration
2. WHEN audio is captured, THE Speaker Application SHALL process audio in 1-3 second chunks with echo cancellation, noise suppression, and auto gain control enabled
3. WHEN audio chunk is processed, THE Speaker Application SHALL convert Float32 audio to PCM 16-bit format, encode as base64, and send via WebSocket with timestamp and chunkId
4. WHILE the speaker is broadcasting, THE Speaker Application SHALL maintain transmission rate of 1 chunk per 1-3 seconds with maximum message size of 1MB
5. IF microphone permission is denied, THEN THE Speaker Application SHALL display "Microphone access required. Please enable in browser settings" with browser-specific instructions

### Requirement 4

**User Story:** As a speaker, I want to see real-time feedback about my audio quality, so that I can adjust my setup to improve listener experience

#### Acceptance Criteria

1. WHEN the Speaker Application receives audio_quality_warning message with issue "snr_low", THE Speaker Application SHALL display "Background noise detected. Move to quieter location" with SNR value
2. WHEN the Speaker Application receives audio_quality_warning message with issue "clipping", THE Speaker Application SHALL display "Audio distortion detected. Reduce microphone volume" with visual indicator
3. WHEN the Speaker Application receives audio_quality_warning message with issue "echo", THE Speaker Application SHALL display "Echo detected. Enable echo cancellation or use headphones"
4. WHEN the Speaker Application receives audio_quality_warning message with issue "silence", THE Speaker Application SHALL display "No audio detected. Check if microphone is muted"
5. WHEN audio quality returns to normal, THE Speaker Application SHALL clear the quality warning display within 2 seconds

### Requirement 5

**User Story:** As a speaker, I want to monitor active listeners and their language preferences, so that I understand my audience composition

#### Acceptance Criteria

1. WHEN the Speaker Application sends getSessionStatus action, THE Speaker Application SHALL receive sessionStatus message with listenerCount and languageDistribution within 2 seconds
2. WHEN sessionStatus is received, THE Speaker Application SHALL display total listener count with minimum 18-point font size
3. WHEN sessionStatus is received, THE Speaker Application SHALL display language distribution as list showing language code and count for each language
4. WHILE session is active, THE Speaker Application SHALL request session status updates every 5 seconds
5. WHEN listener count changes by more than 10%, THE Speaker Application SHALL update the display within 1 second

### Requirement 6

**User Story:** As a speaker, I want to pause or mute my broadcast, so that I can control when audio is transmitted to listeners

#### Acceptance Criteria

1. WHEN the speaker clicks pause button or presses Ctrl+P, THE Speaker Application SHALL stop sending audio chunks and send pauseBroadcast action to server
2. WHEN the speaker clicks mute button or presses Ctrl+M, THE Speaker Application SHALL stop audio capture and send muteBroadcast action to server
3. WHEN pause or mute is activated, THE Speaker Application SHALL update button visual state within 50 milliseconds
4. WHEN the speaker resumes or unmutes, THE Speaker Application SHALL send resumeBroadcast or unmuteBroadcast action and restart audio transmission within 200 milliseconds
5. WHILE paused or muted, THE Speaker Application SHALL display visual indicator showing current state with distinct color coding

### Requirement 7

**User Story:** As a speaker, I want to end my broadcast session, so that I can cleanly disconnect and notify all listeners

#### Acceptance Criteria

1. WHEN the speaker clicks end session button, THE Speaker Application SHALL send endSession action with sessionId and reason "Speaker ended session"
2. WHEN endSession action is sent, THE Speaker Application SHALL stop audio capture and close WebSocket connection within 1 second
3. WHEN session ends, THE Speaker Application SHALL clear session state including sessionId, connectionId, and listener data
4. WHEN session ends, THE Speaker Application SHALL display "Session ended successfully" message and redirect to session creation page within 3 seconds
5. IF session end fails, THEN THE Speaker Application SHALL retry endSession action with exponential backoff (1s, 2s, 4s) up to 3 attempts

### Requirement 8

**User Story:** As a listener, I want to join a broadcast session by entering the session ID and selecting my language, so that I can hear the translated speech

#### Acceptance Criteria

1. WHEN the listener enters session ID and selects target language, THE Listener Application SHALL send joinSession request via WebSocket connection with sessionId and targetLanguage parameters
2. WHEN joinSession succeeds, THE Listener Application SHALL receive sessionJoined message with session metadata within 2 seconds
3. WHEN sessionJoined is received, THE Listener Application SHALL display session information including sourceLanguage, targetLanguage, and listenerCount
4. IF joinSession fails with 404 error, THEN THE Listener Application SHALL display "Session not found. Please check the session ID"
5. IF joinSession fails with 503 error, THEN THE Listener Application SHALL display "Session is full (500 listeners). Please try again later"

### Requirement 9

**User Story:** As a listener, I want to hear the translated audio in real-time, so that I can understand the speaker's message in my language

#### Acceptance Criteria

1. WHEN the Listener Application receives audio message, THE Listener Application SHALL decode base64 audioData to PCM 16-bit samples
2. WHEN audio samples are decoded, THE Listener Application SHALL create Audio Buffer with specified sampleRate and channels, and convert PCM to Float32 format
3. WHEN Audio Buffer is created, THE Listener Application SHALL queue buffer for playback and schedule playback if not currently playing
4. WHILE audio is playing, THE Listener Application SHALL maintain buffer queue of 2-3 chunks to handle network jitter
5. IF audio buffer underruns during playback, THEN THE Listener Application SHALL display "Buffering..." indicator until next chunk arrives

### Requirement 10

**User Story:** As a listener, I want to control my audio playback with pause, mute, and volume, so that I can manage my listening experience

#### Acceptance Criteria

1. WHEN the listener clicks pause button or presses Ctrl+P, THE Listener Application SHALL stop audio playback and buffer incoming audio chunks up to 30 seconds
2. WHEN the listener clicks mute button or presses Ctrl+M, THE Listener Application SHALL set Audio Context output gain to 0 while continuing playback
3. WHEN the listener adjusts volume slider, THE Listener Application SHALL update Audio Context output gain within 100 milliseconds with debounced updates every 50 milliseconds
4. WHEN the listener resumes from pause, THE Listener Application SHALL resume playback from buffered audio within 200 milliseconds
5. WHILE paused with buffer full (30 seconds), THE Listener Application SHALL discard oldest audio chunks and display "Buffer full - audio being skipped" warning

### Requirement 11

**User Story:** As a listener, I want to switch my target language during the session, so that I can hear translations in different languages without reconnecting

#### Acceptance Criteria

1. WHEN the listener selects new target language from dropdown, THE Listener Application SHALL send switchLanguage action with new targetLanguage parameter
2. WHEN switchLanguage action is sent, THE Listener Application SHALL clear current audio buffer and reset playback state
3. WHEN language switch completes, THE Listener Application SHALL receive confirmation and start receiving audio in new language within 1 second
4. WHILE language switch is in progress, THE Listener Application SHALL display "Switching to {languageName}..." indicator
5. IF language switch fails, THEN THE Listener Application SHALL revert to previous language and display "Language switch failed. Please try again"

### Requirement 12

**User Story:** As a listener, I want to see the speaker's broadcast state, so that I know when the speaker has paused or muted their audio

#### Acceptance Criteria

1. WHEN the Listener Application receives speakerPaused message, THE Listener Application SHALL display "Speaker paused" indicator with distinct visual styling
2. WHEN the Listener Application receives speakerMuted message, THE Listener Application SHALL display "Speaker muted" indicator with distinct visual styling
3. WHEN the Listener Application receives speakerResumed message, THE Listener Application SHALL clear "Speaker paused" indicator within 500 milliseconds
4. WHEN the Listener Application receives speakerUnmuted message, THE Listener Application SHALL clear "Speaker muted" indicator within 500 milliseconds
5. WHILE speaker is paused or muted, THE Listener Application SHALL continue displaying last received audio state and buffer status

### Requirement 13

**User Story:** As a speaker or listener, I want the application to maintain my WebSocket connection with automatic heartbeat, so that my session remains active

#### Acceptance Criteria

1. WHILE WebSocket connection is open, THE Speaker Application SHALL send heartbeat message every 30 seconds with current timestamp
2. WHILE WebSocket connection is open, THE Listener Application SHALL send heartbeat message every 30 seconds with current timestamp
3. WHEN heartbeat is sent, THE Speaker Application SHALL expect heartbeatAck response within 5 seconds
4. WHEN heartbeat is sent, THE Listener Application SHALL expect heartbeatAck response within 5 seconds
5. IF heartbeatAck is not received within 5 seconds, THEN THE Speaker Application SHALL attempt reconnection with exponential backoff (1s, 2s, 4s, 8s, maximum 30s)

### Requirement 14

**User Story:** As a speaker or listener, I want my connection to refresh automatically before the 2-hour timeout, so that my session continues without interruption

#### Acceptance Criteria

1. WHEN session duration reaches 100 minutes, THE Speaker Application SHALL receive connectionRefreshRequired message from server
2. WHEN connectionRefreshRequired is received, THE Speaker Application SHALL display "Connection refresh required in 20 minutes" warning
3. WHEN session duration reaches 115 minutes, THE Speaker Application SHALL initiate connection refresh by establishing new WebSocket connection with refreshConnection action
4. WHEN connection refresh completes, THE Speaker Application SHALL receive connectionRefreshComplete message and close old connection within 5 seconds
5. IF connection refresh fails, THEN THE Speaker Application SHALL retry refresh with exponential backoff (1s, 2s, 4s) up to 5 attempts before displaying "Session will expire soon. Please create new session"

### Requirement 15

**User Story:** As a speaker or listener, I want clear error messages with recovery options when connection issues occur, so that I can resolve problems quickly

#### Acceptance Criteria

1. WHEN WebSocket connection fails with network error, THE Speaker Application SHALL display "Connection lost. Reconnecting..." with retry countdown and manual "Retry Now" button
2. WHEN WebSocket connection fails with network error, THE Listener Application SHALL display "Connection lost. Reconnecting..." with retry countdown and manual "Retry Now" button
3. WHEN reconnection attempts exceed 5 failures, THE Speaker Application SHALL display "Unable to connect. Please check your internet connection" with "Start New Session" button
4. WHEN reconnection attempts exceed 5 failures, THE Listener Application SHALL display "Unable to connect. Please check your internet connection" with "Rejoin Session" button
5. IF sessionEnded message is received, THEN THE Listener Application SHALL display "Session ended by speaker" and provide "Join Another Session" button

### Requirement 16

**User Story:** As a speaker or listener, I want my preferences (volume, language, shortcuts) to persist across sessions, so that I don't need to reconfigure each time

#### Acceptance Criteria

1. WHEN the speaker adjusts input volume, THE Speaker Application SHALL store speaker_input_volume value (0-100) in browser localStorage
2. WHEN the listener adjusts playback volume, THE Listener Application SHALL store listener_playback_volume value (0-100) in browser localStorage
3. WHEN the listener selects target language, THE Listener Application SHALL store listener_language_preference as ISO 639-1 code in browser localStorage
4. WHEN the Speaker Application loads, THE Speaker Application SHALL retrieve and apply stored preferences within 500 milliseconds
5. WHEN the Listener Application loads, THE Listener Application SHALL retrieve and apply stored preferences within 500 milliseconds

### Requirement 17

**User Story:** As a speaker or listener, I want to use keyboard shortcuts for common actions, so that I can control the application efficiently without mouse

#### Acceptance Criteria

1. WHEN the speaker presses Ctrl+M or Cmd+M, THE Speaker Application SHALL toggle mute state with visual feedback within 50 milliseconds
2. WHEN the speaker presses Ctrl+P or Cmd+P, THE Speaker Application SHALL toggle pause state with visual feedback within 50 milliseconds
3. WHEN the listener presses Ctrl+Up or Cmd+Up, THE Listener Application SHALL increase volume by 10% up to maximum 100%
4. WHEN the listener presses Ctrl+Down or Cmd+Down, THE Listener Application SHALL decrease volume by 10% down to minimum 0%
5. WHILE any keyboard shortcut is triggered, THE Speaker Application SHALL display temporary tooltip showing action name for 2 seconds

### Requirement 18

**User Story:** As a speaker or listener, I want the application to be accessible with keyboard navigation and screen readers, so that users with disabilities can use the platform

#### Acceptance Criteria

1. WHEN the speaker navigates with Tab key, THE Speaker Application SHALL move focus through all interactive elements in logical order with visible focus indicators
2. WHEN the listener navigates with Tab key, THE Listener Application SHALL move focus through all interactive elements in logical order with visible focus indicators
3. WHEN screen reader is active, THE Speaker Application SHALL announce all button labels, status changes, and error messages using ARIA labels
4. WHEN screen reader is active, THE Listener Application SHALL announce all button labels, status changes, and error messages using ARIA labels
5. THE Speaker Application SHALL maintain color contrast ratio of minimum 4.5:1 for text and 3:1 for UI components per WCAG 2.1 Level AA

### Requirement 19

**User Story:** As a speaker, I want to see visual feedback of my audio input level, so that I can verify my microphone is working and adjust positioning

#### Acceptance Criteria

1. WHILE audio is being captured, THE Speaker Application SHALL display real-time waveform or level meter visualization updating at minimum 30 frames per second
2. WHEN audio input level exceeds 80% of maximum, THE Speaker Application SHALL display visual warning indicator in yellow color
3. WHEN audio input level exceeds 95% of maximum (clipping threshold), THE Speaker Application SHALL display visual warning indicator in red color
4. WHEN audio input level is below 5% for more than 3 seconds, THE Speaker Application SHALL display "Low audio level detected" warning
5. THE Speaker Application SHALL calculate and display average audio level over 1-second rolling window with smoothed visualization

### Requirement 20

**User Story:** As a speaker or listener, I want the application to load quickly and perform smoothly, so that I have a responsive user experience

#### Acceptance Criteria

1. WHEN the Speaker Application loads, THE Speaker Application SHALL achieve Time to Interactive of maximum 3 seconds on 3G network connection
2. WHEN the Listener Application loads, THE Listener Application SHALL achieve Time to Interactive of maximum 3 seconds on 3G network connection
3. WHEN user clicks any button, THE Speaker Application SHALL provide visual feedback within 50 milliseconds
4. WHEN user clicks any button, THE Listener Application SHALL provide visual feedback within 50 milliseconds
5. THE Speaker Application SHALL maintain JavaScript bundle size of maximum 500KB (excluding audio processing libraries) with code splitting and tree shaking enabled
