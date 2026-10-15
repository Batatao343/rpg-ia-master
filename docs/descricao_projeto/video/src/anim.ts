import {interpolate, Easing} from 'remotion';

export const ease = Easing.bezier(0.22, 1, 0.36, 1);

/** 0→1 a partir de `start`, em `dur` frames, com easing suave. */
export const appear = (frame: number, start: number, dur = 18) =>
  interpolate(frame, [start, start + dur], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: ease,
  });

/**
 * Distribui a revelação de `n` elementos ao longo da narração,
 * para que a tela acompanhe a fala em vez de despejar tudo de uma vez.
 */
export const schedule = (n: number, audioFrames: number, lead = 14) => {
  const span = Math.max(audioFrames * 0.72, n * 10);
  const step = Math.min(42, span / Math.max(n, 1));
  return (i: number) => Math.round(lead + i * step);
};

export const fadeUp = (p: number, dist = 24) => ({
  opacity: p,
  transform: `translateY(${(1 - p) * dist}px)`,
});
