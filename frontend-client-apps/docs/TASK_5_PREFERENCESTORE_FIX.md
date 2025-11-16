# Task 5: Fix PreferenceStore Usage in ListenerService

## Task Description

Fixed PreferenceStore usage in ListenerService by replacing `PreferenceStore.getInstance()` calls with direct `preferenceStore` singleton usage.

## Task Instructions

From specification requirement 3.2:
- Import `preferenceStore` singleton from '@frontend/shared/services/PreferenceStore'
- Replace `PreferenceStore.getInstance()` calls with direct `preferenceStore` usage (lines 86, 227, 301)
- Verify listener-app TypeScript errors decrease

## Changes Made

### 1. Added Import Statement

Added import for the `preferenceStore` singleton at the top of the file:

```typescript
import { preferenceStore } from '../../../shared/services/PreferenceStore';
```

### 2. Updated loadPreferences() Method (Line 86)

**Before:**
```typescript
private async loadPreferences(): Promise<void> {
  try {
    const { PreferenceStore } = await import('../../../shared/services/PreferenceStore');
    const preferenceStore = PreferenceStore.getInstance();
    
    const userId = `listener-${this.config.sessionId}`;
    // ... rest of method
  }
}
```

**After:**
```typescript
private async loadPreferences(): Promise<void> {
  try {
    const userId = `listener-${this.config.sessionId}`;
    
    const savedVolume = await preferenceStore.getVolume(userId);
    // ... rest of method
  }
}
```

### 3. Updated setVolume() Method (Line 227)

**Before:**
```typescript
async setVolume(volume: number): Promise<void> {
  // ... volume setting logic
  
  try {
    const { PreferenceStore } = await import('../../../shared/services/PreferenceStore');
    const preferenceStore = PreferenceStore.getInstance();
    const userId = `listener-${this.config.sessionId}`;
    await preferenceStore.saveVolume(userId, clampedVolume);
  } catch (error) {
    console.warn('Failed to save volume preference:', error);
  }
}
```

**After:**
```typescript
async setVolume(volume: number): Promise<void> {
  // ... volume setting logic
  
  try {
    const userId = `listener-${this.config.sessionId}`;
    await preferenceStore.saveVolume(userId, clampedVolume);
  } catch (error) {
    console.warn('Failed to save volume preference:', error);
  }
}
```

### 4. Updated switchLanguage() Method (Line 301)

**Before:**
```typescript
async switchLanguage(newLanguage: string): Promise<void> {
  // ... language switching logic
  
  try {
    const { PreferenceStore } = await import('../../../shared/services/PreferenceStore');
    const preferenceStore = PreferenceStore.getInstance();
    const userId = `listener-${this.config.sessionId}`;
    await preferenceStore.saveLanguage(userId, newLanguage);
  } catch (error) {
    console.warn('Failed to save language preference:', error);
  }
}
```

**After:**
```typescript
async switchLanguage(newLanguage: string): Promise<void> {
  // ... language switching logic
  
  try {
    const userId = `listener-${this.config.sessionId}`;
    await preferenceStore.saveLanguage(userId, newLanguage);
  } catch (error) {
    console.warn('Failed to save language preference:', error);
  }
}
```

## Verification

### TypeScript Error Count

**Before:** 62 errors in listener-app
**After:** 56 errors in listener-app
**Reduction:** 6 errors eliminated

The 6 errors eliminated were:
- 3 errors for dynamic imports of PreferenceStore
- 3 errors for calling non-existent `getInstance()` method

### Remaining Errors

The remaining 56 errors are related to other tasks:
- Integration test API mismatches
- JSX style prop errors
- Component prop type mismatches
- Notification type enum mismatches
- Language data type inconsistencies
- Unused variable warnings

## Technical Details

### Why This Fix Works

The PreferenceStore class exports a singleton instance:

```typescript
export class PreferenceStore {
  // ... methods
}

export const preferenceStore = new PreferenceStore();
```

The code was incorrectly trying to:
1. Dynamically import the PreferenceStore class
2. Call a non-existent `getInstance()` static method

The correct pattern is to:
1. Import the `preferenceStore` singleton directly
2. Use it immediately without instantiation

### Benefits

1. **Simpler Code**: Removed unnecessary dynamic imports
2. **Type Safety**: Direct import provides better TypeScript inference
3. **Performance**: No dynamic import overhead
4. **Consistency**: Matches the pattern used in SpeakerService (Task 4)

## Files Modified

- `frontend-client-apps/listener-app/src/services/ListenerService.ts`

## Requirements Satisfied

✅ Requirement 3.2: Service Implementation Type Safety
- "WHEN THE SpeakerService or ListenerService accesses PreferenceStore, THE System SHALL use the correct API pattern (either getInstance() or direct instantiation) as defined in the PreferenceStore implementation"

## Next Steps

Continue with remaining tasks to resolve the other 56 TypeScript errors in listener-app.
