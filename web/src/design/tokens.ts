// SPEC-208 R3: espelho em JS dos tokens de tokens.css. Fonte da verdade: o CSS;
// estes literais são o fallback (SSR/teste) e a paridade é verificada em tests/design.test.mjs.

export const DURATION_MS = { instant: 80, fast: 140, base: 240, slow: 420 } as const;
export type DurationToken = keyof typeof DURATION_MS;

export const EASING = {
  "ease-out": [0.16, 1, 0.3, 1],
  "ease-in-out": [0.65, 0, 0.35, 1],
} as const;
export type EasingToken = keyof typeof EASING;

export const ELEVATION_TOKENS = ["elev-0", "elev-1", "elev-2", "elev-3"] as const;
export const STATE_TOKENS = ["state-hover", "state-pressed", "state-selected", "state-armed", "state-disabled"] as const;

/** Duração em segundos para `motion`; lê o CSS quando disponível, senão usa o espelho. */
export function durationSeconds(token: DurationToken): number {
  if (typeof document !== "undefined" && typeof getComputedStyle === "function") {
    const raw = getComputedStyle(document.documentElement).getPropertyValue(`--dur-${token}`).trim();
    const ms = raw.endsWith("ms") ? parseFloat(raw) : raw.endsWith("s") ? parseFloat(raw) * 1000 : NaN;
    if (Number.isFinite(ms) && ms > 0) return ms / 1000;
  }
  return DURATION_MS[token] / 1000;
}

export function easingCurve(token: EasingToken): readonly [number, number, number, number] {
  return EASING[token];
}
