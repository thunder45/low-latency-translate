import { useEffect, useRef } from 'react';

/**
 * Hook to manage focus for keyboard navigation
 */
export function useFocusManagement(autoFocus: boolean = false) {
  const elementRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (autoFocus && elementRef.current) {
      elementRef.current.focus();
    }
  }, [autoFocus]);

  return elementRef;
}

/**
 * Hook to ensure visible focus indicators
 */
export function useFocusVisible() {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Tab') {
        document.body.classList.add('keyboard-navigation');
      }
    };

    const handleMouseDown = () => {
      document.body.classList.remove('keyboard-navigation');
    };

    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousedown', handleMouseDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleMouseDown);
    };
  }, []);
}

/**
 * Hook to manage tab order for a group of elements
 */
export function useTabOrder(elements: HTMLElement[], enabled: boolean = true) {
  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;

      const currentIndex = elements.findIndex(el => el === document.activeElement);
      if (currentIndex === -1) return;

      e.preventDefault();

      let nextIndex: number;
      if (e.shiftKey) {
        nextIndex = currentIndex === 0 ? elements.length - 1 : currentIndex - 1;
      } else {
        nextIndex = currentIndex === elements.length - 1 ? 0 : currentIndex + 1;
      }

      elements[nextIndex]?.focus();
    };

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [elements, enabled]);
}
