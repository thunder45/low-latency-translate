# Requirements Document

## Introduction

This specification addresses the resolution of 106 pre-existing TypeScript compilation errors in the frontend-client-apps workspace. These errors prevent the speaker-app (44 errors) and listener-app (62 errors) from building successfully. The errors fall into several categories: integration test API mismatches, component prop type mismatches, service implementation errors, JSX style prop errors, and unused variable warnings.

## Glossary

- **Speaker-App**: The React application used by authenticated speakers to broadcast audio
- **Listener-App**: The React application used by anonymous listeners to receive translated audio
- **Shared Library**: The shared workspace containing common components, services, and utilities used by both apps
- **TypeScript Compiler**: The tsc tool that validates TypeScript code and generates JavaScript output
- **Integration Tests**: Test files that verify end-to-end workflows across multiple components
- **Component Props**: TypeScript interfaces defining the properties that React components accept
- **Service Layer**: Business logic classes that manage WebSocket connections, audio processing, and state management
- **ErrorHandler**: Shared utility for handling and logging application errors
- **PreferenceStore**: Shared utility for persisting user preferences

## Requirements

### Requirement 1: Integration Test API Alignment

**User Story:** As a developer, I want integration tests to use the correct service APIs, so that the test suite accurately validates application behavior and TypeScript compilation succeeds.

#### Acceptance Criteria

1. WHEN THE Speaker-App integration tests reference SpeakerService methods, THE System SHALL use only methods that exist in the current SpeakerService implementation
2. WHEN THE Listener-App integration tests reference ListenerService methods, THE System SHALL use only methods that exist in the current ListenerService implementation
3. WHEN THE integration tests access state properties, THE System SHALL use property names that exist in the current state interfaces (e.g., 'sessionId' not 'session')
4. WHEN THE integration tests configure service instances, THE System SHALL provide configuration objects that match the current service constructor signatures
5. WHEN THE integration tests import testing utilities, THE System SHALL only import utilities that are actually used in the test code

### Requirement 2: Component Prop Type Correctness

**User Story:** As a developer, I want React components to have accurate TypeScript prop interfaces, so that component usage is type-safe and compilation succeeds.

#### Acceptance Criteria

1. WHEN THE AccessibleButton component is used with aria attributes, THE System SHALL accept 'ariaPressed' as a valid prop in the AccessibleButtonProps interface
2. WHEN THE SessionDisplay component is rendered, THE System SHALL require 'listenerCount' and 'languageDistribution' props as defined in SessionDisplayProps
3. WHEN THE AudioVisualizer component is rendered, THE System SHALL accept 'inputLevel' as a number prop rather than 'getInputLevel' as a function
4. WHEN THE SessionJoiner component is used, THE System SHALL accept 'onSessionJoined' callback prop in SessionJoinerProps interface
5. WHEN THE SpeakerStatus component is rendered, THE System SHALL accept 'isPaused' and 'isMuted' boolean props in SpeakerStatusProps interface
6. WHEN THE BufferIndicator component is rendered, THE System SHALL require 'bufferOverflow' prop as defined in BufferIndicatorProps interface

### Requirement 3: Service Implementation Type Safety

**User Story:** As a developer, I want service layer code to use correct TypeScript types for error handling and state management, so that runtime behavior matches compile-time expectations.

#### Acceptance Criteria

1. WHEN THE SpeakerService or ListenerService calls ErrorHandler.handleError(), THE System SHALL pass ErrorType enum values that are compatible with the handleError() method signature
2. WHEN THE SpeakerService or ListenerService accesses PreferenceStore, THE System SHALL use the correct API pattern (either getInstance() or direct instantiation) as defined in the PreferenceStore implementation
3. WHEN THE AuthService handles null values, THE System SHALL include null checks or non-null assertions to satisfy TypeScript's strict null checking
4. WHEN THE services reference ErrorType enum values, THE System SHALL use only enum values that exist in the current ErrorType definition (e.g., use correct error type names)
5. WHEN THE ListenerService calls methods with string parameters, THE System SHALL ensure null values are handled before passing to methods that require non-null strings

### Requirement 4: JSX Style Prop Compliance

