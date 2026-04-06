import { useCallback, useRef, useState } from 'react';

interface UseLongPressOptions {
  isPreventDefault?: boolean;
  delay?: number;
}

export function useLongPress(
  onLongPress: () => void,
  { isPreventDefault = true, delay = 500 }: UseLongPressOptions = {}
) {
  const [isHolding, setIsHolding] = useState(false);
  const [holdProgress, setHoldProgress] = useState(0);
  const timeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const interval = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  const start = useCallback(
    (event: React.MouseEvent | React.TouchEvent) => {
      if (isPreventDefault && event.target) {
        event.preventDefault();
      }
      setIsHolding(true);
      setHoldProgress(0);

      // Start with a timeout to begin the progress
      timeout.current = setTimeout(() => {
        // Start the interval for progress updates
        interval.current = setInterval(() => {
          setHoldProgress((prev) => {
            const newProgress = Math.min(1, prev + 16 / delay);
            if (newProgress >= 1) {
              // Complete the hold
              if (interval.current) {
                clearInterval(interval.current);
                interval.current = undefined;
              }
              setIsHolding(false);
              setHoldProgress(1);
              onLongPress();
              // Vibrate if available
              if (typeof navigator !== 'undefined' && navigator.vibrate) {
                navigator.vibrate(10);
              }
            }
            return newProgress;
          });
        }, 16); // ~60fps
      }, delay);
    },
    [onLongPress, delay, isPreventDefault]
  );

  const cancel = useCallback(() => {
    setIsHolding(false);
    setHoldProgress(0);
    if (timeout.current) {
      clearTimeout(timeout.current);
      timeout.current = undefined;
    }
    if (interval.current) {
      clearInterval(interval.current);
      interval.current = undefined;
    }
  }, []);

  const onPointerDown = useCallback(
    (event: React.PointerEvent) => {
      start(event);
    },
    [start]
  );

  const onPointerUp = useCallback(() => {
    cancel();
  }, [cancel]);

  const onPointerLeave = useCallback(() => {
    cancel();
  }, [cancel]);

  return {
    onPointerDown,
    onPointerUp,
    onPointerLeave,
    isHolding,
    holdProgress,
  };
}
