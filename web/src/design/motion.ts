// SPEC-208 R3/R4/R10: ponte tokens -> motion + estado global de "efeitos habilitados".
import { useSyncExternalStore } from "react";
import { applyKillSwitch } from "./killswitch";
import { durationSeconds, easingCurve, type DurationToken, type EasingToken } from "./tokens";

export { durationSeconds, easingCurve };
export type { DurationToken, EasingToken };

/** Transição `motion` a partir dos tokens (nunca literais soltos nos componentes). */
export function transitionFor(duration: DurationToken, easing: EasingToken = "ease-out") {
  return { duration: durationSeconds(duration), ease: [...easingCurve(easing)] as [number, number, number, number] };
}

export function prefersReduced(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// SPEC-354 P1-1: UMA assinatura compartilhada no DOM. Com N componentes (um por entrada do Livro) cada um
// registrava os próprios listeners; um único `visibilitychange` enfileirava N re-renders no mesmo evento e, com
// mais de 50 entradas, o React acusava "Maximum update depth exceeded".
const listeners = new Set<() => void>();
let teardown: (() => void) | null = null;

function notifyAll() { listeners.forEach((fn) => fn()); }

function attachDom(): () => void {
  if (typeof window === "undefined") return () => {};
  const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  mq?.addEventListener?.("change", notifyAll);
  document.addEventListener("visibilitychange", notifyAll);
  // R10: desligar em outra aba (localStorage) vale aqui sem recarregar — reaplica a marca no <html>.
  const onStorage = (e: StorageEvent) => { if (e.key === null || e.key === "rpg.effects") applyKillSwitch(); notifyAll(); };
  window.addEventListener("storage", onStorage);
  return () => {
    mq?.removeEventListener?.("change", notifyAll);
    document.removeEventListener("visibilitychange", notifyAll);
    window.removeEventListener("storage", onStorage);
  };
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  if (listeners.size === 1) teardown = attachDom();
  return () => {
    listeners.delete(onChange);
    if (listeners.size === 0) { teardown?.(); teardown = null; }
  };
}

const getSnapshot = () => {
  const killed = document.documentElement.dataset.effects === "off";
  return !killed && !prefersReduced() && document.visibilityState !== "hidden";
};

/** reduced-motion + aba em background + kill switch (R10). Falso => tudo estático. */
export function useEffectsEnabled(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}

export function initEffects() {
  applyKillSwitch();
  // R10: rpg.effects mudado em outra aba vale nesta sem recarregar (mesmo sem nenhum primitivo montado).
  if (typeof window !== "undefined") {
    window.addEventListener("storage", (e) => { if (e.key === null || e.key === "rpg.effects") applyKillSwitch(); });
  }
}
