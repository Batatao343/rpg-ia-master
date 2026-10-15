import { clientPlatform } from '../native/platform';
import { AndroidPlayAdapter } from './androidPlay';
import { WebStripeAdapter } from './webStripe';
import type { PurchaseAdapter } from './types';

export type { PurchaseAdapter, StoreProduct, PurchaseResult } from './types';

export function selectPurchaseAdapter(platform: string,
  fetchSkus: ConstructorParameters<typeof WebStripeAdapter>[0]): PurchaseAdapter {
  return platform === 'android' ? new AndroidPlayAdapter() : new WebStripeAdapter(fetchSkus);
}

export const currentPurchaseAdapter = (fetchSkus: ConstructorParameters<typeof WebStripeAdapter>[0]) =>
  selectPurchaseAdapter(clientPlatform(), fetchSkus);
