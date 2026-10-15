import { clientPlatform } from '../native/platform';
import { AndroidPlayAdapter, nativePlayBilling, type GoogleBackend, type PlayBillingPlugin } from './androidPlay';
import { WebStripeAdapter } from './webStripe';
import type { PurchaseAdapter } from './types';

export type { PurchaseAdapter, StoreProduct, PurchaseResult } from './types';
export type { GoogleBackend } from './androidPlay';

let playSingleton: AndroidPlayAdapter | null = null;
/** One adapter per app run so resume recovery and AccountScreen share the dedupe state. */
export function playAdapter(backend: GoogleBackend): AndroidPlayAdapter {
  return playSingleton ||= new AndroidPlayAdapter(nativePlayBilling(), backend);
}

export function selectPurchaseAdapter(platform: string,
  fetchSkus: ConstructorParameters<typeof WebStripeAdapter>[0], backend?: GoogleBackend,
  plugin: PlayBillingPlugin | null = nativePlayBilling()): PurchaseAdapter {
  return platform === 'android'
    ? new AndroidPlayAdapter(plugin, backend as GoogleBackend)
    : new WebStripeAdapter(fetchSkus);
}

export const currentPurchaseAdapter = (fetchSkus: ConstructorParameters<typeof WebStripeAdapter>[0]) =>
  selectPurchaseAdapter(clientPlatform(), fetchSkus);
