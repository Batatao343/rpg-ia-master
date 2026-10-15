import type { PurchaseAdapter, StoreProduct, PurchaseResult } from './types';

export const NOT_AVAILABLE = 'not_available_until_spec_194_native';

/**
 * Seam only. The native Play Billing plugin arrives with SPEC-194/198; the backend contract
 * is GET /account/purchases/google/profile + POST /account/purchases/google/verify.
 */
export class AndroidPlayAdapter implements PurchaseAdapter {
  readonly kind = 'google_play' as const;
  readonly supportsWebCheckout = false;
  async listProducts(): Promise<StoreProduct[]> { throw new Error(NOT_AVAILABLE); }
  async purchase(_productId: string, _obfuscatedAccountId: string): Promise<PurchaseResult> { throw new Error(NOT_AVAILABLE); }
  async restorePending(): Promise<PurchaseResult[]> { throw new Error(NOT_AVAILABLE); }
}
