# Implementation Plan

- [x] 1. Create SessionCreationOrchestrator utility
  - Create `frontend-client-apps/shared/utils/SessionCreationOrchestrator.ts`
  - Implement WebSocket connection logic with retry
  - Implement session creation request sending
  - Implement response waiting with timeout
  - Add cleanup logic for failed attempts
  - _Requirements: 1.1, 1.2, 3.1, 3.2_

- [x] 2. Update SessionCreator component interface
  - Remove `onSendMessage` prop from SessionCreator
  - Add `onCreateSession` callback prop
  - Add `isCreating` and `error` props for state display
  - Update component to call `onCreateSession` with config
  - Remove WebSocket message sending logic
  - _Requirements: 1.1, 2.1_

- [x] 3. Refactor SpeakerService to accept WebSocket client
  - Modify SpeakerService constructor to accept WebSocket client parameter
  - Remove WebSocket client creation from constructor
  - Update `initialize()` method to use provided client
  - Ensure all WebSocket operations use the provided client
  - _Requirements: 1.4_

- [x] 4. Implement session creation flow in SpeakerApp
  - Add state for creation progress (`isCreatingSession`, `creationError`, `creationStep`)
  - Implement `handleCreateSession` method using SessionCreationOrchestrator
  - Update SessionCreator props to pass new callbacks and state
  - Handle successful creation by initializing SpeakerService
  - Handle errors by displaying messages and allowing retry
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4_

- [x] 5. Add error handling and retry logic
  - Implement exponential backoff retry for connection failures
  - Add timeout handling for session creation (5 seconds)
  - Implement cleanup on navigation away
  - Prevent multiple simultaneous creation attempts
  - Display user-friendly error messages
  - _Requirements: 1.5, 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 6. Update UI feedback during creation
  - Show "Creating Session..." text when button is clicked
  - Display connection status during WebSocket connection
  - Show progress through creation steps
  - Display specific error messages on failure
  - Add retry button on error
  - _Requirements: 2.1, 2.2, 2.3, 2.5_

- [x] 7. Add comprehensive error messages
  - Create error message constants for all failure scenarios
  - Map error types to user-friendly messages
  - Include actionable guidance in error messages
  - Log detailed errors for debugging
  - _Requirements: 1.5, 2.3_

- [x] 8. Write unit tests for SessionCreationOrchestrator
  - Test successful WebSocket connection
  - Test connection retry logic
  - Test session creation request sending
  - Test response timeout handling
  - Test cleanup on failure
  - _Requirements: 1.1, 1.2, 3.1, 3.2_

- [x] 9. Write unit tests for updated components
  - Test SessionCreator with new props
  - Test SpeakerApp session creation flow
  - Test error state handling
  - Test retry functionality
  - _Requirements: 1.1, 2.1, 2.2, 2.3_

- [x] 10. Write integration tests
  - Test complete session creation flow
  - Test connection failure with retry
  - Test creation timeout scenario
  - Test multiple rapid clicks prevention
  - Test cleanup on navigation
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 3.3, 3.4_

- [x] 11. Update documentation
  - Document new session creation flow
  - Add troubleshooting guide for common errors
  - Update component documentation
  - Add sequence diagrams for creation flow
  - _Requirements: All_

- [x] 12. Manual testing and verification
  - Test session creation with valid configuration
  - Test with network disconnected
  - Test with slow network
  - Test rapid button clicks
  - Test navigation during creation
  - Verify error messages are clear
  - _Requirements: All_
