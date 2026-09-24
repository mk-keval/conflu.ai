import { useEffect, useCallback } from 'react';

type KeyMap = Record<string, () => void>;

export function useKeyboard(keymap: KeyMap): void {
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      const key = event.key;

      if (key in keymap) {
        const isEditable =
          event.target instanceof HTMLInputElement ||
          event.target instanceof HTMLTextAreaElement ||
          (event.target instanceof HTMLElement &&
            event.target.isContentEditable);

        // Allow Escape globally, allow other keys only when not editing
        if (key === 'Escape' || !isEditable) {
          event.preventDefault();
          keymap[key]();
        }
      }
    },
    [keymap]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}
