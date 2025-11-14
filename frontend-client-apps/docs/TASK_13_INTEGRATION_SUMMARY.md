# Task 13: Integration of Components with State Management

## Task Description

Integrate the SpeakerControls and ListenerControls UI components with the existing SpeakerService and ListenerService, connecting them to state management and ensuring proper event handling.

## Current Status

### Analysis

After reviewing the codebase, I found that:

1. **SpeakerService** already has all control methods implemented:
   - `pause()`, `resume()`, `togglePause()`
   - `mute()`, `unmute()`, `toggleMute()`
   - `setVolume()`
   - Preference loading and saving
   - Latency logging

2. **ListenerService** already has all control methods implemented:
   - Similar control methods as SpeakerService
   - CircularAudioBuffer integration for pause buffering
   - Language switching via LanguageSelector
   - Preference persistence

3. **Existing Components**:
   - `BroadcastControls.tsx` - Already implements speaker controls with similar functionality to `SpeakerControls.tsx`
   - `PlaybackControls.tsx` - Already implements listener controls
   - Both have keyboard shortcuts, debouncing, and accessibility features

### Issue Identified

There appears to be **duplication** between:
- `shared/components/SpeakerControls.tsx` (newly created) vs `speaker-app/src/components/BroadcastControls.tsx` (existing)
- `shared/components/ListenerControls.tsx` (newly created) vs `listener-app/src/components/PlaybackControls.tsx` (existing)

## Resolution Options

### Option 1: Use Existing Components (Recommended)

The existing `BroadcastControls` and `PlaybackControls` components already provide the required functionality and are integrated with the services. We should:

1. Verify they meet all requirements from the spec
2. Add any missing features (e.g., listener count display, buffer status)
3. Ensure keyboard shortcuts are properly integrated
4. Keep the newly created `SpeakerControls` and `ListenerControls` as reference implementations or remove them

### Option 2: Replace with New Components

Replace the existing components with the newly created ones:

1. Update apps to use `SpeakerControls` and `ListenerControls`
2. Remove `BroadcastControls` and `PlaybackControls`
3. Create App.tsx files for both apps to wire everything together

## Recommendation

**Use Option 1** - The existing components are already integrated and working. We should:

1. Audit existing components against requirements
2. Add any missing features
3. Ensure proper integration with KeyboardShortcutManager
4. Document the integration pattern

## Next Steps

1. Review `BroadcastControls.tsx` and `PlaybackControls.tsx` against requirements
2. Add missing features if any
3. Ensure KeyboardShortcutManager is properly integrated
4. Update documentation to reflect the actual implementation
5. Mark Task 13 as complete once verification is done

## Notes

- The services (SpeakerService, ListenerService) are fully implemented with all required control methods
- Preference persistence is working
- Latency logging is implemented
- The main question is whether to use existing UI components or replace them with the newly created ones
