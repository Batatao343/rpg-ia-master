import { isNativeApp } from './platform';

export interface NativeHandlers {
  onBack: () => 'ignore' | 'back' | 'minimize';
  onBackNavigate: () => void;
  onResume: () => void;
}

/** Registers Android back/resume hooks; no-op on the web. Returns a disposer. */
export async function installNativeLifecycle(h: NativeHandlers): Promise<() => void> {
  if (!isNativeApp()) return () => {};
  const { App } = await import('@capacitor/app');
  const back = await App.addListener('backButton', () => {
    const decision = h.onBack();
    if (decision === 'back') h.onBackNavigate();
    else if (decision === 'minimize') void App.minimizeApp();
  });
  const state = await App.addListener('appStateChange', ({ isActive }) => { if (isActive) h.onResume(); });
  return () => { void back.remove(); void state.remove(); };
}
