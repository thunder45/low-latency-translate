import React, { useState, useEffect } from 'react';
import { useKeyboardShortcuts, KeyboardShortcut } from '../../../shared/hooks/useKeyboardShortcuts';
import { useSpeakerStore } from '../store/speakerStore';

export const KeyboardShortcutsHandler: React.FC = () => {
  const { isPaused, isMuted, setPaused, setMuted } = useSpeakerStore();
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
