import type { PurchaseAdapter, StoreProduct, PurchaseResult } from './types';

/** Existing web flow: AccountScreen drives /account/checkout directly; this wraps its SKU list. */
export class WebStripeAdapter implements PurchaseAdapter {
  readonly kind = 'stripe' as const;
  readonly supportsWebCheckout = true;
  constructor(private readonly fetchSkus: (signal?: AbortSignal) =>
    Promise<{ items: { sku_id: string; gross_brl: string; shard_milli: string }[] }>) {}
  async listProducts(signal?: AbortSignal): Promise<StoreProduct[]> {
    const { items } = await this.fetchSkus(signal);
    return items.map(i => ({ productId: i.sku_id, title: i.sku_id, displayPrice: `R$ ${i.gross_brl}`, shardMilli: i.shard_milli }));
  }
  async purchase(): Promise<PurchaseResult> {
    // The redirect checkout stays in AccountScreen.beginCheckout (idempotent request id).
    throw new Error('use_account_checkout_flow');
  }
  async restorePending(): Promise<PurchaseResult[]> { return []; }
}
