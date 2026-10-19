package dev.rpgia.valoria.staging;

import android.util.Log;
import com.android.billingclient.api.BillingClient;
import com.android.billingclient.api.BillingClientStateListener;
import com.android.billingclient.api.BillingFlowParams;
import com.android.billingclient.api.BillingResult;
import com.android.billingclient.api.PendingPurchasesParams;
import com.android.billingclient.api.ProductDetails;
import com.android.billingclient.api.Purchase;
import com.android.billingclient.api.QueryProductDetailsParams;
import com.android.billingclient.api.QueryPurchasesParams;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.json.JSONArray;
import org.json.JSONException;

/**
 * SPEC-194 Play Billing bridge. Everything emitted here is UNTRUSTED client data: the backend
 * verifies with the Play Developer API. This plugin NEVER consumes or acknowledges (the server
 * consumes after fulfilment) and never decides credit. Prices come only from ProductDetails.
 * Fake mode exists only in debug builds assembled with -PplayBillingFake=true.
 */
@CapacitorPlugin(name = "PlayBilling")
public class PlayBillingPlugin extends Plugin {
    private BillingClient client;
    private int fakeCounter = 0;

    private boolean fake() { return BuildConfig.DEBUG && BuildConfig.PLAY_BILLING_FAKE; }

    private interface Ready { void run(BillingClient c); }

    /** SPEC-259 R1/R2: codigo por etapa + responseCode; logcat de release so codigo+responseCode
     *  (debugMessage saneada so no build debug); a mensagem saneada segue no objeto para o JS. */
    private static void fail(PluginCall call, String code, BillingResult r, String stage) {
        int rc = r == null ? -1 : r.getResponseCode();
        String debug = r == null ? "" : BillingErrors.safeDebug(r.getDebugMessage());
        Log.w(BillingErrors.TAG, BillingErrors.logLine(code, rc)
                + (BuildConfig.DEBUG ? " debugMessage=" + debug : ""));
        JSObject data = new JSObject().put("responseCode", rc).put("stage", stage);
        if (r != null) data.put("debugMessage", debug);
        call.reject(code, code, data);
    }

    private synchronized void withClient(PluginCall call, Ready then) {
        if (client == null) {
            client = BillingClient.newBuilder(getContext())
                .setListener((result, purchases) -> onPurchasesUpdated(result, purchases))
                .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
                .enableAutoServiceReconnection()
                .build();
        }
        final BillingClient c = client;
        if (c.isReady()) { then.run(c); return; }
        c.startConnection(new BillingClientStateListener() {
            @Override public void onBillingSetupFinished(BillingResult r) {
                if (r.getResponseCode() == BillingClient.BillingResponseCode.OK) then.run(c);
                else fail(call, BillingErrors.UNAVAILABLE, r, "setup");
            }
            @Override public void onBillingServiceDisconnected() { /* auto reconnection enabled */ }
        });
    }

    private static List<String> ids(PluginCall call) throws JSONException {
        JSONArray a = call.getArray("productIds");
        List<String> out = new ArrayList<>();
        if (a == null) return out;
        for (int i = 0; i < a.length(); i++) out.add(a.getString(i));
        return out;
    }

    private static QueryProductDetailsParams query(List<String> ids) {
        List<QueryProductDetailsParams.Product> q = new ArrayList<>();
        for (String id : ids) q.add(QueryProductDetailsParams.Product.newBuilder()
            .setProductId(id).setProductType(BillingClient.ProductType.INAPP).build());
        return QueryProductDetailsParams.newBuilder().setProductList(q).build();
    }

    @PluginMethod
    public void getProducts(PluginCall call) {
        final List<String> ids;
        try { ids = ids(call); } catch (JSONException e) {
            Log.w(BillingErrors.TAG, BillingErrors.BAD_JSON);
            call.reject(BillingErrors.BAD_JSON, BillingErrors.BAD_JSON);
            return;
        }
        if (ids.isEmpty()) { call.resolve(new JSObject().put("products", new JSArray())); return; }
        if (fake()) {
            JSArray arr = new JSArray();
            for (String id : ids) {
                arr.put(new JSObject().put("productId", id).put("title", "Pacote " + id + " (fake)")
                    .put("formattedPrice", "R$ 9,99").put("priceAmountMicros", 9990000L).put("currency", "BRL"));
            }
            call.resolve(new JSObject().put("products", arr));
            return;
        }
        withClient(call, c -> c.queryProductDetailsAsync(query(ids), (result, details) -> {
            if (result.getResponseCode() != BillingClient.BillingResponseCode.OK) {
                fail(call, BillingErrors.QUERY_FAILED, result, "products");
                return;
            }
            JSArray arr = new JSArray();
            for (ProductDetails d : details.getProductDetailsList()) {
                ProductDetails.OneTimePurchaseOfferDetails o = d.getOneTimePurchaseOfferDetails();
                if (o == null) continue;
                arr.put(new JSObject().put("productId", d.getProductId()).put("title", d.getTitle())
                    .put("formattedPrice", o.getFormattedPrice())
                    .put("priceAmountMicros", o.getPriceAmountMicros())
                    .put("currency", o.getPriceCurrencyCode()));
            }
            call.resolve(new JSObject().put("products", arr));
        }));
    }

