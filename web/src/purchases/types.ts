export interface StoreProduct {
  productId: string;
  title: string;
  /** Formatted by the Store (Play ProductDetails) or by the backend for Stripe. */
  displayPrice: string;
  shardMilli?: string;
}
/**
 * `started`: the Store flow was launched; the outcome arrives asynchronously (subscribe).
 * `disabled`: server kill switch (SPEC-196) -> billing was never launched.
 */
export type PurchaseResult = {
  status: 'fulfilled' | 'pending' | 'redirected' | 'started' | 'cancelled' | 'disabled' | 'error';
  orderId?: string; productId?: string; shardMilli?: string; code?: string;
};

export interface PurchaseAdapter {
  readonly kind: 'stripe' | 'google_play';
  /** Stripe checkout UI is a web-only policy surface (SPEC-194 R8). */
  readonly supportsWebCheckout: boolean;
  listProducts(signal?: AbortSignal): Promise<StoreProduct[]>;
  purchase(productId: string, obfuscatedAccountId: string): Promise<PurchaseResult>;
  /** Re-send unconsumed/pending purchases (queryPurchasesAsync) after resume or process death. */
  restorePending(): Promise<PurchaseResult[]>;
}
