# Implementation Plan

- [x] 1. Create TokenStorage service for secure token management
  - Create `frontend-client-apps/shared/services/TokenStorage.ts`
  - Implement token encryption/decryption using existing storage utility
  - Implement token storage, retrieval, and clearing methods
  - Add token expiration validation
  - _Requirements: 2.1, 2.2, 2.5, 5.1, 5.2, 5.3, 5.4_

- [x] 1.1 Write unit tests for TokenStorage
  - Test token encryption and decryption
  - Test storage and retrieval
  - Test token clearing
  - Test handling of corrupted data
  - Test expiration validation
  - _Requirements: 2.1, 2.2, 2.5_

- [x] 2. Create AuthService for Cognito integration
  - Create `frontend-client-apps/shared/services/AuthService.ts`
  - Implement singleton pattern for service instance
  - Implement Cognito client initialization
  - Implement authentication status check
  - Implement token retrieval with auto-refresh
  - Implement login redirect to Cognito Hosted UI
  - Implement OAuth callback handling
  - Implement logout functionality
  - Implement token refresh logic
  - Implement user info retrieval
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.3, 2.4, 3.3, 5.5_

- [ ] 2.1 Write unit tests for AuthService
  - Test authentication status check
  - Test token retrieval and refresh
  - Test login redirect
  - Test callback handling
  - Test logout
  - Test error handling for each scenario
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.1, 4.2, 4.3, 4.4_

- [x] 3. Create AuthError class and error handling utilities
  - Create `frontend-client-apps/shared/utils/AuthError.ts`
  - Define AuthError class with error codes
  - Define user-friendly error messages
  - Implement error code mapping
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [-] 4. Create AuthGuard component for route protection
  - Create `frontend-client-apps/speaker-app/src/components/AuthGuard.tsx`
  - Implement authentication check on mount
  - Show loading state while checking
  - Redirect to login if not authenticated
  - Render children if authenticated
  - _Requirements: 1.1, 1.2, 3.2_

- [ ] 4.1 Write unit tests for AuthGuard
  - Test renders children when authenticated
  - Test redirects when not authenticated
  - Test shows loading state during check
  - Test handles authentication errors
  - _Requirements: 1.1, 1.2, 3.2_

- [x] 5. Create OAuth callback handler page
  - Create `frontend-client-apps/speaker-app/src/pages/CallbackPage.tsx`
  - Handle OAuth callback from Cognito
  - Extract authorization code from URL
  - Exchange code for tokens using AuthService
  - Redirect to main app on success
  - Show error message on failure
  - _Requirements: 1.2, 1.3, 4.1, 4.2_

- [-] 6. Update SpeakerApp to use AuthService
  - Modify `frontend-client-apps/speaker-app/src/components/SpeakerApp.tsx`
  - Initialize AuthService on component mount
  - Check authentication before session creation
  - Get JWT token from AuthService instead of placeholder
  - Handle authentication errors
  - Show authentication status in UI
  - _Requirements: 1.1, 3.1, 3.2, 3.3, 4.1, 4.2_

- [ ] 6.1 Write integration tests for authenticated session creation
  - Test session creation with valid token
  - Test session creation fails without authentication
  - Test token refresh during session creation
  - Test authentication error handling
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 7. Update configuration and environment setup
  - Update `frontend-client-apps/speaker-app/.env.example`
  - Add Cognito redirect URI configuration
  - Add Cognito logout URI configuration
  - Update configuration validation in `config.ts`
  - Update CONFIGURATION_GUIDE.md with auth setup
  - _Requirements: 1.2, 1.3_

- [x] 8. Add logout functionality to speaker UI
  - Add logout button to SpeakerApp header
  - Implement logout handler using AuthService
  - Clear session state on logout
  - Redirect to login after logout
  - _Requirements: 2.4, 5.4_

- [x] 9. Update Vite configuration for OAuth callback route
  - Update `frontend-client-apps/speaker-app/vite.config.ts`
  - Configure routing for `/callback` path
  - Ensure callback page is included in build
  - _Requirements: 1.2_

- [-] 10. Add authentication monitoring and logging
  - Add authentication success/failure metrics
  - Add token refresh metrics
  - Add login/logout event logging
  - Ensure no tokens are logged
  - _Requirements: 4.1, 4.2, 5.5_

- [ ] 10.1 Write integration tests for complete authentication flow
  - Test complete login flow (mocked Cognito)
  - Test token persistence across page refresh
  - Test automatic token refresh
  - Test logout flow
  - Test error scenarios (network errors, invalid tokens)
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 11. Update documentation
  - Update speaker app README with authentication setup
  - Add authentication troubleshooting guide
  - Document Cognito configuration requirements
  - Add authentication flow diagrams
  - _Requirements: All_
