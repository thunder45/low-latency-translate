# Implementation Plan: Speaker & Listener Controls

- [x] 1. Set up core data models and types
  - Create TypeScript interfaces for AudioState, ControlState, SessionState, and BufferStatus
  - Define error types and ControlError interface
  - Create Language, SpeakerState, and ListenerState interfaces
  - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.1, 3.2, 4.1, 4.2, 5.1, 6.1, 7.1, 9.1_

- [x] 2. Implement CircularAudioBuffer class
  - Create CircularAudioBuffer class with constructor accepting sampleRate and maxDuration
  - Implement write() method with overflow handling
  - Implement read() method for retrieving buffered audio
  - Implement clear() method to reset buffer state
  - Implement getBufferedDuration() and getBufferStatus() methods
  - _Requirements: 2.3, 2.4_

- [x] 3. Implement PreferenceStore service
  - Create PreferenceStore class with local storage backend
  - Implement saveVolume() and getVolume() methods
  - Implement saveLanguage() and getLanguage() methods
  - Implement saveKeyboardShortcuts() and getKeyboardShortcuts() methods
  - Implement resetPreferences() method
  - _Requirements: 5.4, 6.4, 7.5, 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 4. Implement AudioManager for speakers
  - Create SpeakerAudioManager class implementing AudioManager interface
  - Implement pause() method that halts transmission within 100ms
  - Implement resume() method that restores transmission within 100ms
  - Implement mute() method that suppresses audio within 50ms
  - Implement unmute() method that enables audio within 50ms
  - Implement setVolume() method with 0-100 range validation
  - Implement getState() method returning current AudioState
  - Add state change event emitter with onStateChange() callback
  - _Requirements: 1.1, 1.2, 1.3, 3.1, 3.2, 3.3, 5.1, 5.2, 5.5_

- [x] 5. Implement AudioManager for listeners
  - Create ListenerAudioManager class implementing AudioManager interface
  - Implement pause() method that halts playback and starts buffering
  - Implement resume() method that restores playback from buffer
  - Implement mute() method for local audio suppression
  - Implement unmute() method for local audio restoration
  - Implement setVolume() method with local-only application
  - Integrate CircularAudioBuffer for pause functionality
  - Add buffer status monitoring with onBufferStatus() callback
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.1, 4.2, 4.3, 4.5, 6.1, 6.2, 6.5_

- [x] 6. Implement ControlStateManager service
  - Create ControlStateManager class with session state storage
  - Implement updateSpeakerState() method with validation
  - Implement getSpeakerState() method
  - Implement updateListenerState() method with validation
  - Implement getListenerState() method
  - Implement getSessionState() method returning full session state
  - Implement getListenerStates() method returning all listener states
  - Add subscription methods: subscribeToSpeakerState() and subscribeToListenerState()
  - Implement state synchronization logic with retry mechanism
  - _Requirements: 1.5, 3.4, 8.1, 8.2, 8.4_

- [x] 7. Implement NotificationService
  - Create NotificationService class with WebSocket or pub/sub backend
  - Implement notifySpeakerStateChange() method
  - Implement notifyListenerStateChange() method
  - Implement notifyListenerJoined() and notifyListenerLeft() methods
  - Implement subscribeToSession() method with callback support
  - Add notification queuing and delivery confirmation
  - _Requirements: 1.5, 3.4, 8.2_

- [x] 8. Implement LanguageSelector service
  - Create LanguageSelector class
  - Implement getAvailableLanguages() method
  - Implement switchLanguage() method with stream reconnection logic
  - Implement getCurrentLanguage() method
  - Implement getLanguageStreamUrl() method
  - Implement prepareLanguageSwitch() and completeLanguageSwitch() methods
  - Add language change event emitter with onLanguageChange() callback
  - Ensure language switch completes within 500ms
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 9. Create SpeakerControlsUI component
  - Create React component accepting SpeakerControlsProps
  - Implement pause/resume toggle button with visual state
  - Implement mute/unmute toggle button with visual state
  - Implement volume slider (0-100 range) with debouncing
  - Display listener count with real-time updates
  - Display listener states (paused/muted indicators) when available
  - Wire up event handlers: onPauseToggle, onMuteToggle, onVolumeChange
  - Add visual feedback for all control states
  - _Requirements: 1.4, 3.4, 5.3, 8.1, 8.3, 8.4_

