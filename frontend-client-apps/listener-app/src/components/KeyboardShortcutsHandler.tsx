import React, { useState } from 'react';
import { useKeyboardShortcuts, KeyboardShortcut } from '../../../shared/hooks/useKeyboardShortcuts';
import { useListenerStore } from '../../../shared/store/listenerStore';

export const KeyboardShortcutsHandler: React.FC = () => {
  const { isPaused, isMuted, playbackVolume, setPaused, setMuted, setPlaybackVolume } = useListenerStore();
  const [tooltip, setTooltip] = useState<string | null>(null);

  const showTooltip = (message: string) => {
    setTooltip(message);
    setTimeout(() => setTooltip(null), 2000);
  };

  const shortcuts: KeyboardShortcut[] = [
    {
      key: 'm',
      modifiers: { ctrl: true, meta: true },
      handler: () => {
        setMuted(!isMuted);
        showTooltip(isMuted ? 'Unmuted' : 'Muted');
      },
      description: 'Toggle mute'
    },
    {
      key: 'p',
      modifiers: { ctrl: true, meta: true },
      handler: () => {
        setPaused(!isPaused);
        showTooltip(isPaused ? 'Resumed' : 'Paused');
      },
      description: 'Toggle pause'
    },
    {
      key: 'ArrowUp',
      modifiers: { ctrl: true, meta: true },
      handler: () => {
        const newVolume = Math.min(100, playbackVolume + 10);
        setPlaybackVolume(newVolume);
        showTooltip(`Volume: ${newVolume}%`);
      },
      description: 'Increase volume'
    },
    {
      key: 'ArrowDown',
      modifiers: { ctrl: true, meta: true },
      handler: () => {
        const newVolume = Math.max(0, playbackVolume - 10);
        setPlaybackVolume(newVolume);
        showTooltip(`Volume: ${newVolume}%`);
      },
      description: 'Decrease volume'
    }
  ];

  useKeyboardShortcuts(shortcuts);

  return (
    <>
      {tooltip && (
        <div className="keyboard-shortcut-tooltip">
          {tooltip}
        </div>
      )}
    </>
  );
};
