/**
 * Keyboard Shortcut Manager
 * 
 * Manages keyboard shortcuts for audio controls with conflict detection
 * and customization support.
 */

import type { KeyboardShortcuts } from '../types/controls';
import { preferenceStore } from './PreferenceStore';

/**
 * Shortcut action type
 */
export type ShortcutAction = 'mute' | 'pause' | 'volumeUp' | 'volumeDown';

/**
 * Shortcut handler callback
 */
type ShortcutHandler = () => void;

/**
 * Reserved browser/system shortcuts that should not be overridden
 */
const RESERVED_SHORTCUTS = new Set([
  'KeyR', // Refresh
  'KeyT', // New tab
  'KeyW', // Close tab
  'KeyN', // New window
  'KeyQ', // Quit
  'KeyF', // Find
  'KeyS', // Save
  'KeyP', // Print (when Ctrl/Cmd is pressed)
  'F5', // Refresh
  'F11', // Fullscreen
  'F12', // DevTools
]);

/**
 * Keyboard Shortcut Manager
 */
export class KeyboardShortcutManager {
  private static instance: KeyboardShortcutManager;
  private shortcuts: KeyboardShortcuts;
  private handlers: Map<ShortcutAction, ShortcutHandler> = new Map();
  private isEnabled: boolean = true;
  private userId: string | null = null;
  
  constructor() {
    // Initialize with default shortcuts
    this.shortcuts = preferenceStore.getDefaultShortcuts();
    
    // Bind keyboard event listener
    this.handleKeyDown = this.handleKeyDown.bind(this);
  }

  /**
   * Get singleton instance
   */
  static getInstance(): KeyboardShortcutManager {
    if (!KeyboardShortcutManager.instance) {
      KeyboardShortcutManager.instance = new KeyboardShortcutManager();
    }
    return KeyboardShortcutManager.instance;
  }
  
  /**
   * Initialize keyboard shortcuts for a user
   * 
   * @param userId - User identifier
   */
  async initialize(userId: string): Promise<void> {
    this.userId = userId;
    
    // Load saved shortcuts
    const savedShortcuts = await preferenceStore.getKeyboardShortcuts(userId);
    if (savedShortcuts) {
      this.shortcuts = savedShortcuts;
    }
    
    // Start listening for keyboard events
    this.enable();
  }
  
  /**
   * Register a handler for a shortcut action
   * 
   * @param action - Shortcut action
   * @param handler - Handler function
   */
  registerHandler(action: ShortcutAction, handler: ShortcutHandler): void {
    this.handlers.set(action, handler);
  }
  
  /**
   * Unregister a handler for a shortcut action
   * 
   * @param action - Shortcut action
   */
  unregisterHandler(action: ShortcutAction): void {
    this.handlers.delete(action);
  }
  
  /**
   * Update a keyboard shortcut
   * 
   * @param action - Shortcut action
   * @param keyCode - New key code
   * @returns true if successful, false if conflict detected
   */
  async updateShortcut(action: ShortcutAction, keyCode: string): Promise<boolean> {
    // Check for reserved shortcuts
    if (this.isReservedShortcut(keyCode)) {
      console.warn(`Cannot use reserved shortcut: ${keyCode}`);
      return false;
    }
    
    // Check for conflicts with other shortcuts
    const conflictingAction = this.findConflict(keyCode, action);
    if (conflictingAction) {
      console.warn(`Shortcut ${keyCode} conflicts with ${conflictingAction}`);
      return false;
    }
    
    // Update shortcut
    this.shortcuts[action] = keyCode;
    
    // Save to preferences
    if (this.userId) {
      try {
        await preferenceStore.saveKeyboardShortcuts(this.userId, this.shortcuts);
      } catch (error) {
        console.error('Failed to save keyboard shortcuts:', error);
        // Continue anyway - shortcuts will work for this session
      }
    }
    
    return true;
  }
  
  /**
   * Get current shortcuts
   * 
   * @returns Current keyboard shortcuts
   */
  getShortcuts(): KeyboardShortcuts {
    return { ...this.shortcuts };
  }
  
  /**
   * Reset shortcuts to defaults
   */
  async resetToDefaults(): Promise<void> {
    this.shortcuts = preferenceStore.getDefaultShortcuts();
    
    if (this.userId) {
      try {
        await preferenceStore.saveKeyboardShortcuts(this.userId, this.shortcuts);
      } catch (error) {
        console.error('Failed to save default shortcuts:', error);
      }
    }
  }
  
  /**
   * Enable keyboard shortcuts
   */
  enable(): void {
    if (!this.isEnabled) {
      window.addEventListener('keydown', this.handleKeyDown);
      this.isEnabled = true;
    }
  }
  
  /**
   * Disable keyboard shortcuts
   */
  disable(): void {
    if (this.isEnabled) {
      window.removeEventListener('keydown', this.handleKeyDown);
      this.isEnabled = false;
    }
  }
  
  /**
   * Clean up resources
   */
  destroy(): void {
    this.disable();
    this.handlers.clear();
  }
  
  /**
   * Handle keyboard events
   * 
   * @param event - Keyboard event
   */
  private handleKeyDown(event: KeyboardEvent): void {
    // Ignore if modifier keys are pressed (except for volume shortcuts)
    if (event.ctrlKey || event.metaKey || event.altKey) {
      return;
    }
    
    // Ignore if user is typing in an input field
    const target = event.target as HTMLElement;
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
      return;
    }
    
    // Check if this key matches any shortcut
    const action = this.getActionForKey(event.code);
    if (action) {
      const handler = this.handlers.get(action);
      if (handler) {
        event.preventDefault();
        handler();
      }
    }
  }
  
  /**
   * Get action for a key code
   * 
   * @param keyCode - Key code
   * @returns Shortcut action or null
   */
  private getActionForKey(keyCode: string): ShortcutAction | null {
    for (const [action, code] of Object.entries(this.shortcuts)) {
      if (code === keyCode) {
        return action as ShortcutAction;
      }
    }
    return null;
  }
  
  /**
   * Check if a key code is reserved
   * 
   * @param keyCode - Key code to check
   * @returns true if reserved
   */
  private isReservedShortcut(keyCode: string): boolean {
    return RESERVED_SHORTCUTS.has(keyCode);
  }
  
  /**
   * Find conflicting action for a key code
   * 
   * @param keyCode - Key code to check
   * @param excludeAction - Action to exclude from check
   * @returns Conflicting action or null
   */
  private findConflict(keyCode: string, excludeAction: ShortcutAction): ShortcutAction | null {
    for (const [action, code] of Object.entries(this.shortcuts)) {
      if (action !== excludeAction && code === keyCode) {
        return action as ShortcutAction;
      }
    }
    return null;
  }
  
  /**
   * Get human-readable key name
   * 
   * @param keyCode - Key code
   * @returns Human-readable name
   */
  static getKeyName(keyCode: string): string {
    // Convert key codes to readable names
    const keyNames: Record<string, string> = {
      'KeyM': 'M',
      'KeyP': 'P',
      'ArrowUp': '↑',
      'ArrowDown': '↓',
      'ArrowLeft': '←',
      'ArrowRight': '→',
      'Space': 'Space',
    };
    
    return keyNames[keyCode] || keyCode.replace('Key', '');
  }
}

/**
 * Singleton instance
 */
export const keyboardShortcutManager = new KeyboardShortcutManager();