    @PluginMethod
    public void purchase(PluginCall call) {
        final String productId = call.getString("productId");
        final String account = call.getString("obfuscatedAccountId");
        if (productId == null || account == null || account.length() < 16) { call.reject("bad_arguments"); return; }
        if (fake()) {
            if (productId.contains("cancel")) { call.resolve(new JSObject().put("cancelled", true)); return; }
            String state = productId.contains("pending") ? "PENDING" : "PURCHASED";
            fakeCounter++;
            notifyListeners("purchaseUpdated", new JSObject().put("purchaseToken", "fake-" + account + "-" + fakeCounter)
                .put("productId", productId).put("orderId", "GPA.FAKE" + fakeCounter).put("purchaseState", state));
            call.resolve(new JSObject().put("started", true));
            return;
        }
        withClient(call, c -> c.queryProductDetailsAsync(query(Collections.singletonList(productId)), (result, details) -> {
            if (details == null || details.getProductDetailsList().isEmpty()) { call.reject("product_unavailable"); return; }
            BillingFlowParams.ProductDetailsParams pd = BillingFlowParams.ProductDetailsParams.newBuilder()
                .setProductDetails(details.getProductDetailsList().get(0)).build();
            BillingFlowParams flow = BillingFlowParams.newBuilder()
                .setProductDetailsParamsList(Collections.singletonList(pd))
                .setObfuscatedAccountId(account).build();
            getActivity().runOnUiThread(() -> {
                BillingResult r = c.launchBillingFlow(getActivity(), flow);
                int code = r.getResponseCode();
                if (code == BillingClient.BillingResponseCode.OK) call.resolve(new JSObject().put("started", true));
                else if (code == BillingClient.BillingResponseCode.USER_CANCELED) call.resolve(new JSObject().put("cancelled", true));
                else if (code == BillingClient.BillingResponseCode.ITEM_ALREADY_OWNED) {
                    emitOwned(c);
                    call.resolve(new JSObject().put("alreadyOwned", true));
                } else fail(call, BillingErrors.LAUNCH_FAILED, r, "launch");
            });
        }));
    }

    @PluginMethod
    public void queryPendingPurchases(PluginCall call) {
        if (fake()) { call.resolve(new JSObject().put("purchases", new JSArray())); return; }
        withClient(call, c -> c.queryPurchasesAsync(
            QueryPurchasesParams.newBuilder().setProductType(BillingClient.ProductType.INAPP).build(),
            (result, purchases) -> {
                if (result.getResponseCode() != BillingClient.BillingResponseCode.OK) {
                    fail(call, BillingErrors.QUERY_FAILED, result, "pending");
                    return;
                }
                JSArray arr = new JSArray();
                for (Purchase p : purchases) for (String pid : p.getProducts()) arr.put(toJs(p, pid));
                call.resolve(new JSObject().put("purchases", arr));
            }));
    }

    private void emitOwned(BillingClient c) {
        c.queryPurchasesAsync(QueryPurchasesParams.newBuilder().setProductType(BillingClient.ProductType.INAPP).build(),
            (result, purchases) -> {
                if (result.getResponseCode() != BillingClient.BillingResponseCode.OK) return;
                for (Purchase p : purchases) for (String pid : p.getProducts())
                    notifyListeners("purchaseUpdated", toJs(p, pid));
            });
    }

    private void onPurchasesUpdated(BillingResult result, List<Purchase> purchases) {
        int code = result.getResponseCode();
        if (code == BillingClient.BillingResponseCode.USER_CANCELED) {
            notifyListeners("purchaseCancelled", new JSObject());
        } else if (code == BillingClient.BillingResponseCode.ITEM_ALREADY_OWNED && client != null) {
            emitOwned(client);
        } else if (code != BillingClient.BillingResponseCode.OK || purchases == null) {
            Log.w(BillingErrors.TAG, BillingErrors.logLine("billing_purchase_update_failed", code));
            notifyListeners("purchaseError", new JSObject().put("code", code)
                .put("debugMessage", BillingErrors.safeDebug(result.getDebugMessage())));
        } else {
            for (Purchase p : purchases) for (String pid : p.getProducts()) notifyListeners("purchaseUpdated", toJs(p, pid));
        }
    }

    private static JSObject toJs(Purchase p, String productId) {
        return new JSObject().put("purchaseToken", p.getPurchaseToken()).put("productId", productId)
            .put("orderId", p.getOrderId())
            .put("purchaseState", p.getPurchaseState() == Purchase.PurchaseState.PURCHASED ? "PURCHASED" : "PENDING");
    }
}