**User Story:** As a developer, I want JSX style elements to use valid React props, so that components render correctly and TypeScript compilation succeeds.

#### Acceptance Criteria

1. WHEN THE components use inline `<style>` JSX elements, THE System SHALL NOT include 'jsx' as a prop on style elements
2. WHEN THE components need scoped styles, THE System SHALL use valid React style element patterns without custom props
3. WHEN THE BufferIndicator component renders styles, THE System SHALL use only props defined in StyleHTMLAttributes interface
4. WHEN THE LanguageSelector component renders styles, THE System SHALL use only props defined in StyleHTMLAttributes interface
5. WHEN THE PlaybackControls component renders styles, THE System SHALL use only props defined in StyleHTMLAttributes interface

### Requirement 5: Notification Type Enum Alignment

**User Story:** As a developer, I want notification type comparisons to use correct enum values, so that broadcast state changes are handled properly and TypeScript compilation succeeds.

#### Acceptance Criteria

1. WHEN THE BroadcastControlsContainer checks notification types, THE System SHALL compare against 'listenerJoined' and 'listenerLeft' enum values that exist in NotificationType
2. WHEN THE PlaybackControlsContainer checks notification types, THE System SHALL compare against 'broadcastPaused', 'broadcastResumed', 'broadcastMuted', and 'broadcastUnmuted' enum values that exist in NotificationType
3. WHEN THE components handle speaker state notifications, THE System SHALL NOT compare against deprecated notification type values like 'speakerPaused' or 'speakerResumed'
4. WHEN THE notification type enums are used, THE System SHALL ensure all compared values are defined in the NotificationType enum to prevent type overlap errors

### Requirement 6: Unused Variable Elimination

**User Story:** As a developer, I want the codebase to be free of unused variable declarations, so that code quality is maintained and TypeScript compilation succeeds without warnings.

#### Acceptance Criteria

1. WHEN THE integration test files import React Testing Library utilities, THE System SHALL only import utilities that are used in the test code
2. WHEN THE service files declare variables, THE System SHALL only declare variables that are subsequently used in the code
3. WHEN THE hook files import React hooks, THE System SHALL only import hooks that are used in the hook implementation
4. WHEN THE component files declare variables, THE System SHALL only declare variables that are used in the component logic
5. WHEN THE TypeScript compiler runs, THE System SHALL produce zero TS6133 errors (unused variable warnings)

### Requirement 7: Language Data Type Consistency

**User Story:** As a developer, I want language data to use consistent TypeScript types throughout the application, so that language selection and display work correctly.

#### Acceptance Criteria

1. WHEN THE ListenerApp component passes language data to LanguageSelector, THE System SHALL use string type for language codes (e.g., 'en', 'es', 'fr')
2. WHEN THE language selector receives available languages, THE System SHALL accept language data in the format expected by the LanguageSelector component
3. WHEN THE components handle language objects, THE System SHALL ensure type compatibility between language object shapes and expected string types

### Requirement 8: Quality Warning Type Completeness

**User Story:** As a developer, I want quality warning objects to include all required properties, so that audio quality issues are properly displayed to users.

#### Acceptance Criteria

1. WHEN THE speaker integration tests reference QualityWarning objects, THE System SHALL include the 'issue' property as defined in the QualityWarning interface
2. WHEN THE quality warnings are created, THE System SHALL include all required properties defined in the QualityWarning type

### Requirement 9: Build Success Verification

**User Story:** As a developer, I want both speaker-app and listener-app to build successfully with zero TypeScript errors, so that the applications can be deployed to production.

#### Acceptance Criteria

1. WHEN THE command 'npm run build:speaker' is executed, THE System SHALL complete TypeScript compilation with zero errors
2. WHEN THE command 'npm run build:listener' is executed, THE System SHALL complete TypeScript compilation with zero errors
3. WHEN THE command 'npm run build:all' is executed, THE System SHALL successfully build shared library, speaker-app, and listener-app with zero TypeScript errors
4. WHEN THE builds complete successfully, THE System SHALL generate dist/ directories with compiled JavaScript output for all three workspaces
5. WHEN THE TypeScript compiler runs in strict mode, THE System SHALL satisfy all type checking requirements including null safety, type compatibility, and enum value validation