- [x] 10. Create ListenerControlsUI component
  - Create React component accepting ListenerControlsProps
  - Implement pause/resume toggle button with visual state
  - Implement mute/unmute toggle button with visual state
  - Implement volume slider (0-100 range) with debouncing
  - Implement language selector dropdown with available languages
  - Display speaker state (paused/muted indicators)
  - Wire up event handlers: onPauseToggle, onMuteToggle, onVolumeChange, onLanguageChange
  - Add visual feedback for all control states
  - _Requirements: 2.5, 4.4, 6.3, 7.1, 7.4_

- [x] 11. Implement keyboard shortcuts system
  - Create KeyboardShortcutManager class
  - Implement shortcut registration for mute toggle
  - Implement shortcut registration for pause toggle
  - Add shortcut conflict detection with browser/system shortcuts
  - Implement customizable shortcut configuration
  - Add visual indication of available shortcuts in UI
  - Integrate with PreferenceStore for persistence
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 12. Implement error handling and recovery
  - Create error handling utilities for each error type
  - Implement retry with exponential backoff for state sync failures
  - Implement fallback to local state on sync failure
  - Add error display components for user notifications
  - Implement audio manager reinitialization on control failures
  - Add buffer overflow warning display
  - Implement preference save retry logic
  - _Requirements: All requirements (error handling support)_

- [x] 13. Integrate components with state management
  - Connect SpeakerControlsUI to SpeakerAudioManager
  - Connect ListenerControlsUI to ListenerAudioManager
  - Wire ControlStateManager to both audio managers
  - Connect NotificationService to UI components for real-time updates
  - Integrate PreferenceStore with UI components for preference loading
  - Implement optimistic UI updates with rollback on failure
  - _Requirements: 1.1-1.5, 2.1-2.5, 3.1-3.5, 4.1-4.5, 5.1-5.5, 6.1-6.5, 7.1-7.5_

- [x] 14. Implement preference persistence flow
  - Load saved preferences on component mount
  - Apply saved volume settings within 1 second of session join
  - Apply saved language preference within 1 second of session join
  - Save volume changes to PreferenceStore on adjustment
  - Save language changes to PreferenceStore on switch
  - Add reset to defaults functionality in UI
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 15. Add performance optimizations
  - Implement debouncing for volume slider updates (50ms)
  - Add React.memo or similar for UI components
  - Implement throttling for listener state updates (1 per second)
  - Optimize buffer memory usage with efficient audio format
  - Add delta updates for state synchronization
  - Implement batching for multiple state changes within 100ms window
  - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.1, 3.2, 4.1, 4.2, 5.2, 6.2, 8.5_

- [x] 16. Add monitoring and logging
  - Implement control latency tracking
  - Add buffer overflow event logging
  - Track state sync failure rates
  - Monitor language switch success rates
  - Add performance metrics collection
  - Implement error logging with context details
  - _Requirements: All requirements (monitoring support)_

- [x] 17. Create integration tests
  - Write tests for speaker control flow (pause → notify → audio stops)
  - Write tests for listener control flow (pause → buffer → resume)
  - Write tests for multi-user scenarios with different states
  - Write tests for preference persistence across sessions
  - Write tests for language switching with stream reconnection
  - Write tests for error scenarios (network interruption, buffer overflow)
  - _Requirements: All requirements_

- [x] 18. Create end-to-end tests
  - Write E2E test for complete speaker session flow
  - Write E2E test for complete listener session flow
  - Write E2E test for preference save and reload
  - Write E2E test for keyboard shortcuts
  - Write E2E test for real-time listener state updates
  - Validate all timing requirements from requirements document
  - _Requirements: All requirements_
