// SPEC-193: one frontend for web and Android. The Capacitor WebView injects
// `window.Capacitor` before page scripts; no import so this stays dependency-free.
type CapacitorGlobal = { isNativePlatform?: () => boolean; getPlatform?: () => string };
const cap = (): CapacitorGlobal | undefined => (globalThis as { Capacitor?: CapacitorGlobal }).Capacitor;

export type ClientPlatform = 'web' | 'android' | 'ios';

export function clientPlatform(): ClientPlatform {
  try {
    const c = cap();
    if (c?.isNativePlatform?.()) return c.getPlatform?.() === 'ios' ? 'ios' : 'android';
  } catch { /* treat as web */ }
  return 'web';
}
export const isNativeApp = () => clientPlatform() !== 'web';
export const isAndroidClient = () => clientPlatform() === 'android';
