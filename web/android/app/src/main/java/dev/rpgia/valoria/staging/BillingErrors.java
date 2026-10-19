package dev.rpgia.valoria.staging;

import java.util.regex.Pattern;

/**
 * SPEC-259 R1/R2: codigos de rejeicao do PlayBillingPlugin, um por etapa, e saneamento do
 * {@code BillingResult.getDebugMessage()} antes de ir para o JS/logcat (<= 120 chars, sem tokens).
 * Puro Java (sem Android) para ter teste de unidade local.
 */
final class BillingErrors {
    static final String TAG = "RPGBilling";
    static final String UNAVAILABLE = "billing_unavailable";
    static final String QUERY_FAILED = "billing_query_failed";
    static final String LAUNCH_FAILED = "billing_launch_failed";
    static final String BAD_JSON = "billing_bad_json";

    private static final int MAX_DEBUG = 120;
    // Tokens de compra/ids opacos: sequencias longas sem espaco viram [redacted].
    private static final Pattern OPAQUE = Pattern.compile("[A-Za-z0-9._~+/=:-]{24,}");
    private static final Pattern CONTROL = Pattern.compile("[\\p{Cntrl}]+");

    private BillingErrors() {}

    static String safeDebug(String raw) {
        if (raw == null) return "";
        String text = CONTROL.matcher(raw).replaceAll(" ");
        text = OPAQUE.matcher(text).replaceAll("[redacted]").trim();
        return text.length() > MAX_DEBUG ? text.substring(0, MAX_DEBUG) : text;
    }

    /** Linha do logcat: so o codigo e o responseCode (nunca token, produto ou debugMessage). */
    static String logLine(String code, int responseCode) {
        return code + " responseCode=" + responseCode;
    }
}
