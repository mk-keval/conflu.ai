import { useState, useEffect, type RefObject } from 'react';

interface ResizeObserverResult {
  width: number;
  height: number;
}

export function useResizeObserver(ref: RefObject<HTMLElement | null>): ResizeObserverResult {
  const [size, setSize] = useState<ResizeObserverResult>({ width: 0, height: 0 });

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        setSize({ width: Math.round(width), height: Math.round(height) });
      }
    });

    observer.observe(element);
    return () => observer.disconnect();
  }, [ref]);

  return size;
}
