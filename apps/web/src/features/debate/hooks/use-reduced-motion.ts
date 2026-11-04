import { useSyncExternalStore } from "react";

const preference = "(prefers-reduced-motion: reduce)";

function subscribe(callback: () => void) {
  const media = window.matchMedia?.(preference);
  media?.addEventListener("change", callback);
  return () => media?.removeEventListener("change", callback);
}

export function useReducedMotion() {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia?.(preference).matches ?? false,
    () => false,
  );
}
