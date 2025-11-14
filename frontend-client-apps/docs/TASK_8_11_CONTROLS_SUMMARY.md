# Tasks 8 & 11: LanguageSelector and KeyboardShortcutManager

## Task Description
Implemented language switching service and keyboard shortcut management system for speaker-listener controls.

## Task Instructions

### Task 8: Implement LanguageSelector service
- Create LanguageSelector class
- Implement getAvailableLanguages() method
- Implement switchLanguage() method with stream reconnection logic
- Implement getCurrentLanguage() method
- Implement getLanguageStreamUrl() method
- Implement prepareLanguageSwitch() and completeLanguageSwitch() methods
- Add language change event emitter with onLanguageChange() callback
- Ensure language switch completes within 500ms
- Requirements: 7.1, 7.2, 7.3, 7.4

### Task 11: Implement keyboard shortcuts system
- Create KeyboardShortcutManager class
- Implement shortcut registration for mute toggle
- Implement shortcut registration for pause toggle
- Add shortcut conflict detection with browser/system shortcuts
- Implement customizable shortcut configuration
- Add visual indication of available shortcuts in UI
- Integrate with PreferenceStore for persistence
- Requirements: 10.1, 10.2, 10.3, 10.4, 10.5

## Task Tests
No tests written yet - these will be tested through integration tests in later tasks.

## Task Solution

### Files Created

1. **frontend-client-apps/shared/services/LanguageSelector.ts**
   - Manages language switching via stream reconnection
   - Provides list of 12 available languages (en, es, fr, de, it, pt, ja, ko, zh, ar, hi, ru)
   - getAvailableLanguages() returns language list with availability status
   - switchLanguage() coordinates language switch with validation
   - getLanguageStreamUrl() constructs WebSocket URL with language parameter
   - prepareLanguageSwitch() creates switch context with timing info
   - completeLanguageSwitch() coordinates with audio playback (simulated)
   - Event callbacks for language changes and availability updates
   - Target switch time: <500ms with warning if exceeded

2. **frontend-client-apps/shared/services/KeyboardShortcutManager.ts**
   - Manages keyboard shortcuts with conflict detection
   - Default shortcuts: M (mute), P (pause), ↑/↓ (volume)
   - Reserved shortcuts list prevents conflicts with browser shortcuts
   - registerHandler() / unregisterHandler() for action handlers
   - updateShortcut() with conflict and reserved key checking
   - Integrates with PreferenceStore for persistence
   - enable() / disable() for toggling shortcut listening
   - Ignores shortcuts when typing in input fields
   - Ignores shortcuts with modifier keys (Ctrl/Cmd/Alt)
   - getKeyName() provides human-readable key names
   - Singleton pattern for global access

### Key Implementation Decisions

1. **Language Switching**:
   - Stream reconnection approach (not multiplexing)
   - WebSocket URL includes sessionId, language, and role parameters
   - Switch context tracks timing for performance monitoring
   - Rollback to previous language on failure
   - Event-based notification system for UI updates

2. **Keyboard Shortcuts**:
   - Global keyboard event listener on window
   - Prevents conflicts with reserved browser shortcuts (Ctrl+R, Ctrl+T, etc.)
   - Ignores shortcuts when user is typing in input fields
   - Conflict detection prevents duplicate key assignments
   - Persists custom shortcuts via PreferenceStore
   - Singleton pattern ensures single event listener

3. **Error Handling**:
   - Language switch validates availability before attempting
   - Keyboard shortcut updates return boolean for success/failure
   - Console warnings for conflicts and reserved keys
   - Graceful degradation if preference save fails

### Integration Points

These components integrate with:
- ListenerService will use LanguageSelector for language switching
- UI components will use KeyboardShortcutManager for shortcut handling
- PreferenceStore persists both language preferences and custom shortcuts
- Audio playback system coordinates with LanguageSelector for stream switching

## Next Steps

Continue with remaining tasks to implement UI components and integrate all services together.
