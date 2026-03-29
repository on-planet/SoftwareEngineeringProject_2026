import React, { useEffect, useRef, useState } from "react";

type AnimatedNumberProps = {
  value?: number | null;
  className?: string;
  durationMs?: number;
  formatter?: (value: number, target: number) => string;
};

function easeOutCubic(progress: number) {
  return 1 - (1 - progress) ** 3;
}

function usePrefersReducedMotion() {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(mediaQuery.matches);
    update();
    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", update);
      return () => mediaQuery.removeEventListener("change", update);
    }
    mediaQuery.addListener(update);
    return () => mediaQuery.removeListener(update);
  }, []);

  return reducedMotion;
}

export function AnimatedNumber({
  value,
  className,
  durationMs = 680,
  formatter = (current) => Math.round(current).toString(),
}: AnimatedNumberProps) {
  const reducedMotion = usePrefersReducedMotion();
  const targetValue = Number(value);
  const isNumeric = Number.isFinite(targetValue);
  const [displayValue, setDisplayValue] = useState(isNumeric ? targetValue : 0);
  const previousValueRef = useRef(isNumeric ? targetValue : 0);

  useEffect(() => {
    if (!isNumeric) {
      previousValueRef.current = 0;
      setDisplayValue(0);
      return;
    }

    const nextValue = targetValue;
    const startValue = previousValueRef.current;
    previousValueRef.current = nextValue;

    if (reducedMotion || Math.abs(nextValue - startValue) < 0.001) {
      setDisplayValue(nextValue);
      return;
    }

    let frameId = 0;
    const startedAt = performance.now();

    const tick = (now: number) => {
      const progress = Math.min(1, (now - startedAt) / durationMs);
      const eased = easeOutCubic(progress);
      setDisplayValue(startValue + (nextValue - startValue) * eased);
      if (progress < 1) {
        frameId = window.requestAnimationFrame(tick);
      }
    };

    frameId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frameId);
  }, [durationMs, isNumeric, reducedMotion, targetValue]);

  return <span className={className}>{isNumeric ? formatter(displayValue, targetValue) : "--"}</span>;
}
