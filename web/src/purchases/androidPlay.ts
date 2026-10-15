import type { PurchaseAdapter, StoreProduct, PurchaseResult } from './types';

/**
 * SPEC-194 native Play Billing. Trust model: the plugin and its events are UNTRUSTED input; the
 * only thing that credits is the server's answer to POST /verify. The price shown is ONLY the
 * Store's formattedPrice. The app never consumes/acknowledges (the server does after fulfilment).
 */
export interface StoreProductDetails { productId: string; title: string; formattedPrice: string; priceAmountMicros?: number; currency?: string }
export interface PlayPurchaseEvent { purchaseToken: string; productId: string; orderId?: string; purchaseState: 'PURCHASED' | 'PENDING' }
export interface PlayBillingPlugin {
  getProducts(o: { productIds: string[] }): Promise<{ products: StoreProductDetails[] }>;
  purchase(o: { productId: string; obfuscatedAccountId: string }): Promise<{ started?: boolean; cancelled?: boolean; alreadyOwned?: boolean }>;
  queryPendingPurchases(): Promise<{ purchases: PlayPurchaseEvent[] }>;
  addListener(name: string, cb: (e: any) => void): Promise<unknown> | unknown;
}
export interface GoogleBackend {
  profile(): Promise<{ obfuscated_account_id?: string; purchases_disabled?: boolean }>;
  products(): Promise<{ items: { product_id: string; sku_id: string; shard_milli: string }[] }>;
  verify(b: { product_id: string; purchase_token: string; order_id?: string }):
    Promise<{ status: 'fulfilled' | 'pending'; shard_milli?: string; product_id?: string }>;
}

export const NOT_AVAILABLE = 'play_billing_plugin_unavailable';

export function nativePlayBilling(): PlayBillingPlugin | null {
  const cap = (globalThis as any).Capacitor;
  try { return cap?.registerPlugin ? cap.registerPlugin('PlayBilling') : null; } catch { return null; }
}

export class AndroidPlayAdapter implements PurchaseAdapter {
  readonly kind = 'google_play' as const;
  readonly supportsWebCheckout = false;
  private inflight = new Map<string, Promise<PurchaseResult>>();
  private fulfilled = new Set<string>();
  private subscribers = new Set<(r: PurchaseResult) => void>();
  private listening: Promise<void> | null = null;
  /** Last server kill-switch reading; the flag is re-read before EVERY launch. */
  disabled = false;

  constructor(private readonly plugin: PlayBillingPlugin | null, private readonly backend: GoogleBackend) {}

  private need(): PlayBillingPlugin {
    if (!this.plugin) throw new Error(NOT_AVAILABLE);
    return this.plugin;
  }

  subscribe(cb: (r: PurchaseResult) => void): () => void {
    this.subscribers.add(cb);
    void this.listen();
    return () => { this.subscribers.delete(cb); };
  }

  private listen(): Promise<void> {
    const plugin = this.plugin;
    if (!plugin) return Promise.resolve();
    return this.listening ||= (async () => {
      await plugin.addListener('purchaseUpdated', (e: PlayPurchaseEvent) => { void this.handle(e); });
      await plugin.addListener('purchaseCancelled', () => this.emit({ status: 'cancelled' }));
      await plugin.addListener('purchaseError', () => this.emit({ status: 'error', code: 'billing_error' }));
    })();
  }

  private emit(r: PurchaseResult) { for (const s of this.subscribers) s(r); }

  async listProducts(): Promise<StoreProduct[]> {
    const plugin = this.need();
    const profile = await this.backend.profile();
    this.disabled = profile.purchases_disabled === true;
    if (this.disabled) return [];
    const { items } = await this.backend.products();
    if (!items.length) return [];
    const { products } = await plugin.getProducts({ productIds: items.map(i => i.product_id) });
    const byId = new Map(products.map(p => [p.productId, p]));
    const out: StoreProduct[] = [];
    for (const i of items) {
      const p = byId.get(i.product_id);
      if (p && p.formattedPrice) out.push({ productId: i.product_id, title: p.title, displayPrice: p.formattedPrice, shardMilli: i.shard_milli });
    }
    return out;
  }

  async purchase(productId: string): Promise<PurchaseResult> {
    const plugin = this.need();
    const profile = await this.backend.profile();   // fresh: the kill switch must stop launchBillingFlow
    this.disabled = profile.purchases_disabled === true;
    if (this.disabled || !profile.obfuscated_account_id) return { status: 'disabled' };
    await this.listen();
    const res = await plugin.purchase({ productId, obfuscatedAccountId: profile.obfuscated_account_id });
    if (res.cancelled) { const r: PurchaseResult = { status: 'cancelled' }; this.emit(r); return r; }
    return { status: 'started', productId };
  }

  /** Resolves when every verify started so far has settled. */
  async idle(): Promise<void> { await Promise.allSettled([...this.inflight.values()]); }

  /** The outcome is decided ONLY by the server; event fields are forwarded as untrusted input. */
  handle(e: PlayPurchaseEvent): Promise<PurchaseResult> {
    if (!e || typeof e.purchaseToken !== 'string' || typeof e.productId !== 'string') return Promise.resolve({ status: 'error', code: 'bad_event' });
    if (e.purchaseState === 'PENDING') {
      const r: PurchaseResult = { status: 'pending', productId: e.productId };   // no verify, no credit
      this.emit(r);
      return Promise.resolve(r);
    }
    if (e.purchaseState !== 'PURCHASED') return Promise.resolve({ status: 'error', code: 'bad_state' });
    const t = e.purchaseToken;
    if (this.fulfilled.has(t)) return Promise.resolve({ status: 'fulfilled', productId: e.productId });
    const running = this.inflight.get(t);
    if (running) return running;
    const p = (async (): Promise<PurchaseResult> => {
      let r: PurchaseResult;
      try {
        const v = await this.backend.verify({ product_id: e.productId, purchase_token: t, ...(e.orderId ? { order_id: e.orderId } : {}) });
        if (v.status === 'fulfilled') { this.fulfilled.add(t); r = { status: 'fulfilled', productId: e.productId, shardMilli: v.shard_milli }; }
        else r = { status: 'pending', productId: e.productId };
      } catch (err) {
        r = { status: 'error', code: (err as { message?: string })?.message || 'verify_failed' };
      } finally { this.inflight.delete(t); }
      this.emit(r);
      return r;
    })();
    this.inflight.set(t, p);
    return p;
  }

  private restoring: Promise<PurchaseResult[]> | null = null;
  /** Single-flight: startup, resume and AccountScreen mount may all ask; one query runs at a time
   *  (and handle() already dedupes a token that is verifying or fulfilled). */
  restorePending(): Promise<PurchaseResult[]> {
    return this.restoring ||= (async () => {
      try {
        const { purchases } = await this.need().queryPendingPurchases();
        return await Promise.all((purchases || []).map(p => this.handle(p)));
      } finally { this.restoring = null; }
    })();
  }
}
