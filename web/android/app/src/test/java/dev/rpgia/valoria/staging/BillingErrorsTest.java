package dev.rpgia.valoria.staging;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** SPEC-259 R1/R2: codigos distintos por etapa e debugMessage sem token, truncada. */
public class BillingErrorsTest {

    @Test
    public void distinctCodesPerStage() {
        assertEquals("billing_query_failed", BillingErrors.QUERY_FAILED);
        assertEquals("billing_launch_failed", BillingErrors.LAUNCH_FAILED);
        assertEquals("billing_bad_json", BillingErrors.BAD_JSON);
        assertEquals("billing_unavailable", BillingErrors.UNAVAILABLE);
    }

    @Test
    public void debugMessageIsTruncated() {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < 50; i++) b.append("erro ");
        String safe = BillingErrors.safeDebug(b.toString());
        assertTrue(safe.length() <= 120);
    }

    @Test
    public void tokensAreRedacted() {
        String token = "opaque-token-abcdefghijklmnopqrstuvwxyz.AO-J1Ox0123456789";
        String safe = BillingErrors.safeDebug("Purchase token " + token + " invalid");
        assertFalse(safe.contains("abcdefghijklmnopqrstuvwxyz"));
        assertTrue(safe.contains("[redacted]"));
    }

    @Test
    public void nullAndControlCharsAreSafe() {
        assertEquals("", BillingErrors.safeDebug(null));
        assertFalse(BillingErrors.safeDebug("linha1\nlinha2\tx").contains("\n"));
    }

    @Test
    public void logLineHasCodeAndResponseCodeOnly() {
        assertEquals("billing_launch_failed responseCode=6", BillingErrors.logLine(BillingErrors.LAUNCH_FAILED, 6));
    }
}
