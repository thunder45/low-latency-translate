# Implementation Plan

- [x] 1. Install AWS SDK and setup dependencies
  - Install @aws-sdk/client-cognito-identity-provider package
  - Update package.json with correct version
  - Verify installation with npm list
  - _Requirements: 2.1_

- [x] 2. Create CognitoAuthService
  - Create frontend-client-apps/shared/services/CognitoAuthService.ts
  - Implement login() method with USER_PASSWORD_AUTH flow
  - Implement refreshTokens() method with REFRESH_TOKEN_AUTH flow
  - Implement logout() method
  - Handle NEW_PASSWORD_REQUIRED challenge
  - Handle NotAuthorizedException errors
  - Export AuthTokens interface
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 3. Create LoginForm component
  - Create frontend-client-apps/speaker-app/src/components/LoginForm.tsx
  - Add username input field with label
  - Add password input field with label and type="password"
  - Add login button with loading state
  - Add error message display area
  - Implement Enter key submission for both fields
  - Add ARIA labels for accessibility
  - Style with existing theme
  - _Requirements: 1.1, 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 4. Update AuthGuard component
  - Remove OAuth2 redirect logic from AuthGuard.tsx
  - Add check for stored tokens on component mount
  - Show LoginForm when not authenticated
  - Show children when authenticated
  - Implement auto-refresh timer (5 minutes before expiry)
  - Handle token refresh failures by showing login form
  - _Requirements: 1.4, 1.5, 3.2, 3.3, 3.5_

- [x] 5. Remove OAuth2 components and code
  - Delete frontend-client-apps/speaker-app/src/pages/CallbackPage.tsx
  - Remove /callback route from main.tsx
  - Remove OAuth2-specific methods from existing AuthService.ts
  - Remove OAuth2 configuration from config.ts
  - _Requirements: N/A (cleanup)_

- [x] 6. Update environment configuration
  - Update frontend-client-apps/speaker-app/.env
  - Remove VITE_COGNITO_DOMAIN
  - Remove VITE_COGNITO_REDIRECT_URI
  - Remove VITE_COGNITO_LOGOUT_URI
  - Keep VITE_COGNITO_USER_POOL_ID, VITE_COGNITO_CLIENT_ID, VITE_AWS_REGION
  - Update .env.example with same changes
  - _Requirements: N/A (configuration)_

- [x] 7. Update SpeakerApp integration
  - Update SpeakerApp.tsx to use CognitoAuthService
  - Remove OAuth2 initialization code
  - Ensure LoginForm is shown when not authenticated
  - Test login flow integration
  - _Requirements: 1.1, 1.3, 1.5_

- [x] 8. Write unit tests for CognitoAuthService
  - Create __tests__/CognitoAuthService.test.ts
  - Mock CognitoIdentityProviderClient
  - Test successful login
  - Test invalid credentials (NotAuthorizedException)
  - Test token refresh success
  - Test token refresh failure
  - Test NEW_PASSWORD_REQUIRED handling
  - Test network error handling
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 5.3, 5.4_

- [x] 9. Write unit tests for LoginForm
  - Create __tests__/LoginForm.test.tsx
  - Test form rendering
  - Test username input
  - Test password input
  - Test Enter key submission
  - Test login button click
  - Test loading state
  - Test error display
  - Test accessibility attributes
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 10. Write integration tests
  - Update speaker-flow.test.tsx
  - Test login → session creation flow
  - Test token persistence across page refresh
  - Test auto-refresh before expiry
  - Test logout flow
  - _Requirements: 1.1, 1.3, 1.4, 1.5, 3.2, 3.3, 3.4, 3.5_

- [x] 11. Update documentation
  - Create DIRECT_AUTH_IMPLEMENTATION.md in docs/
  - Document the authentication flow
  - Document configuration requirements
  - Document testing approach
  - Add troubleshooting section
  - _Requirements: N/A (documentation)_

- [x] 12. End-to-end testing
  - Start dev server
  - Test login with valid credentials
  - Verify tokens are stored
  - Refresh page and verify still authenticated
  - Test logout
  - Test login with invalid credentials
  - Test network error handling
  - _Requirements: All requirements_
